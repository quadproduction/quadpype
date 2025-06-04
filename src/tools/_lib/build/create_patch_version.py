# -*- coding: utf-8 -*-
"""Create QuadPype patch version from current src."""
import os
import re
import shutil
import hashlib
import platform
import tempfile

from typing import Union, List
from zipfile import ZipFile

import click
import blessed
import enlighten
import semver
from pathlib import Path

from appdirs import user_data_dir


term = blessed.Terminal()

INCLUSION_LIST = [
    "quadpype"
]
EXCLUSION_LIST = [
    ".pyc",
    "__pycache__"
]


def _print(msg: str, msg_type: int = 0) -> None:
    """Print message to console.

    Args:
        msg (str): message to print
        msg_type (int): type of message (0 info, 1 error, 2 note)

    """
    if msg_type == 0:
        header = term.aquamarine3(">>> ")
    elif msg_type == 1:
        header = term.orangered2("!!! ")
    elif msg_type == 2:
        header = term.tan1("... ")
    elif msg_type == 3:
        header = term.gold("*** ")
    else:
        header = term.darkolivegreen3("--- ")

    print(f"{header}{msg}")


def sha256sum(filename):
    """Calculate sha256 for content of the file.

    Args:
         filename (str): Path to file.

    Returns:
        str: hex encoded sha256

    """
    h = hashlib.sha256()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()


def sanitize_long_path(path):
    """Sanitize long paths (260 characters) when on Windows.

    Long paths are not capable with ZipFile or reading a file, so we can
    shorten the path to use.

    Args:
        path (str): path to either directory or file.

    Returns:
        str: sanitized path
    """
    if platform.system().lower() != "windows":
        return path
    path = os.path.abspath(path)

    if path.startswith("\\\\"):
        path = "\\\\?\\UNC\\" + path[2:]
    else:
        path = "\\\\?\\" + path
    return path


def filter_dir(path: Path, exclusion_list: List) -> List[Path]:
    """Recursively crawl over path and filter."""
    result = []
    for item in path.iterdir():
        if item.name in exclusion_list:
            continue
        if item.name.startswith('.'):
            continue
        if item.is_dir():
            result.extend(filter_dir(item, exclusion_list))
        else:
            result.append(item)
    return result


def get_included_files_list(root_path: Path) -> List[Path]:
    included_files = []
    for item in INCLUSION_LIST:
        item_fullpath = root_path.joinpath(item)
        if not item_fullpath.exists():
            continue

        if item_fullpath.is_dir():
            included_files += filter_dir(item_fullpath, EXCLUSION_LIST)
        else:
            included_files.append(item_fullpath)

    return included_files


def create_quadpype_zip(zip_path: Path, quadpype_path: Path) -> None:
    """Pack repositories and QuadPype into zip.

    We are using :mod:`ZipFile` instead :meth:`shutil.make_archive`
    because we need to decide what file and directories to include in zip
    and what not. They are determined by :attr:`exclusion_list` on file level
    and :attr:`inclusion_list` on top level directory in QuadPype
    repository.

    Args:
        zip_path (Path): Path to zip file.
        quadpype_path (Path): Path to QuadPype sources.

    """
    quadpype_root = quadpype_path.resolve()
    included_files = get_included_files_list(quadpype_root)

    # Progress bar: adding 2 to the total for the checksum and test zip operations
    progress_bar_total =  len(included_files) + 2

    progress_bar = enlighten.Counter(
        total=progress_bar_total, desc="QuadPype Patch Creation", units="Files", color="green")

    with ZipFile(zip_path, "w") as zip_file:
        checksums = []

        file: Path
        for file in included_files:
            # Compute the checksum
            checksums.append(
                (
                    sha256sum(sanitize_long_path(file.as_posix())),
                    file.resolve().relative_to(quadpype_root)
                )
            )

            # Add the file in the archive
            zip_file.write(
                file, file.resolve().relative_to(quadpype_root))
            progress_bar.update()

        # Add License file
        zip_file.write(quadpype_root.parent / "LICENSE", "LICENSE")

        checksums_str = ""
        for c in checksums:
            file_str = c[1]
            if platform.system().lower() == "windows":
                file_str = c[1].as_posix().replace("\\", "/")
            checksums_str += "{}:{}\n".format(c[0], file_str)
        zip_file.writestr("checksums", checksums_str)
        progress_bar.update()

        # Test if zip is ok
        zip_file.testzip()

        progress_bar.close(clear=True)


def move_zip_to_dir(zip_file, out_dir_path) -> Union[None, Path]:
    """Move zip with QuadPype version to user data directory.

    Args:
        zip_file (Path): Path to zip file.

    Returns:
        None if move fails.
        Path to moved zip on success.

    """
    zip_dest_path = Path(out_dir_path).joinpath(zip_file.name)
    if zip_dest_path.exists():
        _print(f"Destination ZIP file {zip_dest_path} exists, removing.", 3)
        try:
            zip_dest_path.unlink()
        except Exception as e:  # noqa
            _print(str(e), 1)
            return None

    out_dir_path.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(zip_file.as_posix(), out_dir_path.as_posix())
    except shutil.Error as e:
        _print(str(e), 1)


def create_version_from_live_code(out_dir_path):
    # Determine source directory and current version
    src_root = Path(__file__)
    while (src_root.parts[-1]) != "src":
        src_root = src_root.parent
    src_root.resolve()

    version = {}
    with open(src_root.joinpath("quadpype", "version.py")) as fp:
        exec(fp.read(), version)
    version_match = re.search(r"(\d+\.\d+.\d+.*)", version["__version__"])
    version_str = version_match[1]
    version_obj = semver.VersionInfo.parse(version_str)

    # Ensure the output directory path point to the correct subfolder (if needed)
    correct_subfolder_name = f"{version_obj.major}.{version_obj.minor}"
    if out_dir_path.name != correct_subfolder_name:
        out_dir_path = out_dir_path.joinpath(correct_subfolder_name)

    # create zip inside temporary directory.
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_zip = Path(temp_dir) / f"quadpype-v{version_str}.zip"
        _print(f"Creating zip: {temp_zip}")

        create_quadpype_zip(temp_zip, src_root)
        if not os.path.exists(temp_zip):
            _print("Make archive failed.", 1)
            return None

        move_zip_to_dir(temp_zip, out_dir_path)

    return semver.VersionInfo.parse(version=version_str)


@click.group(invoke_without_command=True)
@click.option("--path", required=False,
              help="Destination path to place the patch zip archive",
              type=click.Path(exists=True))
def main(path):
    # Create ZIP file of the current version
    if path:
        out_dir_path = Path(path)
        if out_dir_path.is_file():
            out_dir_path = out_dir_path.parent
    else:
        out_dir_path = Path(user_data_dir("quadpype", "quad"))

    _print(f"Creating the patch zip archive in {out_dir_path} ...")
    version = create_version_from_live_code(out_dir_path)

    if not version:
        _print("Error while creating the patch zip archive.", 1)
        exit(1)

    _print(f"Successfully created patch archive v{version}")


if __name__ == "__main__":
    main()
