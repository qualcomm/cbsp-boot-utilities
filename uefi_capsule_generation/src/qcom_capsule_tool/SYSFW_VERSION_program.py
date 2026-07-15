# --------------------------------------------------------------------
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------


import ctypes
import os
import re
import sys
import traceback

print_logs = 1
sVersion = "1.0"
S_SIGNATURE = "SYSFWVER"
S_REVISION = "1.0"
QSYS_FW_VERSION_DATA_VERSIONDATACRC32 = 0


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

            if print_logs >= 3:
                print("\n\n")
                print(
                    "from_bytes :: in version_data.VersionDataCrc32:",
                    version_data.VersionDataCrc32,
                )
                print(
                    "from_bytes :: in version_data.Signature:", version_data.Signature
                )
                print("from_bytes :: in version_data.Revision:", version_data.Revision)
                print(
                    "from_bytes :: in version_data.FwVersion:", version_data.FwVersion
                )
                print(
                    "from_bytes :: in version_data.LowestSupported:",
                    version_data.LowestSupportedFwVersion,
                )
                print(
                    "from_bytes :: in version_data.VersionDataSize:",
                    version_data.VersionDataSize,
                )

            return version_data

        except Exception:
            print(traceback.format_exc())
            return None

    @classmethod
    def get_values(cls, byte_arr):
        try:
            version_data = cls()
            new_data = {}
            ctypes.memmove(
                ctypes.addressof(version_data), byte_arr, ctypes.sizeof(version_data)
            )

            if print_logs >= 2:
                print("\n\n")
                print(
                    "get_values :: in version_data.VersionDataCrc32:",
                    version_data.VersionDataCrc32,
                )
                print(
                    "get_values :: in version_data.Signature:", version_data.Signature
                )
                print("get_values :: in version_data.Revision:", version_data.Revision)
                print(
                    "get_values :: in version_data.FwVersion:", version_data.FwVersion
                )
                print(
                    "get_values :: in version_data.LowestSupported:",
                    version_data.LowestSupportedFwVersion,
                )
                print(
                    "get_values :: in version_data.VersionDataSize:",
                    version_data.VersionDataSize,
                )

            s_revision = [None, None]
            s_revision[1] = str(version_data.Revision & 0x0000FFFF)
            s_revision[0] = str(version_data.Revision >> 16)
            new_data["Revision"] = s_revision[0] + "." + s_revision[1]

            if print_logs >= 2:
                print("\n\n")
                print("get_values :: new_data.Revision: ", new_data["Revision"])

            signature_bytes = version_data.Signature.to_bytes(8, byteorder="little")
            ascii_string = signature_bytes.decode("ascii")

            if print_logs >= 2:
                print("\n\n")
                print("get_values :: ascii_string: ", ascii_string)

            return version_data

        except Exception:
            print(traceback.format_exc())
            return None


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

        if print_logs >= 3:
            print("\n\n")
            print("Arguments.ConstructConfData :: parameters : ", self.parameters)

    def __getitem__(self, Param):
        return self.parameters.get(Param)


def Reflect(data_b, l_i):
    data_i = int(data_b)
    reff_i = 0

    for i in range(l_i):
        if (data_i & 0x1) != 0:
            reff_i = reff_i | int(1 << (int(l_i - 1) - i))

        data_i = data_i >> 1
    return reff_i


def CalcCRC32(buffer_b, l_i):
    k_i = 8
    MSB_i = 0
    gx_h = 0x04C11DB7
    regs_h = 0xFFFFFFFF
    regsMask_h = 0xFFFFFFFF
    regsMSB_i = 0

    for i in range(l_i):
        DataByte_b = buffer_b[i]
        DataByte_b = bytes(Reflect(DataByte_b, 8))

        for j in range(k_i):
            MSB = DataByte_b >> (k_i - 1)
            MSB = MSB & 1
            regsMSB_i = int(regs_h >> 31) & 1
            regs_h = regs_h << 1
            if (regsMSB_i ^ MSB_i) != 0:
                regs_h = regs_h ^ gx_h

            regs_h = regs_h & regsMask_h
            DataByte_b = DataByte_b << 1
    regs_h = regs_h & regsMask_h

    return Reflect(regs_h, 32)


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


