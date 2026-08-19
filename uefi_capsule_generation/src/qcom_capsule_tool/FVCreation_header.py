# --------------------------------------------------------------------
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------


import ctypes
import uuid
from collections import deque
from enum import IntEnum


class FWENTRY_OPERATION_TYPE(IntEnum):
    IGNORE = 0x00000000
    UPDATE = 0x00000001
    MAX = 0x00000002


class FWENTRY_OPERATION_PATH_TYPE(IntEnum):
    SOURCE = 0x00000000
    DEST = 0x00000001
    BACKUP = 0x00000002
    MAX = 0x00000003


class FWENTRY_UPDATE_TYPE(IntEnum):
    PARTITION = 0x00000000
    FAT_FILE = 0x00000001
    DPP_QCOM = 0x00000002
    DPP_OEM = 0x00000003
    OPM_PRIV_KEY = 0x00000004
    FWCLASS_GUID = 0x00000005
    MAX = 0x00000006


class FWENTRY_BACKUP_TYPE(IntEnum):
    PARTITION = 0x00000000
    FAT_FILE = 0x00000001
    MAX = 0x00000002


class FWENTRY_DISK_TYPE(IntEnum):
    USER_DATA = 0x00000000
    BOOT1 = 0x00000001
    BOOT2 = 0x00000002
    RPMB = 0x00000003
    GPP1 = 0x00000004
    GPP2 = 0x00000005
    GPP3 = 0x00000006
    GPP4 = 0x00000007
    LUN0 = 0x00000008
    LUN1 = 0x00000009
    LUN2 = 0x0000000A
    LUN3 = 0x0000000B
    LUN4 = 0x0000000C
    LUN5 = 0x0000000D
    LUN6 = 0x0000000E
    LUN7 = 0x0000000F
    SPINOR = 0x00000010
    NVME = 0x00000011
    MAX = 0x00000012


class FlashType(IntEnum):
    EMMC = 0x00000000
    UFS = 0x00000001
    NORNVME = 0x00000002
    NORUFS = 0x00000003


class FWENTRY_BINARY_TYPE(IntEnum):
    RAW = 0x00000000  # For FwEntries which is RAW binary like XBL_SC
    FATFS = 0x00000001  # For FwEntries which is Fat File System binary like PLAT
    MAX = 0x00000003


