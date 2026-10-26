# --------------------------------------------------------------------
# Copyright (c) 2026 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

"""An exception inside an FFS creation step must fail the run.

These helpers used to print the traceback and fall through to
``return True``, so the caller assembled an FV from a partial FFS list
and reported success.
"""

import os

from qcom_capsule_tool import FVCreation


def test_ec_fw_ffs_failure_is_reported(tmp_path, capsys):
    os.chdir(tmp_path)
    ls_ffs = []

    assert FVCreation.process_ec_fw_ffs_creation("does-not-exist.bin", ls_ffs) is False

    assert ls_ffs == []
    assert "FileNotFoundError" in capsys.readouterr().out
