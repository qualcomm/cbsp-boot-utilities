# --------------------------------------------------------------------
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------


import ctypes
import uuid

from . import FVCreation as FVC
from . import FVCreation_header as FVC_h


def partition_fields_checking(raw_fwentry, raw_dev_path, meta_data_dev_path):
    if raw_fwentry.InputBinary is None:
        print("Empty <InputBinary> tag is not allowed for partition operation")
        return False
    if raw_dev_path.DiskType is None:
        print("Empty <DiskType> tag is not allowed for partition operation")
        return False
    if raw_dev_path.PartitionName is None:
        print("Empty <PartitionName> tag is not allowed for partition operation")
        return False
    if raw_dev_path.PartitionTypeGUID is None:
        print(
            "Empty <PartitionTypeGuidName> tag is not allowed for partition operation"
        )
        return False
    return True


def fat_fields_checking(raw_fwentry, raw_dev_path, meta_data_dev_path):
    if raw_fwentry.InputBinary is None:
        print("Empty <InputBinary> tag is not allowed for FAT file operation")
        return False
    if raw_dev_path.DiskType is None:
        print("Empty <DiskType> tag is not allowed for FAT file operation")
        return False
    if raw_dev_path.PartitionName is None and raw_dev_path.PartitionTypeGUID is None:
        print(
            "Enter <PartitionName> or <PartitionTypeGUID> is required for FAT file operation"
        )
        return False
    if raw_dev_path.FileName is None:
        print("Empty <FileName> tag is not allowed for FAT file operation")
        return False
    return True


def dpp_fields_checking(raw_fwentry, raw_dev_path, meta_data_dev_path):
    if raw_fwentry.InputBinary is None:
        print("Empty <InputBinary> tag is not allowed for DPP file operation")
        return False
    if raw_dev_path.FileName is None:
        print("Empty <FileName> tag is not allowed for DPP file operation")
        return False
    return True


def delete_fat_fields_checking(raw_fwentry, raw_dev_path, meta_data_dev_path):
    if raw_dev_path.DiskType is None:
        print("Empty <DiskType> tag is not allowed for FAT file operation")
        return False
    if raw_dev_path.PartitionName is None and raw_dev_path.PartitionTypeGUID is None:
        print(
            "Empty <PartitionName> or <PartitionTypeGUID> is not allowed for FAT file operation"
        )
        return False
    if raw_dev_path.FileName is None:
        print("Empty <FileName> tag is not allowed for FAT file operation")
        return False
    return True


def delete_partition_fields_checking(raw_fwentry, raw_dev_path, meta_data_dev_path):
    if raw_dev_path.DiskType is None:
        print("Empty <DiskType> tag is not allowed for partition operation")
        return False
    if raw_dev_path.PartitionName is None:
        print("Empty <PartitionName> tag is not allowed for partition operation")
        return False
    if raw_dev_path.PartitionTypeGUID is None:
        print("Empty <PartitionTypeGUID> tag is not allowed for partition operation")
        return False
    return True


def find_xml_raw_fw_entry_node(meta_data_fw_entry, g_dynamic_var):
    xml_node_entry = FVC_h.XML_RAW_FWENTRY()

    for xml_raw_fw_entry in g_dynamic_var.XmlRawFwEntryList:
        if xml_raw_fw_entry.FileGuid.lower() == meta_data_fw_entry.FileGuid.lower():
            xml_node_entry = xml_raw_fw_entry

    return xml_node_entry


