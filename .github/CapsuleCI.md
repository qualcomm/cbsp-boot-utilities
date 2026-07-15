Copyright (c) 2026 Qualcomm Innovation Center, Inc. All rights reserved.
SPDX-License-Identifier: BSD-3-Clause-Clear

# CI Workflow: UEFI Capsule Generation

This document describes the GitHub Actions CI workflow defined in
[ci.yml](workflows/ci.yml).

## Overview

The workflow validates the end-to-end UEFI capsule generation process on every
push and pull request. It runs on an `ubuntu-latest` runner and exercises the
same steps a developer would follow locally (see
[uefi_capsule_generation/README.md](../uefi_capsule_generation/README.md)).

## Stages

1. **Setup Python** -- Installs Python 3.11 via `actions/setup-python`.
1. **Install system dependencies** -- Installs `device-tree-compiler` and
   Python packages (`validators`, `requests`, `pyelftools`, `pylibfdt`).
1. **Generate OpenSSL certificates** -- Creates a full certificate chain
   (Root CA, Intermediate CA, User) using OpenSSL. Certificates are stored
   in `$CERT_PATH` and used for capsule signing. Uses the OpenSSL
   configuration from [opensslroot.cfg](opensslroot.cfg).
1. **Convert certificate to HEX** -- Runs `BinToHex.py` to convert the Root
   CA certificate (DER) into a HEX include file for embedding in XBLConfig.
1. **Fetch boot binaries** -- Downloads the QCM6490 boot binaries archive
   from Qualcomm Artifactory and extracts it.
1. **Add certificates to XBLConfig** -- Dumps sections from `xbl_config.elf`,
   patches the `QcCapsuleRootCert` property in the device-tree blob with the
   new Root CA certificate, and re-packs the ELF. Verifies the certificate
   was actually updated.
1. **Generate firmware version and create firmware volume** - Generates a
   `SYSFW_VERSION.bin` file and creates a firmware volume (`firmware.fv`)
   containing the boot binaries and version info.
1. **Update JSON parameters** -- Populates `config.json` with firmware type,
   paths to the firmware volume, signing certificates, and the FMP GUID.
1. **Generate capsule file** -- Runs `qcom-capsule-tool generate-capsule`
   to produce the final signed `capsule_file.cap`. FFS/FV/capsule images
   are generated natively in Python; no EDK2 checkout or BaseTools
   binaries are required.
1. **Dump capsule information** -- Prints the capsule metadata for
   verification.

## Environment Variables

| Variable            | Purpose                                       |
|---------------------|-----------------------------------------------|
| `REP_ROOT`          | Repository checkout (`$GITHUB_WORKSPACE`).    |
| `CERT_PATH`         | Generated certs dir (`$GITHUB_WORKSPACE/certs`). |
| `BOOT_BINARIES_URL` | URL to the QCM6490 boot binaries ZIP.         |

## Trigger Events

- **push** -- runs on every push to any branch.
- **pull_request** -- runs on every pull request targeting any branch.

## Prerequisites for Local Reproduction

To reproduce the CI flow locally, ensure the following are installed:

- Python 3.11+
- OpenSSL
- `device-tree-compiler` system package
- Python packages: `validators`, `requests`, `pyelftools`, `pylibfdt`

Then follow the stages above in order from within the
`uefi_capsule_generation/` directory.
