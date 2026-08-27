# --------------------------------------------------------------------
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------


import binascii
import ctypes
import os
import re
import struct
import sys
import traceback
import uuid
from enum import Enum

from . import fv_builder
from . import FVCreation_header as FVC_h
from . import XmlFwEntryValidation as XFEV
from . import XmlParser as xp

print_logs = 0

TOOL_VERSION_STRING = "1.1"
SYS_FW_METADATA_HEADER_SIGNATURE1 = 0x2E1946FB
SYS_FW_METADATA_HEADER_SIGNATURE2 = 0x7F744D57
FMP_PAYLOAD_HEADER_SIGNATURE = 0x3153534D
SYS_FW_METADATA_HEADER_REVISION_V3 = 0x3
SYS_FW_METADATA_FILE = "Metadata.dat"
SYS_FW_VERSION_DATA_SIGNATURE = "SYSFWVER"
SYS_FW_VERSION_DATA_REVISION = "1.0"
SYS_FW_METADATA_HEADER_REVISION = 0x4
SYS_FW_METADATA_HEADER_REVISION_GLYMUR = 0x5
SYS_FW_METADATA_REVISION = 0x1


class FV_TYPE(Enum):
    UNKNOWN = None
    SYS_FW = None
    EC_FW = None


class QSYS_FW_VERSION_DATA(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("Signature", ctypes.c_ulonglong),
        ("Revision", ctypes.c_uint),
        ("VersionDataSize", ctypes.c_uint),
        ("VersionDataCrc32", ctypes.c_uint),
        ("FwVersion", ctypes.c_uint),
        ("LowestSupportedFwVersion", ctypes.c_uint),
    ]

    def to_bytes(self):
        try:
            return bytes(bytearray(self))
        except Exception as e:
            print(f"ERROR: Failure converting structure to byte array(error:{e})", e)

    @classmethod
    def from_bytes(cls, byte_arr):
        try:
            version_data = cls()
            ctypes.memmove(
                ctypes.addressof(version_data), byte_arr, ctypes.sizeof(version_data)
            )
            return version_data

        except Exception:
            print(traceback.format_exc())
            return None


def remove_files(ls_files):
    for s_file in ls_files:
        try:
            if os.path.exists(s_file):
                os.remove(s_file)
        except Exception as e:
            print(f"Error deleting file {s_file}: {e}")


def get_dir_path(raw_fwentry, ls_search_paths):

    file_path = os.path.join(raw_fwentry.InputPath, raw_fwentry.InputBinary)

    if os.path.exists(file_path):
        print(f"INFO: File {raw_fwentry.InputBinary} found at {raw_fwentry.InputPath}.")
        return raw_fwentry.InputPath

    for s_path in ls_search_paths:
        file_path = os.path.join(s_path, raw_fwentry.InputBinary)
        if os.path.exists(file_path):
            return s_path

    return None


def get_exe_name(ls_files, s_pattern):
    for s_file in ls_files:
        if s_pattern.lower() in s_file.lower():
            return s_file
    return None


def get_file_name_only(s_file):
    if "\\" in s_file:  # it is a relative path
        return s_file[s_file.rfind("\\") + 1 : s_file.rfind(".")]
    else:  # just a file name, remove extension and return
        return s_file[: s_file.rfind(".")]


def Reflect(data_b, l_i):

    data_i = int(data_b)
    reff_i = 0

    for i in range(l_i):
        if (data_i & 0x1) != 0:
            reff_i = reff_i | int(1 << (int(l_i - 1) - i))
        data_i = data_i >> 1

    return reff_i


def CalcCRC32_i(buffer_b, l_i):
    k_i = 8
    MSB_i = 0
    gx_h = 0x04C11DB7
    regs_h = 0xFFFFFFFF
    regsMask_h = 0xFFFFFFFF
    regsMSB_i = 0

    gx_i = int(gx_h)
    regs_i = int(regs_h)
    regsMask_i = int(regsMask_h)

    for i in range(l_i):
        DataByte_b = buffer_b[i]
        DataByte_i = int(DataByte_b)
        DataByte_i = Reflect(DataByte_i, 8)

        for j in range(k_i):
            MSB_i = DataByte_i >> (k_i - 1)
            MSB_i = MSB_i & 1
            regsMSB_i = int(regs_i >> 31) & 1
            regs_i = regs_i << 1
            if (regsMSB_i ^ MSB_i) != 0:
                regs_i = regs_i ^ gx_i

            regs_i = regs_i & regsMask_i
            DataByte_i = DataByte_i << 1
    regs_i = regs_i & regsMask_i

    return Reflect(regs_i, 32) ^ int(0xFFFFFFFF)


