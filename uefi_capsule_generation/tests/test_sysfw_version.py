# --------------------------------------------------------------------
# Copyright (c) 2026 Dezhen Lu
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

"""Tests for the paths SYSFW_VERSION_program reads and writes."""

import pytest

from qcom_capsule_tool.SYSFW_VERSION_program import The_Main


def generate(path, fw_version):
    The_Main(["-Gen", "-FwVer", fw_version, "-LFwVer", "0.0.0.0", "-O", str(path)])


@pytest.mark.parametrize("absolute", [False, True], ids=["relative", "absolute"])
def test_version_file_in_another_directory(tmp_path, monkeypatch, capsys, absolute):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "build").mkdir()
    path = tmp_path / "build" / "SYSFW_VERSION.bin"
    if not absolute:
        path = path.relative_to(tmp_path)
    # A version file from an earlier run in the working directory must not be
    # picked up in place of the requested one.
    generate("SYSFW_VERSION.bin", "0.0.1.1")

    generate(path, "0.0.1.2")
    assert (tmp_path / "build" / "SYSFW_VERSION.bin").is_file()

    capsys.readouterr()
    The_Main(["-GetFwVersionHex", str(path)])
    assert capsys.readouterr().out.strip() == "0x10002"
