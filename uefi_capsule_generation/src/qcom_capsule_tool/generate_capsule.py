# --------------------------------------------------------------------
# Copyright (c) 2026 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

"""Build signed UEFI FMP capsules from a JSON payload descriptor.

A capsule nests the following structures:

    EFI_CAPSULE_HEADER
      EFI_FIRMWARE_MANAGEMENT_CAPSULE_HEADER + ItemOffsetList
        EFI_FIRMWARE_MANAGEMENT_CAPSULE_IMAGE_HEADER (v3, per payload)
          EFI_FIRMWARE_IMAGE_AUTHENTICATION (PKCS7 via openssl smime)
            FMP_PAYLOAD_HEADER ('MSS1')
              payload

All of these structures except FMP_PAYLOAD_HEADER are defined in the
UEFI Specification 2.10 (https://uefi.org/specs/UEFI/2.10/):
EFI_CAPSULE_HEADER in 8.5.3 (UpdateCapsule), the FMP capsule and image
headers in 23.3 (Delivering Capsules Containing Updates), and
EFI_FIRMWARE_IMAGE_AUTHENTICATION in 23.1. FMP_PAYLOAD_HEADER ('MSS1')
is the payload versioning convention consumed by the Qualcomm FMP
driver (see FMP_PAYLOAD_HEADER_SIGNATURE in FVCreation.py).

The command line and the JSON descriptor schema are compatible with
the encode and --dump-info modes of edk2 BaseTools GenerateCapsule.py,
so this subcommand is a drop-in replacement for it; the implementation
is independent and only the interface is shared. signtool signing and
capsule dependency expressions are not supported. The capsule bytes
produced are identical to what shipped devices already receive.
"""

import argparse
import json
import os
import struct
import subprocess
import sys
import uuid
from typing import List, Optional

EFI_FIRMWARE_MANAGEMENT_CAPSULE_ID_GUID = uuid.UUID(
    "6dcbd5ed-e82d-4c44-bda1-7194199ad92a"
)
EFI_CERT_TYPE_PKCS7_GUID = uuid.UUID("4aafd29d-68df-49ee-8aa9-347d375665a7")

# Historical capsules for these targets declare a 32-byte outer header:
# the 28-byte EFI_CAPSULE_HEADER followed by 4 reserved bytes. Parsers
# locate the payload through the HeaderSize field, and 32 is what
# shipped device firmware has always been given, so keep it.
CAPSULE_HEADER_SIZE = 32
CAPSULE_FLAGS = {
    "PersistAcrossReset": 0x00010000,
    "PopulateSystemTable": 0x00020000,
    "InitiateReset": 0x00040000,
}

FMP_CAPSULE_HEADER_VERSION = 1
FMP_CAPSULE_HEADER_SIZE = 8
FMP_IMAGE_HEADER_VERSION = 3
FMP_IMAGE_HEADER_SIZE = 48
CAPSULE_SUPPORT_AUTHENTICATION = 0x0000000000000001

# dwLength counts the WIN_CERTIFICATE fields plus the CertType GUID
# and the certificate data, but not the leading monotonic count.
WIN_CERT_PREFIX_LEN = 24
WIN_CERT_REVISION = 0x0200
WIN_CERT_TYPE_EFI_GUID = 0x0EF1
AUTH_HEADER_SIZE = 8 + WIN_CERT_PREFIX_LEN

FMP_PAYLOAD_SIGNATURE = b"MSS1"
FMP_PAYLOAD_HEADER_SIZE = 16

DEFAULT_HASH_ALGORITHM = "sha256"


