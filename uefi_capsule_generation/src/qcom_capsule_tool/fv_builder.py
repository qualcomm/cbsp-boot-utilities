# --------------------------------------------------------------------
# Copyright (c) 2026 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

"""Pure-Python replacement for the edk2 BaseTools GenFfs/GenFv binaries.

Implements exactly the subset FVCreation.py used to invoke:

    GenFfs -t EFI_FV_FILETYPE_RAW -g <guid> -s -i <binary>
    GenFv  -i FVMain.inf     (fixed [options]/[attributes] template)

The emitted structures are defined in the UEFI Platform Initialization
(PI) Specification, Volume 3: Shared Architectural Elements
(https://uefi.org/specs/PI/1.8/): EFI_FIRMWARE_VOLUME_HEADER (3.2.1.1),
EFI_FIRMWARE_FILE_SYSTEM2_GUID (3.2.2.1), EFI_FIRMWARE_FILE_SYSTEM3_GUID
(3.2.2.2) and EFI_FFS_FILE_HEADER / EFI_FFS_FILE_HEADER2 (3.2.3.1).

Like GenFfs, a payload that does not fit the 24-bit FFS2 size field is
wrapped in the FFS3 large-file header (FFS_ATTRIB_LARGE_FILE plus a
64-bit ExtendedSize), and like GenFv a volume holding such a file is
labelled with the FFS3 file system GUID.

Output is byte-identical to the edk2 tools for this subset; the golden
fixtures in tests/ were generated with the real GenFfs/GenFv binaries.
"""

import struct
import uuid
from typing import Iterable, List

EFI_FV_FILETYPE_RAW = 0x01
FFS_ATTRIB_LARGE_FILE = 0x01
FFS_ATTRIB_CHECKSUM = 0x40
FFS_HEADER_SIZE = 24
# EFI_FFS_FILE_HEADER2: the FFS2 header followed by a UINT64 ExtendedSize.
FFS_HEADER2_SIZE = 32
# EFI_FILE_HEADER_CONSTRUCTION | EFI_FILE_HEADER_VALID | EFI_FILE_DATA_VALID
FFS_FILE_STATE = 0x07
FFS_STATE_OFFSET = 23
# The FFS2 file size field is 24 bits wide and includes the header;
# anything larger needs the FFS3 large-file header.
FFS_MAX_SIZE = 0xFFFFFF

EFI_FIRMWARE_FILE_SYSTEM2_GUID = uuid.UUID("8c8ce578-8a3d-4f1c-9935-896185c32dd3")
EFI_FIRMWARE_FILE_SYSTEM3_GUID = uuid.UUID("5473c07a-3dcb-4dca-bd6f-1e9689e7349a")
FV_SIGNATURE = b"_FVH"
FV_HEADER_REVISION = 2
FV_BLOCK_SIZE = 0x40
# 0x38 bytes of fixed fields plus two block-map entries (one + terminator).
FV_HEADER_SIZE = 0x48
# The EFI_FVB2 attribute set from the FVMain.inf template FVCreation has
# always generated: all read/write/lock capability and status bits,
# STICKY_WRITE, MEMORY_MAPPED, ERASE_POLARITY=1 and ALIGNMENT_8.
FV_ATTRIBUTES = 0x0003FEFF
# Erase polarity 1: free space reads back as 0xFF and FFS state bits
# are stored inverted.
FV_ERASED_BYTE = 0xFF
FFS_ALIGNMENT = 8


def _checksum8(data: Iterable[int]) -> int:
    """Return the value that makes the 8-bit sum of data zero."""
    return (0x100 - sum(data)) & 0xFF


def is_large_ffs(ffs: bytes) -> bool:
    """True if the FFS image carries the FFS3 large-file header."""
    return bool(ffs[19] & FFS_ATTRIB_LARGE_FILE)