def generate_binary_file(args):

    FwVerBinaryData = QSYS_FW_VERSION_DATA()
    FwVerBinaryData.VersionDataCrc32 = QSYS_FW_VERSION_DATA_VERSIONDATACRC32
    FwVerBinaryData.Signature = int.from_bytes(S_SIGNATURE.encode("ascii"), "little")
    sRevisionArr = S_REVISION.split(".")
    FwVerBinaryData.Revision = (int(sRevisionArr[0]) << 16) | int(sRevisionArr[1])

    if args["FwVer"]:
        if not re.match(r"^\d+\.\d+\.\d+\.\d+$", args["FwVer"]):
            print("ERROR: Value to the parameter -FwVer is not specified")
            return False
        sFirmwareVersionArr = args["FwVer"].split(".")
        FwVerBinaryData.FwVersion = (int(sFirmwareVersionArr[2]) << 16) | int(
            sFirmwareVersionArr[3]
        )
    else:
        print("ERROR: Value to the parameter -FwVer is not specified")
        return False

    if args["LFwVer"]:
        if not re.match(r"^\d+\.\d+\.\d+\.\d+$", args["LFwVer"]):
            print("ERROR: Value to the parameter -FwVer is not specified")
            return False
        sFirmwareLowVersionArr = args["LFwVer"].split(".")
        FwVerBinaryData.LowestSupportedFwVersion = (
            int(sFirmwareLowVersionArr[2]) << 16
        ) | int(sFirmwareLowVersionArr[3])
    else:
        print("ERROR: Value to the parameter -LFwVer is not specified")
        return False

    if args["O"]:
        OutputBinary = args["O"]
        FileName = os.path.basename(OutputBinary)
    else:
        print("ERROR: Value to the parameter -o is not specified")
        return False

    if os.path.exists(OutputBinary):
        os.remove(OutputBinary)

    FwVerBinaryData.VersionDataSize = len(FwVerBinaryData.to_bytes())
    FwVerBinaryData.VersionDataCrc32 = CalcCRC32_i(
        FwVerBinaryData.to_bytes(), FwVerBinaryData.VersionDataSize
    )
    output_file_path = os.path.join(os.getcwd(), FileName)

    with open(output_file_path, "wb") as fw_file:
        fw_file.write(FwVerBinaryData.to_bytes())

    return True


def get_fw_version_hex(args):

    if args["GetFwVersionHex"]:
        OutputBinary = args["GetFwVersionHex"]
        FileName = os.path.basename(OutputBinary)
    else:
        print("ERROR: Value to the parameter -GetFwVersionHex is not specified")
        return False

    FilePath = os.path.join(os.getcwd(), FileName)

    with open(FilePath, mode="rb") as file:
        file_content = file.read()

    FwVerBinaryData = QSYS_FW_VERSION_DATA.from_bytes(file_content)
    print(hex(FwVerBinaryData.FwVersion))


def get_ls_version_hex(args):

    if args["GetLSFwVersionHex"]:
        OutputBinary = args["GetLSFwVersionHex"]
        FileName = os.path.basename(OutputBinary)
    else:
        print("ERROR: Value to the parameter -GetLSFwVersionHex is not specified")
        return False

    FilePath = os.path.join(os.getcwd(), FileName)

    with open(FilePath, mode="rb") as file:
        file_content = file.read()

    FwVerBinaryData = QSYS_FW_VERSION_DATA.from_bytes(file_content)
    print(hex(FwVerBinaryData.LowestSupportedFwVersion))


def print_bin_contents(args):

    if args["PrintAll"]:
        OutputBinary = args["PrintAll"]
        FileName = os.path.basename(OutputBinary)
    else:
        print("ERROR: Value to the parameter -PrintAll is not specified")
        return False

    FilePath = os.path.join(os.getcwd(), FileName)

    with open(FilePath, mode="rb") as file:
        file_content = file.read()

    FwVerBinaryData = QSYS_FW_VERSION_DATA.from_bytes(file_content)

    if print_logs >= 0:
        print("\n")
        print("Contents of the provided .bin file: ")
        print("\tFwVerBinaryData.VersionDataCrc32:", FwVerBinaryData.VersionDataCrc32)
        print("\tFwVerBinaryData.Signature:", FwVerBinaryData.Signature)
        print("\tFwVerBinaryData.Revision:", FwVerBinaryData.Revision)
        print("\tFwVerBinaryData.FwVersion:", FwVerBinaryData.FwVersion)
        print(
            "\tFwVerBinaryData.LowestSupported:",
            FwVerBinaryData.LowestSupportedFwVersion,
        )
        print("\tFwVerBinaryData.VersionDataSize:", FwVerBinaryData.VersionDataSize)
        print("\n")

    FwVerBinaryData = QSYS_FW_VERSION_DATA.get_values(file_content)