class GlobalStaticVariable:
    PARTITION_NAME_MAX_SIZE = 36
    FILE_NAME_MAX_SIZE = 255
    DPP_NAME_MAX_SIZE = 255
    MATCH_IDENTIFIER_NAME_MAX_SIZE = 36
    AR_VALIDATION_TYPE_MAX_SIZE = 36
    MAX_IMAGE_COUNT = 2

    FILE_GUID_SBL1 = "{0A85A45E-915F-49DB-8BD5-5337861F8082}"
    FILE_GUID_SBL2 = "{E7BF4F3F-7DC9-40C0-9DF2-CE2EC5CEACEF}"
    FILE_GUID_SBL3 = "{8BA7FEBE-AB44-411D-86E7-A6F2DE7E3F40}"
    FILE_GUID_RPM = "{8A8BD280-F35E-48E1-A891-BF0BB855831E}"
    FILE_GUID_TZ = "{497FBC93-5784-4B8C-8F01-2AF50FB19239}"
    FILE_GUID_WINSECAPP = "{F7A7DF2A-A845-4C17-94B8-85FD9CD022D7}"
    FILE_GUID_UEFI = "{31C5C241-D6CE-4E7A-B400-9C35571B2EA9}"
    FILE_GUID_CSRT_ACPI = "{642F3381-0327-4E0D-A7C1-A2C7D2C45812}"
    FILE_GUID_DSDT_AML = "{044AF707-CDE8-4D15-B811-594BDABEB1FD}"
    FILE_GUID_FACP_ACPI = "{24FC010F-AA0F-4310-AC48-E259FBD07AB0}"
    FILE_GUID_FACS_ACPI = "{E455D6FD-16A5-45D2-8E07-1F5C992ABE28}"
    FILE_GUID_MADT_ACPI = "{CA6BECA3-CD6D-44F4-AFB2-65076B81AD54}"
    FILE_GUID_TPM2_ACPI = "{D298A7FE-C5CC-4C54-9CBC-9A59FA47F3AB}"
    FILE_GUID_BGRT_ACPI = "{8E230A44-9617-40BC-B18D-256795E55526}"
    FILE_GUID_DBG2_ACPI = "{D8E02C2D-9310-47E6-8B92-C7A3564C488A}"
    FILE_GUID_FPDT_ACPI = "{F760AEEB-B172-4522-AFB2-ECCDC523B598}"
    FILE_GUID_logo1_ACPI = "{8AA7DEF2-4B2E-470C-BAE2-057CACA327DB}"
    FILE_GUID_METADATA_GUID = "{C7340E65-0D5D-43D6-ABB7-39751D5EC8E7}"
    FILE_GUID_OPM_PRIV_PROVISION = "{3998E865-A733-4812-97D7-4BC973EA3442}"
    FILE_GUID_OPM_PUB_PROVISION = "{01620DA3-F273-4401-9821-1D0E5169D8DA}"

    PARTITION_TYPE_GUID_BOOT1_SBL1 = "{DEA0BA2C-CBDD-4805-B4F9-F428251C3E98}"
    PARTITION_TYPE_GUID_BOOT1_SBL1_BAK = "{B2CCEF8E-81BD-4E27-A228-5F0DE08CA12C}"
    PARTITION_TYPE_GUID_GPP_SBL2 = "{8C6B52AD-8A9E-4398-AD09-AE916E53AE2D}"
    PARTITION_TYPE_GUID_GPP_SBL2_BAK = "{62E53DFC-81D1-47F3-8867-22BC5592605F}"
    PARTITION_TYPE_GUID_GPP_SBL3 = "{05E044DF-92F1-4325-B69E-374A82E97D6E}"
    PARTITION_TYPE_GUID_GPP_SBL3_BAK = "{7EBF5EA5-4218-44A5-8D57-BF1C749FE7F1}"
    PARTITION_TYPE_GUID_GPP_UEFI = "{400FFDCD-22E0-47E7-9A23-F16ED9382388}"
    PARTITION_TYPE_GUID_GPP_UEFI_BAK = "{E1D14C55-ED7E-464E-A340-E045E6D3108A}"
    PARTITION_TYPE_GUID_GPP_RPM = "{098DF793-D712-413D-9D4E-89D711772228}"
    PARTITION_TYPE_GUID_GPP_RPM_BAK = "{BF132EB0-FC69-4D84-A13C-52F333E63906}"
    PARTITION_TYPE_GUID_GPP_TZ = "{A053AA7F-40B8-4B1C-BA08-2F68AC71A4F4}"
    PARTITION_TYPE_GUID_GPP_TZ_BAK = "{FD78FB93-1037-4AAA-BC9C-37E716D27BEE}"
    PARTITION_TYPE_GUID_GPP_WINSECAPP = "{69B4201F-A5AD-45EB-9F49-45B38CCDAEF5}"
    PARTITION_TYPE_GUID_GPP_WINSECAPP_BAK = "{B8DB2AFE-A8D9-45B3-8661-C29F592B6E76}"
    PARTITION_TYPE_GUID_GPP_SSD = "{2C86E742-745E-4FDD-BFD8-B6A7AC638772}"
    PARTITION_TYPE_GUID_GPP_DPP = "{9992FD7D-EC66-4CBC-A337-0DA1D4C93F8F}"
    PARTITION_TYPE_GUID_GPP_FAT16 = "{543C031A-4CB6-4897-BFFE-4B485768A8AD}"
    PARTITION_TYPE_GUID_USER_ESP = "{C12A7328-F81F-11D2-BA4B-00A0C93EC93B}"

    PARTITION_NAME_SYSFW_VERSION = "SYSFW_VERSION"

    EC_FW_FFS_FILE_GUID = "{4DC8BBB0-D3F6-4407-B46B-4B729F606DC0}"