def generate_fv(s_output_file_name, ls_ffs):
    try:
        fv_builder.write_fv(s_output_file_name, ls_ffs)
    except (OSError, ValueError) as e:
        print(f"ERROR: Failure creating FV file {s_output_file_name}: {e}")
        return False
    return True


def validate_sys_fw_ver_binary_file(fw_ver_binary_data):
    b_return = True
    s_revision = ["", ""]
    temp_version_data_crc32 = 0

    try:
        s_revision = [None, None]
        s_revision[1] = str(fw_ver_binary_data.Revision & 0x0000FFFF)
        s_revision[0] = str(fw_ver_binary_data.Revision >> 16)
        FwVerBinaryData_revision = s_revision[0] + "." + s_revision[1]

        if SYS_FW_VERSION_DATA_REVISION != FwVerBinaryData_revision:
            print("Unexpected REVISION value found")
            b_return = False
        elif print_logs >= 1:
            print("Expected REVISION value found")

        # Validating the signature of binary file
        bytes_signature = struct.pack("<Q", fw_ver_binary_data.Signature)

        if SYS_FW_VERSION_DATA_SIGNATURE != bytes_signature.decode("ascii"):
            print("Unexpected SIGNATURE value found")
            b_return = False
        elif print_logs >= 1:
            print("Expected SIGNATURE value found")

        # Validating CRC of FwVerBinaryData
        temp_version_data_crc32 = fw_ver_binary_data.VersionDataCrc32
        fw_ver_binary_data.VersionDataCrc32 = 0

        if temp_version_data_crc32 != CalcCRC32_i(
            fw_ver_binary_data.to_bytes(), fw_ver_binary_data.VersionDataSize
        ):
            print("Unexpected VersionDataSize value found")
            b_return = False
        elif print_logs >= 1:
            print("Expected VersionDataSize value found")

        fw_ver_binary_data.VersionDataCrc32 = temp_version_data_crc32

    except Exception as e:
        print(f"Encountered exception Message = {e}")

    return b_return


def calc_crc32(data, size):
    return binascii.crc32(data[:size]) & 0xFFFFFFFF


def get_versions_from_sys_fw_ver_binary_file(s_fw_ver_binary_file, fw_ver_binary_data):
    try:
        with open(s_fw_ver_binary_file, "rb") as fs:
            file_content = fs.read()
        fw_ver_binary_data = QSYS_FW_VERSION_DATA()
        fw_ver_binary_data = QSYS_FW_VERSION_DATA.from_bytes(file_content)

        if print_logs >= 2:
            print()
            print(
                "get_versions_from_sys_fw_ver_binary_file :: fw_ver_binary_data.Signature: ",
                fw_ver_binary_data.Signature,
            )
            print(
                "get_versions_from_sys_fw_ver_binary_file :: fw_ver_binary_data.Revision",
                fw_ver_binary_data.Revision,
            )
            print(
                "get_versions_from_sys_fw_ver_binary_file :: fw_ver_binary_data.VersionDataSize",
                fw_ver_binary_data.VersionDataSize,
            )
            print(
                "get_versions_from_sys_fw_ver_binary_file :: fw_ver_binary_data.VersionDataCrc32",
                fw_ver_binary_data.VersionDataCrc32,
            )
            print(
                "get_versions_from_sys_fw_ver_binary_file :: fw_ver_binary_data.FwVersion",
                fw_ver_binary_data.FwVersion,
            )
            print(
                "get_versions_from_sys_fw_ver_binary_file :: fw_ver_binary_data.LowestSupportedFwVersion",
                fw_ver_binary_data.LowestSupportedFwVersion,
            )
            print()
        return fw_ver_binary_data

    except Exception:
        print(traceback.format_exc())
        return False


def guid_to_string(guid):
    fw_entry_UpdatePath_PartitionTypeGUID_uuid_bytes_obj = bytes(guid)
    fw_entry_UpdatePath_PartitionTypeGUID__uuid_str = str(
        uuid.UUID(bytes=fw_entry_UpdatePath_PartitionTypeGUID_uuid_bytes_obj)
    )
    return fw_entry_UpdatePath_PartitionTypeGUID__uuid_str