def ViewBinaryFile(ConfigurationHelper):

    FwVerBinaryData = QSYS_FW_VERSION_DATA()
    FwVerBinaryData.VersionDataSize = len(FwVerBinaryData.to_bytes())
    InputBinPath = None

    if "Gen" in ConfigurationHelper:
        print("ViewBinaryFile :: ERROR: -Gen. -View are not allowed together")
        return False

    if "View" in ConfigurationHelper:
        if print_logs >= 2:
            print(
                "ViewBinaryFile :: ConfigurationHelper['View']: ",
                ConfigurationHelper["View"],
            )

        if ConfigurationHelper["O"] is not None:
            InputBinPath = ConfigurationHelper["O"]

        else:
            print(
                "ViewBinaryFile :: ERROR: Value to the parameter -View is not specified"
            )
            return False

    if not os.path.exists(os.path.join(os.getcwd(), InputBinPath)):
        print(
            "ViewBinaryFile :: ERROR: Provided input file does not exist in given directory"
        )
        return False

    with open(InputBinPath, mode="rb") as file:
        fs = file.read()

    FwVerBinaryData = QSYS_FW_VERSION_DATA.from_bytes(fs)

    s_revision = [None, None]
    s_revision[1] = str(FwVerBinaryData.Revision & 0x0000FFFF)
    s_revision[0] = str(FwVerBinaryData.Revision >> 16)
    FwVerBinaryData_revision = s_revision[0] + "." + s_revision[1]

    s_latest_version = [None, None]
    s_latest_version[1] = str(FwVerBinaryData.FwVersion & 0x0000FFFF)
    s_latest_version[0] = str(FwVerBinaryData.FwVersion >> 16)
    FwVerBinaryData_FwVersion = s_latest_version[0] + "." + s_latest_version[1]

    s_lowest_version = [None, None]
    s_lowest_version[1] = str(FwVerBinaryData.LowestSupportedFwVersion & 0x0000FFFF)
    s_lowest_version[0] = str(FwVerBinaryData.LowestSupportedFwVersion >> 16)
    FwVerBinaryData_LowestSupportedFwVersion = (
        s_lowest_version[0] + "." + s_lowest_version[1]
    )

    if print_logs >= 0:
        print("\n")
        print("Contents of the provided .bin file: ")
        print("\tVersionDataCrc32:", FwVerBinaryData.VersionDataCrc32)
        print("\tSignature:", FwVerBinaryData.Signature)
        print("\tRevision(int):", FwVerBinaryData.Revision)
        print("\tRevision:", FwVerBinaryData_revision)
        print("\tFwVersion(int):", FwVerBinaryData.FwVersion)
        print("\tFwVersion:", FwVerBinaryData_FwVersion)
        print("\tLowestSupported(int):", FwVerBinaryData.LowestSupportedFwVersion)
        print("\tLowestSupported:", FwVerBinaryData_LowestSupportedFwVersion)
        print("\tVersionDataSize:", FwVerBinaryData.VersionDataSize)
        print("\n")

    return True


def The_Main(args):

    ConfigurationHelper = Arguments()
    ConfigurationHelper.ConstructConfData(args)

    if print_logs >= 2:
        print("\n\n")
        print(
            "The_Main :: ConfigurationHelper.parameters: ",
            ConfigurationHelper.parameters,
        )

    if "Gen" in ConfigurationHelper.parameters:
        generate_binary_file(ConfigurationHelper.parameters)

    if "PrintAll" in ConfigurationHelper.parameters:
        print_bin_contents(ConfigurationHelper.parameters)

    if "View" in ConfigurationHelper.parameters:
        ViewBinaryFile(ConfigurationHelper.parameters)

    if "GetFwVersionHex" in ConfigurationHelper.parameters:
        get_fw_version_hex(ConfigurationHelper.parameters)

    if "GetLSFwVersionHex" in ConfigurationHelper.parameters:
        get_ls_version_hex(ConfigurationHelper.parameters)


def main():
    The_Main(args=sys.argv[1:])


if __name__ == "__main__":
    main()