class FWENTRY_DEVICE_PATH(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("DiskType", ctypes.c_uint32),
        (
            "PartitionName",
            ctypes.c_byte * (2 * GlobalStaticVariable.PARTITION_NAME_MAX_SIZE),
        ),
        ("PartitionTypeGUID", ctypes.c_byte * 16),
        ("FileName", ctypes.c_byte * (2 * GlobalStaticVariable.FILE_NAME_MAX_SIZE)),
    ]

    def __init__(self, pType=0):
        self.DiskType = pType
        self.PartitionName = (
            ctypes.c_byte * (2 * GlobalStaticVariable.PARTITION_NAME_MAX_SIZE)
        )()
        self.PartitionTypeGUID = (ctypes.c_byte * 16).from_buffer_copy(
            uuid.UUID(int=0).bytes
        )
        self.FileName = (
            ctypes.c_byte * (2 * GlobalStaticVariable.FILE_NAME_MAX_SIZE)
        )()

    def copy_from(self, devPath):
        self.DiskType = devPath.DiskType
        ctypes.memmove(
            self.PartitionName, devPath.PartitionName, ctypes.sizeof(self.PartitionName)
        )
        self.PartitionTypeGUID = (ctypes.c_byte * 16).from_buffer_copy(
            devPath.PartitionTypeGUID
        )
        ctypes.memmove(self.FileName, devPath.FileName, ctypes.sizeof(self.FileName))

    def equals(self, devPath):
        base_partition_name = "".join(self.PartitionName)
        base_file_name = "".join(self.FileName)
        target_partition_name = "".join(devPath.PartitionName)
        target_file_name = "".join(devPath.FileName)
        return (
            self.DiskType == devPath.DiskType
            and base_partition_name == target_partition_name
            and self.PartitionTypeGUID[:] == devPath.PartitionTypeGUID[:]
            and base_file_name == target_file_name
        )

    def to_bytes(self):
        return bytes(self)


class XML_RAW_FWENTRY_DEVICE_PATH(ctypes.Structure):
    _fields_ = [
        ("DiskType", ctypes.c_wchar_p),
        ("PartitionName", ctypes.c_wchar_p),
        ("PartitionTypeGUID", ctypes.c_wchar_p),
        ("FileName", ctypes.c_wchar_p),
    ]


class FWENTRY_IMAGE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("FileName", ctypes.c_byte * (2 * GlobalStaticVariable.FILE_NAME_MAX_SIZE)),
        (
            "ARValidationType",
            ctypes.c_byte * (2 * GlobalStaticVariable.AR_VALIDATION_TYPE_MAX_SIZE),
        ),
    ]

    def to_bytes(self):
        return bytes(self)


class FWENTRY_ARVALIDATION(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("Images", FWENTRY_IMAGE * GlobalStaticVariable.MAX_IMAGE_COUNT),
        ("ImageCount", ctypes.c_int32),
    ]

    def to_bytes(self):
        return bytes(self)


class XML_RAW_FWENTRY_IMAGE:
    def __init__(self, file_name=None, ar_validation_type=None):
        self.FileName = file_name
        self.ARValidationType = ar_validation_type


class XML_RAW_FWENTRY_ARVALIDATION:
    def __init__(self, images=None):
        self.Images = images  # list of XML_RAW_FWENTRY_IMAGE


class QPAYLOAD_METADATA_FWENTRY(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("FileGuid", ctypes.c_byte * 16),
        ("Operation", ctypes.c_uint32),
        ("UpdateType", ctypes.c_uint32),
        ("BackupType", ctypes.c_uint32),
        ("UpdatePath", FWENTRY_DEVICE_PATH),
        ("BackupPath", FWENTRY_DEVICE_PATH),
        ("Revision", ctypes.c_uint32),
        (
            "MatchIdentifier",
            ctypes.c_char * (2 * GlobalStaticVariable.MATCH_IDENTIFIER_NAME_MAX_SIZE),
        ),
        ("BinaryType", ctypes.c_uint32),
        ("ARValidation", FWENTRY_ARVALIDATION),
    ]

    def to_bytes(self):
        return bytes(self)


