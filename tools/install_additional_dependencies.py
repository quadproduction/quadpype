# -*- coding: utf-8 -*-
"""Install runtime python modules required by QuadPype.

Those should be defined in `pyproject.toml` in QuadPype sources root.
"""

import os
import shutil
import sys
import platform
import hashlib
import time
import subprocess
from pathlib import Path

import toml
import enlighten
import blessed

# Imports for the install_thirdparty function:
from urllib.parse import urlparse
import requests
import tempfile
import math
import tarfile
import zipfile


term = blessed.Terminal()
manager = enlighten.get_manager()
hash_buffer_size = 65536


def sha256_sum(filename: Path):
    """Calculate sha256 hash for the given file.

    Args:
        filename (Path): path to file.

    Returns:
        str: hex hash.

    """
    _hash = hashlib.sha256()
    with open(filename, 'rb', buffering=0) as f:
        buffer = bytearray(128 * 1024)
        mv = memoryview(buffer)
        for n in iter(lambda: f.readinto(mv), 0):
            _hash.update(mv[:n])
    return _hash.hexdigest()


def _print(msg: str, message_type: int = 0) -> None:
    """Print message to console.

    Args:
        msg (str): message to print
        message_type (int): type of message (0 info, 1 error, 2 note)

    """
    if message_type == 0:
        header = term.aquamarine3(">>> ")
    elif message_type == 1:
        header = term.orangered2("!!! ")
    elif message_type == 2:
        header = term.tan1("... ")
    else:
        header = term.darkolivegreen3("--- ")

    print(f"{header}{msg}")


