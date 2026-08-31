# --------------------------------------------------------------------
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

import argparse
import os
import subprocess
import sys


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


def patch_capsule_images(image_paths, cert_cer_path, staging_dir):
    """Patch QcCapsuleRootCert into each ELF in *image_paths*, writing patched
    copies (same basename, e.g. `.xz` in -> `.xz` out) into *staging_dir*.

    Delegates to patch_capsule_cert(), which auto-detects uefi_dtbs vs
    xbl_config and transparently handles `.xz`-compressed inputs/outputs.
    """
    from qcom_capsule_tool.patch_capsule_cert import patch_capsule_cert

    os.makedirs(staging_dir, exist_ok=True)
    for image_path in image_paths:
        output_path = os.path.join(staging_dir, os.path.basename(image_path))
        try:
            patch_capsule_cert(image_path, cert_cer_path, output_path)
        except Exception as exc:
            print(f"Error: failed to patch capsule cert into {image_path}: {exc}")
            sys.exit(1)
        print(f"Patched capsule cert: {image_path} -> {output_path}")


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

    # Step 2b: Patch QcCapsuleRootCert into the requested images, if any.
    # Patched copies are staged in a directory searched ahead of -images, so
    # FVCreation picks them up in place of the unpatched originals.
    image_search_paths = [args.images]
    if args.patch_image:
        staging_dir = os.path.join(os.getcwd(), "patched_images")
        patch_capsule_images(args.patch_image, args.patch_cert, staging_dir)
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
        help="Path to QcFMPRoot.cer; required when --patch-image is given",
    )
    parser.add_argument(
        "--patch-image",
        dest="patch_image",
        action="append",
        default=[],
        help="Path to an image to patch QcCapsuleRootCert into (uefi_dtbs.elf, "
        "uefi_dtbs.xz, or xbl_config.elf -- ELF type and .xz compression are "
        "auto-detected). Repeat for multiple images. Patched copies are "
        "staged in ./patched_images/ and searched ahead of -images, so the "
        "originals under -images are never modified. Omit if the images are "
        "already patched (e.g. via a separate patch-capsule-cert step).",
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
    if args.patch_image and not args.patch_cert:
        parser.error("--patch-cert is required when --patch-image is given")
    _run(args)


if __name__ == "__main__":
    main()
