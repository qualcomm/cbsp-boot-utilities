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
EFI_FIRMWARE_FILE_SYSTEM2_GUID (3.2.2.1) and EFI_FFS_FILE_HEADER
(3.2.3.1).

Output is byte-identical to the edk2 tools for this subset; the golden
fixtures in tests/ were generated with the real GenFfs/GenFv binaries.
"""

import struct
import uuid
from typing import Iterable, List

EFI_FV_FILETYPE_RAW = 0x01
FFS_ATTRIB_CHECKSUM = 0x40
FFS_HEADER_SIZE = 24
# EFI_FILE_HEADER_CONSTRUCTION | EFI_FILE_HEADER_VALID | EFI_FILE_DATA_VALID
FFS_FILE_STATE = 0x07
# The FFS2 file size field is 24 bits wide and includes the header.
FFS_MAX_SIZE = 0xFFFFFF

EFI_FIRMWARE_FILE_SYSTEM2_GUID = uuid.UUID("8c8ce578-8a3d-4f1c-9935-896185c32dd3")
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


def build_raw_ffs(file_guid: str, payload: bytes) -> bytes:
    """Wrap payload in an EFI_FV_FILETYPE_RAW FFS2 file with data checksum."""
    total_size = FFS_HEADER_SIZE + len(payload)
    if total_size > FFS_MAX_SIZE:
        raise ValueError(
            f"payload of {len(payload)} bytes exceeds the 16 MiB FFS2 file limit"
        )

    header = bytearray(FFS_HEADER_SIZE)
    header[0:16] = uuid.UUID(file_guid).bytes_le
    header[18] = EFI_FV_FILETYPE_RAW
    header[19] = FFS_ATTRIB_CHECKSUM
    header[20:23] = total_size.to_bytes(3, "little")
    # Both IntegrityCheck bytes and State must be zero while the header
    # checksum is computed; State is excluded from it permanently.
    header[16] = _checksum8(header)
    header[17] = _checksum8(payload)
    header[23] = FFS_FILE_STATE
    return bytes(header) + payload


def build_fv(ffs_images: List[bytes]) -> bytes:
    """Assemble FFS files into a firmware volume (FFS2, 0x40-byte blocks)."""
    body = bytearray()
    for ffs in ffs_images:
        pad = -(FV_HEADER_SIZE + len(body)) % FFS_ALIGNMENT
        body += bytes([FV_ERASED_BYTE]) * pad
        # Erase polarity 1 stores the FFS state bits inverted.
        body += ffs[:23] + bytes([ffs[23] ^ 0xFF]) + ffs[24:]

    fv_length = FV_HEADER_SIZE + len(body)
    fv_length += -fv_length % FV_BLOCK_SIZE

    header = bytearray(
        struct.pack(
            "<16s16sQ4sIHHHBBIIII",
            b"",
            EFI_FIRMWARE_FILE_SYSTEM2_GUID.bytes_le,
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