def fw_entry_fields_value_checking(raw_fwentry, meta_data_fwentry, g_dynamic_var):
    # Operation
    if raw_fwentry.Operation:
        if raw_fwentry.Operation.upper() in g_dynamic_var.dOperationTypeByString:
            meta_data_fwentry.Operation = g_dynamic_var.dOperationTypeByString[
                raw_fwentry.Operation.upper()
            ]
        else:
            print(f"Operation {raw_fwentry.Operation} is not recognized")
            return False

    # UpdateType
    if raw_fwentry.UpdateType:
        if raw_fwentry.UpdateType.upper() in g_dynamic_var.dUpdateTypeByString:
            meta_data_fwentry.UpdateType = g_dynamic_var.dUpdateTypeByString[
                raw_fwentry.UpdateType.upper()
            ]
            if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FAT_FILE:
                print("ERROR: <UpdateType> is not supported for FAT_FILE")
                return False
        else:
            print(f"<UpdateType> {raw_fwentry.UpdateType} is not recognized")
            return False

    # BackupType
    if raw_fwentry.BackupType:
        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            print("ERROR: <BackupType> is not supported for UPDATE_FWCLASS_GUID")
            return False

        if raw_fwentry.BackupType.upper() in g_dynamic_var.dBackupTypeByString:
            meta_data_fwentry.BackupType = g_dynamic_var.dBackupTypeByString[
                raw_fwentry.BackupType.upper()
            ]
            if meta_data_fwentry.BackupType == FVC_h.FWENTRY_BACKUP_TYPE.FAT_FILE:
                print("ERROR: <BackupType> is not supported for FAT_FILE")
                return False
        else:
            print(f"<BackupType> {raw_fwentry.BackupType} is not recognized")
            return False

    # MatchIdentifier
    if g_dynamic_var.isMatchIdentifierInXML:
        meta_data_fwentry.Revision = FVC.SYS_FW_METADATA_REVISION
        if raw_fwentry.MatchIdentifier:
            if (
                len(raw_fwentry.MatchIdentifier)
                > FVC_h.GlobalStaticVariable.MATCH_IDENTIFIER_NAME_MAX_SIZE
            ):
                print(
                    f"Error: More than {FVC_h.GlobalStaticVariable.MATCH_IDENTIFIER_NAME_MAX_SIZE} characters found in <MatchIdentifier>"
                )
                return False
            meta_data_fwentry.MatchIdentifier = raw_fwentry.MatchIdentifier.encode(
                "utf-8"
            )

    # BinaryType
    if g_dynamic_var.isGlymurMode and raw_fwentry.BinaryType:
        if raw_fwentry.BinaryType.upper() in g_dynamic_var.dBinaryTypeByString:
            meta_data_fwentry.BinaryType = g_dynamic_var.dBinaryTypeByString[
                raw_fwentry.BinaryType.upper()
            ]
        else:
            print(f"<BinaryType> {raw_fwentry.BinaryType} is not recognized")
            return False

    # ARValidation
    if g_dynamic_var.isGlymurMode and raw_fwentry.ARValidation:
        images = raw_fwentry.ARValidation.Images
        image_count = len(images)
        for j, image in enumerate(images):
            if meta_data_fwentry.BinaryType == FVC_h.FWENTRY_BINARY_TYPE.FATFS:
                if image.FileName is None:
                    print(
                        f"ERROR: FileName is null for image {raw_fwentry.InputBinary}"
                    )
                    return False
                if len(image.FileName) > FVC_h.GlobalStaticVariable.FILE_NAME_MAX_SIZE:
                    print(
                        f"ERROR: More than {FVC_h.GlobalStaticVariable.FILE_NAME_MAX_SIZE} characters found in <FileName>"
                    )
                    return False
            elif meta_data_fwentry.BinaryType == FVC_h.FWENTRY_BINARY_TYPE.RAW:
                if (
                    image.FileName is not None
                    and len(image.FileName)
                    < FVC_h.GlobalStaticVariable.FILE_NAME_MAX_SIZE
                ):
                    if image.FileName != raw_fwentry.InputBinary:
                        print(
                            "ARValidation FileName should be same as InputBinary name for RAW FwEntry"
                        )
                        return False

            if not image.ARValidationType:
                print(f"ERROR: ARValidationType is null for image {image.FileName}")
                return False

            if (
                len(image.ARValidationType)
                > FVC_h.GlobalStaticVariable.AR_VALIDATION_TYPE_MAX_SIZE
            ):
                print(
                    f"ERROR: More than {FVC_h.GlobalStaticVariable.AR_VALIDATION_TYPE_MAX_SIZE} characters found in <ARValidationType>"
                )
                return False

            if image.FileName is not None:
                meta_data_fwentry.ARValidation.Images[j].FileName[
                    : len(image.FileName.encode("utf-16-le"))
                ] = image.FileName.encode("utf-16-le")
            meta_data_fwentry.ARValidation.Images[j].ARValidationType[
                : len(image.ARValidationType.encode("utf-16-le"))
            ] = image.ARValidationType.encode("utf-16-le")

        meta_data_fwentry.ARValidation.ImageCount = image_count

    # Dest DiskType
    if raw_fwentry.UpdatePath.DiskType:
        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            print("ERROR: <Dest> is not supported for UPDATE_FWCLASS_GUID")
            return False

        if raw_fwentry.UpdatePath.DiskType.upper() in g_dynamic_var.dDiskTypeByString:
            meta_data_fwentry.UpdatePath.DiskType = g_dynamic_var.dDiskTypeByString[
                raw_fwentry.UpdatePath.DiskType.upper()
            ]
        else:
            print(
                f"Dest <DiskType> {raw_fwentry.UpdatePath.DiskType} is not recognized"
            )
            return False

    # Dest PartitionName
    if raw_fwentry.UpdatePath.PartitionName:
        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            print("ERROR: <Dest> is not supported for UPDATE_FWCLASS_GUID")
            return False
        if (
            len(raw_fwentry.UpdatePath.PartitionName)
            > FVC_h.GlobalStaticVariable.PARTITION_NAME_MAX_SIZE
        ):
            print(
                f"Error: More than {FVC_h.GlobalStaticVariable.PARTITION_NAME_MAX_SIZE} characters found in <PartitionName>"
            )
            return False
        if (
            raw_fwentry.UpdatePath.PartitionName
            == FVC_h.GlobalStaticVariable.PARTITION_NAME_SYSFW_VERSION
        ):
            print(
                f"Error: Partition name {FVC_h.GlobalStaticVariable.PARTITION_NAME_SYSFW_VERSION} is not allowed, Otherwise version conflict will occur when different binary is used"
            )
            return False
        meta_data_fwentry.UpdatePath.PartitionName[
            : len(raw_fwentry.UpdatePath.PartitionName)
        ] = bytearray(raw_fwentry.UpdatePath.PartitionName, "utf-8")

    # Dest PartitionTypeGuid
    if raw_fwentry.UpdatePath.PartitionTypeGUID:
        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            print("ERROR: <Dest> is not supported for UPDATE_FWCLASS_GUID")
            return False

        s_temp = raw_fwentry.UpdatePath.PartitionTypeGUID.strip("{}")
        if s_temp:
            try:
                uuid_obj = uuid.UUID(s_temp)
                meta_data_fwentry.UpdatePath.PartitionTypeGUID = (ctypes.c_byte * 16)(
                    *uuid_obj.bytes
                )

            except ValueError as e:
                print(f"ERROR: Failure creating partitionTypeGuid(error: {e}).\n")
                return False

    # Dest FileName
    if raw_fwentry.UpdatePath.FileName:
        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            print("ERROR: <Dest> is not supported for UPDATE_FWCLASS_GUID")
            return False

        if (
            len(raw_fwentry.UpdatePath.FileName)
            > FVC_h.GlobalStaticVariable.FILE_NAME_MAX_SIZE
        ):
            print(
                f"Error: More than {FVC_h.GlobalStaticVariable.FILE_NAME_MAX_SIZE} characters found in <FileName>"
            )
            return False
        meta_data_fwentry.UpdatePath.FileName = raw_fwentry.UpdatePath.FileName

    # Backup DiskType
    if raw_fwentry.BackupPath.DiskType:
        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            print("ERROR: <Backup> is not supported for UPDATE_FWCLASS_GUID")
            return False

        if raw_fwentry.BackupPath.DiskType.upper() in g_dynamic_var.dDiskTypeByString:
            meta_data_fwentry.BackupPath.DiskType = g_dynamic_var.dDiskTypeByString[
                raw_fwentry.BackupPath.DiskType.upper()
            ]
        else:
            print(
                f"Dest <DiskType> {raw_fwentry.BackupPath.DiskType} is not recognized"
            )
            return False

    # Backup PartitionName
    if raw_fwentry.BackupPath.PartitionName:
        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            print("ERROR: <Backup> is not supported for UPDATE_FWCLASS_GUID")
            return False

        if (
            len(raw_fwentry.BackupPath.PartitionName)
            > FVC_h.GlobalStaticVariable.PARTITION_NAME_MAX_SIZE
        ):
            print(
                f"Error: More than {FVC_h.GlobalStaticVariable.PARTITION_NAME_MAX_SIZE} characters found in <PartitionName>"
            )
            return False
        if (
            raw_fwentry.BackupPath.PartitionName
            == FVC_h.GlobalStaticVariable.PARTITION_NAME_SYSFW_VERSION
        ):
            print(
                f"Error: Partition name {FVC_h.GlobalStaticVariable.PARTITION_NAME_SYSFW_VERSION} is not allowed, Otherwise version conflict will occur when different binary is used"
            )
            return False
        meta_data_fwentry.BackupPath.PartitionName[
            : len(raw_fwentry.BackupPath.PartitionName)
        ] = bytearray(raw_fwentry.BackupPath.PartitionName, "utf-8")

    # Backup PartitionTypeGuid
    if raw_fwentry.BackupPath.PartitionTypeGUID:
        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            print("ERROR: <Backup> is not supported for UPDATE_FWCLASS_GUID")
            return False

        s_temp = raw_fwentry.BackupPath.PartitionTypeGUID.strip("{}")
        if s_temp:
            try:
                uuid_obj = uuid.UUID(s_temp)
                meta_data_fwentry.BackupPath.PartitionTypeGUID = (ctypes.c_byte * 16)(
                    *uuid_obj.bytes
                )
            except ValueError as e:
                print(f"ERROR: Failure creating partitionTypeGuid(error: {e}).\n")
                return False

    # Backup FileName
    if raw_fwentry.BackupPath.FileName:
        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            print("ERROR: <Backup> is not supported for UPDATE_FWCLASS_GUID")
            return False

        if (
            len(raw_fwentry.BackupPath.FileName)
            > FVC_h.GlobalStaticVariable.FILE_NAME_MAX_SIZE
        ):
            print(
                f"Error: More than {FVC_h.GlobalStaticVariable.FILE_NAME_MAX_SIZE} characters found in <FileName>"
            )
            return False
        meta_data_fwentry.BackupPath.FileName = raw_fwentry.BackupPath.FileName

    return True


