import os
import re
import shutil

from pathlib import Path
from abc import abstractmethod
from zipfile import ZipFile, BadZipFile
from typing import Union, List, Tuple, Any, Optional
from appdirs import user_data_dir

import semver


MODULES_SETTINGS_KEY = "modules"
_NOT_SET = object()


class QuadPypeVersionExists(Exception):
    """Exception for handling existing QuadPype version."""
    pass


class QuadPypeVersionInvalid(Exception):
    """Exception for handling invalid QuadPype version."""
    pass


class QuadPypeVersionIOError(Exception):
    """Exception for handling IO errors in QuadPype version."""
    pass


class QuadPypeVersionNotFound(Exception):
    """QuadPype version was not found in remote and local repository."""
    pass


class QuadPypeVersionIncompatible(Exception):
    """QuadPype version is not compatible with the installed one (build)."""
    pass


class BaseVersion(semver.VersionInfo):
    """Class for storing information about version.

    Attributes:
        path (str): path

    """
    # this should match any string complying with https://semver.org/
    _VERSION_REGEX = re.compile(r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>[a-zA-Z\d\-.]*))?(?:\+(?P<buildmetadata>[a-zA-Z\d\-.]*))?$")  # noqa: E501

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
        self._local_path = _NOT_SET
        self._remote_path = _NOT_SET
        self._installed_version = None

        if "version" in kwargs:
            version_value = kwargs.pop("version")
            if not version_value:
                raise ValueError("Invalid version specified")
            v = QuadPypeVersion.parse(version_value)
            kwargs["major"] = v.major
            kwargs["minor"] = v.minor
            kwargs["patch"] = v.patch
            kwargs["prerelease"] = v.prerelease
            kwargs["build"] = v.build

        optional_allowed_kwargs = [
            ("path", "path"),
            ("local_path", "_local_path"),
            ("remote_path", "_remote_path"),
        ]

        for keyword_arg_tuple in optional_allowed_kwargs:
            if keyword_arg_tuple[0] in kwargs:
                curr_arg_value = kwargs.pop(keyword_arg_tuple[0])
                if isinstance(curr_arg_value, str):
                    curr_arg_value = Path(curr_arg_value)
                setattr(self, keyword_arg_tuple[1], curr_arg_value)

        if args or kwargs:
            super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<{self.__class__.__name__}: {str(self)} - path={self.path}>"

    def __lt__(self, other: "BaseVersion"):
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

    @staticmethod
    def version_in_str(string: str) -> Union[None, "BaseVersion"]:
        """Find version in given string.

        Args:
            string (str):  string to search.

        Returns:
            BaseVersion: of detected or None.

        """
        # Strip .zip ext (if present)
        string = re.sub(r"\.zip$", "", string, flags=re.IGNORECASE)
        m = re.search(BaseVersion._VERSION_REGEX, string)

        if not m:
            return None

        return BaseVersion.parse(string[m.start():m.end()])

    @staticmethod
    @abstractmethod
    def is_version_in_dir(
            dir_item: Path, version: "BaseVersion") -> Tuple[bool, str]:
        """Test if path item is the version matching detected version.

        If item is directory that might (based on it's name)
        contain  version, check if it really does contain a package and
        that their versions matches.

        Args:
            dir_item (Path): Directory to test.
            version (BaseVersion): version detected
                from name.

        Returns:
            Tuple: State and reason, True if it is valid  version,
                   False otherwise.

        """
        raise NotImplementedError("Must be implemented by subclasses")

    @staticmethod
    @abstractmethod
    def is_version_in_zip(
            zip_item: Path, version: "BaseVersion") -> Tuple[bool, str]:
        """Check if zip path is a Version matching detected version.

        Open zip file, look inside and parse version from QuadPype
        inside it. If there is none, or it is different from
        version specified in file name, skip it.

        Args:
            zip_item (Path): Zip file to test.
            version (BaseVersion): version detected
                from name.

        Returns:
           Tuple: State and reason, True if it is valid Base Version,
                False otherwise.

        """
        raise NotImplementedError("Must be implemented by subclasses")

    def is_remote_path_accessible(self) -> bool:
        """Path to remote directory is accessible.

        Exists for this machine.
        """
        remote_path = self.get_remote_path()

        return remote_path and remote_path.exists()

    def get_local_path(self) -> Path:
        """Path to local repo.

        By default, it should be user appdata
        """
        if self._local_path is _NOT_SET:
            raise ValueError("Local path need to be set. Call set_local_path() first.")
        if not isinstance(self._local_path, Path):
            raise TypeError("Local path must be Path object.")
        return self._local_path

    def set_local_path(self, local_path: Any):
        """Set local path."""
        if isinstance(local_path, str):
            local_path = Path(local_path)
        self._local_path = local_path

    def get_remote_path(self) -> Union[Path, None]:
        """Path to remote repo"""
        if self._remote_path is _NOT_SET:
            raise ValueError("Remote path need to be set. Call set_remote_path() first.")
        return self._remote_path

    def set_remote_path(self, remote_path: Any):
        """Set remote path."""
        if isinstance(remote_path, str):
            remote_path = Path(remote_path)
        self._remote_path = remote_path

    def get_available_versions(self, local: bool = None, remote: bool = None) -> List["BaseVersion"]:
        """Get all available versions."""
        if local is None and remote is None:
            local = True
            remote = True
        elif local is None and not remote:
            local = True
        elif remote is None and not local:
            remote = True

        versions = {}

        installed_version = self.get_installed_version()
        versions[str(installed_version)] = installed_version

        versions_lists = [
            self.get_local_versions() if local else [],
            self.get_remote_versions() if remote else []
        ]

        for versions_list in versions_lists:
            for version_obj in versions_list:
                version_str = str(version_obj)
                if version_str not in versions:
                    versions[version_str] = version_obj

        return sorted(list(versions.values()))


    def get_latest_version(self, local: bool = None, remote: bool = None ) -> Union["BaseVersion", None]:
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
            Latest BaseVersion or None

        """
        return self.get_available_versions(local=local, remote=remote)[-1]

    def get_local_versions(self) -> List:
        """Get all versions available on this machine.

        Returns:
            list: of compatible versions available on the machine.

        """
        versions = self.get_versions_from_directory(self.get_local_path())
        return list(sorted(set(versions)))

    def get_remote_versions(self, excluded_str_versions: Optional[List[str]] = None) -> List:
        """Get all versions available in remote path.

        Returns:
            list of BaseVersion: Versions found in remote path.

        """
        if excluded_str_versions is None:
            excluded_str_versions = []

        # Return all local versions if arguments are set to None
        dir_to_search: Union[Path, None] = None
        if self.is_remote_path_accessible():
            dir_to_search: Path = self._remote_path

        if not dir_to_search:
            return []

        versions = self.get_versions_from_directory(dir_to_search, excluded_str_versions)

        return list(sorted(set(versions)))

    @abstractmethod
    def get_installed_version(self):
        """Get version inside build."""
        raise NotImplementedError("Must be implemented by subclasses")

    @staticmethod
    def get_versions_from_directory(root_directory: Path, excluded_str_versions: Optional[List[str]] = None) -> List:
        """Get all detected BaseVersions in directory.

        Args:
            root_directory (Path): Directory to scan.
            excluded_str_versions (List[str]): List of excluded versions as strings.

        Returns:
            List[BaseVersion]: List of detected BaseVersions.

        Throws:
            ValueError: if invalid path is specified.

        """
        if excluded_str_versions is None:
            excluded_str_versions = []

        base_versions = []

        # Ensure the directory exists and is valid
        if not root_directory.exists() or not root_directory.is_dir():
            return base_versions

        # Iterate over directory at the first level
        for item in root_directory.iterdir():
            # If the item is a directory with a major.minor version format, dive deeper
            # /!\ Careful: Doing a recursive loop could add multiple versions with the
            #              same base version (major, minor, patch)
            if item.is_dir() and re.match(r"^\d+\.\d+$", item.name):
                detected_versions = BaseVersion.get_versions_from_directory(item, excluded_str_versions)
                if detected_versions:
                    base_versions.extend(detected_versions)

            # If it's a file, process its name (stripped of extension)
            name = item.name if item.is_dir() else item.stem
            version_result = BaseVersion.version_in_str(name)

            if version_result:
                detected_version = version_result

                # If it's a directory, check if version is valid within it
                if item.is_dir() and not BaseVersion.is_version_in_dir(item, detected_version)[0]:
                    continue

                # If it's a file, check if version is valid within the zip
                if item.is_file() and not BaseVersion.is_version_in_zip(item, detected_version)[0]:
                    continue

                detected_version.path = item
                if str(detected_version) not in excluded_str_versions:
                    base_versions.append(detected_version)

        return sorted(base_versions)

    def is_compatible(self, version: "BaseVersion"):
        """Test build compatibility.

        This will simply compare major and minor versions (ignoring patch
        and the rest).

        Args:
            version (BaseVersion): Version to check compatibility with.

        Returns:
            bool: if the version is compatible

        """
        return self.major == version.major and self.minor == version.minor

    def update_local_to_latest_version(self):
        """
            Updates the local additional module to the latest version available from remote.
        """
        installed_version = self.get_installed_version()
        latest_remote_version = self.get_latest_version(remote=True)
        destination_path = Path(self.get_local_path()) / str(latest_remote_version)
        destination_path.mkdir(parents=True, exist_ok=True)
        # If no local version or remote version is newer, copy the latest version
        if (latest_remote_version and installed_version is None) or latest_remote_version > installed_version:
            # Remove the old version (if exists)
            if installed_version:
                shutil.rmtree(installed_version.path)

            # Copy the latest version
            if str(latest_remote_version.path).endswith('.zip'):
                with ZipFile(latest_remote_version.path, 'r') as zip_ref:
                    zip_ref.extractall(destination_path)
            else:
                shutil.copytree(latest_remote_version.path, destination_path, dirs_exist_ok=True)

        return destination_path


class AdditionalModulesVersion(BaseVersion):
    """Class for storing information about Additional Modules version.

    Attributes:
        path (str): path to Additional Modules

    """

    @staticmethod
    def is_version_in_dir(
            dir_item: Path, version: "AdditionalModulesVersion") -> Tuple[bool, str]:
        # TODO: Write this method
        return True, "Versions match"

    @staticmethod
    def is_version_in_zip(
            zip_item: Path, version: "AdditionalModulesVersion") -> Tuple[bool, str]:
        # TODO: Write this method
        return True, "Versions match"

    def get_installed_version(self):
        """Get version inside build."""
        #1. dans les settings overrides check en fonction prod (3.4.1) / staging (7.2.1)
        # if boolean est pas checké c'est directement le path du serveur
        # installed_versions = cls.get_versions_from_directory(LE_PATH_SPECIFIER_DANS_LES_SETTINGS)
        #lorsque bool coché : cls.get_local_path()
        # installed_versions = cls.get_versions_from_directory(cls.get_local_path())

        # if prod check que prod (3.4.1) est bien dans installed_versions
        # if staging la meme

        # si empty pour la version dep rod en prod ou de staging en staging
        # return installed_versions[-1]
        # TODO: Write this method

        #if cls._installed_version is None:
        #    installed_versions = cls.get_versions_from_directory(cls.get_local_path())
        #    if installed_versions:
        #        cls._installed_version = installed_versions[0]
        #return cls._installed_version

    def get_remote_path(self):
        """Path to additional_modules directory."""
        #value = get_studio_global_settings_overrides()
        #addon_settings = value.get(MODULES_SETTINGS_KEY).get("addon")
        #addon_path = addon_settings.get("addon_paths").get(platform.system().lower())

        addon_path = None

        remote_path = None
        if addon_path:
            remote_path = Path(addon_path[0].format(**os.environ)).parent

        self._remote_path = remote_path

        return self._remote_path

    def get_local_path(self):
        """Path to unzipped versions.

        By default, it should be user appdata, but could be overridden by
        settings.
        """
        self._local_path = Path(user_data_dir("quadpype", "quad")) / "additional_modules"
        return self._local_path


class QuadPypeVersion(BaseVersion):

    def get_installed_version(self):
        """Get version of QuadPype inside build."""

        if self._installed_version is None:
            installed_version_str = self.get_version_str_from_quadpype_version(self.path)
            if installed_version_str:
                self._installed_version = QuadPypeVersion(
                    version=installed_version_str,
                    path=self.path
                )

        return self._installed_version

    @classmethod
    def get_version_str_from_quadpype_version(cls, repo_dir: Union[str, Path, None] = None) -> Union[str, None]:
        """Get version of QuadPype in the given version directory.

        Note: in frozen QuadPype installed in user data dir, this must point
        one level deeper as it is:
        `quadpype-version-v3.0.0/quadpype/version.py`

        Args:
            repo_dir (Path): Path to QuadPype repo.

        Returns:
            str: version string.
            None: if QuadPype is not found.

        """
        if repo_dir is None:
            repo_dir = Path(os.environ["QUADPYPE_ROOT"])
        elif not isinstance(repo_dir, Path):
            repo_dir = Path(repo_dir)

        # try to find version
        version_file = repo_dir.joinpath("quadpype", "version.py")
        if not version_file.exists():
            return None

        version = {}
        with version_file.open("r") as fp:
            exec(fp.read(), version)

        return version['__version__']

    @staticmethod
    def is_version_in_dir(
            dir_item: Path, version: "QuadPypeVersion") -> Tuple[bool, str]:
        try:
            # add one level as inside dir there should be many other repositories.
            version_str = QuadPypeVersion.get_version_str_from_quadpype_version(dir_item)
            version_check = QuadPypeVersion(version=version_str)
        except ValueError:
            return False, f"cannot determine version from {dir_item}"

        if not version_check.compare_major_minor_patch(version):
            return False, (f"dir version ({version}) and "
                           f"its content version ({version_check}) "
                           "doesn't match. Skipping.")
        return True, "Versions match"

    @staticmethod
    def is_version_in_zip(
            zip_item: Path, version: "QuadPypeVersion") -> Tuple[bool, str]:
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

                    if not version_check.compare_major_minor_patch(version):
                        return False, (f"zip version ({version}) "
                                       f"and its content version "
                                       f"({version_check}) "
                                       "doesn't match. Skipping.")
        except BadZipFile:
            return False, f"{zip_item} is not a zip file"
        except KeyError:
            return False, "Zip does not contain OpenPype"
        return True, "Versions match"
