# --------------------------------------------------------------------
# Copyright (c) 2026 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

"""Generate a throwaway OEM Root/Sub/Leaf certificate chain for testing.

Target-agnostic: produces the same QcFMPRoot/QcFMPSub/QcFMPCert files that
`create`'s -x/-oc/-p arguments and `patch-capsule-cert` expect, regardless of
which chip the capsule is for. This is a standalone, explicitly-invoked
command -- nothing elsewhere in qcom-capsule-tool auto-generates certs when
they're missing.

NOT for production use: the generated chain is self-signed with a
well-known default password and is only suitable for local testing/CI.
"""

import argparse
import os
import shutil
import subprocess
import sys

DEFAULT_PASSWORD = "testpassword"

_ROOT_SUBJ = "/CN=OEM Root CA/O=FMP/OU=OEM Key/L=San Diego/ST=California/C=US"
_SUB_SUBJ = "/CN=OEM Intermediate CA/O=FMP/OU=OEM Key/L=San Diego/ST=California/C=US"
_LEAF_SUBJ = "/CN=OEM User/O=FMP/OU=OEM Key/L=San Diego/ST=California/C=US"

_PRIVATE_FILES = [
    "QcFMPRoot.key",
    "QcFMPSub.key",
    "QcFMPCert.key",
    "QcFMPCert.pem",
    "QcFMPCert.pfx",
]


