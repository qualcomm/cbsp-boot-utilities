# --------------------------------------------------------------------
# Copyright (c) 2026 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#
# Developer entry point for qcom-capsule-tool.
#
#   make install   - poetry install (creates the project venv)
#   make lint      - ruff check, ruff format --check, mypy
#   make format    - ruff format (writes changes)
#   make unittest  - pytest unit tests (golden FFS/FV/capsule fixtures)
#   make test      - end-to-end capsule generation for $(TARGET)
#   make test-all  - loop `make test` over every supported chip
#   make clean     - remove the build/ tree
#
# All Python tool invocations run inside the poetry-managed venv via
# `poetry run`, so a single `poetry install` is the only setup step
# developers need. `make test` downloads boot binaries from public
# URLs, generates a throwaway test cert chain, patches xbl_config.elf
# with the new root cert, then drives qcom-capsule-tool end-to-end.
# Output lands in build/$(TARGET)/capsule_file.cap.
# --------------------------------------------------------------------

SHELL := /bin/bash

# MSYS2 rewrites arguments that look like POSIX paths into Windows
# paths when calling native binaries. That's helpful for
# `curl -o /d/a/...` but breaks `openssl -subj /CN=...` and
# `set-dtb-property /sw/uefi/uefiplat`. The cert and DTB-patching
# recipes set MSYS2_ARG_CONV_EXCL='*' to disable conversion locally,
# and convert any absolute file-path args to Windows form with
# `cygpath -m` via the `towin` shell helper.

# ---- Chip catalog ---------------------------------------------------
# Each chip exposes _PV and _BOOT_URL.

qcs6490_PV       := 00123
qcs6490_BOOT_URL := https://softwarecenter.qualcomm.com/nexus/generic/product/chip/tech-package/QCM6490_bootbinaries.1.0/qcm6490_bootbinaries.1.0-test-device-public/00123/QCM6490_bootbinaries_00123.zip

qcs8300_PV       := 00123
qcs8300_BOOT_URL := https://softwarecenter.qualcomm.com/nexus/generic/product/chip/tech-package/QCS8300_bootbinaries.1.0/qcs8300_bootbinaries.1.0-test-device-public/00123/QCS8300_bootbinaries_00123.zip

qcs9100_PV       := 00123
qcs9100_BOOT_URL := https://softwarecenter.qualcomm.com/nexus/generic/product/chip/tech-package/QCS9100_bootbinaries.1.0/qcs9100_bootbinaries.1.0-test-device-public/00123/QCS9100_bootbinaries_00123.zip

# SM8750 is intentionally absent: its QcCapsuleRootCert node lives in
# uefi_dtbs.elf rather than xbl_config.elf, so the patching pipeline
# below doesn't apply.

SUPPORTED_TARGETS := qcs6490 qcs8300 qcs9100

# ---- User-overridable knobs ----------------------------------------

TARGET   ?= qcs6490
BOOT_URL ?= $($(TARGET)_BOOT_URL)
PV       ?= $($(TARGET)_PV)

FW_VERSION      ?= 0.0.1.2
LOWEST_FW_VER   ?= 0.0.0.0
CERT_PASSWORD   ?= testpassword
FMP_GUID        ?= 6F25BFD2-A165-468B-980F-AC51A0A45C52

# ---- Paths ----------------------------------------------------------

PROJECT_DIR := $(abspath $(CURDIR))
REPO_ROOT   := $(abspath $(PROJECT_DIR)/..)
BUILD       := $(PROJECT_DIR)/build
CACHE       := $(BUILD)/cache
CERTS       := $(BUILD)/certs
WORK        := $(BUILD)/$(TARGET)

OPENSSL_CFG := $(REPO_ROOT)/.github/opensslroot.cfg
FVUPDATE    := $(PROJECT_DIR)/FvUpdate.xml

# All Python tool invocations run inside the poetry-managed venv.
POETRY              ?= poetry
POETRY_RUN          := $(POETRY) run
POETRY_INSTALL_OPTS ?=
QCT                 := $(POETRY_RUN) qcom-capsule-tool

