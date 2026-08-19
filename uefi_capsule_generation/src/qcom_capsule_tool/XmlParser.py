# --------------------------------------------------------------------
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------


import re
import traceback
import xml.etree.ElementTree as ET
from collections import OrderedDict

from . import FVCreation_header as FVC_h


def print_all_level_d(d, indent=0, log_file_obj=None):
    """
    About:
        Function to print in console, a nested dict with indentation for easy reading
        For debugging

    Args:
        d: dict to be printed -> dict
        indent: The indentation space to use for the current nested dict -> int

    Return:
        None
    """
    if not d:
        return
    if isinstance(d, list):
        s = ""
        for i in range(indent):
            print(" ", end="")
            s += " "

        print("[")
        for x in d:
            print_all_level_d(x, indent, log_file_obj)
            print()

        s = ""
        for i in range(indent):
            print(" ", end="")
            s += " "
        print("]")

        return

    if isinstance(d, str):
        s = ""
        for i in range(indent):
            print(" ", end="")
            s += " "
        print(d)

        return

    for x in d:
        if (
            isinstance(d[x], OrderedDict)
            or isinstance(d[x], dict)
            or isinstance(d[x], list)
        ):
            s = ""
            for i in range(indent):
                print(" ", end="")
                s += " "
            print(x + " : ")
            print_all_level_d(d[x], indent + 4, log_file_obj)

        else:
            s = ""
            for i in range(indent):
                print(" ", end="")
                s += " "
            print(x + " : ", end="")
            print(d[x])


def xml_to_dict(ele):
    if len(ele) == 0:
        return ele.text

    result_dict = OrderedDict()
    for c in ele:
        c_dict = xml_to_dict(c)

        if c.tag in result_dict:
            if type(result_dict[c.tag]) is list:
                result_dict[c.tag].append(c_dict)
            else:
                result_dict[c.tag] = [result_dict[c.tag], c_dict]
        else:
            result_dict[c.tag] = c_dict

    return result_dict


def parse_input_xml(s_xml_file, s_breaking_change_number, g_dynamic_var):

    try:
        tree = ET.parse(s_xml_file)
        root = tree.getroot()

    except Exception:
        print(traceback.format_exc())
        return False

    result_dict = xml_to_dict(root)

    # print_all_level_d(result_dict)

    # print("\n\n\nin custom code:")
    if isinstance(result_dict["FwEntry"], OrderedDict):
        result_dict["FwEntry"] = [result_dict["FwEntry"]]
    for fw_entry in result_dict["FwEntry"]:
        raw_fw_item = FVC_h.XML_RAW_FWENTRY()

        raw_fw_item.Operation = fw_entry["Operation"]
        raw_fw_item.InputBinary = fw_entry["InputBinary"]
        raw_fw_item.InputPath = fw_entry["InputPath"]
        raw_fw_item.UpdateType = fw_entry["UpdateType"]
        raw_fw_item.BackupType = fw_entry["BackupType"]
        raw_fw_item.UpdatePath.DiskType = fw_entry["Dest"]["DiskType"]

        raw_fw_item.UpdatePath.PartitionName = fw_entry["Dest"]["PartitionName"]
        raw_fw_item.UpdatePath.PartitionTypeGUID = fw_entry["Dest"]["PartitionTypeGUID"]
        raw_fw_item.BackupPath.DiskType = fw_entry["Backup"]["DiskType"]
        raw_fw_item.BackupPath.PartitionName = fw_entry["Backup"]["PartitionName"]
        raw_fw_item.BackupPath.PartitionTypeGUID = fw_entry["Backup"][
            "PartitionTypeGUID"
        ]

        if g_dynamic_var.isGlymurMode:
            if "MatchIdentifier" in fw_entry:
                raw_fw_item.MatchIdentifier = fw_entry["MatchIdentifier"]
                g_dynamic_var.isMatchIdentifierInXML = True

            if "BinaryType" in fw_entry:
                raw_fw_item.BinaryType = fw_entry["BinaryType"]
                g_dynamic_var.isBinaryTypeInXML = True

            if "ARValidation" in fw_entry:
                ar_validation = fw_entry["ARValidation"]
                image_nodes = ar_validation.get("Image") if ar_validation else None
                if image_nodes:
                    if isinstance(image_nodes, OrderedDict):
                        image_nodes = [image_nodes]
                    images = []
                    for image_node in image_nodes:
                        image = FVC_h.XML_RAW_FWENTRY_IMAGE(
                            file_name=image_node.get("FileName"),
                            ar_validation_type=image_node.get("ARValidationType"),
                        )
                        images.append(image)
                    raw_fw_item.ARValidation = FVC_h.XML_RAW_FWENTRY_ARVALIDATION(
                        images
                    )

        g_dynamic_var.XmlRawFwEntryList.append(raw_fw_item)

    # print("\n\n\n*******************\n")

    metadata_items = root.findall(".//Metadata")

    for metadata in metadata_items:
        b_found = False
        media_found = False
        s_brk_chg_num = "0"
        s_flash_type_in = "0"

        if len(metadata) != 2:
            print("ERROR: Malformed XML. MetaData node does not contain two elements.")
            return False

        # Traversing MetaData entries
        for child in metadata:
            if child.tag.lower() == "breakingchangenumber":
                s_brk_chg_num = child.text.strip()
                b_found = True
                continue

            if child.tag.lower() == "flashtype":
                s_flash_type_in = child.text.strip()
                media_found = True
                continue

        if not b_found:
            print("Warning: MetaData does not contain BreakingChangeNumber element.")
            return False

        if not re.match("^[0-9]+$", s_brk_chg_num):
            print(
                "ERROR: Invalid BreakingChangeNumber in the XML file. BreakingChangeNumber should only contain numbers."
            )
            return False

        if not media_found:
            print("Warning: MetaData does not contain FlashType element.")
            return False

        if s_flash_type_in.upper() not in g_dynamic_var.dFlashTypeByString:
            print(
                "ERROR: Invalid FlashType in the XML file. FlashType should only be UFS or EMMC."
            )
            return False
        else:
            g_dynamic_var.DeviceFlashType = g_dynamic_var.dFlashTypeByString[
                s_flash_type_in.upper()
            ]

    return True
