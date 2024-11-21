import os
import re
import shutil
import zipfile

from pathlib import Path
from typing import List

import semver

from .version_classes import PackageVersion

class ZXPExtensionData:

    def __init__(self, host_id: str, ext_id: str, installed_version: semver.VersionInfo, shipped_version: semver.VersionInfo):
        self.host_id = host_id
        self.id = ext_id
        self.installed_version = installed_version
        self.shipped_version = shipped_version


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

def update_zxp_extensions(self, quadpype_version: PackageVersion, extensions: [ZXPExtensionData]):
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