class QPAYLOAD_METADATA_FWENTRY_GLYMUR(ctypes.Structure):
    """Glymur (payload header V5) on-disk layout. Real Glymur/Mavros/Honu/
    Kaanapali firmware places Revision as the FIRST field of FWENTRY_METADATA,
    unlike the legacy layout above where Revision sits after BackupPath.
    Field set/sizes are otherwise identical to QPAYLOAD_METADATA_FWENTRY."""

    _pack_ = 1
    _fields_ = [
        ("Revision", ctypes.c_uint32),
        ("FileGuid", ctypes.c_byte * 16),
        ("Operation", ctypes.c_uint32),
        ("UpdateType", ctypes.c_uint32),
        ("BackupType", ctypes.c_uint32),
        ("UpdatePath", FWENTRY_DEVICE_PATH),
        ("BackupPath", FWENTRY_DEVICE_PATH),
        (
            "MatchIdentifier",
            ctypes.c_char * (2 * GlobalStaticVariable.MATCH_IDENTIFIER_NAME_MAX_SIZE),
        ),
        ("BinaryType", ctypes.c_uint32),
        ("ARValidation", FWENTRY_ARVALIDATION),
    ]

    def to_bytes(self):
        return bytes(self)

    @classmethod
    def from_legacy(cls, fw_entry):
        """Build a Glymur-ordered entry from a populated QPAYLOAD_METADATA_FWENTRY."""
        glymur_entry = cls()
        glymur_entry.Revision = fw_entry.Revision
        glymur_entry.FileGuid = fw_entry.FileGuid
        glymur_entry.Operation = fw_entry.Operation
        glymur_entry.UpdateType = fw_entry.UpdateType
        glymur_entry.BackupType = fw_entry.BackupType
        glymur_entry.UpdatePath.copy_from(fw_entry.UpdatePath)
        glymur_entry.BackupPath.copy_from(fw_entry.BackupPath)
        glymur_entry.MatchIdentifier = fw_entry.MatchIdentifier
        glymur_entry.BinaryType = fw_entry.BinaryType
        ctypes.memmove(
            ctypes.byref(glymur_entry.ARValidation),
            ctypes.byref(fw_entry.ARValidation),
            ctypes.sizeof(FWENTRY_ARVALIDATION),
        )
        return glymur_entry


class XML_RAW_FWENTRY(ctypes.Structure):
    _fields_ = [
        ("FileGuid", ctypes.c_byte * 16),
        ("InputBinary", ctypes.c_wchar_p),
        ("InputPath", ctypes.c_wchar_p),
        ("Operation", ctypes.c_wchar_p),
        ("UpdateType", ctypes.c_wchar_p),
        ("BackupType", ctypes.c_wchar_p),
        ("UpdatePath", XML_RAW_FWENTRY_DEVICE_PATH),
        ("BackupPath", XML_RAW_FWENTRY_DEVICE_PATH),
        ("MatchIdentifier", ctypes.c_wchar_p),
    ]

    # BinaryType/ARValidation are not part of the marshaled XML_RAW_FWENTRY
    # layout (they are only ever mapped into QPAYLOAD_METADATA_FWENTRY's
    # ctypes-typed fields), so they are kept as plain, un-marshaled defaults.
    BinaryType = None
    ARValidation = None