class PayloadDescriptor:
    """One entry of the JSON "Payloads" list, with defaults applied."""

    def __init__(self, config: dict):
        def to_int(field: str, default: Optional[int] = None) -> int:
            if field not in config:
                if default is None:
                    raise ValueError(f"missing required JSON field {field}")
                return default
            value = config[field]
            return int(value, 0) if isinstance(value, str) else int(value)

        def to_path(field: str) -> Optional[str]:
            value = os.path.expandvars(str(config.get(field, ""))).strip()
            return value or None

        if "Payload" not in config:
            raise ValueError("missing required JSON field Payload")
        self.payload_file: str = os.path.expandvars(config["Payload"])
        self.guid = uuid.UUID(config["Guid"])
        self.fw_version = to_int("FwVersion")
        self.lowest_supported_version = to_int("LowestSupportedVersion")
        self.monotonic_count = to_int("MonotonicCount", 0)
        self.hardware_instance = to_int("HardwareInstance", 0)
        self.update_image_index = to_int("UpdateImageIndex", 1)
        self.hash_algorithm = str(config.get("HashAlgorithm") or DEFAULT_HASH_ALGORITHM)
        self.signer_private_cert = to_path("OpenSslSignerPrivateCertFile")
        self.other_public_cert = to_path("OpenSslOtherPublicCertFile")
        self.trusted_public_cert = to_path("OpenSslTrustedPublicCertFile")
        self.signing_tool_path = to_path("SigningToolPath")

        if config.get("SignToolPfxFile") or config.get("SignToolSubjectName"):
            raise ValueError("signtool signing is not supported; use OpenSSL fields")
        if config.get("Dependencies"):
            raise ValueError("capsule dependency expressions are not supported")

        certs = (
            self.signer_private_cert,
            self.other_public_cert,
            self.trusted_public_cert,
        )
        self.sign = any(certs)
        if self.sign and not all(certs):
            raise ValueError(
                "incomplete OpenSSL certificate set: "
                "OpenSslSignerPrivateCertFile, OpenSslOtherPublicCertFile "
                "and OpenSslTrustedPublicCertFile must all be set to sign"
            )

        if self.fw_version >> 32:
            raise ValueError("FwVersion does not fit in 32 bits")
        if self.lowest_supported_version >> 32:
            raise ValueError("LowestSupportedVersion does not fit in 32 bits")
        if not 1 <= self.update_image_index <= 0xFF:
            raise ValueError("UpdateImageIndex must be between 0x1 and 0xff")


def sign_payload_openssl(
    payload: bytes,
    tool_path: Optional[str],
    signer_private_cert: str,
    other_public_cert: str,
    hash_algorithm: str,
    verbose: bool,
) -> bytes:
    """Produce a detached PKCS7 signature over payload with openssl."""
    command = [
        os.path.join(tool_path or "", "openssl"),
        "smime",
        "-sign",
        "-binary",
        "-outform",
        "DER",
        "-md",
        hash_algorithm,
        "-signer",
        signer_private_cert,
        "-certfile",
        other_public_cert,
    ]
    if verbose:
        print(" ".join(command))
    result = subprocess.run(command, input=payload, capture_output=True)
    if result.returncode != 0:
        print(result.stderr.decode())
        raise ValueError(f"openssl smime exited with status {result.returncode}")
    return result.stdout


def encode_payload(descriptor: PayloadDescriptor, verbose: bool) -> bytes:
    """Wrap one payload: FMP payload header, then optional signing."""
    with open(descriptor.payload_file, "rb") as f:
        payload = f.read()

    image = (
        FMP_PAYLOAD_SIGNATURE
        + struct.pack(
            "<3I",
            FMP_PAYLOAD_HEADER_SIZE,
            descriptor.fw_version,
            descriptor.lowest_supported_version,
        )
        + payload
    )

    if not descriptor.sign:
        print("WARNING: no OpenSSL certificates given, unsigned capsule payload")
        return image

    # The signature covers the image with the 64-bit monotonic count
    # appended; the count itself travels in the authentication header.
    cert_data = sign_payload_openssl(
        image + struct.pack("<Q", descriptor.monotonic_count),
        descriptor.signing_tool_path,
        descriptor.signer_private_cert or "",
        descriptor.other_public_cert or "",
        descriptor.hash_algorithm,
        verbose,
    )
    win_cert = (
        struct.pack(
            "<IHH",
            WIN_CERT_PREFIX_LEN + len(cert_data),
            WIN_CERT_REVISION,
            WIN_CERT_TYPE_EFI_GUID,
        )
        + EFI_CERT_TYPE_PKCS7_GUID.bytes_le
        + cert_data
    )
    return struct.pack("<Q", descriptor.monotonic_count) + win_cert + image


