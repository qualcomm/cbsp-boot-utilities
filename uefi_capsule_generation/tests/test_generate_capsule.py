# --------------------------------------------------------------------
# Copyright (c) 2026 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

"""Tests for generate_capsule against edk2 GenerateCapsule.py output.

fixtures/unsigned.cap was generated with the real GenerateCapsule.py
(same edk2 commit as the GenFfs/GenFv fixtures) from the deterministic
payload below; an unsigned capsule contains no timestamp so the match
is exact. The signed path is covered by a live openssl round trip.
"""

import shutil
import struct
import subprocess
import uuid

import pytest

from qcom_capsule_tool import generate_capsule

GUID = "6F25BFD2-A165-468B-980F-AC51A0A45C52"
PAYLOAD = bytes((i * 11 + 2) % 256 for i in range(3000))


def make_config(payload_file, **extra):
    config = {
        "Guid": GUID,
        "FwVersion": "0x00000102",
        "LowestSupportedVersion": "0x0",
        "MonotonicCount": "0x2",
        "HardwareInstance": "0x0",
        "UpdateImageIndex": "0x1",
        "Payload": str(payload_file),
    }
    config.update(extra)
    return config


def test_unsigned_matches_generatecapsule(tmp_path, capsys):
    payload_file = tmp_path / "firmware.fv"
    payload_file.write_bytes(PAYLOAD)
    descriptor = generate_capsule.PayloadDescriptor(make_config(payload_file))
    capsule = generate_capsule.encode_capsule(
        [descriptor], [], ["PersistAcrossReset"], 0, verbose=False
    )
    with open(f"{__file__.rsplit('/', 1)[0]}/fixtures/unsigned.cap", "rb") as f:
        assert capsule == f.read()


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not available")
def test_signed_capsule_signature_verifies(tmp_path):
    payload_file = tmp_path / "firmware.fv"
    payload_file.write_bytes(PAYLOAD)
    key, cert, signer = tmp_path / "key.pem", tmp_path / "cert.pem", tmp_path / "s.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "3",
            "-nodes",
            "-subj",
            "/CN=CapsuleTest",
        ],
        check=True,
        capture_output=True,
    )
    signer.write_bytes(key.read_bytes() + cert.read_bytes())

    descriptor = generate_capsule.PayloadDescriptor(
        make_config(
            payload_file,
            OpenSslSignerPrivateCertFile=str(signer),
            OpenSslOtherPublicCertFile=str(cert),
            OpenSslTrustedPublicCertFile=str(cert),
        )
    )
    capsule = generate_capsule.encode_capsule(
        [descriptor], [], ["PersistAcrossReset"], 0, verbose=False
    )

    # outer header, FMP header, one item offset, image header, auth header
    image_header_offset = 32 + 8 + 8
    auth_offset = image_header_offset + 48
    (capsule_support,) = struct.unpack("<Q", capsule[auth_offset - 8 : auth_offset])
    assert capsule_support == generate_capsule.CAPSULE_SUPPORT_AUTHENTICATION
    (dw_length,) = struct.unpack("<I", capsule[auth_offset + 8 : auth_offset + 12])
    sig_start = auth_offset + 32
    sig_end = auth_offset + 8 + dw_length

    content = tmp_path / "content.bin"
    content.write_bytes(capsule[sig_end:] + struct.pack("<Q", 2))
    p7 = tmp_path / "sig.p7"
    p7.write_bytes(capsule[sig_start:sig_end])
    subprocess.run(
        [
            "openssl",
            "smime",
            "-verify",
            "-inform",
            "DER",
            "-in",
            str(p7),
            "-content",
            str(content),
            "-CAfile",
            str(cert),
            "-out",
            "/dev/null",
        ],
        check=True,
        capture_output=True,
    )

    # image type GUID lands in the image header
    assert (
        capsule[image_header_offset + 4 : image_header_offset + 20]
        == uuid.UUID(GUID).bytes_le
    )


def test_partial_openssl_fields_rejected(tmp_path):
    payload_file = tmp_path / "p.bin"
    payload_file.write_bytes(b"x")
    with pytest.raises(ValueError, match="must all be set"):
        generate_capsule.PayloadDescriptor(
            make_config(payload_file, OpenSslSignerPrivateCertFile="only-one.pem")
        )