class QPAYLOAD_METADATA_HEADER(ctypes.Structure):
    _fields_ = [
        ("Signature1", ctypes.c_uint32),
        ("Signature2", ctypes.c_uint32),
        ("Revision", ctypes.c_uint32),
        ("Size", ctypes.c_uint32),
        ("FirmwareVersion", ctypes.c_uint32),
        ("LowestSupportedVersion", ctypes.c_uint32),
        ("BreakingChangeNumber", ctypes.c_uint32),
        ("Reserved1", ctypes.c_uint32),
        ("Reserved2", ctypes.c_uint32),
        ("EntryCount", ctypes.c_uint32),
    ]

    def to_bytes(self):
        return bytes(self)


class QSYS_FW_VERSION_DATA(ctypes.Structure):
    _fields_ = [
        ("Signature", ctypes.c_uint64),
        ("Revision", ctypes.c_uint32),
        ("VersionDataSize", ctypes.c_uint32),
        ("VersionDataCrc32", ctypes.c_uint32),
        ("FwVersion", ctypes.c_uint32),
        ("LowestSupportedFwVersion", ctypes.c_uint32),
    ]

    def to_bytes(self):
        return bytes(self)


class FV_TYPE(IntEnum):
    UNKNOWN = 0
    SYS_FW = 1
    EC_FW = 2


