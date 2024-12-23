import os
import re
import sys
import shutil
import hashlib
import platform

from pathlib import Path
from zipfile import ZipFile, BadZipFile
from typing import Union, List, Tuple, Any, Optional, Dict

import semver


ADDONS_SETTINGS_KEY = "addons"
_NOT_SET = object()

# Versions should match any string complying with https://semver.org/
VERSION_REGEX = re.compile(r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>[a-zA-Z\d\-.]*))?(?:\+(?P<buildmetadata>[a-zA-Z\d\-.]*))?$")  # noqa: E501

_PACKAGE_MANAGER = None


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
        self.is_archive = False

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
    """Exception for handling existing package version."""
    pass


class PackageVersionInvalid(Exception):
    """Exception for handling invalid package version."""
    pass


class PackageVersionIOError(Exception):
    """Exception for handling IO errors in Package version."""
    pass


class PackageVersionNotFound(Exception):
    """Package version was not found in remote and local repository."""
    pass


class PackageVersionIncompatible(Exception):
    """Package version is not compatible with the installed one (build)."""
    pass


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


class PackageHandler:
    """Class for handling a package."""
    type = "package"

    def __init__(self,
                 pkg_name: str,
                 local_dir_path: Union[str, Path, None],
                 remote_dir_paths: List[Union[str, Path]],
                 running_version_str: str,
                 retrieve_locally: bool = True,
                 install_dir_path: Union[str, Path, None] = None):
        self._name = pkg_name
        self.retrieve_locally = retrieve_locally

        if isinstance(local_dir_path, str):
            local_dir_path = Path(local_dir_path)

        if isinstance(remote_dir_paths, str):
            remote_dir_paths = [Path(remote_dir_paths)]

        # Ensure paths are Path objects
        remote_dir_paths = [Path(curr_path) for curr_path in remote_dir_paths]

        if retrieve_locally and not local_dir_path:
            raise ValueError("local_dir_path cannot be None if retrieve_locally = True")

        self._local_dir_path = local_dir_path

        if not self.is_local_dir_path_accessible():
            try:
                self._local_dir_path.mkdir(parents=True, exist_ok=True)
            except Exception:  # noqa
                raise RuntimeError(f"Local directory path for package \"{pkg_name}\" is not accessible.")

        self._remote_dir_paths = remote_dir_paths
        # remote_dir_paths can be None in case the path to package version isn't specified
        # This can happen only for the QuadPype app package

        self._running_version = None

        if install_dir_path and not isinstance(install_dir_path, Path):
            install_dir_path = Path(install_dir_path)

        self._install_dir_path = install_dir_path
        local_version = None
        if self._install_dir_path:
            local_version = PackageVersion(
                version=self.get_package_version_from_dir(
                    self._name,
                    self._install_dir_path
                ),
                path=self._install_dir_path
            )

        if not running_version_str:
            # If no version specified gets the latest version
            latest_version = self.get_latest_version()
            is_local_more_recent = local_version and local_version >= latest_version
            if latest_version and not is_local_more_recent:
                running_version_str = str(latest_version)
            elif local_version:
                running_version_str = str(local_version)

        if not running_version_str:
            # TODO: The caller should catch this and this and should display an error dialog to the user
            raise ValueError("Cannot find a version to run, neither locally or remotely.")

        if not isinstance(running_version_str, str):
            raise ValueError("Running version must be a valid version string.")

        # If there is a local version and
        # the version requested is the same as the local one,
        # then use the local code version
        if local_version and str(local_version) == running_version_str:
            self._running_version = local_version
        else:
            # Find (and retrieve if necessary) the specified version to run
            running_version = self.find_version(running_version_str, from_local=True)
            if running_version:
                running_version = self.ensure_version_is_dir(running_version)
                self._running_version = running_version
            else:
                running_version = self.find_version(running_version_str)
                if not running_version:
                    if self._install_dir_path:
                        self.get_package_version_from_dir(self._name, self._install_dir_path)
                    raise ValueError(f"Specified version \"{running_version_str}\" is not available locally and on the remote path directory.")

                if retrieve_locally:
                    self._running_version = self.retrieve_version_locally(running_version_str)
                else:
                    # We are about to use a remote version
                    # We need to ensure this version is un-archived
                    running_version = self.ensure_version_is_dir(running_version)
                    self._running_version = running_version

        self._add_package_path_to_env()

    @property
    def name(self):
        return self._name

    @property
    def local_dir_path(self):
        return self._local_dir_path

    def change_local_dir_path(self, local_dir_path: Any):
        """Set the local directory path."""
        if isinstance(local_dir_path, str):
            local_dir_path = Path(local_dir_path)

        if not isinstance(local_dir_path, Path):
            raise ValueError("Invalid local directory path. Must be a string or a Path object.")

        self._local_dir_path = local_dir_path

        # Ensure accessibility
        if not self.is_local_dir_path_accessible():
            raise ValueError(f"Local directory path of package \"{self._name}\" is not accessible.")

    def is_local_dir_path_accessible(self) -> bool:
        """Check if the path to the local directory is accessible."""
        return self._local_dir_path and isinstance(self._local_dir_path, Path) and self._local_dir_path.exists()

    @property
    def remote_dir_paths(self):
        return self._remote_dir_paths

    def change_remote_dir_paths(self, remote_dir_paths: Union[List[Union[str, Path]], None]):
        """Set the remote directory path."""
        if isinstance(remote_dir_paths, str):
            remote_dir_paths = [Path(remote_dir_paths)]
        elif not remote_dir_paths:
            # If the remote_dir-path is unset we use the local_dir_path
            remote_dir_paths = [self._local_dir_path]

        # Ensure paths are Path objects
        remote_dir_paths = [Path(curr_path) for curr_path in remote_dir_paths]

        self._remote_dir_paths = remote_dir_paths

    def get_accessible_remote_dir_path(self):
        """Get the first accessible remote directory path (if any)."""
        if not self._remote_dir_paths:
            return None

        for remote_dir_path in self._remote_dir_paths:
            if remote_dir_path and isinstance(remote_dir_path, Path) and remote_dir_path.exists():
                return remote_dir_path

        return None

    @property
    def running_version(self):
        return self._running_version

    @classmethod
    def validate_version_str(cls, version_str:str) -> Union[str, None]:
        # Strip the .zip extension (if present)
        input_string = re.sub(r"\.zip$", "", version_str, flags=re.IGNORECASE)

        # Validate version string
        match_obj = re.search(VERSION_REGEX, input_string)

        # Return the version str part from the original string (if we get a match)
        return input_string[match_obj.start():match_obj.end()] if match_obj else None

    @classmethod
    def get_version_from_str(cls, version_str: str) -> Union[PackageVersion, None]:
        """Find version in given string.

        Args:
            version_str (str):  string to search.

        Returns:
            PackageVersion: of detected or None.
        """
        version_str = cls.validate_version_str(version_str)
        return PackageVersion.parse(version_str) if version_str else None

    @classmethod
    def get_package_version_from_dir(cls, pkg_name: str, dir_path: Union[str, Path]) -> Union[str, None]:
        """Get version of Package in the given directory.

        Args:
            pkg_name (str):  Package name.
            dir_path (Path): Path to the directory containing the package.

        Returns:
            str: version string.
            None: if version file is not found.
        """
        if dir_path is None:
            raise ValueError("Directory path is not set")

        if isinstance(dir_path, str):
            dir_path = Path(dir_path)

        # Try to find version
        version_file = dir_path.joinpath(pkg_name, "version.py")
        if not version_file.exists():
            return None

        version = {}
        with version_file.open("r") as fp:
            exec(fp.read(), version)

        return version['__version__']

    @classmethod
    def compare_version_with_package_dir(cls, pkg_name:str, dir_path: Path, version_obj) -> Tuple[bool, str]:
        if not dir_path or not isinstance(dir_path, Path) or not dir_path.exists() or not dir_path.is_dir():
            raise ValueError("Invalid directory path")

        try:
            version_str = cls.get_package_version_from_dir(pkg_name, dir_path)
            version_check = PackageVersion(version=version_str)
        except ValueError:
            return False, f"Cannot determine version from {dir_path}"

        if not version_check.compare_major_minor_patch(version_obj):
            return False, (f"Dir version ({version_obj}) and "
                           f"its content version ({version_check}) "
                           "doesn't match. Skipping.")
        return True, "Versions match"

    @ classmethod
    def compare_version_with_package_zip(cls, pkg_name:str, zip_path: Path, version_obj) -> Tuple[bool, str]:
        if not zip_path or not isinstance(zip_path, Path) or not zip_path.exists() or not zip_path.is_file():
            raise ValueError("Invalid ZIP file path.")

        # Skip non-zip files
        if zip_path.suffix.lower() != ".zip":
            return False, "Not a ZIP file."

        try:
            with ZipFile(zip_path, "r") as zip_file:
                with zip_file.open(
                        f"{pkg_name}/version.py") as version_file:
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
            return False, "Zip does not contain QuadPype"
        return True, "Versions match"

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

        #if self._install_dir_path:
        #    installed_version = self.get_installed_version()

        if self._running_version:
            installed_version = self._running_version
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

    @classmethod
    def get_versions_from_dir(cls, pkg_name: str, dir_path: Path, priority_to_archives = False, excluded_str_versions: Optional[List[str]] = None, parent_version: Optional[PackageVersion] = None) -> List:
        """Get all detected PackageVersions in directory.

        Args:
            pkg_name (str):  Name of the package.
            dir_path (Path): Directory to scan.
            priority_to_archives (bool, optional): If True, look for archives in priority.
                (if only a dir exists it will still be added).
            excluded_str_versions (List[str]): List of excluded versions as strings.
            parent_version (PackageVersion): Parent version to use for nested directories.

        Returns:
            List[PackageVersion]: List of detected PackageVersions.

        Throws:
            ValueError: if invalid path is specified.

        """
        if excluded_str_versions is None:
            excluded_str_versions = []

        versions = []

        # Ensure the directory exists and is valid
        if not dir_path or not dir_path.exists() or not dir_path.is_dir():
            return versions

        # Iterate over directory at the first level
        for item in dir_path.iterdir():
            # If the item is a directory with a major.minor version format, dive deeper
            if item.is_dir() and re.match(r"^v?\d+\.\d+$", item.name) and parent_version is None:
                parent_version_str = f"{item.name.removeprefix('v')}.0"
                detected_versions = cls.get_versions_from_dir(
                    pkg_name,
                    item,
                    priority_to_archives,
                    excluded_str_versions,
                    PackageVersion(version=parent_version_str)
                )

                if detected_versions:
                    versions.extend(detected_versions)

            # If it's a file, process its name (stripped of extension)
            name = item.name if item.is_dir() else item.stem
            version = cls.get_version_from_str(name)

            if not version or (parent_version and (version.major != parent_version.major or version.minor != parent_version.minor)):
                continue

            # If it's a directory, check if version is valid within it
            if item.is_dir() and not cls.compare_version_with_package_dir(pkg_name, item, version)[0]:
                continue

            # If it's a file, check if version is valid within the zip
            if item.is_file() and not cls.compare_version_with_package_zip(pkg_name, item, version)[0]:
                continue

            version.path = item.resolve()
            version.is_archive = item.is_file()
            if str(version) not in excluded_str_versions:
                versions.append(version)

        # Correlation dict (key is version str, value is version obj)
        versions_correlation = {}

        # Loop to get in priority what was requested (archives or dir)
        for curr_version in versions:
            if str(curr_version) not in versions_correlation:
                versions_correlation[str(curr_version)] = curr_version
            else:
                favorite_version = versions_correlation[str(curr_version)]
                if (priority_to_archives and not favorite_version.is_archive and curr_version.is_archive) or \
                        (not priority_to_archives and favorite_version.is_archive and not curr_version.is_archive):
                    versions_correlation[str(curr_version)] = curr_version

        return list(sorted(versions_correlation.values()))

    @classmethod
    def get_versions_from_dirs(cls, pkg_name: str, dir_paths: List[Path], priority_to_archives = False, excluded_str_versions: Optional[List[str]] = None) -> List:
        versions_set = set()
        for dir_path in dir_paths:
            if not dir_path:
                continue

            if isinstance(dir_path, str):
                dir_path = Path(dir_path)

            found_versions = cls.get_versions_from_dir(pkg_name, dir_path, priority_to_archives, excluded_str_versions)
            versions_set.update(found_versions)

        return sorted(versions_set)

    def get_latest_version(self, from_local: bool = None, from_remote: bool = None):
        """Get the latest available version.

        The version does not contain information about path and source.

        This is utility version to get the latest version from all found.

        Arguments 'from_local' and 'from_remote' define if local and remote repository
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
        available_versions = self.get_available_versions(from_local, from_remote)
        return available_versions[-1] if available_versions else None

    def get_local_versions(self, excluded_str_versions: Optional[List[str]] = None) -> List:
        """Get all versions available on this machine.

        Returns:
            list: of compatible versions available on the machine.

        """
        if excluded_str_versions is None:
            excluded_str_versions = []

        return self.get_versions_from_dir(
            self._name,
            self._local_dir_path,
            excluded_str_versions=excluded_str_versions
        )

    def get_remote_versions(self, excluded_str_versions: Optional[List[str]] = None) -> List:
        """Get all versions available in remote path.

        Returns:
            list of BaseVersion: Versions found in remote path.

        """
        if excluded_str_versions is None:
            excluded_str_versions = []

        # If the goal is to retrieve the code, we want archives
        priority_to_archives = self.retrieve_locally

        return self.get_versions_from_dirs(
            self._name,
            self._remote_dir_paths,
            priority_to_archives=priority_to_archives,
            excluded_str_versions=excluded_str_versions
        )

    def find_version(self, version: Union[PackageVersion, str], from_local: bool = False) -> Union[PackageVersion, None]:
        """Get a specific version from the local or remote dir if available."""
        if isinstance(version, str):
            version = PackageVersion(version=version)

        versions = self.get_local_versions() if from_local else self.get_remote_versions()
        if versions:
            for curr_version in versions:
                if curr_version == version:
                    return curr_version

        return None

    def retrieve_version_locally(self, version: Union[str, PackageVersion, None] = None):
        """Retrieve the version specified available from remote."""
        if isinstance(version, str):
            version = PackageVersion(version=version)

        if not version:
            version = self._running_version

        # Check if the version exists locally
        local_version = self.find_version(version, from_local=True)
        if local_version:
            # The version exists locally
            # We need to ensure this version is un-archived
            return self.ensure_version_is_dir(local_version)

        # Check if the version exists on the remote
        remote_version = self.find_version(version)
        if not remote_version:
            raise PackageVersionNotFound(
                f"Version {version} of package \"{self._name}\" not found in remote repository.")

        destination_dir = self.local_dir_path.joinpath(f"{remote_version.major}.{remote_version.minor}")
        destination_path = destination_dir.joinpath(str(remote_version))
        destination_path.mkdir(parents=True, exist_ok=True)

        if remote_version.path.suffix == ".zip":
            # Copy locally first
            shutil.copy2(remote_version.path, destination_dir, follow_symlinks=True)

            # Unzip the local copy
            with ZipFile(destination_dir.joinpath(remote_version.path.name), 'r') as zip_ref:
                zip_ref.extractall(destination_path)
        else:
            shutil.copytree(remote_version.path, destination_path, dirs_exist_ok=True)

        return PackageVersion(version=str(version), path=destination_path)

    def validate_checksums(self, base_version_path: Union[str, None] = None) -> tuple:
        """Validate checksums in a given path.

        Returns:
            tuple(bool, str): returns status and reason as a bool
                and str in a tuple.

        """
        dir_path = self._running_version.path
        if base_version_path:
            dir_path = base_version_path

        if not isinstance(dir_path, Path):
            dir_path = Path(dir_path)

        if not dir_path:
            raise ValueError("Installation dir path not specified.")

        checksums_file = dir_path.joinpath("checksums")
        if not checksums_file.exists():
            return False, "Cannot read checksums for archive."
        checksums_data = checksums_file.read_text()
        checksums = [
            tuple(line.split(":"))
            for line in checksums_data.split("\n") if line
        ]

        # compare content of the package / folder against list of files from checksum file.
        # If difference exists, something is wrong and we invalidate directly
        package_path = dir_path.joinpath(self._name)
        files_in_dir = set(
            file.relative_to(dir_path).as_posix()
            for file in package_path.iterdir() if file.is_file()
        )
        files_in_dir.discard("checksums")
        if "LICENSE" in files_in_dir:
            files_in_dir.discard("LICENSE")
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
                    sanitize_long_path((dir_path / file_name).as_posix())
                )
            except FileNotFoundError:
                return False, f"Missing file [ {file_name} ]"

            if file_checksum != current:
                return False, f"Invalid checksum on {file_name}"

        return True, "All ok"

    def _add_package_path_to_env(self):
        """Add package path to environment."""
        if not self._running_version.path:
            raise ValueError("Installation dir path not specified in running_version. Please call first retrieve_version_locally.")

        version_path = self._running_version.path.resolve().as_posix()
        sys.path.insert(0, version_path)

    @staticmethod
    def ensure_version_is_dir(version_obj):
        if not version_obj.is_archive:
            return version_obj

        # Unzip
        destination_path = version_obj.path.parent.joinpath(str(version_obj))
        with ZipFile(version_obj.path, 'r') as zip_ref:
            zip_ref.extractall(destination_path)

        version_obj.path = destination_path
        return version_obj


class AddOnHandler(PackageHandler):
    type = "add_on"


class PackageManager:
    def __init__(self):
        self._packages = {}

    def __getitem__(self, key) -> Union[PackageHandler, None]:
        # This is called when you use square bracket syntax to access an item
        if key not in self._packages:
            return None
        return self._packages[key]

    @property
    def packages(self) -> Dict[str, PackageHandler]:
        return self._packages

    def add_package(self, package_instance):
        """Add package to manager."""
        self._packages[package_instance.name] = package_instance

    def remove_package(self, package_name):
        """Remove package from manager."""
        if package_name in self._packages:
            del self._packages[package_name]


def retrieve_package_manager() -> PackageManager:
    global _PACKAGE_MANAGER
    if _PACKAGE_MANAGER is None:
        _PACKAGE_MANAGER = PackageManager()
    return _PACKAGE_MANAGER


def get_package_manager() -> PackageManager:
    global _PACKAGE_MANAGER
    if _PACKAGE_MANAGER is None:
        raise RuntimeError("Package Manager is not initialized")
    return _PACKAGE_MANAGER


def set_package_manager(package_manager: Any):
    global _PACKAGE_MANAGER
    _PACKAGE_MANAGER = package_manager


def get_package(package_name: str) -> PackageHandler:
    global _PACKAGE_MANAGER
    if _PACKAGE_MANAGER is None:
        raise RuntimeError("Package Manager is not initialized")
    return _PACKAGE_MANAGER[package_name]


def get_packages(package_type: Union[str, None]=None) -> List[PackageHandler]:
    global _PACKAGE_MANAGER
    if _PACKAGE_MANAGER is None:
        raise RuntimeError("Package Manager is not initialized")

    packages = []

    all_packages = _PACKAGE_MANAGER.packages.values()
    if not package_type:
        return all_packages

    for package in all_packages:
        if package.type == package_type:
            packages.append(package)

    return packages
