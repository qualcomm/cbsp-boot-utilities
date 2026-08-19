# --------------------------------------------------------------------
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

import argparse
import os
import subprocess
import sys


def run_command(command, fail_on_error=False):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(
                f"Command failed with return code {result.returncode}: {result.stderr}"
            )
        print(result.stdout)
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)


def _run(args):

    python = sys.executable

    if args.setup:
        run_command(f"{python} -m qcom_capsule_tool.capsule_setup", fail_on_error=True)
    # Step 1: Generate SYSFW_VERSION.bin
    run_command(
        f"{python} -m qcom_capsule_tool.SYSFW_VERSION_program -Gen -FwVer {args.fwver} -LFwVer {args.lfwver} -O SYSFW_VERSION.bin"
    )

    # Step 2: Create FvUpdate.xml
    ptool_path_arg = f"--ptool-path {args.ptool_path}" if args.ptool_path else ""
    run_command(
        f"{python} -m qcom_capsule_tool.UpdateFvXml -S {args.StorageType} -T {args.target} {ptool_path_arg}"
    )

    # Step 3: Create firmware volume
    edk2_path_arg = f"--edk2-path {args.edk2_path}" if args.edk2_path else ""
    glymur_arg = "--glymur" if args.target.lower() == "glymur" else ""
    run_command(
        f'{python} -m qcom_capsule_tool.FVCreation firmware.fv "-FvType" "SYS_FW" "FvUpdate.xml" SYSFW_VERSION.bin {args.images} {edk2_path_arg} {glymur_arg}'
    )

    # Step 4: Update JSON parameters
    run_command(
        f"{python} -m qcom_capsule_tool.UpdateJsonParameters -j {args.config} -f SYS_FW -b SYSFW_VERSION.bin -pf firmware.fv -p {args.p} -x {args.x} -oc {args.oc} -g {args.guid}"
    )

    # Step 5: Generate capsule. Resolve edk2 path explicitly so we never depend
    # on cwd-relative GenerateCapsule.py copies; default to $PWD/edk2 (where
    # `qcom-capsule-tool setup` clones it).
    edk2 = args.edk2_path if args.edk2_path else os.path.join(os.getcwd(), "edk2")
    generate_capsule = os.path.join(
        edk2, "BaseTools", "Source", "Python", "Capsule", "GenerateCapsule.py"
    )
    pythonpath = os.path.join(edk2, "BaseTools", "Source", "Python")
    run_command(
        f"PYTHONPATH={pythonpath} python3 {generate_capsule} -e -j {args.config} -o {args.capsule} --capflag PersistAcrossReset -v"
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
    parser.add_argument("-setup", action="store_true", help="Run capsule setup script")
    parser.add_argument(
        "--edk2-path",
        dest="edk2_path",
        default=None,
        help="Path to an existing edk2 directory with built GenFfs/GenFv tools; "
        "when provided, capsule_setup.py does not need to be run",
    )
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

    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