class GlobalDynamicVariable:
    dFileGuidByDestFatFilePath = {
        "\\ACPI\\CSRT.ACP": GlobalStaticVariable.FILE_GUID_CSRT_ACPI,
        "\\ACPI\\TPM2.ACP": GlobalStaticVariable.FILE_GUID_TPM2_ACPI,
        "\\ACPI\\BGRT.ACP": GlobalStaticVariable.FILE_GUID_BGRT_ACPI,
        "\\LOGO1.BMP": GlobalStaticVariable.FILE_GUID_logo1_ACPI,
        "\\ACPI\\DBG2.ACP": GlobalStaticVariable.FILE_GUID_DBG2_ACPI,
        "\\ACPI\\DBGP.ACP": GlobalStaticVariable.FILE_GUID_DBG2_ACPI,
        "\\ACPI\\DSDT.AML": GlobalStaticVariable.FILE_GUID_DSDT_AML,
        "\\ACPI\\FACP.ACP": GlobalStaticVariable.FILE_GUID_FACP_ACPI,
        "\\ACPI\\FACS.ACP": GlobalStaticVariable.FILE_GUID_FACS_ACPI,
        "\\ACPI\\FPDT.ACP": GlobalStaticVariable.FILE_GUID_FPDT_ACPI,
        "\\ACPI\\MADT.ACP": GlobalStaticVariable.FILE_GUID_MADT_ACPI,
    }

    dFileGuidByDestDppItemFile = {
        "OPM_PUB.PROVISION": GlobalStaticVariable.FILE_GUID_OPM_PUB_PROVISION,
        "OPM_PRIV.PROVISION": GlobalStaticVariable.FILE_GUID_OPM_PRIV_PROVISION,
    }

    dDiskTypeByString = {
        "EMMC_PARTITION_USER_DATA": FWENTRY_DISK_TYPE.USER_DATA,
        "EMMC_PARTITION_BOOT1": FWENTRY_DISK_TYPE.BOOT1,
        "EMMC_PARTITION_BOOT2": FWENTRY_DISK_TYPE.BOOT2,
        "EMMC_PARTITION_RPMB": FWENTRY_DISK_TYPE.RPMB,
        "EMMC_PARTITION_GPP1": FWENTRY_DISK_TYPE.GPP1,
        "EMMC_PARTITION_GPP2": FWENTRY_DISK_TYPE.GPP2,
        "EMMC_PARTITION_GPP3": FWENTRY_DISK_TYPE.GPP3,
        "EMMC_PARTITION_GPP4": FWENTRY_DISK_TYPE.GPP4,
        "UFS_LUN0": FWENTRY_DISK_TYPE.LUN0,
        "UFS_LUN1": FWENTRY_DISK_TYPE.LUN1,
        "UFS_LUN2": FWENTRY_DISK_TYPE.LUN2,
        "UFS_LUN3": FWENTRY_DISK_TYPE.LUN3,
        "UFS_LUN4": FWENTRY_DISK_TYPE.LUN4,
        "UFS_LUN5": FWENTRY_DISK_TYPE.LUN5,
        "UFS_LUN6": FWENTRY_DISK_TYPE.LUN6,
        "UFS_LUN7": FWENTRY_DISK_TYPE.LUN7,
        "SPINOR": FWENTRY_DISK_TYPE.SPINOR,
        "NVME": FWENTRY_DISK_TYPE.NVME,
    }

    dDiskTypeByValue = {
        FWENTRY_DISK_TYPE.USER_DATA: "EMMC_PARTITION_USER_DATA",
        FWENTRY_DISK_TYPE.BOOT1: "EMMC_PARTITION_BOOT1",
        FWENTRY_DISK_TYPE.BOOT2: "EMMC_PARTITION_BOOT2",
        FWENTRY_DISK_TYPE.RPMB: "EMMC_PARTITION_RPMB",
        FWENTRY_DISK_TYPE.GPP1: "EMMC_PARTITION_GPP1",
        FWENTRY_DISK_TYPE.GPP2: "EMMC_PARTITION_GPP2",
        FWENTRY_DISK_TYPE.GPP3: "EMMC_PARTITION_GPP3",
        FWENTRY_DISK_TYPE.GPP4: "EMMC_PARTITION_GPP4",
        FWENTRY_DISK_TYPE.LUN0: "UFS_LUN0",
        FWENTRY_DISK_TYPE.LUN1: "UFS_LUN1",
        FWENTRY_DISK_TYPE.LUN2: "UFS_LUN2",
        FWENTRY_DISK_TYPE.LUN3: "UFS_LUN3",
        FWENTRY_DISK_TYPE.LUN4: "UFS_LUN4",
        FWENTRY_DISK_TYPE.LUN5: "UFS_LUN5",
        FWENTRY_DISK_TYPE.LUN6: "UFS_LUN6",
        FWENTRY_DISK_TYPE.LUN7: "UFS_LUN7",
        FWENTRY_DISK_TYPE.SPINOR: "SPINOR",
        FWENTRY_DISK_TYPE.NVME: "NVME",
    }

    dFlashTypeByString = {
        "EMMC": FlashType.EMMC,
        "UFS": FlashType.UFS,
        "NORNVME": FlashType.NORNVME,
        "NORUFS": FlashType.NORUFS,
    }

    dFlashTypeByValue = {
        FlashType.EMMC: "EMMC",
        FlashType.UFS: "UFS",
        FlashType.NORNVME: "NORNVME",
        FlashType.NORUFS: "NORUFS",
    }

    dFlashTypeByDiskType = {
        FWENTRY_DISK_TYPE.USER_DATA: [FlashType.EMMC],
        FWENTRY_DISK_TYPE.BOOT1: [FlashType.EMMC],
        FWENTRY_DISK_TYPE.BOOT2: [FlashType.EMMC],
        FWENTRY_DISK_TYPE.RPMB: [FlashType.EMMC],
        FWENTRY_DISK_TYPE.GPP1: [FlashType.EMMC],
        FWENTRY_DISK_TYPE.GPP2: [FlashType.EMMC],
        FWENTRY_DISK_TYPE.GPP3: [FlashType.EMMC],
        FWENTRY_DISK_TYPE.GPP4: [FlashType.EMMC],
        FWENTRY_DISK_TYPE.LUN0: [FlashType.UFS, FlashType.NORUFS],
        FWENTRY_DISK_TYPE.LUN1: [FlashType.UFS],
        FWENTRY_DISK_TYPE.LUN2: [FlashType.UFS],
        FWENTRY_DISK_TYPE.LUN3: [FlashType.UFS],
        FWENTRY_DISK_TYPE.LUN4: [FlashType.UFS],
        FWENTRY_DISK_TYPE.LUN5: [FlashType.UFS],
        FWENTRY_DISK_TYPE.LUN6: [FlashType.UFS],
        FWENTRY_DISK_TYPE.LUN7: [FlashType.UFS],
        FWENTRY_DISK_TYPE.SPINOR: [FlashType.NORNVME, FlashType.NORUFS],
        FWENTRY_DISK_TYPE.NVME: [FlashType.NORNVME],
    }

    dOperationTypeByString = {
        "IGNORE": FWENTRY_OPERATION_TYPE.IGNORE,
        "UPDATE": FWENTRY_OPERATION_TYPE.UPDATE,
    }

    dOperationTypeByValue = {
        FWENTRY_OPERATION_TYPE.IGNORE: "IGNORE",
        FWENTRY_OPERATION_TYPE.UPDATE: "UPDATE",
    }

    dOperationPathTypeByString = {
        "SOURCE": FWENTRY_OPERATION_PATH_TYPE.SOURCE,
        "DEST": FWENTRY_OPERATION_PATH_TYPE.DEST,
        "BACKUP": FWENTRY_OPERATION_PATH_TYPE.BACKUP,
    }

    dOperationPathTypeByValue = {
        FWENTRY_OPERATION_PATH_TYPE.SOURCE: "SOURCE",
        FWENTRY_OPERATION_PATH_TYPE.DEST: "DEST",
        FWENTRY_OPERATION_PATH_TYPE.BACKUP: "BACKUP",
    }

    dUpdateTypeByString = {
        "UPDATE_PARTITION": FWENTRY_UPDATE_TYPE.PARTITION,
        "UPDATE_FAT_FILE": FWENTRY_UPDATE_TYPE.FAT_FILE,
        "UPDATE_DPP_QCOM": FWENTRY_UPDATE_TYPE.DPP_QCOM,
        "UPDATE_DPP_OEM": FWENTRY_UPDATE_TYPE.DPP_OEM,
        "UPDATE_OPM_PRIV_KEY": FWENTRY_UPDATE_TYPE.OPM_PRIV_KEY,
        "UPDATE_FWCLASS_GUID": FWENTRY_UPDATE_TYPE.FWCLASS_GUID,
    }

    dUpdateTypeByValue = {
        FWENTRY_UPDATE_TYPE.PARTITION: "UPDATE_PARTITION",
        FWENTRY_UPDATE_TYPE.FAT_FILE: "UPDATE_FAT_FILE",
        FWENTRY_UPDATE_TYPE.DPP_QCOM: "UPDATE_DPP_QCOM",
        FWENTRY_UPDATE_TYPE.DPP_OEM: "UPDATE_DPP_OEM",
        FWENTRY_UPDATE_TYPE.OPM_PRIV_KEY: "UPDATE_OPM_PRIV_KEY",
        FWENTRY_UPDATE_TYPE.FWCLASS_GUID: "UPDATE_FWCLASS_GUID",
    }

    dBackupTypeByString = {
        "BACKUP_PARTITION": FWENTRY_BACKUP_TYPE.PARTITION,
        "BACKUP_FAT_FILE": FWENTRY_BACKUP_TYPE.FAT_FILE,
    }

    dBackupTypeByValue = {
        FWENTRY_BACKUP_TYPE.PARTITION: "BACKUP_PARTITION",
        FWENTRY_BACKUP_TYPE.FAT_FILE: "BACKUP_FAT_FILE",
    }

    dBinaryTypeByString = {
        "RAW": FWENTRY_BINARY_TYPE.RAW,
        "FATFS": FWENTRY_BINARY_TYPE.FATFS,
    }

    dBinaryTypeByValue = {
        FWENTRY_BINARY_TYPE.RAW: "RAW",
        FWENTRY_BINARY_TYPE.FATFS: "FATFS",
    }

    XmlRawFwEntryList: deque = deque()
    QpayloadFwEntryList: deque = deque()
    DeviceFlashType = None
    isMatchIdentifierInXML = False
    isBinaryTypeInXML = False
    isGlymurMode = False