def _find_default_openssl_cfg():
    """Search the usual repo-relative locations for opensslroot.cfg."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "..", "..", ".github", "opensslroot.cfg"),
        os.path.join(here, "..", "..", ".github", "opensslroot.cfg"),
        os.path.join(os.getcwd(), ".github", "opensslroot.cfg"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    return None


def _openssl(args, cwd):
    subprocess.run(["openssl"] + args, cwd=cwd, check=True)


def generate_test_cert_chain(output_dir, password=DEFAULT_PASSWORD, openssl_cfg=None):
    """Generate a self-signed OEM Root/Sub/Leaf chain into *output_dir*.

    Writes QcFMPRoot.{key,crt,cer,pub.pem}, QcFMPSub.{key,crt,csr,pub.pem},
    and QcFMPCert.{key,crt,csr,pfx,pem}. Private-key-bearing files are
    chmod 600. Returns *output_dir*.
    """
    if openssl_cfg is None:
        openssl_cfg = _find_default_openssl_cfg()
    if not openssl_cfg or not os.path.exists(openssl_cfg):
        print("Error: opensslroot.cfg not found; pass --openssl-cfg explicitly.")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    shutil.copy(openssl_cfg, os.path.join(output_dir, "opensslroot.cfg"))
    os.makedirs(os.path.join(output_dir, "demoCA", "newcerts"), exist_ok=True)
    open(os.path.join(output_dir, "demoCA", "index.txt"), "w").close()
    with open(os.path.join(output_dir, "demoCA", "serial"), "w") as f:
        f.write("01\n")

    _openssl(["rand", "-out", "randfile", "256"], cwd=output_dir)

    pw = f"pass:{password}"

    # Root CA
    _openssl(
        ["genrsa", "-aes256", "-passout", pw, "-out", "QcFMPRoot.key", "2048"],
        cwd=output_dir,
    )
    _openssl(
        [
            "req",
            "-new",
            "-x509",
            "-config",
            "opensslroot.cfg",
            "-subj",
            _ROOT_SUBJ,
            "-days",
            "3650",
            "-passin",
            pw,
            "-key",
            "QcFMPRoot.key",
            "-out",
            "QcFMPRoot.crt",
        ],
        cwd=output_dir,
    )
    _openssl(
        ["x509", "-in", "QcFMPRoot.crt", "-out", "QcFMPRoot.cer", "-outform", "DER"],
        cwd=output_dir,
    )
    _openssl(
        [
            "x509",
            "-inform",
            "DER",
            "-in",
            "QcFMPRoot.cer",
            "-outform",
            "PEM",
            "-out",
            "QcFMPRoot.pub.pem",
        ],
        cwd=output_dir,
    )

    # Sub CA
    _openssl(
        ["genrsa", "-aes256", "-passout", pw, "-out", "QcFMPSub.key", "2048"],
        cwd=output_dir,
    )
    _openssl(
        [
            "req",
            "-new",
            "-config",
            "opensslroot.cfg",
            "-subj",
            _SUB_SUBJ,
            "-passin",
            pw,
            "-key",
            "QcFMPSub.key",
            "-out",
            "QcFMPSub.csr",
        ],
        cwd=output_dir,
    )
    _openssl(
        [
            "ca",
            "-config",
            "opensslroot.cfg",
            "-extensions",
            "v3_ca",
            "-batch",
            "-in",
            "QcFMPSub.csr",
            "-days",
            "3650",
            "-out",
            "QcFMPSub.crt",
            "-cert",
            "QcFMPRoot.crt",
            "-passin",
            pw,
            "-keyfile",
            "QcFMPRoot.key",
        ],
        cwd=output_dir,
    )
    _openssl(
        ["x509", "-in", "QcFMPSub.crt", "-outform", "PEM", "-out", "QcFMPSub.pub.pem"],
        cwd=output_dir,
    )

    # Leaf signing cert
    _openssl(
        ["genrsa", "-aes256", "-passout", pw, "-out", "QcFMPCert.key", "2048"],
        cwd=output_dir,
    )
    _openssl(
        [
            "req",
            "-new",
            "-config",
            "opensslroot.cfg",
            "-subj",
            _LEAF_SUBJ,
            "-passin",
            pw,
            "-key",
            "QcFMPCert.key",
            "-out",
            "QcFMPCert.csr",
        ],
        cwd=output_dir,
    )
    _openssl(
        [
            "ca",
            "-config",
            "opensslroot.cfg",
            "-batch",
            "-in",
            "QcFMPCert.csr",
            "-days",
            "3650",
            "-out",
            "QcFMPCert.crt",
            "-cert",
            "QcFMPSub.crt",
            "-passin",
            pw,
            "-keyfile",
            "QcFMPSub.key",
        ],
        cwd=output_dir,
    )
    _openssl(
        [
            "pkcs12",
            "-export",
            "-passout",
            pw,
            "-out",
            "QcFMPCert.pfx",
            "-passin",
            pw,
            "-inkey",
            "QcFMPCert.key",
            "-in",
            "QcFMPCert.crt",
        ],
        cwd=output_dir,
    )
    _openssl(
        [
            "pkcs12",
            "-passin",
            pw,
            "-in",
            "QcFMPCert.pfx",
            "-nodes",
            "-out",
            "QcFMPCert.pem",
        ],
        cwd=output_dir,
    )

    for name in _PRIVATE_FILES:
        path = os.path.join(output_dir, name)
        if os.path.exists(path):
            os.chmod(path, 0o600)

    print(f"Test cert chain generated -> {output_dir}")
    print(
        "WARNING: this is a self-signed TEST chain with a well-known "
        "password; do not use it for production capsules."
    )
    return output_dir


def main():
    parser = argparse.ArgumentParser(
        description="Generate a throwaway OEM Root/Sub/Leaf cert chain for "
        "testing (NOT for production use)."
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        required=True,
        help="Directory to write the cert chain into",
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help=f"Password protecting the generated private keys (default: {DEFAULT_PASSWORD})",
    )
    parser.add_argument(
        "--openssl-cfg",
        dest="openssl_cfg",
        default=None,
        help="Path to opensslroot.cfg; auto-detected from the repo if omitted",
    )
    args = parser.parse_args()

    generate_test_cert_chain(args.output_dir, args.password, args.openssl_cfg)


if __name__ == "__main__":
    main()
