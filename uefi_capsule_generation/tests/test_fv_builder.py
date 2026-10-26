# --------------------------------------------------------------------
# Copyright (c) 2026 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

"""Golden-file tests proving fv_builder matches the edk2 BaseTools output.

The fixtures in tests/fixtures/ were generated once with the real GenFfs
and GenFv binaries (edk2 commit b03a21a63e3bd001f52c527e5a57feddb53a690b)
using the same deterministic payloads and the FVMain.inf template that
FVCreation.py historically produced. fv_builder must reproduce them
byte for byte.

The 16 MiB boundary cases (last FFS2 size, first two FFS3 large-file
sizes, and volumes built from them) are too big to commit, so only the
SHA-256 of the GenFfs/GenFv output is recorded for those.
"""

import hashlib
import os

import pytest

from qcom_capsule_tool import fv_builder

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

# (name, guid, size, mult, add) -- must stay in sync with the fixtures
FFS_CASES = [
    ("tiny", "11111111-2222-3333-4455-66778899aabb", 1, 7, 3),
    ("odd", "deadbeef-dead-beef-dead-beefdeadbeef", 37, 13, 1),
    ("aligned", "01234567-89ab-cdef-0123-456789abcdef", 96, 3, 5),
    ("page", "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0000", 4096, 11, 9),
    ("large", "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0", 4101, 5, 7),
]

FV_CASES = {
    "single": ["odd"],
    # ends exactly on a block boundary: no tail fill
    "exact_block": ["aligned"],
    # exercises inter-file 8-byte alignment padding and tail fill
    "multi": ["tiny", "odd", "large"],
    "all": ["tiny", "odd", "aligned", "page", "large"],
}

# (name, guid, size, mult, add, large, sha256 of the GenFfs output)
BIG_FFS_CASES = [
    # largest payload that still fits the 24-bit FFS2 size field
    (
        "boundary",
        "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
        0xFFFFE7,
        3,
        1,
        False,
        "341be58660273983780776242890a7151f2ca7d543dff56fe2f805121d3208cc",
    ),
    # one byte more: GenFfs switches to EFI_FFS_FILE_HEADER2
    (
        "huge",
        "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
        0xFFFFE8,
        5,
        7,
        True,
        "471a434a4ca57e8559b12ec573857812476b4257d67b8dace627c7a1cad3fb7b",
    ),
    (
        "huge_odd",
        "deadbeef-dead-beef-dead-beefdeadbeef",
        0x1000000 + 37,
        13,
        1,
        True,
        "f8f07feb064173dca7bac83cfb078b7c6fd15d1b812960adeecbad7b76acbe25",
    ),
]

# name -> (members, FFS3 volume expected, sha256 of the GenFv output);
# members are looked up in BIG_FFS_CASES first, then the fixtures.
BIG_FV_CASES = {
    "ffs2_boundary": (
        ["boundary"],
        False,
        "67c8293f9d52650df9a2e334897a5e92c29541a16a4c8d2740fc1cf5ee4f5eab",
    ),
    "ffs3_single": (
        ["huge_odd"],
        True,
        "4d61752c522f76b16757d4cc83d2abf6a4216c5e89c9803a253e8059eedbf7eb",
    ),
    # one large file promotes the whole volume to FFS3
    "ffs3_multi": (
        ["tiny", "huge", "odd"],
        True,
        "a198ed18e737050dbfed41c1327aeea7ff1d4f75300dba7778c10278fed83a84",
    ),
}


def pattern(n, mult, add):
    # (i * mult + add) & 0xFF repeats every 256 bytes.
    period = bytes(((i * mult + add) & 0xFF) for i in range(256))
    return (period * (n // 256 + 1))[:n]


def fixture(name):
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


@pytest.mark.parametrize("name,guid,size,mult,add", FFS_CASES)
def test_build_raw_ffs_matches_genffs(name, guid, size, mult, add):
    assert fv_builder.build_raw_ffs(guid, pattern(size, mult, add)) == fixture(
        name + ".ffs"
    )


@pytest.mark.parametrize("fv_name", sorted(FV_CASES))
def test_build_fv_matches_genfv(fv_name):
    ffs_images = [fixture(m + ".ffs") for m in FV_CASES[fv_name]]
    assert fv_builder.build_fv(ffs_images) == fixture(fv_name + ".fv")


def big_ffs(name):
    for case_name, guid, size, mult, add, _, _ in BIG_FFS_CASES:
        if case_name == name:
            return fv_builder.build_raw_ffs(guid, pattern(size, mult, add))
    return fixture(name + ".ffs")


@pytest.mark.parametrize("name,guid,size,mult,add,large,digest", BIG_FFS_CASES)
def test_build_raw_ffs_at_ffs2_limit(name, guid, size, mult, add, large, digest):
    ffs = fv_builder.build_raw_ffs(guid, pattern(size, mult, add))
    header_size = fv_builder.FFS_HEADER2_SIZE if large else fv_builder.FFS_HEADER_SIZE
    assert fv_builder.is_large_ffs(ffs) is large
    assert len(ffs) == header_size + size
    if large:
        assert ffs[20:23] == b"\0\0\0"
        assert int.from_bytes(ffs[24:32], "little") == len(ffs)
    else:
        assert int.from_bytes(ffs[20:23], "little") == len(ffs)
    assert hashlib.sha256(ffs).hexdigest() == digest


@pytest.mark.parametrize("fv_name", sorted(BIG_FV_CASES))
def test_build_fv_with_large_files(fv_name):
    members, ffs3, digest = BIG_FV_CASES[fv_name]
    fv = fv_builder.build_fv([big_ffs(m) for m in members])
    expected_guid = (
        fv_builder.EFI_FIRMWARE_FILE_SYSTEM3_GUID
        if ffs3
        else fv_builder.EFI_FIRMWARE_FILE_SYSTEM2_GUID
    )
    assert fv[16:32] == expected_guid.bytes_le
    assert hashlib.sha256(fv).hexdigest() == digest
