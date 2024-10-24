import os
import re
import logging
import platform
import sys
import ctypes
from pathlib import Path
from ctypes import wintypes

import clique

log = logging.getLogger(__name__)


def format_file_size(file_size, suffix=None):
    """Returns formatted string with size in the appropriate unit.

    Args:
        file_size (int): Size of the file in bytes.
        suffix (str): Suffix for formatted size. Default is 'B' (as bytes).

    Returns:
        str: Formatted size using proper unit and passed suffix (e.g. 7 MiB).
    """

    if suffix is None:
        suffix = "B"

    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(file_size) < 1024.0:
            return "%3.1f%s%s" % (file_size, unit, suffix)
        file_size /= 1024.0
    return "%.1f%s%s" % (file_size, "Yi", suffix)


def create_hardlink(src_path, dst_path):
    """Create hardlink of file.

    Args:
        src_path(str): Full path to a file which is used as source for
            hardlink.
        dst_path(str): Full path to a file where a link of source will be
            added.
    """
    # Use `os.link` if is available
    #   - should be for all platforms with newer python versions
    if hasattr(os, "link"):
        os.link(src_path, dst_path)
        return

    # Windows implementation of hardlinks
    #   - used in Python 2
    if platform.system().lower() == "windows":
        import ctypes
        from ctypes.wintypes import BOOL
        CreateHardLink = ctypes.windll.kernel32.CreateHardLinkW
        CreateHardLink.argtypes = [
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p
        ]
        CreateHardLink.restype = BOOL

        res = CreateHardLink(dst_path, src_path, None)
        if res == 0:
            raise ctypes.WinError()
        return
    # Raises not implemented error if gets here
    raise NotImplementedError(
        "Implementation of hardlink for current environment is missing."
    )


def create_symlink(src_path, dst_path):
    """Create symlink of file.
    Args:
        src_path(str): Full path to a file which is used as source for
            symlink.
        dst_path(str): Full path to a file where a link of source will be
            added.
    """
    # Use `os.symlink` if is available
    #   - should be for all platforms with newer python versions
    if hasattr(os, "symlink"):
        os.symlink(src_path, dst_path)
        return

    # Windows implementation of symlinks (
    #  - for older versions of python
    if platform.system().lower() == "windows":
        import ctypes
        from ctypes.wintypes import BOOL
        CreateSymLink = ctypes.windll.kernel32.CreateSymbolicLinkW
        CreateSymLink.argtypes = [
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p
        ]
        CreateSymLink.restype = BOOL

        res = CreateSymLink(dst_path, src_path, None)
        if res == 0:
            raise ctypes.WinError()
        return
    # Raises not implemented error if gets here
    raise NotImplementedError(
        "Implementation of symlink for current environment is missing."
    )


def collect_frames(files):
    """Returns dict of source path and its frame, if from sequence

    Uses clique as most precise solution, used when anatomy template that
    created files is not known.

    Assumption is that frames are separated by '.', negative frames are not
    allowed.

    Args:
        files(list) or (set with single value): list of source paths

    Returns:
        (dict): {'/asset/subset_v001.0001.png': '0001', ....}
    """

    patterns = [clique.PATTERNS["frames"]]
    collections, remainder = clique.assemble(
        files, minimum_items=1, patterns=patterns)

    sources_and_frames = {}
    if collections:
        for collection in collections:
            src_head = collection.head
            src_tail = collection.tail

            for index in collection.indexes:
                src_frame = collection.format("{padding}") % index
                src_file_name = "{}{}{}".format(
                    src_head, src_frame, src_tail)
                sources_and_frames[src_file_name] = src_frame
    else:
        sources_and_frames[remainder.pop()] = None

    return sources_and_frames


def _rreplace(s, a, b, n=1):
    """Replace a with b in string s from right side n times."""
    return b.join(s.rsplit(a, n))