def c_sharp_guid_format(guid_array):
    new_guid_array = (
        guid_array.bytes[3:4]
        + guid_array.bytes[2:3]
        + guid_array.bytes[1:2]
        + guid_array.bytes[0:1]
        + guid_array.bytes[5:6]
        + guid_array.bytes[4:5]
        + guid_array.bytes[7:8]
        + guid_array.bytes[6:7]
        + guid_array.bytes[8:]
    )
    return new_guid_array


def generate_sys_fw_meta_data_file(
    fw_ver_binary_data, s_breaking_change_number, g_dynamic_var
):

    if fw_ver_binary_data.FwVersion < fw_ver_binary_data.LowestSupportedFwVersion:
        print(
            "ERROR: Lowest Firmware version value is greater than or equal to current firmware version value.\n"
        )
        return False

    # Check Metadata.dat file exists, if yes delete it.
    if os.path.exists(SYS_FW_METADATA_FILE):
        try:
            os.remove(SYS_FW_METADATA_FILE)
        except Exception as e:
            print(f"ERROR: Failure deleting metadata file(error: {e}).\n")
            return False

    meta_data_header = FVC_h.QPAYLOAD_METADATA_HEADER()
    fw_entry_meta_data_size = 0

    meta_data_header.Signature1 = SYS_FW_METADATA_HEADER_SIGNATURE1
    meta_data_header.Signature2 = SYS_FW_METADATA_HEADER_SIGNATURE2

    if g_dynamic_var.isGlymurMode:
        # Use Glymur Payload header format whenever --glymur is passed,
        # regardless of whether any FwEntry declares <BinaryType>.
        meta_data_header.Revision = SYS_FW_METADATA_HEADER_REVISION_GLYMUR
        fw_entry_meta_data_size = ctypes.sizeof(FVC_h.QPAYLOAD_METADATA_FWENTRY_GLYMUR)

    elif g_dynamic_var.isMatchIdentifierInXML:
        # Use V4 Payload header format if MatchIdentifier in XML.
        meta_data_header.Revision = SYS_FW_METADATA_HEADER_REVISION
        fw_entry_meta_data_size = sys.getsizeof(FVC_h.QPAYLOAD_METADATA_FWENTRY)

    else:
        # Use V3 Payload header format if MatchIdentifier not in XML.
        meta_data_header.Revision = SYS_FW_METADATA_HEADER_REVISION_V3
        fw_entry_meta_data_size = (
            ctypes.sizeof(FVC_h.QPAYLOAD_METADATA_FWENTRY)
            - ctypes.sizeof(ctypes.c_uint32)
            - ctypes.sizeof(
                ctypes.c_char
                * (2 * FVC_h.GlobalStaticVariable.MATCH_IDENTIFIER_NAME_MAX_SIZE)
            )
            - ctypes.sizeof(ctypes.c_uint32)
            - ctypes.sizeof(FVC_h.FWENTRY_ARVALIDATION)
        )

    meta_data_header_temp = FVC_h.QPAYLOAD_METADATA_HEADER()
    meta_data_header.Size = len(meta_data_header_temp.to_bytes()) - (
        4 * struct.calcsize("<I")
    )
    meta_data_header.FirmwareVersion = fw_ver_binary_data.FwVersion
    meta_data_header.LowestSupportedVersion = (
        fw_ver_binary_data.LowestSupportedFwVersion
    )
    meta_data_header.BreakingChangeNumber = int(s_breaking_change_number)
    meta_data_header.Reserved1 = 0x0
    meta_data_header.Reserved2 = 0x0
    meta_data_header.EntryCount = len(g_dynamic_var.QpayloadFwEntryList)

    with open(SYS_FW_METADATA_FILE, "wb") as fs:
        header_bytes = ctypes.string_at(
            ctypes.byref(meta_data_header), ctypes.sizeof(meta_data_header)
        )
        fs.write(header_bytes)

        # Write metaData fw entries to metadata.dat
        for fw_entry in g_dynamic_var.QpayloadFwEntryList:
            new_uuid_obj = c_sharp_guid_format(
                uuid.UUID(bytes=bytes(fw_entry.FileGuid))
            )
            fw_entry.FileGuid = (ctypes.c_byte * 16)(*new_uuid_obj)

            UpdatePath_PartitionName_string = "".join(
                chr(b) for b in fw_entry.UpdatePath.PartitionName
            )
            UpdatePath_PartitionName_string = UpdatePath_PartitionName_string.replace(
                "\0", ""
            )
            fw_entry.UpdatePath.PartitionName[
                : len(UpdatePath_PartitionName_string.encode("utf-16-le"))
            ] = UpdatePath_PartitionName_string.encode("utf-16-le")

            new_uuid_obj = c_sharp_guid_format(
                uuid.UUID(bytes=bytes(fw_entry.UpdatePath.PartitionTypeGUID))
            )
            fw_entry.UpdatePath.PartitionTypeGUID = (ctypes.c_byte * 16)(*new_uuid_obj)

            BackupPath_PartitionName_string = "".join(
                chr(b) for b in fw_entry.BackupPath.PartitionName
            )
            BackupPath_PartitionName_string = BackupPath_PartitionName_string.replace(
                "\0", ""
            )
            fw_entry.BackupPath.PartitionName[
                : len(BackupPath_PartitionName_string.encode("utf-16-le"))
            ] = BackupPath_PartitionName_string.encode("utf-16-le")

            new_uuid_obj = c_sharp_guid_format(
                uuid.UUID(bytes=bytes(fw_entry.BackupPath.PartitionTypeGUID))
            )
            fw_entry.BackupPath.PartitionTypeGUID = (ctypes.c_byte * 16)(*new_uuid_obj)

            if g_dynamic_var.isGlymurMode:
                # Real Glymur/Mavros/Honu/Kaanapali V5 firmware expects Revision
                # as the FIRST field of FWENTRY_METADATA, unlike the legacy
                # layout QpayloadFwEntryList entries are built in.
                glymur_entry = FVC_h.QPAYLOAD_METADATA_FWENTRY_GLYMUR.from_legacy(
                    fw_entry
                )
                bytes_data = glymur_entry.to_bytes()
            else:
                bytes_data = fw_entry.to_bytes()
            fs.write(bytes_data[:fw_entry_meta_data_size])

    return True


