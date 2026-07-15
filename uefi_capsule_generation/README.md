# Capsule Generation Tools

## 1. Introduction to the Capsule Generation Tools

Capsule Generation Tools are specialized utilities designed to create capsule
files, which are essential for performing firmware updates on various devices.
These tools streamline the process of packaging firmware updates into a format
that can be easily deployed and applied to the target hardware.

## 2. Overview of the Capsule Generation Tools

The tools are packaged as a single Python distribution (`qcom-capsule-tool`)
managed with [poetry][poetry] and runnable on Linux, macOS, and Windows
(via MSYS2). By using OpenSSL for certificate generation and signing, the
tools ensure that firmware updates are secure and authenticated.

[poetry]: https://python-poetry.org/
[pipx]: https://pipx.pypa.io/

### 2.1 Installation

**End users -- install the tool globally with [pipx][pipx]:**

```sh
cd uefi_capsule_generation
pipx install .
qcom-capsule-tool --help
```

`pipx` puts the `qcom-capsule-tool` command on your `PATH` in an isolated
venv. You can run it from any directory without a `poetry run` prefix.

**Developers -- use poetry for an editable, project-local environment:**

```sh
cd uefi_capsule_generation
poetry install
poetry run qcom-capsule-tool --help
```

`poetry install` creates `.venv/` next to `pyproject.toml` with all runtime
and dev dependencies (ruff, mypy). Prefix subsequent commands with
`poetry run`, or enter a shell with `poetry shell`.

Subcommands wrap the individual tools:

| Subcommand              | Replaces script             |
| ----------------------- | --------------------------- |
| `create`                | `capsule_creator.py`        |
| `fv-create`             | `FVCreation.py`             |
| `generate-capsule`      | edk2 `GenerateCapsule.py`   |
| `update-fv-xml`         | `UpdateFvXml.py`            |
| `update-json`           | `UpdateJsonParameters.py`   |
| `sysfw-version-create`  | `SYSFW_VERSION_program.py`  |
| `bin-to-hex`            | `BinToHex.py`               |
| `set-dtb-property`      | `set_dtb_property.py`       |
| `parse-config`          | `xblconfig_parser.py`       |

### 2.2 Quick start with Make

A `Makefile` wraps the most common developer workflows (uses `poetry run`
under the hood):

```sh
make install     # poetry install
make lint        # ruff check + ruff format --check + mypy
make unittest    # pytest unit tests (golden FFS/FV/capsule fixtures)
make test TARGET=qcs6490   # end-to-end capsule generation for a chip
make test-all              # iterate over every supported chip
make clean
```

Supported `TARGET`s: `qcs6490`, `qcs8300`, `qcs9100`. The
`test` target downloads chip-specific boot binaries from public URLs,
generates a throwaway test cert chain, patches `xbl_config.elf` with
the new root cert, and runs `qcom-capsule-tool` end-to-end. Output
lands in `build/$(TARGET)/capsule_file.cap`.

## 3. Working of the Host Signing Tool

### 3.1 Pre-requisites to Run the Tool

**For Linux:**

1. **OpenSSL**: A toolkit for the Transport Layer Security (TLS) and Secure
   Sockets Layer (SSL) protocols.
1. **Python3**: A programming language widely used for scripting and
   automation.
1. **GIT**: version control system.

**For Windows:**

1. **OpenSSL**: Same as above.
1. **Python3**: Same as above.
1. **GIT**: version control system.

Before starting the capsule generation process, you need to generate OpenSSL
certificates as mentioned in
[Capsule-Based System Firmware Update - Generate Keys][capsule-keys].
These certificates should be placed in a separate folder named 'Certificates'.

[capsule-keys]: https://github.com/tianocore/tianocore.github.io/wiki/Capsule-Based-System-Firmware-Update-Generate-Keys

Sample Certificates folder:

```
QcFMPCert.pem
QcFMPRoot.pub.pem
QcFMPSub.pub.pem
```

The `QcFMPRoot.cer` (or `NewRoot.cer`) should be converted to a hex value.

Use the `bin-to-hex` subcommand to convert `NewRoot.cer` to a hex value:

```sh
qcom-capsule-tool bin-to-hex NewRoot.cer NewRoot.inc
```

This `NewRoot.inc` contains the cert value, which needs to be provided in the BOOT DT [will be part of `xbl_config.elf`] for QCS6490,QCS9100,QCS8300,QCS615 or in UEFI DT [will be part of `uefi_dtbs.elf`] for IQ-X7181,IQ-X5121,Kaanapali,SM8750,QRB2210-RB1,CQ2390M targets at node
`/sw/uefi/uefiplat/QcCapsuleRootCert` using QDTE tool.