def build_raw_ffs(file_guid: str, payload: bytes) -> bytes:
    """Wrap payload in an EFI_FV_FILETYPE_RAW FFS file with data checksum.

    Payloads that fit the 24-bit FFS2 size field get the plain
    EFI_FFS_FILE_HEADER; larger ones get EFI_FFS_FILE_HEADER2 with
    FFS_ATTRIB_LARGE_FILE set and the size in ExtendedSize, exactly as
    GenFfs does.
    """
    if FFS_HEADER_SIZE + len(payload) > FFS_MAX_SIZE:
        header = bytearray(FFS_HEADER2_SIZE)
        attributes = FFS_ATTRIB_CHECKSUM | FFS_ATTRIB_LARGE_FILE
        total_size = FFS_HEADER2_SIZE + len(payload)
        # Size stays zero; ExtendedSize carries the real value.
        header[24:32] = struct.pack("<Q", total_size)
    else:
        header = bytearray(FFS_HEADER_SIZE)
        attributes = FFS_ATTRIB_CHECKSUM
        total_size = FFS_HEADER_SIZE + len(payload)
        header[20:23] = total_size.to_bytes(3, "little")

    header[0:16] = uuid.UUID(file_guid).bytes_le
    header[18] = EFI_FV_FILETYPE_RAW
    header[19] = attributes
    # Both IntegrityCheck bytes and State must be zero while the header
    # checksum is computed; State is excluded from it permanently.
    header[16] = _checksum8(header)
    header[17] = _checksum8(payload)
    header[FFS_STATE_OFFSET] = FFS_FILE_STATE
    return bytes(header) + payload


def build_fv(ffs_images: List[bytes]) -> bytes:
    """Assemble FFS files into a firmware volume (0x40-byte blocks).

    The volume is labelled FFS2 unless any file uses the FFS3 large-file
    header, in which case it is labelled FFS3 -- the same promotion GenFv
    performs. Nothing else in the layout differs.
    """
    body = bytearray()
    for ffs in ffs_images:
        pad = -(FV_HEADER_SIZE + len(body)) % FFS_ALIGNMENT
        body += bytes([FV_ERASED_BYTE]) * pad
        # Erase polarity 1 stores the FFS state bits inverted.
        body += (
            ffs[:FFS_STATE_OFFSET]
            + bytes([ffs[FFS_STATE_OFFSET] ^ 0xFF])
            + ffs[FFS_STATE_OFFSET + 1 :]
        )

    fv_length = FV_HEADER_SIZE + len(body)
    fv_length += -fv_length % FV_BLOCK_SIZE

    if any(is_large_ffs(ffs) for ffs in ffs_images):
        file_system_guid = EFI_FIRMWARE_FILE_SYSTEM3_GUID
    else:
        file_system_guid = EFI_FIRMWARE_FILE_SYSTEM2_GUID

    header = bytearray(
        struct.pack(
            "<16s16sQ4sIHHHBBIIII",
            b"",
            file_system_guid.bytes_le,
            fv_length,
            FV_SIGNATURE,
            FV_ATTRIBUTES,
            FV_HEADER_SIZE,
            0,  # Checksum, filled in below
            0,  # ExtHeaderOffset
            0,  # Reserved
            FV_HEADER_REVISION,
            fv_length // FV_BLOCK_SIZE,
            FV_BLOCK_SIZE,
            0,  # block map terminator
            0,
        )
    )
    checksum = (0x10000 - sum(struct.unpack("<36H", header))) & 0xFFFF
    header[0x32:0x34] = struct.pack("<H", checksum)

    image = header + body
    image += bytes([FV_ERASED_BYTE]) * (fv_length - len(image))
    return bytes(image)


def write_raw_ffs(output_path: str, file_guid: str, input_path: str) -> None:
    """Create an FFS file from a raw input binary (GenFfs replacement)."""
    with open(input_path, "rb") as f:
        payload = f.read()
    with open(output_path, "wb") as f:
        f.write(build_raw_ffs(file_guid, payload))


def write_fv(output_path: str, ffs_paths: List[str]) -> None:
    """Create a firmware volume from FFS files (GenFv replacement)."""
    ffs_images = []
    for path in ffs_paths:
        with open(path, "rb") as f:
            ffs_images.append(f.read())
    with open(output_path, "wb") as f:
        f.write(build_fv(ffs_images))