def assign_file_guid_for_fw_entry(raw_fwentry, meta_data_fwentry, g_dynamic_var):

    if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FAT_FILE:
        return False

    if meta_data_fwentry.UpdateType in [
        FVC_h.FWENTRY_UPDATE_TYPE.DPP_OEM,
        FVC_h.FWENTRY_UPDATE_TYPE.DPP_QCOM,
        FVC_h.FWENTRY_UPDATE_TYPE.OPM_PRIV_KEY,
    ]:
        if (
            raw_fwentry.UpdatePath.FileName.upper()
            in g_dynamic_var.dFileGuidByDestDppItemFile
        ):
            s_temp_guid1 = g_dynamic_var.dFileGuidByDestDppItemFile[
                raw_fwentry.UpdatePath.FileName.upper()
            ].strip("{}")
            raw_fwentry.FileGuid = s_temp_guid1
            try:
                meta_data_fwentry.FileGuid = uuid.UUID(s_temp_guid1)
            except ValueError as e:
                print(f"ERROR: Failure creating FileGuid(error: {e}).\n")
                return False
            return True

    try:
        uuid_obj = uuid.uuid4()
        meta_data_fwentry.FileGuid = (ctypes.c_byte * 16)(*uuid_obj.bytes)

    except ValueError as e:
        print(f"ERROR: Failure creating FileGuid(error: {e}).\n")
        return False

    raw_fwentry.FileGuid = meta_data_fwentry.FileGuid
    return True


