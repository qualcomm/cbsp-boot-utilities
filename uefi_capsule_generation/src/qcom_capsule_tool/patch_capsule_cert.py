#!/usr/bin/env python3
# Copyright (c) Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""
patch-capsule-cert: Patch QcCapsuleRootCert in a uefi_dtbs or xbl_config ELF.

Auto-detects the ELF type by scanning program-header payloads:
  - uefi_dtbs  : one or more ELF segments contain raw DTBs (FDT magic 0xd00dfeed).
                 The certificate is stored as a DTB property and is replaced in
                 every DTB that carries it.
  - xbl_config : PH#1 contains a valid XBLConfig metadata blob (4-byte ASCII
                 type tag + version + entry count).  The certificate is stored
                 as a DTB property inside one of the named DTB payload segments.

Both paths accept a plain DER (.cer) certificate file.

A `.xz`-suffixed input or output path is transparently decompressed/
recompressed (pure-Python `lzma`) around the patch step.

Usage:
    qcom-capsule-tool patch-capsule-cert <input.elf> <cert.cer> <output.elf> \\
        [--prop-name QcCapsuleRootCert]
"""

import argparse
import hashlib
import io
import lzma
import os
import re
import struct
import sys
import tempfile
from dataclasses import dataclass
from io import BytesIO
from typing import List, Optional, Tuple

import libfdt
from elftools.elf.elffile import ELFFile

from qcom_capsule_tool.BinToHex import bin_to_hex

# ============================================================
# ELF header read/write helpers  (was elf_utils.py)
# ============================================================

# ELF32 Phdr: type(4) offset(4) vaddr(4) paddr(4) filesz(4) memsz(4) flags(4) align(4)
# ELF64 Phdr: type(4) flags(4) offset(8) vaddr(8) paddr(8) filesz(8) memsz(8) align(8)
# ELF32 Shdr: name(4) type(4) flags(4) addr(4) offset(4) ...
# ELF64 Shdr: name(4) type(4) flags(8) addr(8) offset(8) ...


def _ph_file_offset_field(is_64: bool) -> Tuple[int, int]:
    return (8, 8) if is_64 else (4, 4)


def _ph_filesz_field(is_64: bool) -> Tuple[int, int]:
    return (0x20, 8) if is_64 else (0x10, 4)


def _ph_memsz_field(is_64: bool) -> Tuple[int, int]:
    return (0x28, 8) if is_64 else (0x14, 4)


def _sh_offset_field(is_64: bool) -> Tuple[int, int]:
    return (24, 8) if is_64 else (16, 4)


def _pack(endian: str, size: int, value: int) -> bytes:
    return struct.pack(endian + {4: "I", 8: "Q"}[size], value)


def _write_ph_field(
    data: bytearray,
    elf: ELFFile,
    seg_idx: int,
    field_off: int,
    field_size: int,
    value: int,
) -> None:
    endian = "<" if elf.little_endian else ">"
    pos = elf.header["e_phoff"] + seg_idx * elf.header["e_phentsize"] + field_off
    data[pos : pos + field_size] = _pack(endian, field_size, value)


def _write_sh_field(
    data: bytearray,
    elf: ELFFile,
    sec_idx: int,
    field_off: int,
    field_size: int,
    value: int,
) -> None:
    endian = "<" if elf.little_endian else ">"
    pos = elf.header["e_shoff"] + sec_idx * elf.header["e_shentsize"] + field_off
    data[pos : pos + field_size] = _pack(endian, field_size, value)


def _update_elf_headers_for_growth(
    data: bytearray, elf: ELFFile, seg_file_offset: int, grow: int
) -> None:
    """
    After splicing *grow* bytes at *seg_file_offset*, fix all ELF offsets that
    point past the splice point (p_offset, sh_offset, e_shoff).
    *elf* must be bound to the pre-splice bytes so header field positions are valid.
    """
    is_64 = elf.elfclass == 64
    endian = "<" if elf.little_endian else ">"

    off_field, off_sz = _ph_file_offset_field(is_64)
    for i, seg in enumerate(elf.iter_segments()):
        if seg["p_offset"] > seg_file_offset:
            _write_ph_field(data, elf, i, off_field, off_sz, seg["p_offset"] + grow)

    sh_off_field, sh_off_sz = _sh_offset_field(is_64)
    for i, sec in enumerate(elf.iter_sections()):
        if sec["sh_offset"] > seg_file_offset:
            _write_sh_field(
                data, elf, i, sh_off_field, sh_off_sz, sec["sh_offset"] + grow
            )

    e_shoff = elf.header["e_shoff"]
    if e_shoff > seg_file_offset:
        e_shoff_pos = 0x28 if is_64 else 0x20
        e_shoff_sz = 8 if is_64 else 4
        data[e_shoff_pos : e_shoff_pos + e_shoff_sz] = _pack(
            endian, e_shoff_sz, e_shoff + grow
        )


# ============================================================
# DTB property setter  (was set_dtb_property.py)
# ============================================================


def _encode_dtb_value(value: str) -> bytes:
    """
    Encode a value string for FDT:
      @file:<path>  -> binary split into 32-bit big-endian words
      @list:<path>  -> text file with hex/decimal ints, each -> 32-bit word
      single int    -> 4-byte big-endian
      int list      -> array of 4-byte big-endian words
      otherwise     -> UTF-8 string
    """
    value = value.strip()

    if value.startswith("@file:"):
        data = open(value[6:], "rb").read()
        if len(data) % 4 != 0:
            data += b"\x00" * (4 - (len(data) % 4))
        return b"".join(
            struct.pack(">I", struct.unpack(">I", data[i : i + 4])[0])
            for i in range(0, len(data), 4)
        )

    if value.startswith("@list:"):
        text = open(value[6:]).read()
        parts = re.split(r"[\s,]+", text.strip())
        return b"".join(struct.pack(">I", int(p, 16)) for p in parts if p)

    int_pattern = re.compile(r"^-?(0x[0-9a-fA-F]+|\d+)$")
    int_list_pattern = re.compile(
        r"^(-?(0x[0-9a-fA-F]+|\d+)[ ,]+)+(-?(0x[0-9a-fA-F]+|\d+))$"
    )
    if int_pattern.match(value):
        return struct.pack(">I", int(value, 0))
    if int_list_pattern.match(value + " "):
        parts = re.split(r"[ ,]+", value.strip())
        return b"".join(struct.pack(">I", int(p, 0)) for p in parts if p)

    return value.encode("utf-8")


def _set_dtb_property(
    dtb_path: str,
    node_path: str,
    prop_name: str,
    value: str,
    out_path: str,
    extra_space: int = 1024,
) -> None:
    """Set or add a property in a DTB, automatically resizing if needed."""
    with open(dtb_path, "rb") as f:
        dtb_data = f.read()

    fdt_obj = libfdt.Fdt(dtb_data)

    try:
        node_off = fdt_obj.path_offset(node_path)
    except libfdt.FdtException:
        raise ValueError(f"Node path '{node_path}' not found in DTB")

    value_bytes = _encode_dtb_value(value)

    try:
        fdt_obj.setprop(node_off, prop_name, value_bytes)
    except libfdt.FdtException as e:
        if hasattr(e, "err") and e.err == -libfdt.FDT_ERR_NOSPACE:
            fdt_obj.resize(
                len(fdt_obj.as_bytearray()) + max(len(value_bytes), extra_space)
            )
            fdt_obj.setprop(node_off, prop_name, value_bytes)
        else:
            raise

    with open(out_path, "wb") as f:
        f.write(fdt_obj.as_bytearray())


# ============================================================
# DTB scanner, cert-node walker, single-DTB patcher  (was dtb_utils.py)
# ============================================================

DTB_MAGIC = 0xD00DFEED
_DEFAULT_PROP_NAME = "QcCapsuleRootCert"


def _scan_dtbs(data: bytes) -> List[Tuple[int, int]]:
    """Return (offset, totalsize) for every DTB found in *data*."""
    results: List[Tuple[int, int]] = []
    i = 0
    while i <= len(data) - 8:
        if struct.unpack(">I", data[i : i + 4])[0] == DTB_MAGIC:
            size = struct.unpack(">I", data[i + 4 : i + 8])[0]
            if size >= 8 and i + size <= len(data):
                results.append((i, size))
                i = (i + size + 3) & ~3
                continue
        i += 4
    return results


def _fdt_first_subnode(fdt: libfdt.Fdt, node_off: int) -> int:
    try:
        return fdt.first_subnode(node_off)
    except libfdt.FdtException:
        return -1


def _fdt_next_subnode(fdt: libfdt.Fdt, node_off: int) -> int:
    try:
        return fdt.next_subnode(node_off)
    except libfdt.FdtException:
        return -1


def _find_cert_node(
    dtb_bytes: bytes, prop_name: str = _DEFAULT_PROP_NAME
) -> Optional[str]:
    """
    Walk *dtb_bytes* and return the first node path that owns *prop_name*.
    Handles both regular DTBs (/sw/uefi/uefiplat) and overlay DTBs
    (/fragment@N/__overlay__/.../uefiplat) without dtc dependency.
    """
    try:
        fdt = libfdt.Fdt(dtb_bytes)
    except Exception:
        return None

    def _walk(node_off: int, path: str) -> Optional[str]:
        try:
            fdt.getprop(node_off, prop_name)
            return path
        except libfdt.FdtException:
            pass
        child = _fdt_first_subnode(fdt, node_off)
        while child >= 0:
            try:
                name = fdt.get_name(child)
            except Exception:
                child = _fdt_next_subnode(fdt, child)
                continue
            child_path = path + name if path == "/" else f"{path}/{name}"
            result = _walk(child, child_path)
            if result is not None:
                return result
            child = _fdt_next_subnode(fdt, child)
        return None

    try:
        root = fdt.path_offset("/")
        return _walk(root, "/")
    except Exception:
        return None


def _patch_dtb(
    dtb_bytes: bytes,
    node_path: str,
    cert_inc_path: str,
    prop_name: str = _DEFAULT_PROP_NAME,
) -> bytes:
    """Patch *prop_name* in a single DTB and return the patched bytes."""
    tmp_in = tmp_out = ""
    try:
        tmp_in_fd, tmp_in = tempfile.mkstemp(suffix=".dtb")
        os.close(tmp_in_fd)
        with open(tmp_in, "wb") as f:
            f.write(dtb_bytes)
        tmp_out_fd, tmp_out = tempfile.mkstemp(suffix=".dtb")
        os.close(tmp_out_fd)
        os.unlink(tmp_out)
        _set_dtb_property(
            tmp_in, node_path, prop_name, f"@list:{cert_inc_path}", tmp_out
        )
        with open(tmp_out, "rb") as f:
            return f.read()
    finally:
        for p in (tmp_in, tmp_out):
            try:
                os.unlink(p)
            except OSError:
                pass


# ============================================================
# XBLConfig metadata parser + replace_ph  (was xblconfig_parser.py)
# ============================================================

# Metadata v2 layout (PH blob):
#   Header (12 bytes): xcfg_type[4] major[1] minor[1] entries[2-LE] meta_size[4-LE]
#   Item (repeated):   attributes[4] offset_from_meta_start[4] item_size[4]
#                      chipinfo[8] platforminfo[8] config_name_len[4]
#                      config_name[config_name_len]  PAD-to-8


@dataclass
class _MetaHeader:
    xcfg_type: str
    major: int
    minor: int
    entries: int
    meta_size: int


@dataclass
class _MetaItemV2:
    attributes: int
    offset_from_meta_start: int
    item_size: int
    chipinfo: int
    platforminfo: int
    config_name_len: int
    config_name: str
    start_off: int
    end_off: int


def _align_up(x: int, a: int) -> int:
    r = x % a
    return x if r == 0 else x + (a - r)


def _parse_meta_header(blob: bytes, off: int = 0) -> Tuple[_MetaHeader, int]:
    if off + 12 > len(blob):
        raise ValueError("Metadata header truncated")
    xcfg_type = blob[off : off + 4].decode("ascii", errors="replace")
    major = blob[off + 4]
    minor = blob[off + 5]
    entries = int.from_bytes(blob[off + 6 : off + 8], "little")
    meta_size = int.from_bytes(blob[off + 8 : off + 12], "little")
    return _MetaHeader(xcfg_type, major, minor, entries, meta_size), off + 12


def _parse_meta_items_v2(
    blob: bytes, off: int, count: int
) -> Tuple[List[_MetaItemV2], int]:
    items: List[_MetaItemV2] = []
    cur = off
    for idx in range(count):
        item_start = cur
        if cur + 32 > len(blob):
            raise ValueError(f"Metadata v2 item {idx} truncated")
        attributes = int.from_bytes(blob[cur + 0 : cur + 4], "little")
        ofs_from_meta_start = int.from_bytes(blob[cur + 4 : cur + 8], "little")
        item_size = int.from_bytes(blob[cur + 8 : cur + 12], "little")
        chipinfo = int.from_bytes(blob[cur + 12 : cur + 20], "little")
        platforminfo = int.from_bytes(blob[cur + 20 : cur + 28], "little")
        name_len = int.from_bytes(blob[cur + 28 : cur + 32], "little")
        cur += 32
        if cur + name_len > len(blob):
            raise ValueError(f"Metadata v2 item {idx} name truncated")
        config_name = blob[cur : cur + name_len].decode("utf-8", errors="replace")
        cur += name_len
        padded_len = _align_up(cur - item_start, 8)
        cur = item_start + padded_len
        items.append(
            _MetaItemV2(
                attributes=attributes,
                offset_from_meta_start=ofs_from_meta_start,
                item_size=item_size,
                chipinfo=chipinfo,
                platforminfo=platforminfo,
                config_name_len=name_len,
                config_name=config_name,
                start_off=item_start,
                end_off=cur,
            )
        )
    return items, cur


def _load_elf(elf_path: str) -> Tuple[bytearray, ELFFile, List]:
    with open(elf_path, "rb") as f:
        file_bytes = f.read()
    data = bytearray(file_bytes)
    elf = ELFFile(io.BytesIO(file_bytes))
    return data, elf, list(elf.iter_segments())


def _parse_metadata_from_ph(
    elf: ELFFile, meta_ph_index: int
) -> Tuple[_MetaHeader, List[_MetaItemV2], bytes, int]:
    """Return (header, items, meta_blob, meta_file_offset)."""
    segments = list(elf.iter_segments())
    if not segments or meta_ph_index >= len(segments):
        raise IndexError(f"Program header #{meta_ph_index} not found")
    meta_seg = segments[meta_ph_index]
    meta_blob = meta_seg.data()
    ph = elf._get_segment_header(meta_ph_index)
    meta_file_off = ph["p_offset"]
    hdr, off = _parse_meta_header(meta_blob, 0)
    items, _ = _parse_meta_items_v2(meta_blob, off, hdr.entries)
    return hdr, items, meta_blob, meta_file_off


def _replace_ph(
    elf_path: str,
    target_ph_index: int,
    new_file: str,
    output_file: str,
    meta_ph_index: int,
) -> None:
    """
    Replace the payload in *target_ph_index* with the contents of *new_file*,
    then update p_filesz/p_memsz, metadata item_size, and SHA-384 hash.
    """
    data, elf, segments = _load_elf(elf_path)

    if target_ph_index >= len(segments):
        raise IndexError(f"Target program header #{target_ph_index} not found")

    old_seg = segments[target_ph_index]
    old_data = old_seg.data()
    old_size = old_seg["p_filesz"]
    seg_offset = old_seg["p_offset"]

    with open(new_file, "rb") as f:
        new_data = f.read()
    new_size = len(new_data)

    old_hash = hashlib.sha384(old_data[:old_size]).digest()
    new_hash = hashlib.sha384(new_data).digest()

    print(
        f"[i] Replacing PH#{target_ph_index}: old size={old_size}, new size={new_size}"
    )
    print(f"[i] Old SHA-384: {old_hash.hex()}")
    print(f"[i] New SHA-384: {new_hash.hex()}")

    is_64 = elf.elfclass == 64
    grow_size = new_size - old_size

    # Save hashes of segments whose content will be modified by side effects:
    # - PH#0 (ELF/program header segment): _write_ph_field and
    #   _update_elf_headers_for_growth both write into the program header table,
    #   which lives inside PH#0's file region.
    # - PH#meta_ph_index (XBLConfig metadata segment): metadata item_size is
    #   patched directly inside this segment's payload.
    # These must be captured before any writes so the old hashes can be located
    # and replaced in the hash table after all modifications are done.
    side_effect_phs: List[Tuple[int, bytes]] = []
    for ph_i in set([0, meta_ph_index]):
        if ph_i == target_ph_index or ph_i >= len(segments):
            continue
        seg_i = segments[ph_i]
        d = seg_i.data()
        if d:
            side_effect_phs.append((ph_i, hashlib.sha384(d).digest()))

    if grow_size <= 0:
        data[seg_offset : seg_offset + new_size] = new_data
        if grow_size < 0:
            data[seg_offset + new_size : seg_offset + old_size] = b"\x00" * (-grow_size)
    else:
        tail = bytes(data[seg_offset + old_size :])
        data[seg_offset : seg_offset + new_size] = new_data
        new_tail_start = seg_offset + new_size
        data[new_tail_start : new_tail_start + len(tail)] = tail
        data.extend(b"\x00" * grow_size)
        _update_elf_headers_for_growth(data, elf, seg_offset, grow_size)

    filesz_field, filesz_field_sz = _ph_filesz_field(is_64)
    memsz_field, memsz_field_sz = _ph_memsz_field(is_64)
    _write_ph_field(data, elf, target_ph_index, filesz_field, filesz_field_sz, new_size)
    _write_ph_field(data, elf, target_ph_index, memsz_field, memsz_field_sz, new_size)

    meta_item_index = target_ph_index - (meta_ph_index + 1)
    if meta_item_index >= 0:
        try:
            _, items, _, meta_file_off = _parse_metadata_from_ph(elf, meta_ph_index)
            if meta_item_index < len(items):
                it = items[meta_item_index]
                abs_field_off = meta_file_off + it.start_off + 8
                data[abs_field_off : abs_field_off + 4] = struct.pack("<I", new_size)
                print(
                    f"[i] Updated metadata item[{meta_item_index}] ('{it.config_name}') "
                    f"item_size: {it.item_size} -> {new_size}"
                )
            else:
                print(
                    f"[!] meta_item_index={meta_item_index} out of range; item_size not updated"
                )
        except Exception as exc:
            print(f"[!] Could not update metadata item_size: {exc}")

    pos = bytes(data).find(old_hash)
    if pos != -1:
        print(f"[i] Found old SHA-384 at file offset 0x{pos:x}; replacing")
        data[pos : pos + len(new_hash)] = new_hash
    else:
        print("[!] Old SHA-384 hash not found in ELF binary; hash table not updated")

    # Update hashes for side-effect segments (PH#0 and metadata PH).
    data_bytes = bytes(data)
    for ph_i, old_h in side_effect_phs:
        seg_i = segments[ph_i]
        new_h = hashlib.sha384(
            data_bytes[seg_i["p_offset"] : seg_i["p_offset"] + seg_i["p_filesz"]]
        ).digest()
        if old_h == new_h:
            continue
        pos = data_bytes.find(old_h)
        if pos != -1:
            data[pos : pos + 48] = new_h
            print(f"[i] PH#{ph_i} SHA-384 updated at file offset 0x{pos:x}")
        else:
            print(
                f"[!] PH#{ph_i} SHA-384 not found in ELF binary; hash table not updated"
            )

    with open(output_file, "wb") as out:
        out.write(data)
    print(f"[+] Written patched ELF to '{output_file}'")


# ============================================================
# uefi_dtbs patch logic  (was patch_uefi_dtbs.py)
# ============================================================


def _get_dtb_model(dtb_bytes: bytes) -> str:
    try:
        fdt = libfdt.Fdt(dtb_bytes)
        root = fdt.path_offset("/")
        prop = fdt.getprop(root, "model")
        return bytes(prop).rstrip(b"\x00").decode("utf-8", errors="replace")
    except Exception:
        return "unknown"


def _patch_uefi_dtbs(
    elf_path: str,
    cert_inc_path: str,
    output_path: str,
    prop_name: str = _DEFAULT_PROP_NAME,
) -> List[dict]:
    """
    Patch *prop_name* in every DTB embedded in a uefi_dtbs ELF.

    Returns a list of result dicts (one per DTB found) with keys:
    segment, dtb_index, offset, model, node_path, status.
    """
    with open(elf_path, "rb") as f:
        raw = bytearray(f.read())

    elf0 = ELFFile(BytesIO(bytes(raw)))
    seg_indices_with_dtbs = [
        i for i, seg in enumerate(elf0.iter_segments()) if _scan_dtbs(seg.data())
    ]

    results: List[dict] = []

    for seg_idx in seg_indices_with_dtbs:
        elf = ELFFile(BytesIO(bytes(raw)))
        is_64 = elf.elfclass == 64

        seg = list(elf.iter_segments())[seg_idx]
        seg_data = bytearray(seg.data())
        seg_file_offset = seg["p_offset"]
        orig_seg_size = len(seg_data)

        dtbs = _scan_dtbs(bytes(seg_data))
        old_seg_hash = hashlib.sha384(bytes(seg_data)).digest()

        delta = 0
        seg_modified = False
        per_dtb_hash_pairs: List[Tuple[bytes, bytes]] = []

        for dtb_idx, (dtb_off_orig, dtb_sz) in enumerate(dtbs):
            dtb_off = dtb_off_orig + delta
            dtb_bytes = bytes(seg_data[dtb_off : dtb_off + dtb_sz])

            model = _get_dtb_model(dtb_bytes)
            node_path = _find_cert_node(dtb_bytes, prop_name)

            if node_path is None:
                results.append(
                    dict(
                        segment=seg_idx,
                        dtb_index=dtb_idx,
                        offset=dtb_off,
                        model=model,
                        node_path=None,
                        status=f"skip (no {prop_name})",
                    )
                )
                continue

            try:
                old_dtb_hash = hashlib.sha384(dtb_bytes).digest()
                patched = _patch_dtb(dtb_bytes, node_path, cert_inc_path, prop_name)
                new_dtb_hash = hashlib.sha384(patched).digest()
            except Exception as exc:
                results.append(
                    dict(
                        segment=seg_idx,
                        dtb_index=dtb_idx,
                        offset=dtb_off,
                        model=model,
                        node_path=node_path,
                        status=f"error: {exc}",
                    )
                )
                continue

            per_dtb_hash_pairs.append((old_dtb_hash, new_dtb_hash))
            seg_data = (
                seg_data[:dtb_off] + bytearray(patched) + seg_data[dtb_off + dtb_sz :]
            )
            delta += len(patched) - dtb_sz
            seg_modified = True

            results.append(
                dict(
                    segment=seg_idx,
                    dtb_index=dtb_idx,
                    offset=dtb_off,
                    model=model,
                    node_path=node_path,
                    status="patched",
                )
            )

        if not seg_modified:
            continue

        new_seg_hash = hashlib.sha384(bytes(seg_data)).digest()
        grow = len(seg_data) - orig_seg_size

        # Save PH#0 hash before ELF headers are modified by growth fixup.
        # _update_elf_headers_for_growth() rewrites p_offset fields inside
        # PH#0's payload, so its SHA-384 changes and must be updated too.
        ph0_seg = list(elf.iter_segments())[0]
        ph0_off = ph0_seg["p_offset"]
        ph0_filesz = ph0_seg["p_filesz"]
        old_ph0_hash = (
            hashlib.sha384(bytes(raw[ph0_off : ph0_off + ph0_filesz])).digest()
            if grow != 0 and ph0_filesz > 0
            else None
        )

        raw[seg_file_offset : seg_file_offset + orig_seg_size] = seg_data

        if grow != 0:
            _update_elf_headers_for_growth(raw, elf, seg_file_offset, grow)

        filesz_f, filesz_sz = _ph_filesz_field(is_64)
        memsz_f, memsz_sz = _ph_memsz_field(is_64)
        _write_ph_field(raw, elf, seg_idx, filesz_f, filesz_sz, len(seg_data))
        _write_ph_field(raw, elf, seg_idx, memsz_f, memsz_sz, len(seg_data))

        raw_bytes = bytes(raw)
        segs_now = list(ELFFile(BytesIO(raw_bytes)).iter_segments())
        hash_seg = next(
            (s for s in segs_now[seg_idx + 1 :] if s["p_type"] == "PT_NULL"),
            None,
        )
        if hash_seg is not None:
            h_start = hash_seg["p_offset"]
            h_end = h_start + hash_seg["p_filesz"]
        else:
            h_start, h_end = 0, len(raw_bytes)

        for old_h, new_h in per_dtb_hash_pairs:
            pos = raw_bytes.find(old_h, h_start, h_end)
            if pos != -1:
                raw[pos : pos + 48] = new_h
                print(f"[i] Per-DTB SHA-384 updated at file 0x{pos:x}")
            else:
                print("[!] Per-DTB SHA-384 not found in hash segment (non-fatal)")

        pos = raw_bytes.find(old_seg_hash, h_start, h_end)
        if pos != -1:
            raw[pos : pos + 48] = new_seg_hash
            print(f"[i] Segment SHA-384 updated at file 0x{pos:x}")
        else:
            print("[!] Segment SHA-384 not found in hash segment (non-fatal)")

        if old_ph0_hash is not None:
            new_ph0_hash = hashlib.sha384(
                raw_bytes[ph0_off : ph0_off + ph0_filesz]
            ).digest()
            pos = raw_bytes.find(old_ph0_hash, h_start, h_end)
            if pos != -1:
                raw[pos : pos + 48] = new_ph0_hash
                print(
                    f"[i] ELF-header segment (PH#0) SHA-384 updated at file 0x{pos:x}"
                )
            else:
                print(
                    "[!] ELF-header segment (PH#0) SHA-384 not found in hash segment (non-fatal)"
                )

    with open(output_path, "wb") as f:
        f.write(raw)

    return results


# ============================================================
# ELF-type detection
# ============================================================

ELF_TYPE_UEFI_DTBS = "uefi_dtbs"
ELF_TYPE_XBL_CONFIG = "xbl_config"


def _has_dtb_segment(elf: ELFFile) -> bool:
    for seg in elf.iter_segments():
        data = seg.data()
        for i in range(0, len(data) - 3, 4):
            if struct.unpack(">I", data[i : i + 4])[0] == DTB_MAGIC:
                return True
    return False


def _has_xblconfig_metadata(elf: ELFFile, meta_ph_index: int = 1) -> bool:
    segs = list(elf.iter_segments())
    if meta_ph_index >= len(segs):
        return False
    data = segs[meta_ph_index].data()
    if len(data) < 12:
        return False
    if not all(0x20 <= b < 0x7F for b in data[:4]):
        return False
    try:
        _parse_meta_header(data, 0)
        return True
    except Exception:
        return False


def detect_elf_type(elf_path: str, meta_ph_index: int = 1) -> str:
    with open(elf_path, "rb") as f:
        elf = ELFFile(f)
        if _has_xblconfig_metadata(elf, meta_ph_index):
            return ELF_TYPE_XBL_CONFIG
        if _has_dtb_segment(elf):
            return ELF_TYPE_UEFI_DTBS
    raise ValueError(
        f"Cannot determine ELF type for '{elf_path}': "
        "no XBLConfig metadata header and no DTB segments found."
    )


# ============================================================
# xbl_config cert-patch path
# ============================================================


def _patch_xbl_config(
    elf_path: str,
    cert_cer_path: str,
    output_path: str,
    prop_name: str,
    meta_ph_index: int,
) -> None:
    """
    Patch *prop_name* in xbl_config ELFs:
      1. Find which named segment contains a DTB with *prop_name*.
      2. Patch the DTB property with the new certificate.
      3. Call _replace_ph() to write back and update p_filesz/p_memsz,
         xblconfig item_size, and SHA-384.
    """
    inc_fd, inc_path = tempfile.mkstemp(suffix=".inc")
    os.close(inc_fd)
    try:
        bin_to_hex(cert_cer_path, inc_path)

        with open(elf_path, "rb") as f:
            raw = f.read()
        elf = ELFFile(io.BytesIO(raw))
        segs = list(elf.iter_segments())
        _, items, _, _ = _parse_metadata_from_ph(elf, meta_ph_index)

        patched = skipped = errors = 0
        for idx, item in enumerate(list(items)):
            ph_index = idx + meta_ph_index + 1
            if ph_index >= len(segs):
                continue

            seg_data = segs[ph_index].data()
            dtbs = _scan_dtbs(seg_data)
            if not dtbs:
                continue

            for dtb_off, dtb_sz in dtbs:
                dtb_bytes = seg_data[dtb_off : dtb_off + dtb_sz]
                node_path = _find_cert_node(dtb_bytes, prop_name)
                if node_path is None:
                    skipped += 1
                    continue

                print(
                    f"[+] xbl_config: found '{prop_name}' in "
                    f"'{item.config_name}' (PH#{ph_index}) at {node_path}"
                )

                try:
                    patched_dtb = _patch_dtb(dtb_bytes, node_path, inc_path, prop_name)
                except Exception as exc:
                    print(f"[!] xbl_config: error patching '{item.config_name}': {exc}")
                    errors += 1
                    continue

                # Always splice patched_dtb back into a copy of seg_data so
                # any tail-padding bytes beyond the DTB totalsize are preserved.
                new_seg = bytearray(seg_data)
                new_seg[dtb_off : dtb_off + dtb_sz] = patched_dtb
                new_seg_bytes = bytes(new_seg)

                tmp_fd, tmp_seg_path = tempfile.mkstemp(suffix=".dtb")
                os.close(tmp_fd)
                try:
                    with open(tmp_seg_path, "wb") as f:
                        f.write(new_seg_bytes)
                    _replace_ph(
                        elf_path=elf_path,
                        target_ph_index=ph_index,
                        new_file=tmp_seg_path,
                        output_file=output_path,
                        meta_ph_index=meta_ph_index,
                    )
                    elf_path = output_path
                    with open(elf_path, "rb") as f:
                        raw = f.read()
                    elf = ELFFile(io.BytesIO(raw))
                    segs = list(elf.iter_segments())
                    patched += 1
                finally:
                    try:
                        os.unlink(tmp_seg_path)
                    except OSError:
                        pass

        print(f"[+] xbl_config: patched={patched}  skipped={skipped}  errors={errors}")
        if errors:
            sys.exit(1)
        if patched == 0:
            raise ValueError(
                f"No DTB segment in '{elf_path}' contains property '{prop_name}'"
            )
    finally:
        try:
            os.unlink(inc_path)
        except OSError:
            pass


# ============================================================
# Top-level API
# ============================================================


def _patch_capsule_cert_elf(
    elf_path: str,
    cert_cer_path: str,
    output_path: str,
    prop_name: str,
    meta_ph_index: int,
) -> str:
    """Patch a plain (non-xz) ELF. See patch_capsule_cert() for the public API."""
    elf_type = detect_elf_type(elf_path, meta_ph_index)
    print(f"[+] Detected ELF type : {elf_type}")

    if elf_type == ELF_TYPE_UEFI_DTBS:
        inc_fd, inc_path = tempfile.mkstemp(suffix=".inc")
        os.close(inc_fd)
        try:
            bin_to_hex(cert_cer_path, inc_path)
            results = _patch_uefi_dtbs(elf_path, inc_path, output_path, prop_name)
        finally:
            try:
                os.unlink(inc_path)
            except OSError:
                pass

        patched = sum(1 for r in results if "patched" in r["status"])
        skipped = sum(1 for r in results if "skip" in r["status"])
        errors = sum(1 for r in results if "error" in r["status"])
        print(f"[+] uefi_dtbs: patched={patched}  skipped={skipped}  errors={errors}")
        if errors:
            sys.exit(1)

    else:
        _patch_xbl_config(
            elf_path=elf_path,
            cert_cer_path=cert_cer_path,
            output_path=output_path,
            prop_name=prop_name,
            meta_ph_index=meta_ph_index,
        )

    return elf_type


def patch_capsule_cert(
    elf_path: str,
    cert_cer_path: str,
    output_path: str,
    prop_name: str = _DEFAULT_PROP_NAME,
    meta_ph_index: int = 1,
) -> str:
    """
    Patch the capsule root certificate in *elf_path* and write to *output_path*.

    If *elf_path* ends in ``.xz``, it is transparently decompressed to a
    temporary ELF before patching. If *output_path* ends in ``.xz``, the
    patched ELF is recompressed before being written out. Either, both, or
    neither may be ``.xz`` -- e.g. patching an xz input into a plain ELF
    output, or vice versa, both work.

    Args:
        elf_path:       Input ELF (uefi_dtbs or xbl_config), optionally `.xz`.
        cert_cer_path:  DER certificate file (.cer).
        output_path:    Path for the patched output ELF, optionally `.xz`.
        prop_name:      DTB property name to patch (default: QcCapsuleRootCert).
        meta_ph_index:  PH index of the XBLConfig metadata blob (default: 1).

    Returns:
        Detected ELF type string ("uefi_dtbs" or "xbl_config").
    """
    input_is_xz = elf_path.endswith(".xz")
    output_is_xz = output_path.endswith(".xz")

    if not input_is_xz and not output_is_xz:
        return _patch_capsule_cert_elf(
            elf_path, cert_cer_path, output_path, prop_name, meta_ph_index
        )

    decompressed_fd, decompressed_path = tempfile.mkstemp(suffix=".elf")
    os.close(decompressed_fd)
    patched_fd, patched_path = tempfile.mkstemp(suffix=".elf")
    os.close(patched_fd)
    try:
        if input_is_xz:
            with lzma.open(elf_path, "rb") as src, open(decompressed_path, "wb") as dst:
                dst.write(src.read())
            source_elf = decompressed_path
        else:
            source_elf = elf_path

        elf_type = _patch_capsule_cert_elf(
            source_elf, cert_cer_path, patched_path, prop_name, meta_ph_index
        )

        if output_is_xz:
            with open(patched_path, "rb") as src, lzma.open(output_path, "wb") as dst:
                dst.write(src.read())
        else:
            os.replace(patched_path, output_path)
    finally:
        for tmp in (decompressed_path, patched_path):
            try:
                os.unlink(tmp)
            except OSError:
                pass

    return elf_type


# ============================================================
# CLI
# ============================================================


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="qcom-capsule-tool patch-capsule-cert",
        description=(
            "Patch QcCapsuleRootCert in a uefi_dtbs or xbl_config ELF. "
            "The ELF type is detected automatically."
        ),
    )
    ap.add_argument("elf_file", help="Input ELF file (uefi_dtbs or xbl_config)")
    ap.add_argument("cert_cer", help="DER certificate file (.cer)")
    ap.add_argument("output_elf", help="Output patched ELF file")
    ap.add_argument(
        "--prop-name",
        default=_DEFAULT_PROP_NAME,
        help="DTB property name to patch (default: %(default)s)",
    )
    ap.add_argument(
        "--meta-ph",
        type=int,
        default=1,
        help="XBLConfig metadata program-header index (default: %(default)s)",
    )
    args = ap.parse_args()

    print(f"[+] Input ELF  : {args.elf_file}")
    print(f"[+] Cert (.cer): {args.cert_cer}")
    print(f"[+] Output ELF : {args.output_elf}")

    patch_capsule_cert(
        elf_path=args.elf_file,
        cert_cer_path=args.cert_cer,
        output_path=args.output_elf,
        prop_name=args.prop_name,
        meta_ph_index=args.meta_ph,
    )

    print(f"[+] Done. Output written to: {args.output_elf}")


if __name__ == "__main__":
    main()
