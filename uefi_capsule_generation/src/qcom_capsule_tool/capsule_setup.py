# --------------------------------------------------------------------
# Copyright (c) 2025 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------


__prog__ = "Sync and build edk2"
__version__ = "1.0"
__description__ = (
    "Downloads the required files from github and builds"
    "required executables for linux/windows.\n"
)


import argparse
import os
import platform
import shutil
import subprocess
import traceback
from urllib.parse import urlparse

import requests


def _is_http_url(url):
    """Return True if `url` looks like a syntactically valid http(s) URL."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


edk2_branch = "master"
edk2_git_repo_sync_url = "https://github.com/tianocore/edk2.git"
edk2_pin_tag = "master"
generate_capsule_py_sync_url = (
    "https://raw.githubusercontent.com/tianocore"
    "/edk2/master/BaseTools/Source/Python"
    "/Capsule/GenerateCapsule.py"
)
basetools_common_sync_url = (
    "https://github.com/tianocore/edk2/tree/master/BaseTools/Source/Python/Common"
)
BROTLI_SUBMODULE_PATH = "BaseTools/Source/C/BrotliCompress/brotli"


def _clone_edk2_pinned(edk2_dir_path):
    """Shallow-clone edk2 at the pinned stable release tag."""
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            edk2_pin_tag,
            edk2_git_repo_sync_url,
            edk2_dir_path,
        ],
        check=True,
    )


###
# Linux functions #
###


def _make_env():
    """Return env for invoking edk2 BaseTools `make`.

    Two things need to be fixed up for MSYS2 builds:

    1. edk2's GNUmakefile checks `OS=Windows_NT` (which MSYS2 inherits
       from Windows) and, when matched, forces `SHELL := cmd.exe` and
       switches to nmake-style cmd recipes. Clearing OS makes the
       makefile take the POSIX path so recipes run under MSYS2's bash.

    2. edk2's HOST_ARCH autodetection also branches on OS=Windows and
       uses cmd-style `if defined ...` syntax that fails under sh. Pass
       HOST_ARCH explicitly so the autodetection block is skipped.
    """
    env = os.environ.copy()
    if platform.system() == "Windows":
        env.pop("OS", None)
        if "HOST_ARCH" not in env:
            machine = platform.machine().lower()
            env["HOST_ARCH"] = "AARCH64" if machine in ("aarch64", "arm64") else "X64"
    return env


def run_make_command_linux(edk2_dir_path):

    if not os.path.exists(edk2_dir_path) or not os.path.isdir(edk2_dir_path):
        print(f"\n\nDirectory '{edk2_dir_path}' does not exist.\n\n")
        return f"Directory '{edk2_dir_path}' does not exist."

    base_dir = os.getcwd()

    try:
        os.chdir(edk2_dir_path)
        subprocess.run(["make"], check=True, env=_make_env())
    except Exception:
        print("\n", traceback.format_exc())
        print("\nFailed to build edk2\n\n")
        return "Failed to build edk2"

    print(f"'make' command executed successfully in {edk2_dir_path}")
    os.chdir(base_dir)
    return True


def init_brotli_submodule(edk2_dir_path):
    """Initialize only the brotli submodule needed by the BaseTools C build."""

    if not os.path.exists(edk2_dir_path):
        print(f"\n\nDirectory '{edk2_dir_path}' does not exist\n\n")
        return f"Directory '{edk2_dir_path}' does not exist"

    base_dir = os.getcwd()
    os.chdir(edk2_dir_path)

    try:
        subprocess.run(
            [
                "git",
                "submodule",
                "update",
                "--init",
                "--depth",
                "1",
                BROTLI_SUBMODULE_PATH,
            ],
            check=True,
        )
    except Exception:
        print("\n\nFailed initializing brotli submodule\n\n")
        print(traceback.format_exc())
        return "Failed initializing brotli submodule"

    os.chdir(base_dir)
    print("brotli submodule initialization done")
    return True


def print_header_sync_edk2_linux(clone_dir):
    print("\n\n\n")
    print("Copying edk2")
    print(
        "--------------------------------------------------------------"
        "------------------------------------"
    )
    print(f"Github URL: {edk2_git_repo_sync_url}")
    print(f"Clone local path: {clone_dir}")
    print(
        "--------------------------------------------------------------"
        "------------------------------------"
    )
    print("\n\n")


def sync_edk2_linux(edk2_git_repo_sync_url, edk2_dir_path):

    if os.path.exists(edk2_dir_path) and os.path.isdir(edk2_dir_path):
        print(f"Directory '{edk2_dir_path}' already esists")
        return f"Directory '{edk2_dir_path}' already esists"

    print_header_sync_edk2_linux(edk2_dir_path)

    try:
        _clone_edk2_pinned(edk2_dir_path)
        print(f"Repository cloned into {edk2_dir_path} at {edk2_pin_tag}")

    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e}")
        return "Error cloning repository"

    if init_brotli_submodule(edk2_dir_path) is not True:
        print("Failed to init brotli submodule")
        return "Failed to init brotli submodule"

    return True


def sync_and_build_edk2_linux(edk2_dir_path, c_dir):

    if platform.system() in ("Linux", "Darwin"):
        edk2_get_repo_sync_stats = sync_edk2_linux(
            edk2_git_repo_sync_url, edk2_dir_path
        )
        if edk2_get_repo_sync_stats is not True:
            return edk2_get_repo_sync_stats

        edk2_build_stats = run_make_command_linux(c_dir)

        if edk2_build_stats is not True:
            return edk2_build_stats

    return True


###
# Windows functions #
###


def sync_edk2_win(clone_dir):
    """Clone edk2 on Windows using POSIX git via MSYS2/git-for-windows."""

    if os.path.exists(clone_dir):
        print("\n\nedk2 found\n\n")
        return "edk2 found"

    print_header_sync_edk2_linux(clone_dir)

    if not _is_http_url(edk2_git_repo_sync_url):
        print(f"Invalid URL: {edk2_git_repo_sync_url}")
        return f"Invalid URL: {edk2_git_repo_sync_url}"

    try:
        _clone_edk2_pinned(clone_dir)
        print(f"\n\n\nEdk2 cloning complete at {edk2_pin_tag}\n\n")
    except Exception:
        print("\n", traceback.format_exc())
        print("\nFailed to sync edk2 from github\n\n")
        return "Failed to sync edk2 from github"

    return True


def sync_and_build_edk2_win(clone_dir, full_build):
    """Sync and build edk2 BaseTools C on Windows via MSYS2 (make + gcc)."""

    if platform.system() == "Windows":
        edk2_get_repo_sync_stats = sync_edk2_win(clone_dir)
        if edk2_get_repo_sync_stats is not True:
            return edk2_get_repo_sync_stats

        if init_brotli_submodule(clone_dir) is not True:
            return "Failed to init brotli submodule"

        c_dir = os.path.join(clone_dir, "BaseTools", "Source", "C")
        edk2_build_stats = run_make_command_linux(c_dir)
        if edk2_build_stats is not True:
            return edk2_build_stats

    return True


###
# Common functions #
###


def force_delete_folder(folder_path):

    if platform.system() == "Windows":
        try:
            subprocess.run(["rmdir", "/S", "/Q", folder_path], check=True, shell=True)
            print(f"Folder deleted successfully: {folder_path}")

        except Exception as e:
            print(f"Failed to delete Dir {folder_path}")
            print(e)

    if platform.system() in ("Linux", "Darwin"):
        try:
            shutil.rmtree(folder_path)
            print(f"Dir deleted successfully: {folder_path}")

        except Exception as e:
            print(f"Failed to delete Dir {folder_path}")
            print(e)


def del_file(file_path):
    try:
        os.remove(file_path)
        print(f"File deleted successfully: {file_path}")

    except Exception:
        print(f"Failed to delete file: {file_path}")
        print(traceback.format_exc())


def print_header_sync_generate_capsule_py(generate_capsule_py_file_path_abs):
    print("\n\n\n")
    print("Copying GenerateCapsule.py")
    print(
        "--------------------------------------------------------------"
        "------------------------------------"
    )
    print(f"Github URL: {generate_capsule_py_sync_url}")
    print(f"Clone local path: {generate_capsule_py_file_path_abs}")
    print(
        "--------------------------------------------------------------"
        "------------------------------------"
    )
    print("\n\n")


def sync_generate_capsule_py(
    generate_capsule_py_sync_url, generate_capsule_py_file_path_abs
):

    if os.path.exists(generate_capsule_py_file_path_abs):
        print("\n\nGenerateCapsule.py  found\n\n")
        return "GenerateCapsule.py  found"

    print_header_sync_generate_capsule_py(generate_capsule_py_file_path_abs)

    if not _is_http_url(generate_capsule_py_sync_url):
        print(f"Invalid URL: {generate_capsule_py_sync_url}")
        print("Terminated copying GenerateCapsule.py")
        return f"Invalid URL: {generate_capsule_py_sync_url}"

    try:
        response = requests.get(generate_capsule_py_sync_url)
        if response.status_code == 200:
            with open(generate_capsule_py_file_path_abs, "wb") as file:
                file.write(response.content)
            print("GenerateCapsule.py File downloaded successfully\n\n")
    except Exception:
        print(traceback.format_exc())
        print("\nFailed to download file\n\n")
        return "Failed to download file"
    return True


def copy_GenFv(base_dir_abs, genfv_path_win, genfv_local_path_abs):

    if os.path.exists(genfv_local_path_abs):
        print("\n\nGenFv.exe  found\n\n")
        return "GenFv.exe  found"

    try:
        shutil.copy(genfv_path_win, base_dir_abs)
        print(f"Copied {genfv_path_win} to {base_dir_abs}")
    except Exception:
        print(
            f"\n\nFailed to copy GenFv.exe from {genfv_path_win} to {base_dir_abs}\n\n"
        )
        print(traceback.format_exc())
        return f"Failed to copy GenFv.exe from {genfv_path_win} to {base_dir_abs}"

    return True


def copy_GenFfs(base_dir_abs, genffs_path_win, genffs_local_path_abs):

    if os.path.exists(genffs_local_path_abs):
        print("\n\nGenFfs.exe  found\n\n")
        return "GenFfs.exe  found"

    try:
        shutil.copy(genffs_path_win, base_dir_abs)
        print(f"Copied {genffs_path_win} to {base_dir_abs}")
    except Exception:
        print(
            f"\n\nFailed to copy GenFv.exe from {genffs_path_win} to {base_dir_abs}\n\n"
        )
        print(traceback.format_exc())
        return f"Failed to copy GenFv.exe from {genffs_path_win} to {base_dir_abs}"

    return True


def print_header_sync_common_dir(branch, common_dir, local_path, Common_dir_path):
    print("\n\n\n")
    print("Copying common dir")
    print(
        "--------------------------------------------------------------"
        "------------------------------------"
    )
    print(f"Github URL: {edk2_git_repo_sync_url}")
    print(f"Branch: {branch}")
    print(f"Clone local path: {Common_dir_path}")
    print(f"Local temp working path: {local_path}")
    print(f"Final copy path: {common_dir}")
    print(
        "--------------------------------------------------------------"
        "------------------------------------"
    )
    print("\n\n")


def sync_single_dir(edk2_git_repo_sync_url, branch, target_dir, local_path):

    if not os.path.exists(local_path):
        os.makedirs(local_path)

    try:
        subprocess.run(["git", "init"], cwd=local_path)
        subprocess.run(
            ["git", "remote", "add", "origin", edk2_git_repo_sync_url], cwd=local_path
        )
        subprocess.run(["git", "config", "core.sparseCheckout", "true"], cwd=local_path)

        sparse_checkout_file = os.path.join(
            local_path, ".git", "info", "sparse-checkout"
        )
        print(f"\n\nsparse_checkout_file: {sparse_checkout_file}\n\n")
        if not os.path.exists(os.path.join(local_path, ".git", "info")):
            os.mkdir(os.path.join(local_path, ".git", "info"))
        with open(sparse_checkout_file, "w") as f:
            f.write("%s/\n" % (target_dir))

        subprocess.run(["git", "pull", "origin", branch], cwd=local_path)
    except Exception:
        print("Failed to sync common dir")
        print(traceback.format_exc())
        return "Failed to sync common dir"

    return True


def sync_common_dir(base_dir_abs, common_dir_local_sync_path_abs):

    temp_local_working_dir_path = os.path.join(base_dir_abs, "Common_sync")
    Common_dir_path = os.path.join(
        temp_local_working_dir_path, "BaseTools", "Source", "Python", "Common"
    )

    if os.path.exists(common_dir_local_sync_path_abs):
        print("\n\nCommon dir found\n\n")
        return "Common dir found"

    print_header_sync_common_dir(
        edk2_branch,
        common_dir_local_sync_path_abs,
        temp_local_working_dir_path,
        Common_dir_path,
    )

    try:
        sync_single_dir(
            edk2_git_repo_sync_url,
            edk2_branch,
            target_dir="BaseTools/Source/Python/Common",
            local_path=temp_local_working_dir_path,
        )
        print("\n\nCompleted common folder sync\n\n")
    except Exception:
        print("\n", traceback.format_exc())
        print("\nFailed to sync common dir from github\n\n")
        return "Failed to sync common dir from github"

    shutil.copytree(Common_dir_path, common_dir_local_sync_path_abs)

    if os.path.exists(temp_local_working_dir_path):
        force_delete_folder(temp_local_working_dir_path)

    return True


def clean_build(
    clean_build,
    generate_capsule_py_file_path_abs,
    edk2_sync_local_path_abs,
    genffs_path_abs,
    genfv_path_abs,
    common_dir_local_sync_path_abs,
):

    if not clean_build:
        return True
    print("Clean build enabled")

    if os.path.exists(generate_capsule_py_file_path_abs):
        del_file(generate_capsule_py_file_path_abs)
    else:
        print(f"File not found: {generate_capsule_py_file_path_abs}, skipping delete")

    if os.path.exists(edk2_sync_local_path_abs):
        force_delete_folder(edk2_sync_local_path_abs)
    else:
        print(f"Dir not found: {edk2_sync_local_path_abs}, skipping delete")

    if os.path.exists(genffs_path_abs):
        del_file(genffs_path_abs)
    else:
        print(f"File not found: {genffs_path_abs}, skipping delete")

    if os.path.exists(genfv_path_abs):
        del_file(genfv_path_abs)
    else:
        print(f"File not found: {genfv_path_abs}, skipping delete")

    if os.path.exists(common_dir_local_sync_path_abs):
        force_delete_folder(common_dir_local_sync_path_abs)
    else:
        print(f"Dir not found: {common_dir_local_sync_path_abs}, skipping delete")

    return True


def print_stats(
    sync_generate_capsule_py_stats,
    sync_and_build_edk2_win_stats,
    copy_GenFfs_win_stats,
    copy_GenFv_win_stats,
    sync_common_dir_stats,
):

    print("\n\n\n")
    print("Capsule setup status:")
    print(
        "--------------------------------------------------------------"
        "------------------------------------"
    )

    if sync_generate_capsule_py_stats is True:
        print("Downloaded GenerateCapsule.py successfully")
    else:
        print(
            f"Downloading GenerateCapsule.py failed: {sync_generate_capsule_py_stats}"
        )

    if sync_and_build_edk2_win_stats is True:
        print("Downloaded and Built EDK2 successfully")
    else:
        print(f"Downloading and Building EDK2 failed: {sync_and_build_edk2_win_stats}")

    if copy_GenFfs_win_stats is True:
        print("Copied GenFfs successfully")
    else:
        print(f"Copying GenFfs failed: {copy_GenFfs_win_stats}")

    if copy_GenFv_win_stats is True:
        print("Copied GenFv successfully")
    else:
        print(f"Copying GenFv failed: {copy_GenFv_win_stats}")

    if sync_common_dir_stats is True:
        print("Downloaded Common directory successfully")
    else:
        print(f"Downloading Common directory failed: {sync_common_dir_stats}")
    print(
        "--------------------------------------------------------------"
        "------------------------------------"
    )
    print("\n\n")


def Main(args):

    if platform.system() in ("Linux", "Darwin"):
        base_dir_abs = os.getcwd()
        generate_capsule_py_file_path_abs = os.path.join(
            base_dir_abs, "GenerateCapsule.py"
        )
        edk2_sync_local_path_abs = os.path.join(base_dir_abs, "edk2")
        c_dir = os.path.join(edk2_sync_local_path_abs, "BaseTools", "Source", "C")
        genffs_sync_path_linux_abs = os.path.join(c_dir, "bin", "GenFfs")
        genfv_sync_path_linux_abs = os.path.join(c_dir, "bin", "GenFv")
        genffs_local_path_abs = os.path.join(base_dir_abs, "GenFfs")
        genfv_local_path_abs = os.path.join(base_dir_abs, "GenFv")
        common_dir_local_sync_path_abs = os.path.join(base_dir_abs, "Common")

        clean_build(
            args.clean_build,
            generate_capsule_py_file_path_abs,
            edk2_sync_local_path_abs,
            genffs_local_path_abs,
            genfv_local_path_abs,
            common_dir_local_sync_path_abs,
        )

        sync_generate_capsule_py_stats = sync_generate_capsule_py(
            generate_capsule_py_sync_url, generate_capsule_py_file_path_abs
        )
        sync_and_build_edk2_win_stats = sync_and_build_edk2_linux(
            edk2_sync_local_path_abs, c_dir
        )
        copy_GenFfs_win_stats = copy_GenFfs(
            base_dir_abs, genffs_sync_path_linux_abs, genffs_local_path_abs
        )
        copy_GenFv_win_stats = copy_GenFv(
            base_dir_abs, genfv_sync_path_linux_abs, genfv_local_path_abs
        )
        sync_common_dir_stats = sync_common_dir(
            base_dir_abs, common_dir_local_sync_path_abs
        )

        print_stats(
            sync_generate_capsule_py_stats,
            sync_and_build_edk2_win_stats,
            copy_GenFfs_win_stats,
            copy_GenFv_win_stats,
            sync_common_dir_stats,
        )

    if platform.system() == "Windows":
        base_dir_abs = os.getcwd()
        generate_capsule_py_file_path_abs = os.path.join(
            base_dir_abs, "GenerateCapsule.py"
        )
        edk2_sync_local_path_abs = os.path.join(base_dir_abs, "edk2")
        c_dir = os.path.join(edk2_sync_local_path_abs, "BaseTools", "Source", "C")
        genffs_sync_path_win_abs = os.path.join(c_dir, "bin", "GenFfs.exe")
        genfv_sync_path_win_abs = os.path.join(c_dir, "bin", "GenFv.exe")
        genffs_local_path_abs = os.path.join(base_dir_abs, "GenFfs.exe")
        genfv_local_path_abs = os.path.join(base_dir_abs, "GenFv.exe")
        common_dir_local_sync_path_abs = os.path.join(base_dir_abs, "Common")

        clean_build(
            args.clean_build,
            generate_capsule_py_file_path_abs,
            edk2_sync_local_path_abs,
            genffs_local_path_abs,
            genfv_local_path_abs,
            common_dir_local_sync_path_abs,
        )

        sync_generate_capsule_py_stats = sync_generate_capsule_py(
            generate_capsule_py_sync_url, generate_capsule_py_file_path_abs
        )

        sync_and_build_edk2_win_stats = sync_and_build_edk2_win(
            edk2_sync_local_path_abs, args.full_build
        )

        copy_GenFfs_win_stats = copy_GenFfs(
            base_dir_abs, genffs_sync_path_win_abs, genffs_local_path_abs
        )

        copy_GenFv_win_stats = copy_GenFv(
            base_dir_abs, genfv_sync_path_win_abs, genfv_local_path_abs
        )

        sync_common_dir_stats = sync_common_dir(
            base_dir_abs, common_dir_local_sync_path_abs
        )

        print_stats(
            sync_generate_capsule_py_stats,
            sync_and_build_edk2_win_stats,
            copy_GenFfs_win_stats,
            copy_GenFv_win_stats,
            sync_common_dir_stats,
        )


def main():
    parser = argparse.ArgumentParser(
        prog=__prog__,
        description="VERSION: " + __version__ + ", " + __description__,
        conflict_handler="resolve",
    )

    parser.add_argument(
        "-c",
        "--clean_build",
        dest="clean_build",
        default=False,
        help="If set to 'True', "
        "deletes any existing folders/files "
        "and download again. Default - 'False'",
    )

    parser.add_argument(
        "-f",
        "--full_build",
        dest="full_build",
        default=False,
        help="If set to 'True', "
        "downloads additional submodules "
        "for a full edk2 build. "
        "These submodules and full build are not "
        "required for capsule update. Default - 'False'",
    )

    args = parser.parse_args()
    Main(args)


if __name__ == "__main__":
    main()