def fw_entry_fields_combination_checking(raw_fwentry, meta_data_fwentry, g_dynamic_var):
    if meta_data_fwentry.Operation == FVC_h.FWENTRY_OPERATION_TYPE.UPDATE:
        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.PARTITION:
            if partition_fields_checking(
                raw_fwentry, raw_fwentry.UpdatePath, meta_data_fwentry.UpdatePath
            ):
                if meta_data_fwentry.BackupType == FVC_h.FWENTRY_BACKUP_TYPE.PARTITION:
                    if partition_fields_checking(
                        raw_fwentry,
                        raw_fwentry.BackupPath,
                        meta_data_fwentry.BackupPath,
                    ):
                        print("Firmware entry validated\n")
                        return True
                    print("BackupPath partition validation failed")
                    return False
                if meta_data_fwentry.BackupType == FVC_h.FWENTRY_BACKUP_TYPE.FAT_FILE:
                    print("Invalid BackupPath")
                    return False
            print("UpdatePath partition validation failed")
            return False

        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            print("Firmware entry validated\n")
            return True

        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FAT_FILE:
            return False

        if meta_data_fwentry.UpdateType in [
            FVC_h.FWENTRY_UPDATE_TYPE.DPP_QCOM,
            FVC_h.FWENTRY_UPDATE_TYPE.DPP_OEM,
        ]:
            if dpp_fields_checking(
                raw_fwentry, raw_fwentry.UpdatePath, meta_data_fwentry.UpdatePath
            ):
                if meta_data_fwentry.BackupType == FVC_h.FWENTRY_BACKUP_TYPE.FAT_FILE:
                    return False
                if meta_data_fwentry.BackupType == FVC_h.FWENTRY_BACKUP_TYPE.PARTITION:
                    if partition_fields_checking(
                        raw_fwentry,
                        raw_fwentry.BackupPath,
                        meta_data_fwentry.BackupPath,
                    ):
                        print("Firmware entry validated\n")
                        return True
                    return False
                return False
            return False

        if meta_data_fwentry.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.OPM_PRIV_KEY:
            if dpp_fields_checking(
                raw_fwentry, raw_fwentry.UpdatePath, meta_data_fwentry.UpdatePath
            ):
                if meta_data_fwentry.BackupType == FVC_h.FWENTRY_BACKUP_TYPE.FAT_FILE:
                    return False
                if meta_data_fwentry.BackupType == FVC_h.FWENTRY_BACKUP_TYPE.PARTITION:
                    if partition_fields_checking(
                        raw_fwentry,
                        raw_fwentry.BackupPath,
                        meta_data_fwentry.BackupPath,
                    ):
                        print("Firmware entry validated\n")
                        return True
                    return False
                return False
            return False

        return False

    if meta_data_fwentry.Operation == FVC_h.FWENTRY_OPERATION_TYPE.IGNORE:
        return True

    return False