def encode_capsule(
    descriptors: List[PayloadDescriptor],
    embedded_drivers: List[bytes],
    capsule_flags: List[str],
    oem_flags: int,
    verbose: bool,
) -> bytes:
    """Assemble the FMP capsule body and the outer capsule header."""
    items = list(embedded_drivers)
    for descriptor in descriptors:
        image_payload = encode_payload(descriptor, verbose)
        capsule_support = CAPSULE_SUPPORT_AUTHENTICATION if descriptor.sign else 0
        items.append(
            struct.pack("<I", FMP_IMAGE_HEADER_VERSION)
            + descriptor.guid.bytes_le
            + struct.pack("<B3x", descriptor.update_image_index)
            + struct.pack("<II", len(image_payload), 0)  # no vendor code bytes
            + struct.pack("<QQ", descriptor.hardware_instance, capsule_support)
            + image_payload
        )

    body = struct.pack(
        "<I2H", FMP_CAPSULE_HEADER_VERSION, len(embedded_drivers), len(descriptors)
    )
    offset = FMP_CAPSULE_HEADER_SIZE + 8 * len(items)
    for item in items:
        body += struct.pack("<Q", offset)
        offset += len(item)
    body += b"".join(items)

    flags = oem_flags
    for flag in capsule_flags:
        flags |= CAPSULE_FLAGS[flag]
    return (
        EFI_FIRMWARE_MANAGEMENT_CAPSULE_ID_GUID.bytes_le
        + struct.pack(
            "<4I",
            CAPSULE_HEADER_SIZE,
            flags,
            CAPSULE_HEADER_SIZE + len(body),
            0,  # reserved tail of the 32-byte header
        )
        + body
    )