def process_sys_fw_ffs_creation(
    s_xml_file_name,
    s_fw_ver_binary_file,
    s_breaking_change_number,
    fw_ver_binary_data,
    ls_ffs,
    ls_paths,
    g_dynamic_var,
):
    try:
        #
        # Firmware version validation
        #
        if not os.path.exists(s_fw_ver_binary_file):
            print(
                "ERROR: Invalid SYSFW_VERSION.BIN file, please check the input file provided.\n"
            )
            return False
        elif print_logs >= 2:
            print("%s file found" % (s_fw_ver_binary_file))

        fw_ver_binary_data = get_versions_from_sys_fw_ver_binary_file(
            s_fw_ver_binary_file, fw_ver_binary_data
        )
        if not fw_ver_binary_data:
            print("ERROR: Error parsing SYSFW_VERSION.BIN file.")
            return False
        elif print_logs >= 2:
            print("%s parsed successfully" % (s_fw_ver_binary_file))

        if not validate_sys_fw_ver_binary_file(fw_ver_binary_data):
            print("ERROR: Wrong SYSFW_VERSION.BIN file is supplied")
            return False
        elif print_logs >= 2:
            print("%s data validated successfully" % (s_fw_ver_binary_file))

        #
        # Parse input XML
        #
        if not xp.parse_input_xml(
            s_xml_file_name, s_breaking_change_number, g_dynamic_var
        ):
            print("ERROR: Error parsing XML file.")
            return False
        elif print_logs >= 2:
            print("XML file parsed with xp.parse_input_xml")

        #
        # Validate raw fw entries
        #
        if not XFEV.fw_entry_list_validation_main(g_dynamic_var):
            print("ERROR: Error validating XML file.")
            return False
        elif print_logs >= 2:
            print("XML file validated with XFEV.fw_entry_list_validation_main")

        #
        # Create metadata
        #
        if not generate_sys_fw_meta_data_file(
            fw_ver_binary_data, s_breaking_change_number, g_dynamic_var
        ):
            print("ERROR: Failure creating metadata file. Aborting...\n")
            return False
        elif print_logs >= 2:
            print("metadata file created with generate_sys_fw_meta_data_file")

        #
        # Generate FFS file of each input binary
        #
        if not generate_sys_fw_ffs_list(ls_ffs, ls_paths, g_dynamic_var):
            print("ERROR: Error Generating FFS files.")
            return False
        elif print_logs >= 2:
            print("generated ffs file with generate_sys_fw_ffs_list")

    except Exception:
        print(traceback.format_exc())

    return True