def _pip_install(python_vendor_dir, package, version=None):
    arg = None
    if package and version:
        arg = f"{package}=={version}"
    elif package:
        arg = package

    if not arg:
        _print("Couldn't find package to install")
        sys.exit(1)

    _print(f"We'll install {arg}")

    try:
        subprocess.run(
            [
                sys.executable,
                "-m", "pip",
                "install",
                "--upgrade", arg,
                "-t", str(python_vendor_dir)
            ],
            check=True,
            stdout=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError as e:
        _print(f"Error during {package} installation.", 1)
        _print(str(e), 1)
        sys.exit(1)


def install_qtbinding(
    pyproject, python_vendor_dir, platform_name, use_pyside2
):
    _print("Install Qt binding framework ...")

    qt_variants = []
    if use_pyside2:
        qt_variants.append("pyside2")

    # Use QT_BINDING environment variable if set
    # - existence is not validate, if does not exists it is just skipped
    qt_package = os.getenv("QT_BINDING")
    if qt_package:
        qt_variants.append(qt_package)

    # Special handling for specific distro (e.g. centos7 and rocky8)
    if platform_name == "linux":
        import distro

        qt_variants.append(f"{distro.id()}{distro.major_version()}")

    qt_binding_options = pyproject["quadpype"]["qtbinding"]
    qtbinding_def = None
    for qt_variant in qt_variants:
        qtbinding_def = qt_binding_options.get(qt_variant)
        if qtbinding_def:
            break

    # Use platform default Qt binding
    if not qtbinding_def:
        qtbinding_def = pyproject["quadpype"]["qtbinding"][platform_name]

    package = qtbinding_def["package"]
    version = qtbinding_def.get("version")

    _pip_install(python_vendor_dir, package, version)

    # Remove libraries for QtSql which don't have available libraries
    #   by default and Postgre library would require to modify rpath of
    #   dependency
    if platform_name == "darwin":
        sqldrivers_dir = (
            python_vendor_dir / package / "Qt" / "plugins" / "sqldrivers"
        )
        for filepath in sqldrivers_dir.iterdir():
            os.remove(str(filepath))


def install_runtime_dependencies(pyproject, python_vendor_dir):
    _print("Installing Runtime Dependencies ...")
    runtime_deps = (
        pyproject
        .get("quadpype", {})
        .get("runtime", {})
        .get("deps", {})
    )
    for package, version in runtime_deps.items():
        _pip_install(python_vendor_dir, package, version)


def install_thirdparty(pyproject, platform_name):
    _print("Processing third-party dependencies ...")

    quadpype_root = Path(os.path.dirname(__file__)).parent

    thirdparty = (
        pyproject
        .get("quadpype", {})
        .get("thirdparty", {})
    )

    for k, v in thirdparty.items():
        _print(f"processing {k}")
        destination_path = quadpype_root / "vendor" / "bin" / k

        if not v.get(platform_name):
            _print(("No definition for current "
                    f"platform [ {platform_name} ]"), 2)
            _print("trying to get universal url for all platforms")
            url = v.get("url")
            if not url:
                _print("cannot get url for all platforms", 1)
                _print((f"Warning: {k} cannot be installed for current platform "
                       "and it might be missing in the build"), 1)
                continue
        else:
            url = v.get(platform_name).get("url")
            destination_path = destination_path / platform_name

        parsed_url = urlparse(url)

        # check if the file is already extracted in /vendor/bin
        if destination_path.exists():
            _print("destination path already exists, deleting ...", 2)
            if destination_path.is_dir():
                try:
                    shutil.rmtree(destination_path)
                except OSError as e:
                    _print("cannot delete folder.", 1)
                    raise SystemExit(e)

        # download file
        _print(f"Downloading {url} ...")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = Path(temp_dir) / Path(parsed_url.path).name

            r = requests.get(url, stream=True)
            content_len = int(r.headers.get('Content-Length', '0')) or None
            with manager.counter(
                color='green',
                total=content_len and math.ceil(content_len / 2 ** 20),
                unit='MiB',
                leave=False
            ) as counter:
                with open(temp_file, 'wb', buffering=2 ** 24) as file_handle:
                    for chunk in r.iter_content(chunk_size=2 ** 20):
                        file_handle.write(chunk)
                        counter.update()

            # Compute the file checksum
            _print("Calculating sha256 ...", 2)
            calc_checksum = sha256_sum(temp_file)

            if v.get(platform_name):
                item_hash = v.get(platform_name).get("hash")
            else:
                item_hash = v.get("hash")

            if item_hash != calc_checksum:
                _print("Downloaded files checksum invalid.")
                sys.exit(1)

            _print("File OK", 3)
            if not destination_path.exists():
                destination_path.mkdir(parents=True)

            # Extract to destination
            archive_type = temp_file.suffix.lstrip(".")
            _print(f"Extracting {archive_type} file to {destination_path}")
            if archive_type in ['zip']:
                zip_file = zipfile.ZipFile(temp_file)
                zip_file.extractall(destination_path)
                zip_file.close()
            elif archive_type in [
                'tar', 'tgz', 'tar.gz', 'tar.xz', 'tar.bz2'
            ]:
                if archive_type == 'tar':
                    tar_type = 'r:'
                elif archive_type.endswith('xz'):
                    tar_type = 'r:xz'
                elif archive_type.endswith('gz'):
                    tar_type = 'r:gz'
                elif archive_type.endswith('bz2'):
                    tar_type = 'r:bz2'
                else:
                    tar_type = 'r:*'
                try:
                    tar_file = tarfile.open(temp_file, tar_type)
                except tarfile.ReadError:
                    raise SystemExit("corrupted archive")
                tar_file.extractall(destination_path)
                tar_file.close()

            _print("Extraction OK", 3)


def main():
    start_time = time.time_ns()
    repo_root = Path(os.path.dirname(__file__)).parent
    python_vendor_dir = repo_root / "vendor" / "python"
    if python_vendor_dir.exists():
        _print("Removing existing vendor directory")
        shutil.rmtree(python_vendor_dir)
    python_vendor_dir.mkdir(parents=True, exist_ok=True)
    pyproject = toml.load(repo_root / "pyproject.toml")
    platform_name = platform.system().lower()
    use_pyside2 = "--use-pyside2" in sys.argv

    install_qtbinding(
        pyproject, python_vendor_dir, platform_name, use_pyside2
    )
    install_runtime_dependencies(pyproject, python_vendor_dir)
    install_thirdparty(pyproject, platform_name)
    end_time = time.time_ns()
    total_time = (end_time - start_time) / 1000000000
    _print(f"Downloading and extracting took {total_time} secs.")


if __name__ == "__main__":
    main()