def version_up(filepath):
    """Version up filepath to a new non-existing version.

    Parses for a version identifier like `_v001` or `.v001`
    When no version present _v001 is appended as suffix.

    Args:
        filepath (str): full url

    Returns:
        (str): filepath with increased version number

    """
    dirname = os.path.dirname(filepath)
    basename, ext = os.path.splitext(os.path.basename(filepath))

    regex = r"[._]v\d+"
    matches = re.findall(regex, str(basename), re.IGNORECASE)
    if not matches:
        log.info("Creating version...")
        new_label = "_v{version:03d}".format(version=1)
        new_basename = "{}{}".format(basename, new_label)
    else:
        label = matches[-1]
        version = re.search(r"\d+", label).group()
        padding = len(version)

        new_version = int(version) + 1
        new_version = '{version:0{padding}d}'.format(version=new_version,
                                                     padding=padding)
        new_label = label.replace(version, new_version, 1)
        new_basename = _rreplace(basename, label, new_label)
    new_filename = "{}{}".format(new_basename, ext)
    new_filename = os.path.join(dirname, new_filename)
    new_filename = os.path.normpath(new_filename)

    if new_filename == filepath:
        raise RuntimeError("Created path is the same as current file,"
                           "this is a bug")

    # We check for version clashes against the current file for any file
    # that matches completely in name up to the {version} label found. Thus
    # if source file was test_v001_test.txt we want to also check clashes
    # against test_v002.txt but do want to preserve the part after the version
    # label for our new filename
    clash_basename = new_basename
    if not clash_basename.endswith(new_label):
        index = (clash_basename.find(new_label))
        index += len(new_label)
        clash_basename = clash_basename[:index]

    for file in os.listdir(dirname):
        if file.endswith(ext) and file.startswith(clash_basename):
            log.info("Skipping existing version %s" % new_label)
            return version_up(new_filename)

    log.info("New version %s" % new_label)
    return new_filename


def get_version_from_path(file):
    """Find version number in file path string.

    Args:
        file (str): file path

    Returns:
        str: version number in string ('001')
    """

    pattern = re.compile(r"[\._]v([0-9]+)", re.IGNORECASE)
    try:
        return pattern.findall(file)[-1]
    except IndexError:
        log.error(
            "templates:get_version_from_workfile:"
            "`{}` missing version string."
            "Example `v004`".format(file)
        )


def get_last_version_from_path(path_dir, filter):
    """Find last version of given directory content.

    Args:
        path_dir (str): directory path
        filter (list): list of strings used as file name filter

    Returns:
        str: file name with last version

    Example:
        last_version_file = get_last_version_from_path(
            "/project/shots/shot01/work", ["shot01", "compositing", "nk"])
    """

    assert os.path.isdir(path_dir), "`path_dir` argument needs to be directory"
    assert isinstance(filter, list) and (
        len(filter) != 0), "`filter` argument needs to be list and not empty"

    filtred_files = list()

    # form regex for filtering
    pattern = r".*".join(filter)

    for file in os.listdir(path_dir):
        if not re.findall(pattern, file):
            continue
        filtred_files.append(file)

    if filtred_files:
        sorted(filtred_files)
        return filtred_files[-1]

    return None


def check_input_is_optimizable_path(input):
    if not input:
        return False

    # Skip if input contains template path syntax: {template_var}
    if re.search(r'{[\w.-]+}', input):
        return False

    # Expand environment variables and user home in the input element
    input_expanded = os.path.expandvars(input)
    input_expanded = os.path.expanduser(input_expanded)

    low_platform = platform.system().lower()
    # Check if input is a valid path according to the platform
    if low_platform == "windows":
        # Match path with drive letter or network syntax
        # Examples: C:/blabla , D:\blabla , //blabla , \\blabla
        path_regex = r'^([a-zA-Z]:[/\\]|^[/\\]{2}).+$'
    else:
        # Unix (MacOS or Linux)
        # Examples: /blabla , ///blabla
        path_regex = r'^/(//)?.+$'

    return True if re.match(path_regex, input_expanded) else False


def optimize_path_compatibility(input_string):
    # Check if filepath is None or empty first, return original value
    if not input_string:
        return input_string

    if not check_input_is_optimizable_path(input_string):
        return input_string

    try:
        workfile_path = Path(input_string)
        workfile_path.parent.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
         return input_string

    if 'win' not in sys.platform:
        # Nothing done, only applicable for Windows
        return input_string

    # Windows-specific logic to convert the filepath to its short path form.
    _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
    _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    _GetShortPathNameW.restype = wintypes.DWORD

    workfile_parent = str(workfile_path.parent)
    output_buf_size = len(workfile_parent)
    # Iteratively try to get the short path name, increasing buffer size if needed.
    while True:
        output_buf = ctypes.create_unicode_buffer(output_buf_size)
        needed_size = _GetShortPathNameW(workfile_parent, output_buf, output_buf_size)
        if needed_size == 0:
            raise ctypes.WinError()
        if output_buf_size >= needed_size:
            return os.path.join(output_buf.value, workfile_path.name)  # Return the short path version.
        else:
            output_buf_size = needed_size  # Adjust the buffer size if needed.