For more information on the QDTE Tool, refer to the
[QDTE Tool documentation][qdte-tool].

[qdte-tool]: https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-4/tools.html?vproduct=1601111740013072&version=1.3&facet=Boot#qdte


*Please Note - for QLI Hamoa/Purwa uefi_dtbs.elf needs to compressed using xz tool and then flashed.
```
xz -k uefi_dtbs.elf

Usage:
xz -k  <InputFile>
-k : to keep the original uncompressed file
```


### 3.2 Setting QcCapsuleRootCert Without QDTE (for targets - QCS6490, QCS9100, QCS8300, QCS615)

As an alternative to QDTE, you can patch the certificate directly into
`xbl_config.elf` using `xblconfig_parser.py` and `set_dtb_property.py`.

1. Extract all DTB payloads from `xbl_config.elf`:

   ```sh
   qcom-capsule-tool parse-config xbl_config.elf dump --out-dir ./out
   ```

1. Patch the `QcCapsuleRootCert` property into the appropriate DTB.
   The target is the DTB containing the `/sw/uefi/uefiplat` node
   (typically a `post-ddr` DTB):

   ```sh
   qcom-capsule-tool set-dtb-property \
     out/<post-ddr-dtb>.dtb \
     /sw/uefi/uefiplat \
     QcCapsuleRootCert \
     @list:QcFMPRoot.inc \
     out/<post-ddr-dtb>_patched.dtb
   ```

   The `@list:QcFMPRoot.inc` argument reads the integer list produced by
   `bin-to-hex` and encodes it as 32-bit big-endian words into the DTB
   property.

1. Replace the patched DTB back into `xbl_config.elf`. Use the program
   header index (`<ph_num>`) shown by the `dump` step above:

   ```sh
   qcom-capsule-tool parse-config xbl_config.elf replace \
     <ph_num> out/<post-ddr-dtb>_patched.dtb xbl_config_patched.elf
   ```

## 4. Steps to Generate Capsule Files

Clone the repository and enter the
`cbsp-boot-utilities/uefi_capsule_generation/` directory:

```sh
git clone https://github.com/quic/cbsp-boot-utilities.git
```

1. **Generate Firmware Version bin File:**

   ```sh
   qcom-capsule-tool sysfw-version-create \
     -Gen -FwVer 0.0.A.B -LFwVer 0.0.0.0 -O SYSFW_VERSION.bin
   ```

   Where A and B are the version numbers:

   - `-Gen`: Generate a new firmware version file.
   - `-FwVer`: Specifies the firmware version.
   - `-LFwVer`: Specifies the lowest firmware version.
   - `-O`: Output file name.

   To print the Firmware Versions in the `.bin` file:

   ```sh
   qcom-capsule-tool sysfw-version-create --PrintAll SYSFW_VERSION.bin
   ```

1. **Generate/Update FvUpdate.xml with Firmware entries:**

  * For targets IQ-X7181-EVK, IQ-X5121, Kaanapali-MTP, SM8750-MTP - Manually update FvUpdate.xml (UpdateFvXml.py not supported yet)

   This subcommand generates the `FvUpdate.xml` file with firmware
   entries:

   ```sh
   qcom-capsule-tool update-fv-xml -S <StorageType> -T <Target>
   ```

   or using a local partition configuration file:

   ```sh
   qcom-capsule-tool update-fv-xml -F <partition.conf>
   ```

   - `-S <StorageType>`: Storage type, `EMMC` or `UFS`.
   - `-T <Target>`: Target platform, `QCS6490`, `QCS9100`, `QCS8300`,
     or `QCS615`.
   - `-F <partition.conf>`: Path to a local `partition.conf` file.
   - `--ptool-path <dir>`: Path to an existing `qcom-ptool` checkout.
     When provided, the repository is not cloned from GitHub.

   Once `FvUpdate.xml` is generated, update the `Operation` field for
   each firmware entry as needed. By default the operation is set to
   `IGNORE`.