def dump_info(capsule_file: str) -> None:
    """Decode a capsule file and print its structure (--dump-info)."""
    with open(capsule_file, "rb") as f:
        data = f.read()

    guid = uuid.UUID(bytes_le=data[:16])
    header_size, flags, image_size, _ = struct.unpack_from("<4I", data, 16)
    flag_names = ", ".join(n for n, bit in CAPSULE_FLAGS.items() if flags & bit)
    known = " (firmware management capsule)"
    print(f"capsule: {capsule_file}")
    print("  outer header")
    print(
        f"    capsule guid    : {guid}"
        f"{known if guid == EFI_FIRMWARE_MANAGEMENT_CAPSULE_ID_GUID else ''}"
    )
    print(f"    header size     : {header_size} bytes")
    print(f"    flags           : {flags:#010x} [{flag_names}]")
    print(f"    total size      : {image_size} bytes")
    if image_size != len(data):
        raise ValueError(
            f"declared capsule size {image_size} does not match file size {len(data)}"
        )

    fmp = data[header_size:]
    version, driver_count, item_count = struct.unpack_from("<I2H", fmp)
    print("  fmp header")
    print(f"    version         : {version}")
    print(f"    embedded drivers: {driver_count}")
    print(f"    payload items   : {item_count}")
    offsets = [
        struct.unpack_from("<Q", fmp, FMP_CAPSULE_HEADER_SIZE + 8 * i)[0]
        for i in range(driver_count + item_count)
    ]

    for index in range(driver_count, driver_count + item_count):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(fmp)
        item = fmp[offsets[index] : end]
        (version,) = struct.unpack_from("<I", item)
        type_guid = uuid.UUID(bytes_le=item[4:20])
        (image_index,) = struct.unpack_from("<B", item, 20)
        image_len, vendor_len = struct.unpack_from("<II", item, 24)
        hw_instance, support = struct.unpack_from("<QQ", item, 32)
        print(f"  payload {index - driver_count} (offset {offsets[index]:#x})")
        print(f"    header version  : {version}")
        print(f"    image type guid : {type_guid}")
        print(f"    image index     : {image_index}")
        print(f"    image size      : {image_len} bytes")
        print(f"    vendor code     : {vendor_len} bytes")
        print(f"    hw instance     : {hw_instance:#x}")
        print(f"    capsule support : {support:#x}")

        image = item[FMP_IMAGE_HEADER_SIZE:]
        if support & CAPSULE_SUPPORT_AUTHENTICATION:
            count, dw_length, revision, cert_kind = struct.unpack_from("<QIHH", image)
            cert_guid = uuid.UUID(bytes_le=image[16:32])
            pkcs7 = " (PKCS7)" if cert_guid == EFI_CERT_TYPE_PKCS7_GUID else ""
            print("    authentication")
            print(f"      monotonic count : {count:#x}")
            print(
                f"      certificate     : {dw_length - WIN_CERT_PREFIX_LEN} bytes"
                f" (win-cert revision {revision:#06x}, type {cert_kind:#06x})"
            )
            print(f"      cert type guid  : {cert_guid}{pkcs7}")
            image = image[8 + dw_length :]

        if image[:4] == FMP_PAYLOAD_SIGNATURE:
            hdr_size, fw_version, lowest = struct.unpack_from("<3I", image, 4)
            print("    firmware payload (MSS1)")
            print(f"      fw version      : {fw_version:#010x}")
            print(f"      lowest supported: {lowest:#010x}")
            print(f"      payload size    : {len(image) - hdr_size} bytes")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="qcom-capsule-tool generate-capsule",
        description="Generate a signed UEFI FMP capsule from a JSON payload "
        "descriptor (drop-in for the encode mode of edk2 GenerateCapsule.py)",
    )
    parser.add_argument("-e", "--encode", action="store_true", help="Encode a capsule")
    parser.add_argument(
        "-j", "--json-file", dest="json_file", help="JSON payload descriptor file"
    )
    parser.add_argument("-o", "--output", dest="output_file", help="Output file")
    parser.add_argument(
        "--capflag",
        dest="capsule_flags",
        action="append",
        default=[],
        choices=sorted(CAPSULE_FLAGS),
        help="Capsule flag, may be repeated",
    )
    parser.add_argument(
        "--capoemflag",
        dest="oem_flags",
        type=lambda value: int(value, 0),
        default=0,
        help="OEM flag bits 0x0000..0xffff",
    )
    parser.add_argument(
        "--dump-info", dest="dump_file", help="Decode and display a capsule file"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    try:
        if args.dump_file:
            dump_info(args.dump_file)
            return
        if not args.encode:
            parser.error("one of --encode or --dump-info is required")
        if not args.json_file or not args.output_file:
            parser.error("--encode requires --json-file and --output")
        if "InitiateReset" in args.capsule_flags and (
            "PersistAcrossReset" not in args.capsule_flags
        ):
            parser.error("--capflag InitiateReset also requires PersistAcrossReset")
        if args.oem_flags > 0xFFFF:
            parser.error("--capoemflag must be between 0x0000 and 0xffff")

        with open(args.json_file, "r") as f:
            config = json.load(f)
        descriptors = [
            PayloadDescriptor(payload) for payload in config.get("Payloads", [])
        ]
        if not descriptors:
            raise ValueError(f'no "Payloads" entries in {args.json_file}')
        embedded_drivers = []
        for driver in config.get("EmbeddedDrivers", []):
            with open(os.path.expandvars(driver["Driver"]), "rb") as f:
                embedded_drivers.append(f.read())

        capsule = encode_capsule(
            descriptors,
            embedded_drivers,
            args.capsule_flags,
            args.oem_flags,
            args.verbose,
        )
        with open(args.output_file, "wb") as f:
            f.write(capsule)
        if args.verbose:
            print(f"Wrote capsule {args.output_file} ({len(capsule)} bytes)")
    except (OSError, ValueError, KeyError, struct.error) as e:
        print(f"generate-capsule: error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
