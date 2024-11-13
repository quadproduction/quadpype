# -*- coding: utf-8 -*-
"""Bootstrap QuadPype repositories."""
from __future__ import annotations
import logging as log
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Union, List, Tuple
import hashlib
import platform

from zipfile import ZipFile, BadZipFile

import blessed
from appdirs import user_data_dir
from speedcopy import copyfile
import semver

from .user_settings import (
    QuadPypeSecureRegistry,
    QuadPypeSettingsRegistry
)
from .tools import (
    get_quadpype_global_settings,
    get_quadpype_path_from_settings,
    get_expected_studio_version_str,
    get_local_quadpype_path_from_settings
)


term = blessed.Terminal()


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


class ZipFileLongPaths(ZipFile):
    def _extract_member(self, member, target_path, pwd):
        return ZipFile._extract_member(
            self, member, sanitize_long_path(target_path), pwd
        )


class QuadPypeVersion(semver.VersionInfo):
    """Class for storing information about QuadPype version.

    Attributes:
        path (str): path to QuadPype

    """
    path = None

    _local_quadpype_path = None
    # this should match any string complying with https://semver.org/
    _VERSION_REGEX = re.compile(r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>[a-zA-Z\d\-.]*))?(?:\+(?P<buildmetadata>[a-zA-Z\d\-.]*))?")  # noqa: E501
    _installed_version = None

    def __init__(self, *args, **kwargs):
        """Create QuadPype version.

        .. deprecated:: 3.0.0-rc.2
            `client` and `variant` are removed.


        Args:
            major (int): version when you make incompatible API changes.
            minor (int): version when you add functionality in a
                backwards-compatible manner.
            patch (int): version when you make backwards-compatible bug fixes.
            prerelease (str): an optional prerelease string
            build (str): an optional build string
            version (str): if set, it will be parsed and will override
                parameters like `major`, `minor` and so on.
            path (Path): path to version location.

        """
        self.path = None

        if "version" in kwargs.keys():
            if not kwargs.get("version"):
                raise ValueError("Invalid version specified")
            v = QuadPypeVersion.parse(kwargs.get("version"))
            kwargs["major"] = v.major
            kwargs["minor"] = v.minor
            kwargs["patch"] = v.patch
            kwargs["prerelease"] = v.prerelease
            kwargs["build"] = v.build
            kwargs.pop("version")

        if kwargs.get("path"):
            if isinstance(kwargs.get("path"), str):
                self.path = Path(kwargs.get("path"))
            elif isinstance(kwargs.get("path"), Path):
                self.path = kwargs.get("path")
            else:
                raise TypeError("Path must be str or Path")
            kwargs.pop("path")

        if "path" in kwargs.keys():
            kwargs.pop("path")

        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<{self.__class__.__name__}: {str(self)} - path={self.path}>"

    def __lt__(self, other: QuadPypeVersion):
        result = super().__lt__(other)
        # prefer path over no path
        if self == other and not self.path and other.path:
            return True

        if self == other and self.path and other.path and \
                other.path.is_dir() and self.path.is_file():
            return True

        if self.finalize_version() == other.finalize_version() and \
                self.prerelease == other.prerelease:
            return True

        return result

    def get_main_version(self) -> str:
        """Return main version component.

        This returns x.x.x part of version from possibly more complex one
        like x.x.x-foo-bar.

        .. deprecated:: 3.0.0-rc.2
            use `finalize_version()` instead.
        Returns:
            str: main version component

        """
        return str(self.finalize_version())

    @staticmethod
    def version_in_str(string: str) -> Union[None, QuadPypeVersion]:
        """Find QuadPype version in given string.

        Args:
            string (str):  string to search.

        Returns:
            QuadPypeVersion: of detected or None.

        """
        # strip .zip ext if present
        string = re.sub(r"\.zip$", "", string, flags=re.IGNORECASE)
        m = re.search(QuadPypeVersion._VERSION_REGEX, string)
        if not m:
            return None
        version = QuadPypeVersion.parse(string[m.start():m.end()])
        return version

    def __hash__(self):
        return hash(self.path) if self.path else hash(str(self))

    @staticmethod
    def is_version_in_dir(
            dir_item: Path, version: QuadPypeVersion) -> Tuple[bool, str]:
        """Test if path item is QuadPype version matching detected version.

        If item is directory that might (based on it's name)
        contain QuadPype version, check if it really does contain
        QuadPype and that their versions matches.

        Args:
            dir_item (Path): Directory to test.
            version (QuadPypeVersion): QuadPype version detected
                from name.

        Returns:
            Tuple: State and reason, True if it is valid QuadPype version,
                   False otherwise.

        """
        try:
            # add one 'quadpype' level as inside dir there should
            # be many other repositories.
            version_str = QuadPypeVersion.get_version_string_from_directory(
                dir_item)  # noqa: E501
            version_check = QuadPypeVersion(version=version_str)
        except ValueError:
            return False, f"cannot determine version from {dir_item}"

        version_main = version_check.get_main_version()
        detected_main = version.get_main_version()
        if version_main != detected_main:
            return False, (f"dir version ({version}) and "
                           f"its content version ({version_check}) "
                           "doesn't match. Skipping.")
        return True, "Versions match"

    @staticmethod
    def is_version_in_zip(
            zip_item: Path, version: QuadPypeVersion) -> Tuple[bool, str]:
        """Test if zip path is QuadPype version matching detected version.

        Open zip file, look inside and parse version from QuadPype
        inside it. If there is none, or it is different from
        version specified in file name, skip it.

        Args:
            zip_item (Path): Zip file to test.
            version (QuadPypeVersion): Pype version detected
                from name.

        Returns:
           Tuple: State and reason, True if it is valid QuadPype version,
                False otherwise.

        """
        # skip non-zip files
        if zip_item.suffix.lower() != ".zip":
            return False, "Not a zip"

        try:
            with ZipFile(zip_item, "r") as zip_file:
                with zip_file.open(
                        "quadpype/version.py") as version_file:
                    zip_version = {}
                    exec(version_file.read(), zip_version)
                    try:
                        version_check = QuadPypeVersion(
                            version=zip_version["__version__"])
                    except ValueError as e:
                        return False, str(e)

                    version_main = version_check.get_main_version()  #
                    # noqa: E501
                    detected_main = version.get_main_version()
                    # noqa: E501

                    if version_main != detected_main:
                        return False, (f"zip version ({version}) "
                                       f"and its content version "
                                       f"({version_check}) "
                                       "doesn't match. Skipping.")
        except BadZipFile:
            return False, f"{zip_item} is not a zip file"
        except KeyError:
            return False, "Zip does not contain QuadPype"
        return True, "Versions match"

    @staticmethod
    def get_version_string_from_directory(repo_dir: Path) -> Union[str, None]:
        """Get version of QuadPype in given directory.

        Note: in frozen QuadPype installed in user data dir, this must point
        one level deeper as it is:
        `quadpype-version-v3.0.0/quadpype/version.py`

        Args:
            repo_dir (Path): Path to QuadPype repo.

        Returns:
            str: version string.
            None: if QuadPype is not found.

        """
        # try to find version
        version_file = Path(repo_dir) / "quadpype" / "version.py"
        if not version_file.exists():
            return None

        version = {}
        with version_file.open("r") as fp:
            exec(fp.read(), version)

        return version['__version__']

    @classmethod
    def get_quadpype_path(cls):
        """Path to quadpype zip directory.

        Path can be set through environment variable 'QUADPYPE_PATH' which
        is set during start of QuadPype if is not available.
        """
        return os.getenv("QUADPYPE_PATH")

    @classmethod
    def get_local_quadpype_path(cls):
        """Path to unzipped versions.

        By default, it should be user appdata, but could be overridden by
        settings.
        """
        if cls._local_quadpype_path:
            return cls._local_quadpype_path

        settings = get_quadpype_global_settings(os.environ["QUADPYPE_DB_URI"])
        data_dir = get_local_quadpype_path_from_settings(settings)
        if not data_dir:
            data_dir = Path(user_data_dir("quadpype", "quad"))
        cls._local_quadpype_path = data_dir
        return data_dir

    @classmethod
    def quadpype_path_is_set(cls):
        """Path to QuadPype zip directory is set."""
        if cls.get_quadpype_path():
            return True
        return False

    @classmethod
    def quadpype_path_is_accessible(cls):
        """Path to QuadPype zip directory is accessible.

        Exists for this machine.
        """
        # First check if is set
        if not cls.quadpype_path_is_set():
            return False

        # Validate existence
        if Path(cls.get_quadpype_path()).exists():
            return True
        return False

    @classmethod
    def get_local_versions(cls) -> List:
        """Get all versions available on this machine.

        Returns:
            list: of compatible versions available on the machine.

        """
        dir_to_search = cls.get_local_quadpype_path()
        versions = cls.get_versions_from_directory(dir_to_search)

        return list(sorted(set(versions)))

    @classmethod
    def get_remote_versions(cls) -> List:
        """Get all versions available in QuadPype Path.

        Returns:
            list of QuadPypeVersions: Versions found in QuadPype path.

        """
        # Return all local versions if arguments are set to None

        dir_to_search = None
        if cls.quadpype_path_is_accessible():
            dir_to_search = Path(cls.get_quadpype_path())
        else:
            registry = QuadPypeSettingsRegistry()
            try:
                registry_dir = Path(str(registry.get_item("quadpypePath")))
                if registry_dir.exists():
                    dir_to_search = registry_dir

            except ValueError:
                # nothing found in registry, we'll use data dir
                pass

        if not dir_to_search:
            return []

        versions = cls.get_versions_from_directory(dir_to_search)

        return list(sorted(set(versions)))

    @staticmethod
    def get_versions_from_directory(
            quadpype_dir: Path) -> List:
        """Get all detected QuadPype versions in directory.

        Args:
            quadpype_dir (Path): Directory to scan.

        Returns:
            list of QuadPypeVersion

        Throws:
            ValueError: if invalid path is specified.

        """
        quadpype_versions = []
        if not quadpype_dir.exists() and not quadpype_dir.is_dir():
            return quadpype_versions

        # iterate over directory in first level and find all that might
        # contain QuadPype.
        for item in quadpype_dir.iterdir():
            # if the item is directory with major.minor version, dive deeper

            if item.is_dir() and re.match(r"^\d+\.\d+$", item.name):
                _versions = QuadPypeVersion.get_versions_from_directory(
                    item)
                if _versions:
                    quadpype_versions += _versions

            # if file exists, strip extension, in case of dir don't.
            name = item.name if item.is_dir() else item.stem
            result = QuadPypeVersion.version_in_str(name)

            if result:
                detected_version: QuadPypeVersion
                detected_version = result

                if item.is_dir() and not QuadPypeVersion.is_version_in_dir(
                        item, detected_version
                )[0]:
                    continue

                if item.is_file() and not QuadPypeVersion.is_version_in_zip(
                        item, detected_version
                )[0]:
                    continue

                detected_version.path = item
                quadpype_versions.append(detected_version)

        return sorted(quadpype_versions)

    @staticmethod
    def get_installed_version_str() -> str:
        """Get version of local QuadPype."""

        version = {}
        path = Path(os.environ["QUADPYPE_ROOT"]) / "quadpype" / "version.py"
        with open(path, "r") as fp:
            exec(fp.read(), version)
        return version["__version__"]

    @classmethod
    def get_installed_version(cls):
        """Get version of QuadPype inside build."""
        if cls._installed_version is None:
            installed_version_str = cls.get_installed_version_str()
            if installed_version_str:
                cls._installed_version = QuadPypeVersion(
                    version=installed_version_str,
                    path=Path(os.environ["QUADPYPE_ROOT"])
                )
        return cls._installed_version

    @staticmethod
    def get_latest_version(
        local: bool = None,
        remote: bool = None
    ) -> Union[QuadPypeVersion, None]:
        """Get the latest available version.

        The version does not contain information about path and source.

        This is utility version to get the latest version from all found.

        Arguments 'local' and 'remote' define if local and remote repository
        versions are used. All versions are used if both are not set (or set
        to 'None'). If only one of them is set to 'True' the other is disabled.
        It is possible to set both to 'True' (same as both set to None) and to
        'False' in that case only build version can be used.

        Args:
            local (bool, optional): List local versions if True.
            remote (bool, optional): List remote versions if True.

        Returns:
            Latest QuadPypeVersion or None

        """
        if local is None and remote is None:
            local = True
            remote = True

        elif local is None and not remote:
            local = True

        elif remote is None and not local:
            remote = True

        installed_version = QuadPypeVersion.get_installed_version()
        local_versions = QuadPypeVersion.get_local_versions() if local else []
        remote_versions = QuadPypeVersion.get_remote_versions() if remote else []  # noqa: E501
        all_versions = local_versions + remote_versions + [installed_version]

        all_versions.sort()
        return all_versions[-1]

    @classmethod
    def get_expected_studio_version(cls, staging=False, global_settings=None):
        """Expected QuadPype version that should be used at the moment.

        If version is not defined in settings the latest found version is
        used.

        Using precached global settings is needed for usage inside QuadPype.

        Args:
            staging (bool): Staging version or production version.
            global_settings (dict): Optional precached global settings.

        Returns:
            QuadPypeVersion: Version that should be used.
        """
        result = get_expected_studio_version_str(staging, global_settings)
        if not result:
            return None
        return QuadPypeVersion(version=result)

    def is_compatible(self, version: QuadPypeVersion):
        """Test build compatibility.

        This will simply compare major and minor versions (ignoring patch
        and the rest).

        Args:
            version (QuadPypeVersion): Version to check compatibility with.

        Returns:
            bool: if the version is compatible

        """
        return self.major == version.major and self.minor == version.minor