def generate_sys_fw_ffs_list(ls_ffs, ls_paths, g_dynamic_var):

    try:
        for raw_fwentry in g_dynamic_var.XmlRawFwEntryList:
            if (
                raw_fwentry.Operation.lower()
                == g_dynamic_var.dOperationTypeByValue[
                    FVC_h.FWENTRY_OPERATION_TYPE.IGNORE
                ].lower()
            ):
                continue

            s_file_name = raw_fwentry.InputBinary[: raw_fwentry.InputBinary.rfind(".")]
            s_dir_path = get_dir_path(raw_fwentry, ls_paths)

            if s_dir_path is None:
                print(
                    f"ERROR: File {raw_fwentry.InputBinary} cannot be found in any of the search paths.\n"
                )
                return False

            #
            # Handle FFS file naming to avoid overwriting
            #
            if s_file_name + ".ffs" in ls_ffs:
                temp_str = (
                    raw_fwentry.UpdatePath.PartitionName.lower()
                    .replace(s_file_name.lower(), "")
                    .strip("_")
                )
                s_file_name = f"{s_file_name}_{temp_str}"

            print(f"INFO: Creating ffs file for {raw_fwentry.InputBinary}.")

            raw_fwentry_FileGuid_uuid_str = str(
                uuid.UUID(bytes=bytes(raw_fwentry.FileGuid))
            )
            fv_builder.write_raw_ffs(
                s_file_name + ".ffs",
                raw_fwentry_FileGuid_uuid_str,
                os.path.join(s_dir_path, raw_fwentry.InputBinary),
            )

            ls_ffs.append(s_file_name + ".ffs")

        s_file_name = SYS_FW_METADATA_FILE[: SYS_FW_METADATA_FILE.rfind(".")]
        s_guid = FVC_h.GlobalStaticVariable.FILE_GUID_METADATA_GUID.strip("{}")

        print(f"INFO: Creating ffs file for {SYS_FW_METADATA_FILE}.")
        fv_builder.write_raw_ffs(s_file_name + ".ffs", s_guid, SYS_FW_METADATA_FILE)

        ls_ffs.append(s_file_name + ".ffs")

        #
        # Check if all ffs files are present and can be located
        #
        for s_file in ls_ffs:
            if not os.path.exists(s_file):
                print(f"ERROR: Failure locating {s_file} file to create FV.")
                return False

    except Exception:
        print(traceback.format_exc())

    return True


def generate_ffs_for_ec_fw(ls_ffs, s_ec_fw_file_name):
    s_file_name = "EC_FW"
    s_guid = FVC_h.GlobalStaticVariable.EC_FW_FFS_FILE_GUID.strip("{}")

    try:
        print(f"INFO: Creating FFS file for {s_ec_fw_file_name}.")

        fv_builder.write_raw_ffs(s_file_name + ".ffs", s_guid, s_ec_fw_file_name)

        ls_ffs.append(s_file_name + ".ffs")

        #
        # Check if all ffs files are present and can be located
        #
        for s_file in ls_ffs:
            if not os.path.exists(s_file):
                print(f"ERROR: Failure locating {s_file} file to create FV.")
                return False

    except Exception:
        print(traceback.format_exc())

    return True


def process_ec_fw_ffs_creation(s_ec_fw_file_name, ls_ffs):
    try:
        if not generate_ffs_for_ec_fw(ls_ffs, s_ec_fw_file_name):
            print("Generating FFS file for EC FW failed.\n")
            return False
    except Exception:
        print(traceback.format_exc())

    return True


def print_help():
    print("<======== FvCreator.py Usage ======>\n")
    print(
        "[For System Firmware FV Creation]        FVCreator.py <output FV file> -FvType SYS_FW <input xml file with binary & guid combinations> <SysFwVersionBinaryFile> <Binary Search Path 1> <Binary Search Path 2> ...\n"
    )
    print(
        "[For EC Device Firmware FV Creation]    FVCreator.py <output FV file> -FvType EC_FW <EC Firmware Binary path>"
    )
    return


