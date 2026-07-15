# --------------------------------------------------------------------
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

import argparse
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
    run_module(
        "UpdateFvXml", "-S", args.StorageType, "-T", args.target, *ptool_path_args
    )

    # Step 3: Create firmware volume
    run_module(
        "FVCreation",
        "firmware.fv",
        "-FvType",
        "SYS_FW",
        "FvUpdate.xml",
        "SYSFW_VERSION.bin",
        args.images,
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
        choices=["UFS", "EMMC"],
        required=True,
        help="Specify storage type: UFS or EMMC",
    )
    parser.add_argument(
        "-T", "--target", required=True, help="Specify target platform (e.g., QCS6490)"
    )

    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
