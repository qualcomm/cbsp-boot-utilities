# SPDX-License-Identifier: BSD-3-Clause-Clear

"""bin-to-hex output, as read back by patch-capsule-cert (@list:)."""

import struct

import pytest

from qcom_capsule_tool.BinToHex import bin_to_hex
from qcom_capsule_tool.patch_capsule_cert import _encode_dtb_value


@pytest.mark.parametrize("size", [928, 929, 930, 931])
def test_round_trip_keeps_every_byte(tmp_path, size):
    data = bytes((i * 7 + 3) % 256 for i in range(size))
    src = tmp_path / "cert.cer"
    inc = tmp_path / "cert.inc"
    src.write_bytes(data)

    bin_to_hex(str(src), str(inc))
    value = _encode_dtb_value(f"@list:{inc}")

    (length,) = struct.unpack(">I", value[:4])
    assert length == size
    assert value[4 : 4 + length] == data
    assert len(value) % 4 == 0
