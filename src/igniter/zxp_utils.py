import os
import re
import shutil
import zipfile
import platform

from pathlib import Path
from typing import List

import semver
from qtpy import QtCore


class ZXPExtensionData:

    def __init__(self, host_id: str, ext_id: str, installed_version: semver.VersionInfo, shipped_version: semver.VersionInfo):
        self.host_id = host_id
        self.id = ext_id
        self.installed_version = installed_version
        self.shipped_version = shipped_version


def extract_zxp_info_from_manifest(path_manifest: Path):
    extension_id = ""
    extension_version = ""

    if not path_manifest.exists():
        return extension_id, extension_version

    pattern_regex_extension_id = r"ExtensionBundleId=\"(?P<extension_id>[\w.]+)\""
    pattern_regex_extension_version = r"ExtensionBundleVersion=\"(?P<extension_version>[\d.]+)\""
    try:
        with open(path_manifest, mode="r") as f:
            content = f.read()
            match_extension_id = re.search(pattern_regex_extension_id, content)
            match_extension_version = re.search(pattern_regex_extension_version, content)
            if match_extension_id:
                extension_id = match_extension_id.group("extension_id")
            if match_extension_version:
                extension_version = semver.VersionInfo.parse(match_extension_version.group("extension_version"))
    except Exception:  # noqa
        return extension_id, extension_version

    return extension_id, extension_version


def update_zxp_extensions(running_version_fullpath: Path, extensions: [ZXPExtensionData]):
    # Determine the user-specific Adobe extensions directory
    user_extensions_dir = Path(os.getenv('APPDATA'), 'Adobe', 'CEP', 'extensions')

    # Create the user extensions directory if it doesn't exist
    os.makedirs(user_extensions_dir, exist_ok=True)

    for extension in extensions:
        # Remove installed ZXP extension
        if user_extensions_dir.joinpath(extension.host_id).exists():
            shutil.rmtree(user_extensions_dir.joinpath(extension.host_id))

        # Install ZXP shipped in the current version folder
        fullpath_curr_zxp_extension = running_version_fullpath.joinpath(
            "quadpype",
            "hosts",
            extension.host_id,
            "api",
            "extension.zxp"
        )
        if not fullpath_curr_zxp_extension.exists():
            continue

        # Copy zxp into APPDATA user folder
        shutil.copy2(fullpath_curr_zxp_extension, user_extensions_dir)
        extracted_folder = Path(user_extensions_dir, extension.id)
        zip_path = Path(user_extensions_dir, 'extension.zxp')

        # Extract the .zxp file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extracted_folder)

        # Cleaned up temporary files removed zip_path
        os.remove(zip_path)


def get_zxp_extensions_to_update(running_version_fullpath, global_settings, force=False) -> List[ZXPExtensionData]:
    # List of all Adobe software ids (named hosts) handled by QuadPype
    # TODO: where and how to store the list of Adobe software ids
    low_platform = platform.system().lower()
    if low_platform == "linux":
        # ZXP skipped for Linux
        return []
    elif low_platform == "darwin":
        # TODO: implement this function for macOS
        return []
        # raise NotImplementedError(f"MacOS not implemented, implementation need before the first macOS release")

    zxp_host_ids = ["photoshop", "aftereffects"]

    # Determine the user-specific Adobe extensions directory
    user_extensions_dir = Path(os.getenv('APPDATA'), 'Adobe', 'CEP', 'extensions')

    zxp_hosts_to_update = []
    for zxp_host_id in zxp_host_ids:
        path_manifest = running_version_fullpath.joinpath(
            "quadpype", "hosts", zxp_host_id, "api", "extension", "CSXS", "manifest.xml")
        running_extension_id, running_extension_version = extract_zxp_info_from_manifest(path_manifest)
        if not running_extension_id or not running_extension_version:
            # ZXP extension seems invalid or doesn't exists for this software, skipping
            continue

        cur_manifest = user_extensions_dir.joinpath(running_extension_id, "CSXS", "manifest.xml")
        # Get the installed version
        installed_extension_id, installed_extension_version = extract_zxp_info_from_manifest(cur_manifest)

        if not force:
            # Is the update required?

            # Check if the software is enabled in the current global settings
            if global_settings and not global_settings["applications"][zxp_host_id]["enabled"]:
                # The update isn't necessary if the soft is disabled for the studio, skipping
                continue

            # Compare the installed version with the new version
            if installed_extension_version and installed_extension_version == running_extension_version:
                # The two extensions have the same version number, skipping
                continue

        zxp_hosts_to_update.append(ZXPExtensionData(zxp_host_id,
                                                    running_extension_id,
                                                    installed_extension_version,
                                                    running_extension_version))

    return zxp_hosts_to_update


class ZXPUpdateThread(QtCore.QThread):
    """Thread worker to update the ZXP"""
    log_signal = QtCore.Signal((str, bool))
    step_text_signal = QtCore.Signal(str)

    def __init__(self, parent=None):
        self._result = None
        self._version_fullpath = None
        self._zxp_hosts = []
        super().__init__(parent)

    def set_version_fullpath(self, version_fullpath):
        self._version_fullpath = version_fullpath

    def set_zxp_hosts(self, zxp_hosts: List[ZXPExtensionData]):
        self._zxp_hosts = zxp_hosts

    def result(self):
        """Result of finished installation."""
        return self._result

    def _set_result(self, value):
        self._result = value

    def run(self):
        """Thread entry point."""
        update_zxp_extensions(self._version_fullpath, self._zxp_hosts)
        self._set_result(self._version_fullpath)
