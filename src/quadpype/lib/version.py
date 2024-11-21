import os
import re
import shutil

from pathlib import Path
from abc import abstractmethod
from zipfile import ZipFile, BadZipFile
from typing import Union, List, Tuple, Any, Optional

import semver

MODULES_SETTINGS_KEY = "modules"
_NOT_SET = object()

# Versions should match any string complying with https://semver.org/
VERSION_REGEX = re.compile(r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>[a-zA-Z\d\-.]*))?(?:\+(?P<buildmetadata>[a-zA-Z\d\-.]*))?$")  # noqa: E501

QUADPYPE_VERSION_MANAGER = None
ADDON_VERSION_MANAGER = None


class PackageVersion(semver.VersionInfo):
    """Class for storing information about version.

    Attributes:
        path (str): path

    """

    def __init__(self, *args, **kwargs):
        """Create version.

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
        self._installed_version = None

        if "version" in kwargs:
            version_value = kwargs.pop("version")
            if not version_value:
                raise ValueError("Invalid version specified")
            v = semver.VersionInfo.parse(version_value)
            kwargs["major"] = v.major
            kwargs["minor"] = v.minor
            kwargs["patch"] = v.patch
            kwargs["prerelease"] = v.prerelease
            kwargs["build"] = v.build

        if "path" in kwargs:
            path_value = kwargs.pop("path")
            if isinstance(path_value, str):
                path_value = Path(path_value)
            self.path = path_value

        if args or kwargs:
            super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<{self.__class__.__name__}: {str(self)} - path={self.path}>"

    def __lt__(self, other):
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

    def __hash__(self):
        return hash(self.path) if self.path else hash(str(self))

    def compare_major_minor_patch(self, other) -> bool:
        return self.finalize_version() == other.finalize_version()

    def is_compatible(self, version):
        """Test build compatibility.

        This will simply compare major and minor versions (ignoring patch
        and the rest).

        Args:
            version (BaseVersion): Version to check compatibility with.

        Returns:
            bool: if the version is compatible

        """
        return self.major == version.major and self.minor == version.minor


class PackageVersionExists(Exception):
    """Exception for handling existing QuadPype version."""
    pass


class PackageVersionInvalid(Exception):
    """Exception for handling invalid QuadPype version."""
    pass


class PackageVersionIOError(Exception):
    """Exception for handling IO errors in QuadPype version."""
    pass


class PackageVersionNotFound(Exception):
    """QuadPype version was not found in remote and local repository."""
    pass


class PackageVersionIncompatible(Exception):
    """QuadPype version is not compatible with the installed one (build)."""
    pass


class BaseVersionManager:
    _version_class = PackageVersion

    def __init__(self, local_dir_path: Union[str, Path], remote_dir_path: Union[str, Path]):
        self._local_dir_path = local_dir_path
        self._remote_dir_path = remote_dir_path

        self._installed_version = None

    @property
    def local_dir_path(self):
        return self._local_dir_path

    def change_local_dir_path(self, local_dir_path: Any):
        """Set local path."""
        if isinstance(local_dir_path, str):
            local_dir_path = Path(local_dir_path)
        self._local_dir_path = local_dir_path

    @property
    def remote_dir_path(self):
        return self._remote_dir_path

    def change_remote_dir_path(self, remote_dir_path: Any):
        """Set remote path."""
        if isinstance(remote_dir_path, str):
            remote_dir_path = Path(remote_dir_path)
        self._remote_dir_path = remote_dir_path

    def get_version(self, version, from_remote=False, from_local=False):
        target_version = self.get_version_from_str(version)
        available_versions = self.get_available_versions(from_local=from_local, from_remote=from_remote)
        for available_version in available_versions:
            if str(available_version) == str(target_version):
                return available_version
        return None

    @classmethod
    def get_version_from_str(cls, input_string: str):
        """Find version in given string.

        Args:
            input_string (str):  string to search.

        Returns:
            BaseVersion: of detected or None.

        """
        # Strip .zip ext (if present)
        input_string = re.sub(r"\.zip$", "", input_string, flags=re.IGNORECASE)
        match_obj = re.search(VERSION_REGEX, input_string)

        if not match_obj:
            return None

        return cls._version_class.parse(input_string[match_obj.start():match_obj.end()])

    @abstractmethod
    def is_version_in_dir(self, dir_path: Path, version_obj) -> Tuple[bool, str]:
        """Test if path item is the version matching detected version.

        If item is directory that might (based on it's name)
        contain  version, check if it really does contain a package and
        that their versions matches.

        Args:
            dir_path (Path): Directory to test.
            version_obj (BaseVersion): version detected
                from name.

        Returns:
            Tuple: State and reason, True if it is valid  version,
                   False otherwise.

        """
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def is_version_in_zip(self, zip_path: Path, version_obj) -> Tuple[bool, str]:
        """Check if zip path is a Version matching detected version.

        Open zip file, look inside and parse version from QuadPype
        inside it. If there is none, or it is different from
        version specified in file name, skip it.

        Args:
            zip_path (Path): Path to the ZIP file to test.
            version_obj (BaseVersion): version detected
                from name.

        Returns:
           Tuple: State and reason, True if it is valid Base Version,
                False otherwise.

        """
        raise NotImplementedError("Must be implemented by subclasses")

    def is_remote_dir_path_accessible(self) -> bool:
        """Path to remote directory is accessible.

        Exists for this machine.
        """
        return self._remote_dir_path and self._remote_dir_path.exists()

    def get_available_versions(self, from_local: bool = None, from_remote: bool = None) -> List:
        """Get all available versions."""
        if from_local is None and from_remote is None:
            from_local = True
            from_remote = True
        elif from_local is None and not from_remote:
            from_local = True
        elif from_remote is None and not from_local:
            from_remote = True

        versions = {}

        installed_version = self.get_installed_version()
        versions[str(installed_version)] = installed_version

        versions_lists = [
            self.get_local_versions() if from_local else [],
            self.get_remote_versions() if from_remote else []
        ]

        for versions_list in versions_lists:
            for version_obj in versions_list:
                version_str = str(version_obj)
                if version_str not in versions:
                    versions[version_str] = version_obj

        return sorted(list(versions.values()))

    def get_versions_from_dir(self, dir_path: Path, excluded_str_versions: Optional[List[str]] = None) -> List:
        """Get all detected BaseVersions in directory.

        Args:
            dir_path (Path): Directory to scan.
            excluded_str_versions (List[str]): List of excluded versions as strings.

        Returns:
            List[BaseVersion]: List of detected BaseVersions.

        Throws:
            ValueError: if invalid path is specified.

        """
        if excluded_str_versions is None:
            excluded_str_versions = []

        versions = []

        # Ensure the directory exists and is valid
        if not dir_path.exists() or not dir_path.is_dir():
            return versions

        # Iterate over directory at the first level
        for item in dir_path.iterdir():
            # If the item is a directory with a major.minor version format, dive deeper
            # /!\ Careful: Doing a recursive loop could add multiple versions with the
            #              same base version (major, minor, patch)
            if item.is_dir() and re.match(r"^\d+\.\d+$", item.name):
                detected_versions = self.get_versions_from_dir(item, excluded_str_versions)
                if detected_versions:
                    versions.extend(detected_versions)

            # If it's a file, process its name (stripped of extension)
            name = item.name if item.is_dir() else item.stem
            version = self.get_version_from_str(name)

            if version:
                detected_version = version

                # If it's a directory, check if version is valid within it
                if item.is_dir() and not self.is_version_in_dir(item, detected_version)[0]:
                    continue

                # If it's a file, check if version is valid within the zip
                if item.is_file() and not self.is_version_in_zip(item, detected_version)[0]:
                    continue

                detected_version.path = item
                if str(detected_version) not in excluded_str_versions:
                    versions.append(detected_version)

        return list(sorted(set(versions)))

    def get_latest_version(self, from_local: bool = None, from_remote: bool = None):
        """Get the latest available version.

        The version does not contain information about path and source.

        This is utility version to get the latest version from all found.

        Arguments 'local' and 'remote' define if local and remote repository
        versions are used. All versions are used if both are not set (or set
        to 'None'). If only one of them is set to 'True' the other is disabled.
        It is possible to set both to 'True' (same as both set to None) and to
        'False' in that case only build version can be used.

        Args:
            from_local (bool, optional): List local versions if True.
            from_remote (bool, optional): List remote versions if True.

        Returns:
            Latest version or None

        """
        return self.get_available_versions(from_local, from_remote)[-1]

    def get_local_versions(self, excluded_str_versions: Optional[List[str]] = None) -> List:
        """Get all versions available on this machine.

        Returns:
            list: of compatible versions available on the machine.

        """
        if excluded_str_versions is None:
            excluded_str_versions = []
        return self.get_versions_from_dir(self._local_dir_path, excluded_str_versions)

    def get_remote_versions(self, excluded_str_versions: Optional[List[str]] = None) -> List:
        """Get all versions available in remote path.

        Returns:
            list of BaseVersion: Versions found in remote path.

        """
        if excluded_str_versions is None:
            excluded_str_versions = []

        if not self.is_remote_dir_path_accessible():
            return []

        return self.get_versions_from_dir(self._remote_dir_path, excluded_str_versions)

    @abstractmethod
    def get_installed_version(self):
        """Get version inside build."""
        raise NotImplementedError("Must be implemented by subclasses")

    def retrieve_version(self, version: PackageVersion, from_remote=False, from_local=False):
        """Retrieve specific version available."""
        version_obj  = self.get_version(version, from_remote=from_remote, from_local=from_local)
        if not version_obj:
            raise ValueError(f"Mo version ({version}) available found.")

        if from_remote:
            destination_path = self.local_dir_path.joinpath(str(version_obj))
        elif from_local:
            destination_path = self.remote_dir_path.joinpath(str(version_obj))
        destination_path.mkdir(parents=True, exist_ok=True)

        # Copy the latest version
        if str(version_obj.path).endswith('.zip'):
            with ZipFile(version_obj.path, 'r') as zip_ref:
                zip_ref.extractall(version_obj)
        else:
            shutil.copytree(version_obj.path, destination_path, dirs_exist_ok=True)

        return version_obj



class QuadPypeVersionManager(BaseVersionManager):
    def __init__(self, root_dir_path: Union[str, Path], local_dir_path: Union[str, Path], remote_dir_path: Union[str, Path]):
        super().__init__(local_dir_path, remote_dir_path)

        self._root_dir_path = root_dir_path

    @property
    def root_dir_path(self):
        return self._root_dir_path

    def change_root_dir_path(self, root_dir_path: Any):
        """Set root path."""
        if isinstance(root_dir_path, str):
            root_dir_path = Path(root_dir_path)
        self._root_dir_path = root_dir_path

    @classmethod
    def get_package_version_from_dir(cls, dir_path: Union[str, Path, None] = None) -> Union[str, None]:
        """Get version of QuadPype in the given version directory.

        Note: in frozen QuadPype installed in user data dir, this must point
        one level deeper as it is:
        `quadpype-version-v3.0.0/quadpype/version.py`

        Args:
            dir_path (Path): Path to QuadPype repo.

        Returns:
            str: version string.
            None: if QuadPype is not found.

        """
        if dir_path is None:
            dir_path = Path(os.environ["QUADPYPE_ROOT"])
        elif not isinstance(dir_path, Path):
            dir_path = Path(dir_path)

        # try to find version
        version_file = dir_path.joinpath("quadpype", "version.py")
        if not version_file.exists():
            return None

        version = {}
        with version_file.open("r") as fp:
            exec(fp.read(), version)

        return version['__version__']

    def is_version_in_dir(self, dir_path: Path, version_obj) -> Tuple[bool, str]:
        try:
            # add one level as inside dir there should be many other repositories.
            version_str = self.get_package_version_from_dir(dir_path)
            version_check = PackageVersion(version=version_str)
        except ValueError:
            return False, f"Cannot determine version from {dir_path}"

        if not version_check.compare_major_minor_patch(version_obj):
            return False, (f"Dir version ({version_obj}) and "
                           f"its content version ({version_check}) "
                           "doesn't match. Skipping.")
        return True, "Versions match"

    def is_version_in_zip(self, zip_path: Path, version_obj) -> Tuple[bool, str]:
        # Skip non-zip files
        if zip_path.suffix.lower() != ".zip":
            return False, "Not a zip"

        try:
            with ZipFile(zip_path, "r") as zip_file:
                with zip_file.open(
                        "quadpype/version.py") as version_file:
                    zip_version = {}
                    exec(version_file.read(), zip_version)
                    try:
                        version_check = PackageVersion(
                            version=zip_version["__version__"])
                    except ValueError as e:
                        return False, str(e)

                    if not version_check.compare_major_minor_patch(version_obj):
                        return False, (f"zip version ({version_obj}) "
                                       f"and its content version "
                                       f"({version_check}) "
                                       "doesn't match. Skipping.")
        except BadZipFile:
            return False, f"{zip_path} is not a zip file"
        except KeyError:
            return False, "Zip does not contain OpenPype"
        return True, "Versions match"

    def get_installed_version(self):
        """Get version of QuadPype inside build."""

        if self._installed_version is None:
            installed_version_str = self.get_package_version_from_dir(self._root_dir_path)
            if installed_version_str:
                self._installed_version = PackageVersion(
                    version=installed_version_str,
                    path=self._root_dir_path
                )

        return self._installed_version


class AddOnVersionManager(BaseVersionManager):
    def __init__(self, local_dir_path: Union[str, Path], remote_dir_path: Union[str, Path], use_local_dir: bool = False):
        super().__init__(local_dir_path, remote_dir_path)

        self._use_local_dir = use_local_dir
        self._current_version = None

    @property
    def use_local_dir(self):
        return self._use_local_dir

    @property
    def current_version(self):
        return self._current_version

    def change_current_version(self, current_version: Any):
        """Set current version."""
        if isinstance(current_version, str):
            current_version = PackageVersion(version=current_version)
        self._current_version = current_version

    @classmethod
    def get_package_version_from_dir(cls, dir_path: Union[str, Path, None] = None) -> Union[str, None]:
        return cls.get_version_from_str(dir_path.name)

    def is_version_in_dir(self, dir_path: Path, version_obj) -> Tuple[bool, str]:
        return True, "Versions match"

    def is_version_in_zip(self, zip_path: Path, version_obj) -> Tuple[bool, str]:
        return True, "Versions match"

    def get_installed_version(self):
        return self._current_version


def create_app_version_manager(root_dir_path: Union[str, Path], local_dir_path: Union[str, Path], remote_dir_path: Union[str, Path]) -> QuadPypeVersionManager:
    global QUADPYPE_VERSION_MANAGER
    if QUADPYPE_VERSION_MANAGER is None:
        QUADPYPE_VERSION_MANAGER = QuadPypeVersionManager(root_dir_path, local_dir_path, remote_dir_path)
    return QUADPYPE_VERSION_MANAGER


def get_app_version_manager() -> QuadPypeVersionManager:
    global QUADPYPE_VERSION_MANAGER
    if QUADPYPE_VERSION_MANAGER is None:
        raise RuntimeError("QuadPype Version Manager is not initialized")
    return QUADPYPE_VERSION_MANAGER


def create_addon_version_manager(local_dir_path: Union[str, Path], remote_dir_path: Union[str, Path]) -> AddOnVersionManager:
    global ADDON_VERSION_MANAGER
    if ADDON_VERSION_MANAGER:
        raise RuntimeError("AddOn version manager already initialized")
    ADDON_VERSION_MANAGER = AddOnVersionManager(local_dir_path, remote_dir_path)
    return ADDON_VERSION_MANAGER


def get_addon_version_manager() -> AddOnVersionManager:
    global ADDON_VERSION_MANAGER
    if ADDON_VERSION_MANAGER is None:
        raise RuntimeError("AddOn Version Manager is not initialized")
    return ADDON_VERSION_MANAGER