1. **Create Firmware Volume (FV):**

   - Ensure the `/Images` folder contains all the required firmware images
     for Capsule generation.
   - Update `FvUpdate.xml` with `FwEntry` for each firmware image,
     referencing the corresponding image in the `/Images` folder.
   - Refer to `FirmwarePartitions.md` for Partitions related information.

   ```sh
   qcom-capsule-tool fv-create firmware.fv -FvType SYS_FW \
     FvUpdate.xml SYSFW_VERSION.bin Images/
   ```

   - `firmware.fv`: The firmware volume file.
   - `-FvType`: Type of firmware volume.
   - `FvUpdate.xml`: XML file for firmware update.
   - `SYSFW_VERSION.bin`: The firmware version file generated in the
     previous step.
   - `Images/`: Directory containing the images.

   FFS and FV images are generated natively in Python; no edk2
   checkout or BaseTools binaries are required.

1. **Update JSON Parameters:**

   ```sh
   qcom-capsule-tool update-json \
     -j config.json \
     -f SYS_FW \
     -b SYSFW_VERSION.bin \
     -pf firmware.fv \
     -p Certificates/QcFMPCert.pem \
     -x Certificates/QcFMPRoot.pub.pem \
     -oc Certificates/QcFMPSub.pub.pem \
     -g <ESRT GUID>
   ```

   - `-j config.json`: JSON configuration file.
   - `-f SYS_FW`: Firmware type.
   - `-b SYSFW_VERSION.bin`: Firmware version file.
   - `-pf firmware.fv`: Firmware volume file.
   - `-p Certificates/QcFMPCert.pem`: Certificate file.
   - `-x Certificates/QcFMPRoot.pub.pem`: Root public certificate.
   - `-oc Certificates/QcFMPSub.pub.pem`: Subordinate public certificate.
   - `-g <ESRT GUID>`: ESRT GUID.

   ESRT GUIDs:

   - QCS6490 ESRT GUID: `6F25BFD2-A165-468B-980F-AC51A0A45C52`
   - QCS9100 ESRT GUID: `78462415-6133-431C-9FAE-48F2BAFD5C71`
   - QCS8300 ESRT GUID: `8BF4424F-E842-409C-80BE-1418E91EF343`
   - QCS615 ESRT GUID: `9FD379D2-670E-4BB3-86A1-40497E6E17B0`
   - QRB2210-RB1 ESRT GUID: `A2C156D8-ABBF-49B4-9F3D-8C13-4DDE-977B`
   - CQ2390M ESRT GUID: `BD3276F4-219C-452F-9E59-B15D8F242B75`
   - IQ-X7181 ESRT GUID: `0F6D58FC-2258-4D27-9E23-D77219B0897C`
   - IQ-X5121 ESRT GUID: `185A798B-13B2-4595-BD08-E2770A4BB190`
   - Kaanapali ESRT GUID: `2153308F-BE7C-404A-8605-1FF25E8703B9`
   - SM8750 ESRT GUID: `3409BE01-F1F6-40C2-9336-192FD96606F4`
   


2. **Generate the Capsule File:**

   ```sh
   qcom-capsule-tool generate-capsule \
     -e -j config.json \
     -o <capsule_name>.cap \
     --capflag PersistAcrossReset \
     -v
   ```

   - `-e`: Enable capsule generation.
   - `-j config.json`: JSON configuration file.
   - `-o <capsule_name>.cap`: Output capsule file.
   - `--capflag PersistAcrossReset`: Flag to persist across reset.
   - `-v`: Verbose mode.

   The subcommand is a drop-in replacement for the JSON encode mode of
   edk2 `GenerateCapsule.py` (OpenSSL signing); no edk2 checkout is
   required.

   To dump info from the Capsule headers:

   ```sh
   qcom-capsule-tool generate-capsule --dump-info capsule.cap
   ```

## 5. Alternative: Master Script

Instead of the above 5 steps, use the `create` subcommand to run all
steps at once:

```sh
qcom-capsule-tool create \
  -fwver 0.0.A.B \
  -lfwver 0.0.0.0 \
  -config config.json \
  -p Certificates/QcFMPCert.pem \
  -x Certificates/QcFMPRoot.pub.pem \
  -oc Certificates/QcFMPSub.pub.pem \
  -guid <ESRT GUID> \
  -capsule <capsule_name>.cap \
  -images /Images \
  -S <StorageType> \
  -T <Target> \
  --ptool-path /path/to/qcom-ptool
```

 - `-S <StorageType>`: Storage type, `EMMC` or `UFS`.
 - `-T <Target>`: Target platform, `QCS6490`, `QCS9100`, `QCS8300`,
   or `QCS615`.
 - `--ptool-path <dir>`: Optional path to an existing `qcom-ptool`
   checkout. When provided, the repository is not cloned from GitHub.