class ZXPExtensionData:

    def __init__(self, host_id: str, ext_id: str, installed_version: semver.VersionInfo, shipped_version: semver.VersionInfo):
        self.host_id = host_id
        self.id = ext_id
        self.installed_version = installed_version
        self.shipped_version = shipped_version


class BootstrapRepos:
    """Class for bootstrapping local QuadPype installation.

    Attributes:
        data_dir (Path): local QuadPype installation directory.
        registry (QuadPypeSettingsRegistry): QuadPype registry object.
        zip_filter (list): List of files to exclude from zip
        quadpype_filter (list): list of top level directories to
            include in zip in QuadPype repository.

    """

    def __init__(self, progress_bar=None, log_signal=None, step_text_signal=None):
        """Constructor.

        Args:
            progress_bar: Optional instance of a progress bar.
            log_signal (QtCore.Signal, optional): Signal to report messages back.

        """
        # vendor and app used to construct user data dir
        self._log_signal = log_signal
        self._step_text_signal = step_text_signal
        self.data_dir = None
        self.set_data_dir(None)
        self.secure_registry = QuadPypeSecureRegistry("Database")
        self.registry = QuadPypeSettingsRegistry()
        self.zip_filter = [".pyc", "__pycache__"]
        self.quadpype_filter = [
            "quadpype", "../LICENSE"
        ]
        self._progress_bar = progress_bar

    def progress_bar_set_total(self, total):
        if not self._progress_bar:
            return
        self._progress_bar.total = total

    def progress_bar_increment(self, value=1):
        if not self._progress_bar:
            return
        self._progress_bar.update(incr=value)

    def progress_bar_remove(self):
        if not self._progress_bar:
            return
        self._progress_bar.close(clear=True)

    def set_data_dir(self, data_dir):
        if not data_dir:
            self.data_dir = Path(user_data_dir("quadpype", "quad"))
        else:
            self._print(f"Overriding local folder: {data_dir}")
            self.data_dir = data_dir

    @staticmethod
    def get_version_path_from_list(
            version: str, version_list: list) -> Union[Path, None]:
        """Get path for specific version in list of QuadPype versions.

        Args:
            version (str): Version string to look for (1.2.4-nightly.1+test)
            version_list (list of QuadPypeVersion): list of version to search.

        Returns:
            Path: Path to given version.

        """
        for v in version_list:
            if str(v) == version:
                return v.path
        return None

    @staticmethod
    def get_version(repo_dir: Path) -> Union[QuadPypeVersion, None]:
        """Get version of QuadPype in given directory.

        Note: in frozen QuadPype installed in user data dir, this must point
        one level deeper as it is:
        `quadpype-version-v3.0.0/quadpype/version.py`

        Args:
            repo_dir (Path): Path to QuadPype repo.

        Returns:
            str: version string.
            None: if QuadPype is not found.

        """
        # try to find version
        version_file = Path(repo_dir) / "quadpype" / "version.py"
        if not version_file.exists():
            return None

        version = {}
        with version_file.open("r") as fp:
            exec(fp.read(), version)

        return QuadPypeVersion(version=version['__version__'], path=repo_dir)

    def create_version_from_live_code(
            self, repo_dir: Path = None, data_dir: Path = None) -> Union[QuadPypeVersion, None]:
        """Copy zip created from QuadPype repositories to user data dir.

        This detects QuadPype version either in local "live" QuadPype
        repository or in user provided path. Then it will zip it in temporary
        directory, and finally it will move it to destination which is user
        data directory. Existing files will be replaced.

        Args:
            repo_dir (Path, optional): Path to QuadPype repository.
            data_dir (Path, optional): Path to the user data directory.

        Returns:
            version (QuadPypeVersion): Info of the version created.

        """
        # If repo dir is not set, we detect local "live" QuadPype repository
        # version and use it as a source. Otherwise, repo_dir is user
        # entered location.
        if repo_dir:
            version_str = str(self.get_version(repo_dir))
        else:
            installed_version = QuadPypeVersion.get_installed_version()
            version_str = str(installed_version)
            repo_dir = installed_version.path

        if not version_str:
            self._print("QuadPype not found.", level=log.ERROR)
            return

        # create destination directory
        destination = (data_dir or self.data_dir) / f"{installed_version.major}.{installed_version.minor}"  # noqa
        if not destination.exists():
            destination.mkdir(parents=True)

        # create zip inside temporary directory.
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_zip = \
                Path(temp_dir) / f"quadpype-v{version_str}.zip"
            self._print(f"Creating zip: {temp_zip}")

            self._create_quadpype_zip(temp_zip, repo_dir)
            if not os.path.exists(temp_zip):
                self._print("Make archive failed.", level=log.ERROR)
                return None

            destination = self._move_zip_to_data_dir(temp_zip)

        self.progress_bar_remove()

        return QuadPypeVersion(version=version_str, path=Path(destination))

    def _move_zip_to_data_dir(self, zip_file) -> Union[None, Path]:
        """Move zip with QuadPype version to user data directory.

        Args:
            zip_file (Path): Path to zip file.

        Returns:
            None if move fails.
            Path to moved zip on success.

        """
        version = QuadPypeVersion.version_in_str(zip_file.name)
        destination_dir = self.data_dir / f"{version.major}.{version.minor}"
        if not destination_dir.exists():
            destination_dir.mkdir(parents=True)
        destination = destination_dir / zip_file.name

        if destination.exists():
            self._print(
                f"Destination file {destination} exists, removing.",
                level=log.WARNING)
            try:
                destination.unlink()
            except Exception as e:
                self._print(str(e), level=log.ERROR)
                return None
        if not destination_dir.exists():
            destination_dir.mkdir(parents=True)
        elif not destination_dir.is_dir():
            self._print(
                "Destination exists but is not directory.", level=log.ERROR)
            return None

        try:
            shutil.move(zip_file.as_posix(), destination_dir.as_posix())
        except shutil.Error as e:
            self._print(str(e), level=log.ERROR)
            return None

        return destination

    def _filter_dir(self, path: Path, path_filter: List) -> List[Path]:
        """Recursively crawl over path and filter."""
        result = []
        for item in path.iterdir():
            if item.name in path_filter:
                continue
            if item.name.startswith('.'):
                continue
            if item.is_dir():
                result.extend(self._filter_dir(item, path_filter))
            else:
                result.append(item)
        return result

    def create_version_from_frozen_code(self) -> Union[None, QuadPypeVersion]:
        """Create QuadPype version from *frozen* code distributed by installer.

        This should be real edge case for those wanting to try out QuadPype
        without setting up whole infrastructure but is strongly discouraged
        in studio setup as this use local version independent of others
        that can be out of date.

        Returns:
            :class:`QuadPypeVersion` zip file to be installed.

        """
        frozen_root = Path(sys.executable).parent

        quadpype_list = []
        for f in self.quadpype_filter:
            if (frozen_root / f).is_dir():
                quadpype_list += self._filter_dir(
                    frozen_root / f, self.zip_filter)
            else:
                quadpype_list.append(frozen_root / f)

        version_str = str(self.get_version(frozen_root))

        # create zip inside temporary directory.
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_zip = \
                Path(temp_dir) / f"quadpype-v{version_str}.zip"
            self._print(f"Creating zip: {temp_zip}")

            with ZipFile(temp_zip, "w") as zip_file:
                self.progress_bar_set_total(len(quadpype_list))

                file: Path
                for file in quadpype_list:
                    arc_name = file.relative_to(frozen_root.parent)
                    # we need to replace first part of path which starts with
                    # something like `exe.win/linux....` with `quadpype` as
                    # this is expected by QuadPype in zip archive.
                    arc_name = Path().joinpath(*arc_name.parts[1:])
                    zip_file.write(file, arc_name)
                    self.progress_bar_increment()

            destination = self._move_zip_to_data_dir(temp_zip)

        self.progress_bar_remove()

        return QuadPypeVersion(version=version_str, path=destination)

    def _create_quadpype_zip(self, zip_path: Path, quadpype_path: Path) -> None:
        """Pack repositories and QuadPype into zip.

        We are using :mod:`ZipFile` instead :meth:`shutil.make_archive`
        because we need to decide what file and directories to include in zip
        and what not. They are determined by :attr:`zip_filter` on file level
        and :attr:`quadpype_filter` on top level directory in QuadPype
        repository.

        Args:
            zip_path (Path): Path to zip file.
            quadpype_path (Path): Path to QuadPype sources.

        """
        # get filtered list of file in Pype repository
        # quadpype_list = self._filter_dir(quadpype_path, self.zip_filter)
        quadpype_list = []
        for f in self.quadpype_filter:
            if (quadpype_path / f).is_dir():
                quadpype_list += self._filter_dir(
                    quadpype_path / f, self.zip_filter)
            else:
                quadpype_list.append(quadpype_path / f)

        with ZipFile(zip_path, "w") as zip_file:
            quadpype_root = quadpype_path.resolve()
            # generate list of filtered paths
            dir_filter = [quadpype_root / f for f in self.quadpype_filter]
            checksums = []

            file: Path
            # Adding 2 to the total for the checksum and test zip operations
            self.progress_bar_set_total(len(quadpype_list) + 2)
            for file in quadpype_list:
                # if file resides in filtered path, skip it
                is_inside = None
                df: Path
                for df in dir_filter:
                    try:
                        is_inside = file.resolve().relative_to(df)
                    except ValueError:
                        pass

                if not is_inside:
                    continue

                checksums.append(
                    (
                        sha256sum(sanitize_long_path(file.as_posix())),
                        file.resolve().relative_to(quadpype_root)
                    )
                )
                zip_file.write(
                    file, file.resolve().relative_to(quadpype_root))
                self.progress_bar_increment()

            checksums_str = ""
            for c in checksums:
                file_str = c[1]
                if platform.system().lower() == "windows":
                    file_str = c[1].as_posix().replace("\\", "/")
                checksums_str += "{}:{}\n".format(c[0], file_str)
            zip_file.writestr("checksums", checksums_str)
            self.progress_bar_increment()
            # test if zip is ok
            zip_file.testzip()
            self.progress_bar_increment()

    def validate_quadpype_version(self, path: Path) -> tuple:
        """Validate version directory or zip file.

        This will load `checksums` file if present, calculate checksums
        of existing files in given path and compare. It will also compare
        lists of files together for missing files.

        Args:
            path (Path): Path to QuadPype version to validate.

        Returns:
            tuple(bool, str): with version validity as first item
                and string with reason as second.

        """
        if os.getenv("QUADPYPE_DONT_VALIDATE_VERSION"):
            return True, "Disabled validation"
        if not path.exists():
            return False, "Path doesn't exist"

        if path.is_file():
            return self._validate_zip(path)
        return self._validate_dir(path)

    @staticmethod
    def _validate_zip(path: Path) -> tuple:
        """Validate content of zip file."""
        with ZipFile(path, "r") as zip_file:
            # read checksums
            try:
                checksums_data = str(zip_file.read("checksums"))
            except IOError:
                # FIXME: This should be set to False sometimes in the future
                return True, "Cannot read checksums for archive."

            # split it to the list of tuples
            checksums = [
                tuple(line.split(":"))
                for line in checksums_data.split("\n") if line
            ]

            # get list of files in zip minus `checksums` file itself
            # and turn in to set to compare against list of files
            # from checksum file. If difference exists, something is
            # wrong
            files_in_zip = set(zip_file.namelist())
            files_in_zip.remove("checksums")
            files_in_checksum = {file[1] for file in checksums}
            diff = files_in_zip.difference(files_in_checksum)
            if diff:
                return False, f"Missing files {diff}"

            # calculate and compare checksums in the zip file
            for file_checksum, file_name in checksums:
                if platform.system().lower() == "windows":
                    file_name = file_name.replace("/", "\\")
                h = hashlib.sha256()
                try:
                    h.update(zip_file.read(file_name))
                except FileNotFoundError:
                    return False, f"Missing file [ {file_name} ]"
                if h.hexdigest() != file_checksum:
                    return False, f"Invalid checksum on {file_name}"

        return True, "All ok"

    @staticmethod
    def _validate_dir(path: Path) -> tuple:
        """Validate checksums in a given path.

        Args:
            path (Path): path to folder to validate.

        Returns:
            tuple(bool, str): returns status and reason as a bool
                and str in a tuple.

        """
        checksums_file = Path(path / "checksums")
        if not checksums_file.exists():
            # FIXME: This should be set to False sometimes in the future
            return True, "Cannot read checksums for archive."
        checksums_data = checksums_file.read_text()
        checksums = [
            tuple(line.split(":"))
            for line in checksums_data.split("\n") if line
        ]

        # compare file list against list of files from checksum file.
        # If difference exists, something is wrong and we invalidate directly
        files_in_dir = set(
            file.relative_to(path).as_posix()
            for file in path.iterdir() if file.is_file()
        )
        files_in_dir.remove("checksums")
        files_in_checksum = {file[1] for file in checksums}

        diff = files_in_dir.difference(files_in_checksum)
        if diff:
            return False, f"Missing files {diff}"

        # calculate and compare checksums
        for file_checksum, file_name in checksums:
            if platform.system().lower() == "windows":
                file_name = file_name.replace("/", "\\")
            try:
                current = sha256sum(
                    sanitize_long_path((path / file_name).as_posix())
                )
            except FileNotFoundError:
                return False, f"Missing file [ {file_name} ]"

            if file_checksum != current:
                return False, f"Invalid checksum on {file_name}"

        return True, "All ok"

    @staticmethod
    def add_paths_from_archive(archive: Path) -> None:
        """Add first-level directory and 'repos' as paths to :mod:`sys.path`.

        This will enable Python to import QuadPype and modules in `repos`
        submodule directory in zip file.

        Adding to both `sys.path` and `PYTHONPATH`, skipping duplicates.

        Args:
            archive (Path): path to archive.

        .. deprecated:: 3.0
            we don't use zip archives directly

        """
        if not archive.is_file() and not archive.exists():
            raise ValueError("Archive is not file.")

        archive_path = str(archive)
        sys.path.insert(0, archive_path)
        pythonpath = os.getenv("PYTHONPATH", "")
        python_paths = pythonpath.split(os.pathsep)
        python_paths.insert(0, archive_path)

        os.environ["PYTHONPATH"] = os.pathsep.join(python_paths)

    @staticmethod
    def add_paths_from_directory(directory: Path) -> None:
        """Add repos first level directories as paths to :mod:`sys.path`.

        This works the same as :meth:`add_paths_from_archive` but in
        specified directory.

        Adding to both `sys.path` and `PYTHONPATH`, skipping duplicates.

        Args:
            directory (Path): path to directory.

        """

        sys.path.insert(0, directory.as_posix())

    @staticmethod
    def find_quadpype_local_version(version: QuadPypeVersion) -> Union[QuadPypeVersion, None]:
        """
           Finds the specified QuadPype version in the local directory.

           Parameters:
           - version (QuadPypeVersion): A specific version of QuadPype to search for.

           Returns:
           - QuadPypeVersion() or None: Returns the found QuadPype version if available, or None if not found.
        """
        zip_version = None
        for local_version in QuadPypeVersion.get_local_versions():
            if local_version == version:
                if local_version.path.suffix.lower() == ".zip":
                    zip_version = local_version
                else:
                    return local_version

        return zip_version

    @staticmethod
    def find_quadpype_remote_version(version: QuadPypeVersion) -> Union[QuadPypeVersion, None]:
        """
           Finds the specified QuadPype version in the remote directory.

           Parameters:
           - version (QuadPypeVersion): A specific version of QuadPype to search for.

           Returns:
           - QuadPypeVersion() or None: Returns the found QuadPype version if available, or None if not found.
        """
        remote_versions = QuadPypeVersion.get_remote_versions()
        return next(
            (
                remote_version for remote_version in remote_versions
                if remote_version == version
            ), None)

    @staticmethod
    def find_quadpype_version(
            version: Union[str, QuadPypeVersion]
    ) -> Union[QuadPypeVersion, None]:
        """Find location of specified QuadPype version.

        Args:
            version (Union[str, QuadPypeVersion): Version to find.

        Returns:
            requested QuadPypeVersion.

        """
        if isinstance(version, str):
            version = QuadPypeVersion(version=version)

        installed_version = QuadPypeVersion.get_installed_version()
        if installed_version == version:
            return installed_version

        op_version = BootstrapRepos.find_quadpype_local_version(version)
        if op_version is not None:
            return op_version

        return BootstrapRepos.find_quadpype_remote_version(version)

    @staticmethod
    def find_latest_quadpype_version() -> Union[QuadPypeVersion, None]:
        """Find the latest available QuadPype version in all location.

        Returns:
            Latest QuadPype version on None if nothing was found.

        """
        installed_version = QuadPypeVersion.get_installed_version()
        local_versions = QuadPypeVersion.get_local_versions()
        remote_versions = QuadPypeVersion.get_remote_versions()
        all_versions = local_versions + remote_versions + [installed_version]

        if not all_versions:
            return None

        all_versions.sort()
        latest_version = all_versions[-1]
        if latest_version == installed_version:
            return latest_version

        if not latest_version.path.is_dir():
            for version in local_versions:
                if version == latest_version and version.path.is_dir():
                    latest_version = version
                    break
        return latest_version

    def find_quadpype(
            self,
            quadpype_path: Union[Path, str] = None,
            include_zips: bool = False
    ) -> Union[List[QuadPypeVersion], None]:
        """Get ordered dict of detected QuadPype version.

        Resolution order for QuadPype is following:

            1) First we test for ``QUADPYPE_PATH`` environment variable
            2) We try to find ``quadpypePath`` in registry setting
            3) We use user data directory

        Args:
            quadpype_path (Path or str, optional): Try to find QuadPype on
                the given path or url.
            include_zips (bool, optional): If set True it will try to find
                QuadPype in zip files in given directory.

        Returns:
            dict of Path: Dictionary of detected QuadPype version.
                 Key is version, value is path to zip file.

            None: if QuadPype is not found.

        Todo:
            implement git/url support as QuadPype location, so it would be
            possible to enter git url, QuadPype would check it out and if it is
            ok install it as normal version.

        """
        if quadpype_path and not isinstance(quadpype_path, Path):
            raise NotImplementedError(
                ("Finding QuadPype in non-filesystem locations is"
                 " not implemented yet."))

        # if checks bellow for QUADPYPE_PATH and registry fails, use data_dir
        # DEPRECATED: lookup in root of this folder is deprecated in favour
        #             of major.minor sub-folders.
        dirs_to_search = [self.data_dir]

        if quadpype_path:
            dirs_to_search = [quadpype_path]
        elif os.getenv("QUADPYPE_PATH") \
                and Path(os.getenv("QUADPYPE_PATH")).exists():
            # first try QUADPYPE_PATH and if that is not available,
            # try registry.
            dirs_to_search = [Path(os.getenv("QUADPYPE_PATH"))]
        else:
            try:
                registry_dir = Path(
                    str(self.registry.get_item("quadpypePath")))
                if registry_dir.exists():
                    dirs_to_search = [registry_dir]

            except ValueError:
                # nothing found in registry, we'll use data dir
                pass

        quadpype_versions = []
        for dir_to_search in dirs_to_search:
            try:
                quadpype_versions += self.get_quadpype_versions(
                    dir_to_search)
            except ValueError:
                # location is invalid, skip it
                pass

        if not include_zips:
            quadpype_versions = [
                v for v in quadpype_versions if v.path.suffix != ".zip"
            ]

        # remove duplicates
        quadpype_versions = sorted(list(set(quadpype_versions)))

        return quadpype_versions

    def process_entered_location(self, location: str) -> Union[Path, None]:
        """Process user entered location string.

        It decides if location string is database URI or path.
        If it is a database URI, it will connect and load ``QUADPYPE_PATH`` from
        there and use it as path to QuadPype. In it is _not_ a database URI, it
        is assumed we have a path, this is tested and zip file is
        produced and installed using :meth:`create_version_from_live_code`.

        Args:
            location (str): User entered location.

        Returns:
            Path: to QuadPype zip produced from this location.
            None: Zipping failed.

        """
        quadpype_path = None
        # try to get QuadPype path from database.
        if location.startswith("mongodb"):
            global_settings = get_quadpype_global_settings(location)
            quadpype_path = get_quadpype_path_from_settings(global_settings)
            if not quadpype_path:
                self._print("Cannot find QUADPYPE_PATH in settings.", level=log.ERROR)
                return None

        # if not successful, consider location to be fs path.
        if not quadpype_path:
            quadpype_path = Path(location)

        # test if this path does exist.
        if not quadpype_path.exists():
            self._print(f"{quadpype_path} doesn't exists.", level=log.ERROR)
            return None

        # test if entered path isn't user data dir
        if self.data_dir == quadpype_path:
            self._print("Cannot point to user data dir", level=log.ERROR)
            return None

        # find quadpype zip files in location. There can be
        # either "live" QuadPype repository, or multiple zip files or even
        # multiple QuadPype version directories. This process looks into zip
        # files and directories and tries to parse `version.py` file.
        versions = self.find_quadpype(quadpype_path, include_zips=True)
        if versions:
            self._print(f"Found QuadPype in [ {quadpype_path} ]")
            self._print(f"Latest version found is [ {versions[-1]} ]")

            return self.install_version(versions[-1])

        # if we got here, it means that location is "live"
        # QuadPype repository. We'll create zip from it and move it to user
        # data dir.
        live_quadpype = self.create_version_from_live_code(quadpype_path)
        if not live_quadpype.path.exists():
            self._print(f"Installing zip {live_quadpype} failed.", level=log.ERROR)
            return None
        # install it
        return self.install_version(live_quadpype)

    def _print(self,
               message: str,
               level: int = log.INFO,
               exception: Exception = None):
        """Helper function passing logs to UI and to logger.

        Supporting 3 levels of logs defined with `log.INFO`, `log.WARNING` and
        `log.ERROR` constants.

        Args:
            message (str): Message to log.
            level (int, optional): Log level to use.
            exception (Exception, optional): Exception info object to pass to logger.

        """
        if self._log_signal:
            self._log_signal.emit(message, level == log.ERROR)

        if level == log.INFO:
            header = term.aquamarine3(">>> ")
        elif level == log.WARNING:
            header = term.gold("*** ")
        elif level == log.ERROR:
            header = term.red("!!! ")
        elif level == log.DEBUG:
            header = term.tan1("... ")
        else:
            header = term.cyan("--- ")

        print(f"{header}{message}")
        if exception:
            print(term.red(f"{str(exception)}"))

    def extract_quadpype(self, version: QuadPypeVersion) -> Union[Path, None]:
        """Extract zipped QuadPype version to user data directory.

        Args:
            version (QuadPypeVersion): Version of QuadPype.

        Returns:
            Path: path to extracted version.
            None: if something failed.

        """
        if not version.path:
            raise ValueError(
                f"version {version} is not associated with any file")

        destination = self.data_dir / f"{version.major}.{version.minor}" / version.path.stem  # noqa
        if destination.exists() and destination.is_dir():
            try:
                shutil.rmtree(destination)
            except OSError as e:
                msg = f"Cannot remove already existing {destination}"
                self._print(msg, log.ERROR, exception=e)
                raise e

        destination.mkdir(parents=True)

        # extract zip there
        self._print("Extracting zip to destination ...")
        with ZipFileLongPaths(version.path, "r") as zip_ref:
            zip_ref.extractall(destination)

        self._print(f"Installed as {version.path.stem}")

        return destination

    def is_inside_user_data(self, path: Path) -> bool:
        """Test if version is located in user data dir.

        Args:
            path (Path) Path to test.

        Returns:
            True if path is inside user data dir.

        """
        is_inside = False
        try:
            is_inside = path.resolve().relative_to(
                self.data_dir)
        except ValueError:
            # if relative path cannot be calculated, QuadPype version is not
            # inside user data dir
            pass
        return is_inside

    def install_version(self,
                        quadpype_version: QuadPypeVersion,
                        force: bool = False) -> Path:
        """Install QuadPype version to user data directory.

        Args:
            quadpype_version (QuadPypeVersion): QuadPype version to install.
            force (bool, optional): Force overwrite existing version.

        Returns:
            Path: Path to installed QuadPype.

        Raises:
            QuadPypeVersionExists: If not forced and this version already exist
                in user data directory.
            QuadPypeVersionInvalid: If version to install is invalid.
            QuadPypeVersionIOError: If copying or zipping fail.

        """
        if self.is_inside_user_data(quadpype_version.path) and not quadpype_version.path.is_file():  # noqa
            raise QuadPypeVersionExists(
                "QuadPype already inside user data dir")

        # determine destination directory name
        # for zip file strip suffix, in case of dir use whole dir name
        if quadpype_version.path.is_dir():
            dir_name = quadpype_version.path.name
        else:
            dir_name = quadpype_version.path.stem

        destination = self.data_dir / f"{quadpype_version.major}.{quadpype_version.minor}" / dir_name  # noqa

        # test if destination directory already exist, if so let's delete it.
        if destination.exists() and force:
            self._print("Removing existing directory")
            try:
                shutil.rmtree(destination)
            except OSError as e:
                self._print(
                    f"Cannot remove already existing {destination}",
                    log.ERROR, exception=e)
                raise QuadPypeVersionIOError(
                    f"Cannot remove existing {destination}") from e
        elif destination.exists() and not force:
            self._print("Destination directory already exists")
            raise QuadPypeVersionExists(f"{destination} already exist.")
        else:
            # create destination parent directories even if they don't exist.
            destination.mkdir(parents=True)

        remove_source_file = False
        # version is directory
        if quadpype_version.path.is_dir():
            # create zip inside temporary directory.
            self._print("Creating zip from directory ...")
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_zip = \
                    Path(temp_dir) / f"quadpype-v{quadpype_version}.zip"
                self._print(f"Creating zip: {temp_zip}")

                self._create_quadpype_zip(temp_zip, quadpype_version.path)
                if not os.path.exists(temp_zip):
                    self._print("Make archive failed.", log.ERROR)
                    raise QuadPypeVersionIOError("Zip creation failed.")

                # set zip as version source
                quadpype_version.path = temp_zip

                if self.is_inside_user_data(quadpype_version.path):
                    raise QuadPypeVersionInvalid(
                        "Version is in user data dir.")
                quadpype_version.path = self._copy_zip(
                    quadpype_version.path, destination)

        elif quadpype_version.path.is_file():
            # check if file is zip (by extension)
            if quadpype_version.path.suffix.lower() != ".zip":
                raise QuadPypeVersionInvalid("Invalid file format")

            if not self.is_inside_user_data(quadpype_version.path):
                quadpype_version.path = self._copy_zip(
                    quadpype_version.path, destination)
                # Mark zip to be deleted when done
                remove_source_file = True

        # extract zip there
        self._print("Extracting zip to destination ...")
        with ZipFileLongPaths(quadpype_version.path, "r") as zip_ref:
            zip_ref.extractall(destination)

        # Remove zip file copied to local app data
        if remove_source_file:
            os.remove(quadpype_version.path)

        return destination

    def extract_zxp_info_from_manifest(self, path_manifest: Path):
        pattern_regex_extension_id = r"ExtensionBundleId=\"(?P<extension_id>[\w.]+)\""
        pattern_regex_extension_version = r"ExtensionBundleVersion=\"(?P<extension_version>[\d.]+)\""

        extension_id = ""
        extension_version = ""
        try:
            with open(path_manifest, mode="r") as f:
                content = f.read()
                match_extension_id = re.search(pattern_regex_extension_id, content)
                match_extension_version = re.search(pattern_regex_extension_version, content)
                if match_extension_id:
                    extension_id = match_extension_id.group("extension_id")
                if match_extension_version:
                    extension_version = semver.VersionInfo.parse(match_extension_version.group("extension_version"))
        except IOError as e:
            if self._log_signal:
                self._log_signal.emit("I/O error({}): {}".format(e.errno, e.strerror), True)
        except Exception as e:  # handle other exceptions such as attribute errors
            if self._log_signal:
                self._log_signal.emit("Unexpected error: {}".format(e), True)

        return extension_id, extension_version

    def update_zxp_extensions(self, quadpype_version: QuadPypeVersion, extensions: [ZXPExtensionData]):
        # Determine the user-specific Adobe extensions directory
        user_extensions_dir = Path(os.getenv('APPDATA'), 'Adobe', 'CEP', 'extensions')

        # Create the user extensions directory if it doesn't exist
        os.makedirs(user_extensions_dir, exist_ok=True)

        version_path = quadpype_version.path

        for extension in extensions:
            # Remove installed ZXP extension
            if self._step_text_signal:
                self._step_text_signal.emit("Removing installed ZXP extension for "
                                            "<b>{}</b> ...".format(extension.host_id))
            if user_extensions_dir.joinpath(extension.host_id).exists():
                shutil.rmtree(user_extensions_dir.joinpath(extension.host_id))

            # Install ZXP shipped in the current version folder
            fullpath_curr_zxp_extension = version_path.joinpath("quadpype",
                                                                "hosts",
                                                                extension.host_id,
                                                                "api",
                                                                "extension.zxp")
            if not fullpath_curr_zxp_extension.exists():
                if self._log_signal:
                    self._log_signal.emit("Cannot find ZXP extension for {}, looked at: {}".format(
                        extension.host_id, str(fullpath_curr_zxp_extension)), True)
                continue

            if self._step_text_signal:
                self._step_text_signal.emit("Install ZXP extension for <b>{}</b> ...".format(extension.host_id))

            # Copy zxp into APPDATA user folder
            shutil.copy2(fullpath_curr_zxp_extension, user_extensions_dir)
            extracted_folder = Path(user_extensions_dir, extension.id)
            zip_path = Path(user_extensions_dir, 'extension.zxp')

            # Extract the .zxp file
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extracted_folder)

            # Cleaned up temporary files removed zip_path
            os.remove(zip_path)

    def get_zxp_extensions_to_update(self, quadpype_version, global_settings, force=False) -> List[ZXPExtensionData]:
        # List of all Adobe software ids (named hosts) handled by QuadPype
        # TODO: where and how to store the list of Adobe software ids
        zxp_host_ids = ["photoshop", "aftereffects"]

        # Determine the user-specific Adobe extensions directory
        user_extensions_dir = Path(os.getenv('APPDATA'), 'Adobe', 'CEP', 'extensions')

        zxp_hosts_to_update = []
        for zxp_host_id in zxp_host_ids:
            version_path = quadpype_version.path
            path_manifest = version_path.joinpath("quadpype", "hosts", zxp_host_id, "api", "extension", "CSXS",
                                                  "manifest.xml")
            extension_new_id, extension_new_version = self.extract_zxp_info_from_manifest(path_manifest)
            if not extension_new_id or not extension_new_version:
                # ZXP extension seems invalid or doesn't exists for this software, skipping
                continue

            cur_manifest = user_extensions_dir.joinpath(extension_new_id, "CSXS", "manifest.xml")
            # Get the installed version
            extension_cur_id, extension_curr_version = self.extract_zxp_info_from_manifest(cur_manifest)

            if not force:
                # Is the update required?

                # Check if the software is enabled in the current global settings
                if global_settings and not global_settings["applications"][zxp_host_id]["enabled"]:
                    # The update isn't necessary if the soft is disabled for the studio, skipping
                    continue

                # Compare the installed version with the new version
                if extension_curr_version and extension_curr_version == extension_new_version:
                    # The two extensions have the same version number, skipping
                    continue

            zxp_hosts_to_update.append(ZXPExtensionData(zxp_host_id,
                                                        extension_new_id,
                                                        extension_curr_version,
                                                        extension_new_version))

        return zxp_hosts_to_update

    def _copy_zip(self, source: Path, destination: Path) -> Path:
        try:
            # copy file to destination
            self._print("Copying zip to destination ...")
            _destination_zip = destination.parent / source.name  # noqa: E501
            copyfile(
                source.as_posix(),
                _destination_zip.as_posix())
        except OSError as e:
            self._print(
                "Cannot copy version to user data directory", log.ERROR,
                exception=e)
            raise QuadPypeVersionIOError((
                f"can't copy version {source.as_posix()} "
                f"to destination {destination.parent.as_posix()}")) from e
        return _destination_zip

    def _is_quadpype_in_dir(self,
                            dir_item: Path,
                            detected_version: QuadPypeVersion) -> bool:
        """Test if path item is QuadPype version matching detected version.

        If item is directory that might (based on it's name)
        contain QuadPype version, check if it really does contain
        QuadPype and that their versions matches.

        Args:
            dir_item (Path): Directory to test.
            detected_version (QuadPypeVersion): QuadPype version detected
                from name.

        Returns:
            True if it is valid QuadPype version, False otherwise.

        """
        try:
            # add one 'quadpype' level as inside dir there should
            # be many other repositories.
            version_check = BootstrapRepos.get_version(dir_item)
        except ValueError as e:
            self._print(
                f"Cannot determine version from {dir_item}", level=log.ERROR, exception=e)
            return False

        version_main = version_check.get_main_version()
        detected_main = detected_version.get_main_version()
        if version_main != detected_main:
            self._print(
                (f"Dir version ({detected_version}) and "
                 f"its content version ({version_check}) "
                 "doesn't match. Skipping."), level=log.ERROR)
            return False
        return True

    def _is_quadpype_in_zip(self,
                            zip_item: Path,
                            detected_version: QuadPypeVersion) -> bool:
        """Test if zip path is QuadPype version matching detected version.

        Open zip file, look inside and parse version from QuadPype
        inside it. If there is none, or it is different from
        version specified in file name, skip it.

        Args:
            zip_item (Path): Zip file to test.
            detected_version (QuadPypeVersion): Pype version detected from
                name.

        Returns:
           True if it is valid QuadPype version, False otherwise.

        """
        # skip non-zip files
        if zip_item.suffix.lower() != ".zip":
            return False

        try:
            with ZipFile(zip_item, "r") as zip_file:
                with zip_file.open(
                        "quadpype/version.py") as version_file:
                    zip_version = {}
                    exec(version_file.read(), zip_version)
                    try:
                        version_check = QuadPypeVersion(
                            version=zip_version["__version__"])
                    except ValueError as e:
                        self._print(str(e), level=log.ERROR)
                        return False

                    version_main = version_check.get_main_version()  # noqa: E501
                    detected_main = detected_version.get_main_version()  # noqa: E501

                    if version_main != detected_main:
                        self._print(
                            (f"Zip version ({detected_version}) "
                             "and its content version "
                             f"({version_check}) "
                             "doesn't match. Skipping."), level=log.ERROR)
                        return False
        except BadZipFile as e:
            self._print(f"{zip_item} is not a zip file", level=log.ERROR, exception=e)
            return False
        except KeyError as e:
            self._print("Zip does not contain QuadPype", level=log.ERROR, exception=e)
            return False
        return True

    def get_quadpype_versions(self, quadpype_dir: Path) -> list:
        """Get all detected QuadPype versions in directory.

        Args:
            quadpype_dir (Path): Directory to scan.

        Returns:
            list of QuadPypeVersion

        Throws:
            ValueError: if invalid path is specified.

        """
        if not quadpype_dir.exists() and not quadpype_dir.is_dir():
            raise ValueError(f"specified directory {quadpype_dir} is invalid")

        quadpype_versions = []
        # iterate over directory in first level and find all that might
        # contain QuadPype.
        for item in quadpype_dir.iterdir():
            # if the item is directory with major.minor version, dive deeper
            if item.is_dir() and re.match(r"^\d+\.\d+$", item.name):
                _versions = self.get_quadpype_versions(item)
                if _versions:
                    quadpype_versions += _versions

            # if it is file, strip extension, in case of dir don't.
            name = item.name if item.is_dir() else item.stem
            result = QuadPypeVersion.version_in_str(name)

            if result:
                detected_version: QuadPypeVersion
                detected_version = result

                if item.is_dir() and not self._is_quadpype_in_dir(
                        item, detected_version
                ):
                    continue

                if item.is_file() and not self._is_quadpype_in_zip(
                        item, detected_version
                ):
                    continue

                detected_version.path = item
                quadpype_versions.append(detected_version)

        return sorted(quadpype_versions)


class QuadPypeVersionExists(Exception):
    """Exception for handling existing QuadPype version."""
    pass


class QuadPypeVersionInvalid(Exception):
    """Exception for handling invalid QuadPype version."""
    pass


class QuadPypeVersionIOError(Exception):
    """Exception for handling IO errors in QuadPype version."""
    pass
