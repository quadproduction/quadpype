# -*- coding: utf-8 -*-
"""Create QuadPype patch from current src."""
import click
import enlighten
from pathlib import Path

from appdirs import user_data_dir
from igniter.version_classes import create_package_manager,PackageHandler, PackageVersion, get_package
from zipfile import ZipFile

import tempfile
import logging
import os
import platform
import hashlib
import shutil

log = logging.getLogger(__name__)
manager = enlighten.get_manager()


@click.group(invoke_without_command=True)
@click.option("--version", required=True,
              help="Version of the software (e.g., 4.0.0)")
@click.option("--path", required=False,
              help="Destination path to place the patch zip archive",
              type=click.Path(exists=True))
def main(path, version):
    def _filter_dir(path, exclusion_list):
        """Recursively crawl over path and filter."""
        result = []
        for item in path.iterdir():
            if item.name in exclusion_list:
                continue
            if item.name.startswith('.'):
                continue
            if item.is_dir():
                result.extend(_filter_dir(item, exclusion_list))
            else:
                result.append(item)
        return result

    def _get_included_files_list(root_path: Path):
        included_files = []
        for item in ["quadpype", "LICENSE"]:
            item_fullpath = root_path.joinpath(item)
            if not item_fullpath.exists():
                continue

            if item_fullpath.is_dir():
                included_files += _filter_dir(item_fullpath, [".pyc", "__pycache__"])
            else:
                included_files.append(item_fullpath)

        return included_files

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

    out_dir_path = Path(user_data_dir("quadpype", "quad"))
    if path:
        out_dir_path = Path(path)
        if out_dir_path.is_file():
            out_dir_path = out_dir_path.parent

    print(f"Creating the patch zip archive in {out_dir_path} ...")
    package_manager = create_package_manager()
    quadpype_package = PackageHandler(
        pkg_name="quadpype",
        local_dir_path=Path(user_data_dir("quadpype", "quad")),
        remote_dir_path='',
        retrieve_locally=False,
        running_version_str=version,
        install_dir_path=os.getenv("QUADPYPE_ROOT")
    )
    package_manager.add_package(quadpype_package)
    installed_version = quadpype_package.running_version
    version_str = str(installed_version)
    repo_dir = installed_version.path

    if not version_str:
        log.error("QuadPype not found.")
        return

    # create destination directory
    destination_dir = out_dir_path / f"{installed_version.major}.{installed_version.minor}"  # noqa
    if not destination_dir.exists():
        destination_dir.mkdir(parents=True)

    # create zip inside temporary directory.
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_zip = Path(temp_dir) / f"quadpype-v{version_str}.zip"
        print(f"Creating zip: {temp_zip}")
        quadpype_root = repo_dir.resolve()
        included_files = _get_included_files_list(quadpype_root)

        with ZipFile(temp_zip, "w") as zip_file:
            checksums = []
            for file in included_files:
                checksums.append(
                    (
                        sha256sum(sanitize_long_path(file.as_posix())),
                        file.resolve().relative_to(quadpype_root)
                    )
                )
                zip_file.write(
                    file, file.resolve().relative_to(quadpype_root))

            checksums_str = ""
            for c in checksums:
                file_str = c[1]
                if platform.system().lower() == "windows":
                    file_str = c[1].as_posix().replace("\\", "/")
                checksums_str += "{}:{}\n".format(c[0], file_str)
            zip_file.writestr("checksums", checksums_str)
            # test if zip is ok
            zip_file.testzip()

        if not temp_zip.exists():
            log.error("Make archive failed.")
            return None

        # Move zip to data dir
        destination = destination_dir / temp_zip.name
        if destination.exists():
            log.warning(f"Destination file {destination} exists, removing.")
            try:
                destination.unlink()
            except Exception as e:
                log.error(str(e))
                return None
        if not destination_dir.exists():
            destination_dir.mkdir(parents=True)
        elif not destination_dir.is_dir():
            log.error("Destination exists but is not directory.")

        try:
            shutil.move(temp_zip.as_posix(), destination_dir.as_posix())
        except shutil.Error as e:
            log.error(str(e))

    version = PackageVersion(version=version_str, path=Path(destination))
    if not version:
        print("Error while creating the patch zip archive.")
        exit(1)

    print(f"Successfully created patch archive v{version}")


if __name__ == "__main__":
    main()