# Sentinel marking that `poetry install` has succeeded for the current
# pyproject.toml. Recipes that need the venv depend on this file.
INSTALL_STAMP := $(BUILD)/.poetry-install.stamp

# ---- Top-level targets ----------------------------------------------

.PHONY: install lint format unittest test test-all clean check-target help

help:
	@echo 'Targets: install lint format unittest test test-all clean'
	@echo 'Variables: TARGET ($(TARGET))'
	@echo 'Supported: $(SUPPORTED_TARGETS)'

install: $(INSTALL_STAMP)

$(INSTALL_STAMP): pyproject.toml | $(BUILD)
	$(POETRY) install $(POETRY_INSTALL_OPTS)
	touch $@

lint: $(INSTALL_STAMP)
	$(POETRY_RUN) ruff check src tests
	$(POETRY_RUN) ruff format --check src tests
	$(POETRY_RUN) mypy src/qcom_capsule_tool

unittest: $(INSTALL_STAMP)
	$(POETRY_RUN) pytest tests

format: $(INSTALL_STAMP)
	$(POETRY_RUN) ruff format src

clean:
	rm -rf $(BUILD)

# Refuse to run target-specific recipes without a recognised TARGET.
check-target:
	@if [ -z "$(BOOT_URL)" ]; then \
		echo "ERROR: unknown TARGET='$(TARGET)'. Supported: $(SUPPORTED_TARGETS)" >&2; \
		exit 1; \
	fi

test: check-target $(WORK)/capsule_file.cap
	@echo
	@echo "=== capsule generated: $(WORK)/capsule_file.cap ==="
	@ls -lh $(WORK)/capsule_file.cap

test-all:
	@for t in $(SUPPORTED_TARGETS); do \
		echo "===== make test TARGET=$$t ====="; \
		$(MAKE) test TARGET=$$t || exit $$?; \
	done

# ---- Download cache -------------------------------------------------

$(BUILD) $(CACHE) $(CERTS) $(WORK):
	mkdir -p $@

$(CACHE)/$(TARGET)-bootbinaries.zip: check-target | $(CACHE)
	curl -fsSL -o $@ '$(BOOT_URL)'

# ---- Cert chain -----------------------------------------------------
# A single sentinel file (QcFMPRoot.inc) marks the whole chain as ready.

$(CERTS)/QcFMPRoot.inc: $(INSTALL_STAMP) | $(CERTS)
	set -e; \
	export MSYS2_ARG_CONV_EXCL='*'; \
	cd $(CERTS); \
	cp $(OPENSSL_CFG) ./opensslroot.cfg; \
	mkdir -p demoCA/newcerts; \
	: > demoCA/index.txt; \
	echo 01 > demoCA/serial; \
	openssl rand -out randfile 256; \
	pw=$(CERT_PASSWORD); \
	openssl genrsa -aes256 -passout pass:$$pw -out QcFMPRoot.key 2048; \
	openssl req -new -x509 -config opensslroot.cfg \
	    -subj '/CN=OEM Root CA/O=FMP/OU=OEM Key/L=San Diego/ST=California/C=US' \
	    -days 3650 -passin pass:$$pw -key QcFMPRoot.key -out QcFMPRoot.crt; \
	openssl x509 -in QcFMPRoot.crt -out QcFMPRoot.cer -outform DER; \
	openssl x509 -inform DER -in QcFMPRoot.cer -outform PEM -out QcFMPRoot.pub.pem; \
	openssl genrsa -aes256 -passout pass:$$pw -out QcFMPSub.key 2048; \
	openssl req -new -config opensslroot.cfg \
	    -subj '/CN=OEM Intermediate CA/O=FMP/OU=OEM Key/L=San Diego/ST=California/C=US' \
	    -passin pass:$$pw -key QcFMPSub.key -out QcFMPSub.csr; \
	openssl ca -config opensslroot.cfg -extensions v3_ca -batch \
	    -in QcFMPSub.csr -days 3650 -out QcFMPSub.crt -cert QcFMPRoot.crt \
	    -passin pass:$$pw -keyfile QcFMPRoot.key; \
	openssl x509 -in QcFMPSub.crt -outform PEM -out QcFMPSub.pub.pem; \
	openssl genrsa -aes256 -passout pass:$$pw -out QcFMPCert.key 2048; \
	openssl req -new -config opensslroot.cfg \
	    -subj '/CN=OEM User/O=FMP/OU=OEM Key/L=San Diego/ST=California/C=US' \
	    -passin pass:$$pw -key QcFMPCert.key -out QcFMPCert.csr; \
	openssl ca -config opensslroot.cfg -batch -in QcFMPCert.csr -days 3650 \
	    -out QcFMPCert.crt -cert QcFMPSub.crt -passin pass:$$pw -keyfile QcFMPSub.key; \
	openssl pkcs12 -export -passout pass:$$pw -out QcFMPCert.pfx \
	    -passin pass:$$pw -inkey QcFMPCert.key -in QcFMPCert.crt; \
	openssl pkcs12 -passin pass:$$pw -in QcFMPCert.pfx -nodes -out QcFMPCert.pem; \
	$(QCT) bin-to-hex QcFMPRoot.cer QcFMPRoot.inc

