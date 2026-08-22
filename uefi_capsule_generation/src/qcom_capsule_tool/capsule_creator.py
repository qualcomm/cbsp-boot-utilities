# --------------------------------------------------------------------
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

import argparse
import lzma
import os
import subprocess
import sys

UEFI_DTBS_ELF = "uefi_dtbs.elf"
UEFI_DTBS_XZ = "uefi_dtbs.xz"
XBL_CONFIG_ELF = "xbl_config.elf"


def run_module(module, *args):
    """Run a qcom_capsule_tool module in a subprocess, exit on failure."""
    command = [sys.executable, "-m", f"qcom_capsule_tool.{module}"] + [
        str(arg) for arg in args
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        print(f"Error: {' '.join(command)} failed with code {result.returncode}")
        sys.exit(1)


def _patch_one(elf_path, cert_cer_path, output_path):
    from qcom_capsule_tool.patch_capsule_cert import patch_capsule_cert

    try:
        patch_capsule_cert(elf_path, cert_cer_path, output_path)
    except Exception as exc:
        print(f"Error: failed to patch capsule cert into {elf_path}: {exc}")
        sys.exit(1)
    print(f"Patched capsule cert: {elf_path} -> {output_path}")


def patch_capsule_images(images_dir, cert_cer_path, staging_dir):
    """Patch QcCapsuleRootCert into uefi_dtbs/xbl_config images found under
    *images_dir*, writing patched copies into *staging_dir*.

    uefi_dtbs.elf and uefi_dtbs.xz are mutually exclusive inputs; xbl_config.elf
    is independent and optional. Either, both, or neither may be patched --
    whichever of the two is present under *images_dir*.
    """
    os.makedirs(staging_dir, exist_ok=True)

    dtbs_elf = os.path.join(images_dir, UEFI_DTBS_ELF)
    dtbs_xz = os.path.join(images_dir, UEFI_DTBS_XZ)
    if os.path.exists(dtbs_elf) and os.path.exists(dtbs_xz):
        print(
            f"Error: both {UEFI_DTBS_ELF} and {UEFI_DTBS_XZ} found in "
            f"{images_dir}; only one is allowed."
        )
        sys.exit(1)
    elif os.path.exists(dtbs_xz):
        decompressed = os.path.join(staging_dir, UEFI_DTBS_ELF)
        with lzma.open(dtbs_xz, "rb") as src, open(decompressed, "wb") as dst:
            dst.write(src.read())
        patched = os.path.join(staging_dir, "uefi_dtbs_patched.elf")
        _patch_one(decompressed, cert_cer_path, patched)
        out_xz = os.path.join(staging_dir, UEFI_DTBS_XZ)
        with open(patched, "rb") as src, lzma.open(out_xz, "wb") as dst:
            dst.write(src.read())
        print(f"Recompressed: {out_xz}")
    elif os.path.exists(dtbs_elf):
        _patch_one(dtbs_elf, cert_cer_path, os.path.join(staging_dir, UEFI_DTBS_ELF))
    else:
        print(f"No {UEFI_DTBS_ELF}/{UEFI_DTBS_XZ} found in {images_dir}, skipping")

    xbl_config = os.path.join(images_dir, XBL_CONFIG_ELF)
    if os.path.exists(xbl_config):
        _patch_one(xbl_config, cert_cer_path, os.path.join(staging_dir, XBL_CONFIG_ELF))
    else:
        print(f"No {XBL_CONFIG_ELF} found in {images_dir}, skipping")


def _run(args):
    # Step 1: Generate SYSFW_VERSION.bin
    run_module(
        "SYSFW_VERSION_program",
        "-Gen",
        "-FwVer",
        args.fwver,
        "-LFwVer",
        args.lfwver,
        "-O",
        "SYSFW_VERSION.bin",
    )

    # Step 2: Create FvUpdate.xml
    ptool_path_args = ["--ptool-path", args.ptool_path] if args.ptool_path else []
    update_partitions_args = (
        ["--update-partitions", args.update_partitions]
        if args.update_partitions
        else []
    )
    run_module(
        "UpdateFvXml",
        "-S",
        args.StorageType,
        "-T",
        args.target,
        *ptool_path_args,
        *update_partitions_args,
    )

    # Step 2b: Patch QcCapsuleRootCert into uefi_dtbs/xbl_config, if requested.
    # Patched copies are staged in a directory searched ahead of -images, so
    # FVCreation picks them up in place of the unpatched originals.
    image_search_paths = [args.images]
    if args.patch_cert:
        staging_dir = os.path.join(os.getcwd(), "patched_images")
        patch_capsule_images(args.images, args.patch_cert, staging_dir)
        image_search_paths = [staging_dir, args.images]

    # Step 3: Create firmware volume
    glymur_args = ["--glymur"] if args.target.lower() == "glymur" else []
    run_module(
        "FVCreation",
        "firmware.fv",
        "-FvType",
        "SYS_FW",
        "FvUpdate.xml",
        "SYSFW_VERSION.bin",
        *image_search_paths,
        *glymur_args,
    )

    # Step 4: Update JSON parameters
    run_module(
        "UpdateJsonParameters",
        "-j",
        args.config,
        "-f",
        "SYS_FW",
        "-b",
        "SYSFW_VERSION.bin",
        "-pf",
        "firmware.fv",
        "-p",
        args.p,
        "-x",
        args.x,
        "-oc",
        args.oc,
        "-g",
        args.guid,
    )

    # Step 5: Generate capsule
    run_module(
        "generate_capsule",
        "-e",
        "-j",
        args.config,
        "-o",
        args.capsule,
        "--capflag",
        "PersistAcrossReset",
        "-v",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Combined script for Capsule generation"
    )
    parser.add_argument("-fwver", required=True, help="Firmware version")
    parser.add_argument(
        "-lfwver", required=True, help="Lowest supported firmware version"
    )
    parser.add_argument("-config", required=True, help="Configuration JSON file")
    parser.add_argument("-p", required=True, help="Certificate file")
    parser.add_argument("-x", required=True, help="Root certificate file")
    parser.add_argument("-oc", required=True, help="Sub certificate file")
    parser.add_argument("-guid", required=True, help="FMP GUID")
    parser.add_argument("-capsule", required=True, help="Output capsule file name")
    parser.add_argument("-images", required=True, help="Images directory")
    parser.add_argument(
        "--ptool-path",
        dest="ptool_path",
        default=None,
        help="Path to an existing qcom-ptool directory; "
        "when provided, the repository is not cloned",
    )
    parser.add_argument(
        "-S",
        "--StorageType",
        choices=["UFS", "EMMC", "NORUFS", "NORNVME"],
        required=True,
        help="Specify storage type: UFS, EMMC, NORUFS, or NORNVME",
    )
    parser.add_argument(
        "-T", "--target", required=True, help="Specify target platform (e.g., QCS6490)"
    )
    parser.add_argument(
        "--patch-cert",
        dest="patch_cert",
        default=None,
        help="Path to QcFMPRoot.cer; when provided, patches QcCapsuleRootCert "
        "into uefi_dtbs.elf/.xz and/or xbl_config.elf found under -images "
        "before firmware volume creation",
    )
    parser.add_argument(
        "--update-partitions",
        dest="update_partitions",
        default=None,
        help="Comma-separated base partition names (e.g. dtb,uefi_dtb) to mark "
        "Operation=UPDATE in the generated FvUpdate.xml; all other entries "
        "stay Operation=IGNORE. Omit to keep every entry IGNORE (unchanged "
        "default behavior).",
    )

    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