def fw_entry_validation(raw_fwentry, meta_data_fwentry, g_dynamic_var):
    print("Validating firmware entry...")
    print("============================")
    print(
        f"               <FlashType>         = {g_dynamic_var.dFlashTypeByValue[g_dynamic_var.DeviceFlashType]}"
    )
    print(f"               <InputBinary>       = {raw_fwentry.InputBinary}")
    print(f"               <Operation>         = {raw_fwentry.Operation}")
    print(f"               <UpdateType>        = {raw_fwentry.UpdateType}")
    print(f"               <BackupType>        = {raw_fwentry.BackupType}")
    if raw_fwentry.MatchIdentifier:
        print(f"               <MatchIdentifier>   = {raw_fwentry.MatchIdentifier}")
    print(f"    DestPath   <DiskType>          = {raw_fwentry.UpdatePath.DiskType}")
    print(
        f"    DestPath   <PartitionName>     = {raw_fwentry.UpdatePath.PartitionName}"
    )
    print(
        f"    DestPath   <PartitionTypeGuid> = {raw_fwentry.UpdatePath.PartitionTypeGUID}"
    )
    print(f"    DestPath   <FileName>          = {raw_fwentry.UpdatePath.FileName}")
    print("\n")
    print(f"    BackupPath <DiskType>          = {raw_fwentry.BackupPath.DiskType}")
    print(
        f"    BackupPath <PartitionName>     = {raw_fwentry.BackupPath.PartitionName}"
    )
    print(
        f"    BackupPath <PartitionTypeGuid> = {raw_fwentry.BackupPath.PartitionTypeGUID}"
    )
    print(f"    BackupPath <FileName>          = {raw_fwentry.BackupPath.FileName}")

    if not fw_entry_fields_value_checking(
        raw_fwentry, meta_data_fwentry, g_dynamic_var
    ):
        return False

    if not assign_file_guid_for_fw_entry(raw_fwentry, meta_data_fwentry, g_dynamic_var):
        return False

    if not fw_entry_fields_combination_checking(
        raw_fwentry, meta_data_fwentry, g_dynamic_var
    ):
        return False

    return True