# ---- Boot binaries extraction --------------------------------------

$(WORK)/.bootbinaries.unpacked: $(CACHE)/$(TARGET)-bootbinaries.zip | $(WORK)
	rm -rf $(WORK)/bootbinaries
	mkdir -p $(WORK)/bootbinaries
	cd $(WORK)/bootbinaries && unzip -q $(CACHE)/$(TARGET)-bootbinaries.zip
	# Boot archives unpack to <CHIP>_bootbinaries/ -- flatten that.
	@inner=$$(find $(WORK)/bootbinaries -maxdepth 1 -mindepth 1 -type d | head -1); \
	if [ -n "$$inner" ] && [ "$$inner" != "$(WORK)/bootbinaries" ]; then \
	    mv $$inner/* $(WORK)/bootbinaries/ && rmdir $$inner; \
	fi
	touch $@

# ---- XBLConfig DTB patching ----------------------------------------
# Patch QcCapsuleRootCert into xbl_config.elf.  patch-capsule-cert
# auto-detects the ELF type and locates the correct DTB segment.

$(WORK)/.xbl_config.patched: $(WORK)/.bootbinaries.unpacked $(CERTS)/QcFMPRoot.inc $(INSTALL_STAMP)
	set -e; \
	export MSYS2_ARG_CONV_EXCL='*'; \
	towin() { command -v cygpath >/dev/null 2>&1 && cygpath -m "$$1" || echo "$$1"; }; \
	xbl=$$(towin $(WORK)/bootbinaries/xbl_config.elf); \
	if [ ! -f "$$xbl" ]; then \
	    echo "ERROR: $$xbl not found in extracted boot binaries"; exit 1; \
	fi; \
	cer=$$(towin $(CERTS)/QcFMPRoot.cer); \
	$(QCT) patch-capsule-cert "$$xbl" "$$cer" "$$xbl.patched"; \
	mv "$$xbl.patched" "$$xbl"; \
	touch $@

# ---- Capsule generation --------------------------------------------

$(WORK)/capsule_file.cap: \
		$(WORK)/.xbl_config.patched \
		$(CERTS)/QcFMPRoot.inc \
		| $(WORK)
	set -e; \
	cd $(WORK); \
	cp $(FVUPDATE) FvUpdate.xml; \
	$(QCT) sysfw-version-create -Gen \
	    -FwVer $(FW_VERSION) -LFwVer $(LOWEST_FW_VER) -O SYSFW_VERSION.bin; \
	$(QCT) fv-create firmware.fv -FvType SYS_FW FvUpdate.xml \
	    SYSFW_VERSION.bin ./bootbinaries; \
	$(QCT) update-json -j config.json -f SYS_FW \
	    -b SYSFW_VERSION.bin -pf firmware.fv \
	    -p $(CERTS)/QcFMPCert.pem \
	    -x $(CERTS)/QcFMPRoot.pub.pem \
	    -oc $(CERTS)/QcFMPSub.pub.pem \
	    -g $(FMP_GUID); \
	$(QCT) generate-capsule -e -j config.json -o capsule_file.cap \
	    --capflag PersistAcrossReset -v; \
	$(QCT) generate-capsule --dump-info capsule_file.cap
