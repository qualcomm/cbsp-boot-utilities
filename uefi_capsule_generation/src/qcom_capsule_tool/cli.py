# --------------------------------------------------------------------
# Copyright (c) 2026 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

"""Unified CLI dispatcher for qcom-capsule-tool.

Usage:
    qcom-capsule-tool <subcommand> [args ...]

Each subcommand delegates to the corresponding module's main() function,
passing remaining arguments through sys.argv.
"""

import argparse
import sys


# Lazy-import helpers -- keep startup fast by importing modules only
# when their subcommand is actually invoked.


def _cmd_create(argv):
    sys.argv = ["qcom-capsule-tool create"] + argv
    from qcom_capsule_tool.capsule_creator import main

    main()


def _cmd_fv_create(argv):
    sys.argv = ["qcom-capsule-tool fv-create"] + argv
    from qcom_capsule_tool.FVCreation import main

    main()


def _cmd_generate_capsule(argv):
    sys.argv = ["qcom-capsule-tool generate-capsule"] + argv
    from qcom_capsule_tool.generate_capsule import main

    main()


def _cmd_update_fv_xml(argv):
    sys.argv = ["qcom-capsule-tool update-fv-xml"] + argv
    from qcom_capsule_tool.UpdateFvXml import main

    main()


def _cmd_update_json(argv):
    sys.argv = ["qcom-capsule-tool update-json"] + argv
    from qcom_capsule_tool.UpdateJsonParameters import main

    main()


def _cmd_sysfw_version_create(argv):
    sys.argv = ["qcom-capsule-tool sysfw-version-create"] + argv
    from qcom_capsule_tool.SYSFW_VERSION_program import main

    main()


def _cmd_bin_to_hex(argv):
    sys.argv = ["qcom-capsule-tool bin-to-hex"] + argv
    from qcom_capsule_tool.BinToHex import main

    main()


def _cmd_set_dtb_property(argv):
    sys.argv = ["qcom-capsule-tool set-dtb-property"] + argv
    from qcom_capsule_tool.set_dtb_property import main

    main()


def _cmd_parse_config(argv):
    sys.argv = ["qcom-capsule-tool parse-config"] + argv
    from qcom_capsule_tool.xblconfig_parser import main

    main()


SUBCOMMANDS = {
    "create": ("Run the full capsule generation pipeline", _cmd_create),
    "fv-create": ("Create a firmware volume from XML + binaries", _cmd_fv_create),
    "generate-capsule": (
        "Generate a signed FMP capsule from JSON",
        _cmd_generate_capsule,
    ),
    "update-fv-xml": ("Generate FvUpdate.xml from partitions.conf", _cmd_update_fv_xml),
    "update-json": ("Update JSON config with firmware parameters", _cmd_update_json),
    "sysfw-version-create": (
        "Generate or inspect SYSFW_VERSION.bin",
        _cmd_sysfw_version_create,
    ),
    "bin-to-hex": ("Convert a binary file to hex format", _cmd_bin_to_hex),
    "set-dtb-property": ("Set or add a property in a DTB file", _cmd_set_dtb_property),
    "parse-config": ("Inspect or patch xbl_config.elf payloads", _cmd_parse_config),
}


def main():
    parser = argparse.ArgumentParser(
        prog="qcom-capsule-tool",
        description="Qualcomm capsule generation tools for UEFI firmware updates",
    )
    sub = parser.add_subparsers(dest="subcommand", title="subcommands")

    for name, (help_text, _) in SUBCOMMANDS.items():
        sub.add_parser(name, help=help_text, add_help=False)

    # Parse only the first positional arg; the rest is forwarded.
    args, remaining = parser.parse_known_args()

    if args.subcommand is None:
        parser.print_help()
        sys.exit(1)

    _, handler = SUBCOMMANDS[args.subcommand]
    handler(remaining)


if __name__ == "__main__":
    main()