def fw_entry_list_validation_main(g_dynamic_var):
    base_match_identifier = None
    target_match_identifier = None

    for i in range(len(g_dynamic_var.XmlRawFwEntryList)):
        raw_fw_entry_temp = g_dynamic_var.XmlRawFwEntryList.popleft()
        m_fw_entry = FVC_h.QPAYLOAD_METADATA_FWENTRY()
        m_fw_entry.UpdatePath = FVC_h.FWENTRY_DEVICE_PATH(0x0)
        m_fw_entry.BackupPath = FVC_h.FWENTRY_DEVICE_PATH(0x0)
        if g_dynamic_var.isMatchIdentifierInXML:
            m_fw_entry.MatchIdentifier = (
                b"\0" * FVC_h.GlobalStaticVariable.MATCH_IDENTIFIER_NAME_MAX_SIZE
            )

        if fw_entry_validation(raw_fw_entry_temp, m_fw_entry, g_dynamic_var):
            if m_fw_entry.Operation != FVC_h.FWENTRY_OPERATION_TYPE.IGNORE:
                g_dynamic_var.QpayloadFwEntryList.append(m_fw_entry)
        else:
            print("ERROR: Error validating firmware entry.")
            return False
        g_dynamic_var.XmlRawFwEntryList.append(raw_fw_entry_temp)

    # FlashType exclusive checking
    print("FlashType exclusive checking\n")
    for i in range(len(g_dynamic_var.QpayloadFwEntryList)):
        m_fw_entry = g_dynamic_var.QpayloadFwEntryList[i]
        if m_fw_entry.UpdateType != FVC_h.FWENTRY_UPDATE_TYPE.FWCLASS_GUID:
            if m_fw_entry.UpdateType not in [
                FVC_h.FWENTRY_UPDATE_TYPE.DPP_QCOM,
                FVC_h.FWENTRY_UPDATE_TYPE.DPP_OEM,
                FVC_h.FWENTRY_UPDATE_TYPE.OPM_PRIV_KEY,
            ]:
                if (
                    g_dynamic_var.DeviceFlashType
                    not in g_dynamic_var.dFlashTypeByDiskType[
                        FVC_h.FWENTRY_DISK_TYPE(m_fw_entry.UpdatePath.DiskType)
                    ]
                ):
                    print(
                        f"ERROR1: DiskType {g_dynamic_var.dDiskTypeByValue[FVC_h.FWENTRY_DISK_TYPE(m_fw_entry.UpdatePath.DiskType)]} can't be used on a {g_dynamic_var.dFlashTypeByValue[g_dynamic_var.DeviceFlashType]} device."
                    )
                    return False

            if (
                g_dynamic_var.DeviceFlashType
                not in g_dynamic_var.dFlashTypeByDiskType[
                    FVC_h.FWENTRY_DISK_TYPE(m_fw_entry.BackupPath.DiskType)
                ]
            ):
                print(
                    f"ERROR2: DiskType {g_dynamic_var.dDiskTypeByValue[FVC_h.FWENTRY_DISK_TYPE(m_fw_entry.BackupPath.DiskType)]} can't be used on a {g_dynamic_var.dFlashTypeByValue[g_dynamic_var.DeviceFlashType]} device."
                )
                return False

    # QCOM Dpp Item Name exclusive checking
    print("QCOM Dpp Item Name exclusive checking\n")
    for i in range(len(g_dynamic_var.QpayloadFwEntryList)):
        m_fw_entry_base = g_dynamic_var.QpayloadFwEntryList[i]

        if m_fw_entry_base.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.DPP_QCOM:
            base_file_name = "".join(m_fw_entry_base.UpdatePath.FileName)

            for j in range(i + 1, len(g_dynamic_var.QpayloadFwEntryList)):
                m_fw_entry_target = g_dynamic_var.QpayloadFwEntryList[j]
                if m_fw_entry_target.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.DPP_QCOM:
                    target_file_name = "".join(m_fw_entry_target.UpdatePath.FileName)
                    if base_file_name == target_file_name:
                        print(
                            "ERROR: duplicated QCOM type DPP items found in the list."
                        )
                        return False

    # OEM Dpp Item Name exclusive checking
    print("OEM Dpp Item Name exclusive checking\n")
    for i in range(len(g_dynamic_var.QpayloadFwEntryList)):
        m_fw_entry_base = g_dynamic_var.QpayloadFwEntryList[i]

        if m_fw_entry_base.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.DPP_OEM:
            base_file_name = "".join(m_fw_entry_base.UpdatePath.FileName)

            for j in range(i + 1, len(g_dynamic_var.QpayloadFwEntryList)):
                m_fw_entry_target = g_dynamic_var.QpayloadFwEntryList[j]
                if m_fw_entry_target.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.DPP_OEM:
                    target_file_name = "".join(m_fw_entry_target.UpdatePath.FileName)
                    if base_file_name == target_file_name:
                        print("ERROR: duplicated OEM type DPP items found in the list.")
                        return False

    # Partition device path exclusive checking
    print("Partition device path exclusive checking\n")
    for i in range(len(g_dynamic_var.QpayloadFwEntryList)):
        m_fw_entry_base = g_dynamic_var.QpayloadFwEntryList[i]

        if m_fw_entry_base.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.PARTITION:
            base_update_part_name = "".join(
                chr(b) for b in m_fw_entry_base.UpdatePath.PartitionName
            )
            base_backup_part_name = "".join(
                chr(b) for b in m_fw_entry_base.BackupPath.PartitionName
            )

            # Case 1: BaseFwEntry's updatePath VS BaseFwEntry's BackupPath.
            if (
                m_fw_entry_base.UpdatePath.DiskType
                == m_fw_entry_base.BackupPath.DiskType
                and m_fw_entry_base.UpdatePath.PartitionTypeGUID
                == m_fw_entry_base.BackupPath.PartitionTypeGUID
                and base_update_part_name == base_backup_part_name
            ):
                print(
                    "ERROR: same partition update path and backup path found in the same entry."
                )
                return False

            for j in range(i + 1, len(g_dynamic_var.QpayloadFwEntryList)):
                m_fw_entry_target = g_dynamic_var.QpayloadFwEntryList[j]
                if m_fw_entry_target.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.PARTITION:
                    target_update_part_name = "".join(
                        chr(b) for b in m_fw_entry_target.UpdatePath.PartitionName
                    )
                    target_backup_part_name = "".join(
                        chr(b) for b in m_fw_entry_target.BackupPath.PartitionName
                    )

                    if g_dynamic_var.isMatchIdentifierInXML:
                        if any(m_fw_entry_base.MatchIdentifier):
                            base_match_identifier = "".join(
                                m_fw_entry_base.MatchIdentifier
                            )
                        if any(m_fw_entry_target.MatchIdentifier):
                            target_match_identifier = "".join(
                                m_fw_entry_target.MatchIdentifier
                            )

                    # Case 2: BaseFwEntry's updatePath VS TargetFwEntry's UpdatePath
                    if (
                        m_fw_entry_base.UpdatePath.DiskType
                        == m_fw_entry_target.UpdatePath.DiskType
                        and m_fw_entry_base.UpdatePath.PartitionTypeGUID
                        == m_fw_entry_target.UpdatePath.PartitionTypeGUID
                        and base_update_part_name == target_update_part_name
                    ):
                        if not base_match_identifier or not target_match_identifier:
                            print(
                                "ERROR: same partition update path found in the list."
                            )
                            return False
                        elif base_match_identifier == target_match_identifier:
                            print(
                                "ERROR: same partition update path with same match identifier found in the list."
                            )
                            return False
                        elif base_match_identifier != target_match_identifier:
                            xml_entry_base = find_xml_raw_fw_entry_node(
                                m_fw_entry_base, g_dynamic_var
                            )
                            xml_entry_target = find_xml_raw_fw_entry_node(
                                m_fw_entry_target, g_dynamic_var
                            )
                            if (
                                xml_entry_base.InputBinary
                                == xml_entry_target.InputBinary
                            ):
                                print(
                                    "ERROR: same partition update path with same input binary found in the list."
                                )
                                return False

                    # Case 3: BaseFwEntry's updatePath VS TargetFwEntry's BackupPath
                    if (
                        m_fw_entry_base.UpdatePath.DiskType
                        == m_fw_entry_target.BackupPath.DiskType
                        and m_fw_entry_base.UpdatePath.PartitionTypeGUID
                        == m_fw_entry_target.BackupPath.PartitionTypeGUID
                        and base_update_part_name == target_backup_part_name
                    ):
                        print(
                            "ERROR: same partition update path and backup path found in the list."
                        )
                        return False

                    # Case 4: BaseFwEntry's BackupPath VS TargetFwEntry's UpdatePath
                    if (
                        m_fw_entry_base.BackupPath.DiskType
                        == m_fw_entry_target.UpdatePath.DiskType
                        and m_fw_entry_base.BackupPath.PartitionTypeGUID
                        == m_fw_entry_target.UpdatePath.PartitionTypeGUID
                        and base_backup_part_name == target_update_part_name
                    ):
                        print(
                            "ERROR: same partition update path and backup path found in the list."
                        )
                        return False

                    # Case 5: BaseFwEntry's BackupPath VS TargetFwEntry's BackupPath
                    if (
                        m_fw_entry_base.BackupPath.DiskType
                        == m_fw_entry_target.BackupPath.DiskType
                        and m_fw_entry_base.BackupPath.PartitionTypeGUID
                        == m_fw_entry_target.BackupPath.PartitionTypeGUID
                        and base_backup_part_name == target_backup_part_name
                    ):
                        if not base_match_identifier or not target_match_identifier:
                            print(
                                "ERROR: same partition backup path found in the list."
                            )
                            return False
                        elif base_match_identifier == target_match_identifier:
                            print(
                                "ERROR: same partition backup path with same match identifier found in the list."
                            )
                            return False
                        elif base_match_identifier != target_match_identifier:
                            xml_entry_base = find_xml_raw_fw_entry_node(
                                m_fw_entry_base, g_dynamic_var
                            )
                            xml_entry_target = find_xml_raw_fw_entry_node(
                                m_fw_entry_target, g_dynamic_var
                            )
                            if (
                                xml_entry_base.InputBinary
                                == xml_entry_target.InputBinary
                            ):
                                print(
                                    "ERROR: same partition backup path with same input binary found in the list."
                                )
                                return False

    # Fat device path exclusive checking
    print("Fat device path exclusive checking\n")
    for i in range(len(g_dynamic_var.QpayloadFwEntryList)):
        m_fw_entry_base = g_dynamic_var.QpayloadFwEntryList[i]

        if m_fw_entry_base.UpdateType == FVC_h.FWENTRY_UPDATE_TYPE.FAT_FILE:
            print("Invalid BackupPath")
            return False

    return True
