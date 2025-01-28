# -*- coding: utf-8 -*-
"""Setup info for building QuadPype 4."""
import os
import re
import platform
import hashlib
from pathlib import Path
from typing import List

from cx_Freeze import setup, Executable
from sphinx.setup_command import BuildDoc

app_root = Path(os.path.dirname(__file__))


def validate_thirdparty_binaries():
    """Check the existence of third party executables."""
    low_platform = platform.system().lower()
    binary_vendors_dir = Path(os.environ["QUADPYPE_ROOT"]).joinpath("vendor", "bin")

    ext_list = [""]  # Add no extension (for linux)
    ext_list.extend(os.environ.get("PATHEXT", "").lower().split(os.pathsep))

    error_msg = (
        "Missing binary dependency {}. Please fetch thirdparty dependencies."
    )
    # Validate existence of FFMPEG
    ffmpeg_dir_path = binary_vendors_dir.joinpath("ffmpeg", low_platform)
    if low_platform == "windows":
        ffmpeg_dir_path = ffmpeg_dir_path.joinpath("bin")

    ffmpeg_binary_path = ffmpeg_dir_path.joinpath("ffmpeg")

    binary_exists = False
    for ext in ext_list:
        test_ffmpeg_binary_path = ffmpeg_binary_path.with_suffix(ext)
        if test_ffmpeg_binary_path.exists():
            binary_exists = True
            break
    if not binary_exists:
        raise RuntimeError(error_msg.format("FFMPEG"))

    # Validate existence of OpenImageIO (not on macOS)
    if low_platform == "darwin":
        return

    oiiotool_dir_path = binary_vendors_dir.joinpath("oiio", low_platform)
    if low_platform == "linux":
        oiiotool_dir_path = oiiotool_dir_path.joinpath("bin")

    oiiotool_binary_path = oiiotool_dir_path.joinpath("oiiotool")

    binary_exists = False
    for ext in ext_list:
        test_oiiotool_binary_path = oiiotool_binary_path.with_suffix(ext)
        if test_oiiotool_binary_path.exists():
            binary_exists = True
            break

    if not binary_exists:
        raise RuntimeError(error_msg.format("OpenImageIO"))


# Give the ability to skip the validation
if not os.getenv("SKIP_THIRD_PARTY_VALIDATION"):
    validate_thirdparty_binaries()

version = {}

with open(app_root / "quadpype" / "version.py") as fp:
    exec(fp.read(), version)

version_match = re.search(r"(\d+\.\d+.\d+).*", version["__version__"])
__version__ = version_match.group(1)

low_platform_name = platform.system().lower()
IS_WINDOWS = low_platform_name == "windows"
IS_LINUX = low_platform_name == "linux"
IS_MACOS = low_platform_name == "darwin"

base = None
if IS_WINDOWS:
    base = "Win32GUI"

# -----------------------------------------------------------------------
# build_exe
# Build options for cx_Freeze. Manually add/exclude packages and binaries

# In a perfect world, the install_requires should probably be the exact
# same as the poetry dependency list in pyproject.toml
install_requires = [
    "fastapi",
    "uvicorn",
    "appdirs",
    "cx_Freeze",
    "keyring",
    "clique",
    "jsonschema",
    "pathlib2",
    "pkg_resources",
    "PIL",
    "pymongo",
    "pynput",
    "jinxed",
    "blessed",
    "Qt",
    "qtpy",
    "speedcopy",
    "googleapiclient",
    "httplib2",
    # Harmony implementation
    "filecmp",
    "dns",
    # Python defaults (cx_Freeze skip them by default)
    "dbm",
    "sqlite3",
    "dataclasses",
    "timeit"
]

includes = []
# WARNING: As of cx_freeze there is a bug?
# when this is empty, its hooks will not kick in
# and won't clean platform irrelevant modules
# like dbm mentioned above.
excludes = [
    "quadpype"
]
bin_includes = [
    "vendor"
]
include_files = [
    "igniter",
    "quadpype",
    "../LICENSE",
    "../README.md"
]

if IS_WINDOWS:
    install_requires.extend([
        # `pywin32` packages
        "win32ctypes",
        "win32comext",
        "pythoncom"
    ])


icons_dir_path = app_root.resolve().joinpath("igniter", "resources", "icons")
icon_path = icons_dir_path.joinpath("quadpype.ico")
mac_icon_path = icons_dir_path.joinpath("quadpype.icns")

build_exe_options = dict(
    build_exe="build\exe_quadpype",
    packages=install_requires,
    includes=includes,
    excludes=excludes,
    bin_includes=bin_includes,
    include_files=include_files,
    optimize=0
)

bdist_mac_options = dict(
    bundle_name=f"QuadPype {__version__}",
    iconfile=mac_icon_path
)

executables = [
    Executable(
        "start.py",
        base=base,
        target_name="quadpype_gui",
        icon=icon_path.as_posix()
    ),
    Executable(
        "start.py",
        base=None,
        target_name="quadpype_console",
        icon=icon_path.as_posix()
    ),
]

if IS_LINUX:
    executables.append(
        Executable(
            "app_launcher.py",
            base=None,
            target_name="app_launcher",
            icon=icon_path.as_posix()
        )
    )

setup(
    name="QuadPype",
    version=__version__,
    description="Open-source pipeline solution for all of productions (2D, 3D, VFX, …).",
    cmdclass={"build_sphinx": BuildDoc},
    options={
        "build_exe": build_exe_options,
        "bdist_mac": bdist_mac_options,
        "build_sphinx": {
            "project": "QuadPype",
            "version": __version__,
            "release": __version__,
            "source_dir": (app_root / "docs" / "source").as_posix(),
            "build_dir": (app_root / "docs" / "build").as_posix()
        }
    },
    executables=executables,
    packages=[]
)


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


def _get_dir_files(dir_path: Path) -> List[Path]:
    dir_files = []
    for item in dir_path.iterdir():
        if item.name.startswith('.'):
            continue
        if item.is_dir():
            dir_files.extend(_get_dir_files(item))
        else:
            dir_files.append(item)
    return dir_files


def _get_included_files_list(included_paths: List[Path]) -> List[Path]:
    included_files = []
    for curr_path in included_paths:
        if curr_path.is_dir():
            included_files += _get_dir_files(curr_path)
        else:
            included_files.append(curr_path)

    return included_files


def generate_checksums_file(root_path, included_paths, dest_file_path):
    checksums = []

    included_files = _get_included_files_list(included_paths)
    for filepath in included_files:
        checksums.append(
            (
                sha256sum(sanitize_long_path(filepath.as_posix())),
                filepath.resolve().relative_to(root_path)
            )
        )

    # Write the output lines to the checksum file
    checksums_str = ""
    for checksum_tuple in checksums:
        file_str = checksum_tuple[1]
        if platform.system().lower() == "windows":
            file_str = checksum_tuple[1].as_posix().replace("\\", "/")
        checksums_str += "{}:{}\n".format(checksum_tuple[0], file_str)

    with open(dest_file_path, 'w', encoding='ascii') as f:
        f.write(checksums_str + "\n")
    print(f">>> Checksum Written to {dest_file_path}")


# Generate the checksums file
build_dir_path = app_root.joinpath(build_exe_options.get("build_exe"))
input_paths = [
    build_dir_path.joinpath("quadpype"),
    build_dir_path.joinpath("LICENSE")
]
checksum_file_path = build_dir_path.joinpath("checksums").resolve()
generate_checksums_file(build_dir_path, input_paths, checksum_file_path)
