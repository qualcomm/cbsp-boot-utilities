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
"""

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


def pattern(n, mult, add):
    return bytes(((i * mult + add) & 0xFF) for i in range(n))


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


def test_ffs_size_limit():
    with pytest.raises(ValueError, match="16 MiB"):
        fv_builder.build_raw_ffs(
            "11111111-2222-3333-4455-66778899aabb", b"\0" * 0x1000000
        )