class Arguments:
    MINIMUM_ARGUMENT_COUNT = 4
    MAXIMUM_ARGUMENT_COUNT = 6

    def __init__(self):
        self.parameters = {}

    def ConstructConfData(self, args):

        self.parameters.clear()
        splitter = re.compile(r"^-{1,2}|^/", re.IGNORECASE)
        remover = re.compile(r"^['\"]?(.*?)['\"]?$", re.IGNORECASE)
        parameter = None

        for txt in args:
            parts = splitter.split(txt, maxsplit=2)

            if len(parts) == 1:
                if parameter is not None:
                    if parameter not in self.parameters:
                        parts[0] = remover.sub(r"\1", parts[0])
                        self.parameters[parameter] = parts[0]
                    parameter = None

            elif len(parts) == 2:
                if parameter is not None:
                    if parameter not in self.parameters:
                        self.parameters[parameter] = "true"
                parameter = parts[1]

        if parameter is not None:
            if parameter not in self.parameters:
                self.parameters[parameter] = "true"

    def __getitem__(self, Param):
        return self.parameters.get(Param)


def The_Main(args):

    s_breaking_change_number = "0"
    ls_ffs = []
    ls_paths = []
    g_dynamic_var = FVC_h.GlobalDynamicVariable()
    fw_ver_binary_data = FVC_h.QSYS_FW_VERSION_DATA()

    # FFS/FV generation is native Python now; strip the obsolete flag so
    # old invocations do not misparse it as a binary search path.
    args = list(args)
    for i, arg in enumerate(args):
        if arg in ("--edk2-path", "-edk2path") and i + 1 < len(args):
            print("WARNING: --edk2-path is deprecated and ignored.")
            del args[i : i + 2]
            break

    # Extract --glymur if provided; enables Glymur BinaryType/ARValidation XML support
    for i, arg in enumerate(args):
        if arg == "--glymur":
            g_dynamic_var.isGlymurMode = True
            del args[i]
            break

    # fv_type = FV_TYPE.UNKNOWN

    # Skipping the re-creation of all executables
    if len(args) == 1 and args[0].lower() == "-v":
        print("Version: %s" % (TOOL_VERSION_STRING))
        return

    s_output_file_name = args[0]

    if args[1].lower() == "-FvType".lower():
        if args[2].lower() != "SYS_FW".lower() and args[2].lower() != "EC_FW".lower():
            print(
                "Invalid FvType detected, expecting 'SYS_FW' or 'EC_FW' got %s"
                % (args[2])
            )
        else:
            fv_type = args[2].lower()
    else:
        print("Invalid arguments")
        print_help()

    if fv_type.lower() == "SYS_FW".lower():
        s_xml_file_name = args[3]
        s_fw_ver_binary_file = args[4]

        for i in range(5, len(args)):
            temp_search_path = args[i].strip().strip('"')

            # To fix root directory entry. For example: If user passed just "C:" normalize to "C:\"
            if (
                len(temp_search_path) == 2
                and temp_search_path[1] == ":"
                and temp_search_path[0].isalpha()
            ):
                temp_search_path += "\\"

            ls_paths.append(temp_search_path)

        r = process_sys_fw_ffs_creation(
            s_xml_file_name=s_xml_file_name,
            s_fw_ver_binary_file=s_fw_ver_binary_file,
            s_breaking_change_number=s_breaking_change_number,
            fw_ver_binary_data=fw_ver_binary_data,
            ls_ffs=ls_ffs,
            ls_paths=ls_paths,
            g_dynamic_var=g_dynamic_var,
        )
        if not r:
            print("process_sys_fw_ffs_creation failed")

    elif fv_type.lower() == "EC_FW".lower():
        s_ec_fw_file_name = args[3]

        r = process_ec_fw_ffs_creation(
            s_ec_fw_file_name=s_ec_fw_file_name,
            ls_ffs=ls_ffs,
        )
        if not r:
            print("process_ec_fw_ffs_creation failed")

    if not generate_fv(s_output_file_name, ls_ffs):
        print("GenerateFV failed.\n")
        return
    else:
        print("FV created successfully")

    # Remove only the intermediates this run created, never other
    # files that happen to share an extension with them.
    remove_files(ls_ffs + [SYS_FW_METADATA_FILE])


def main():
    The_Main(args=sys.argv[1:])


if __name__ == "__main__":
    main()
