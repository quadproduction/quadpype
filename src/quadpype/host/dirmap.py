"""Dirmap functionality used in host integrations inside DCCs.

Idea for current dirmap implementation was used from Maya where is possible to
enter source and destination roots and maya will try each found source
in referenced file replace with each destination paths. First path which
exists is used.
"""

import os
from abc import ABC, abstractmethod
import platform

from quadpype.lib import Logger
from quadpype.modules import ModulesManager
from quadpype.settings import get_project_settings


class HostDirmap(ABC):
    """Abstract class for running dirmap on a workfile in a host.

    Dirmap is used to translate paths inside of host workfile from one
    OS to another. (Eg. arstist created workfile on Win, different artists
    opens same file on Linux.)

    Expects methods to be implemented inside of host:
        on_dirmap_enabled: run host code for enabling dirmap
        do_dirmap: run host code to do actual remapping
    """

    def __init__(
        self,
        host_name,
        project_name,
        project_settings=None,
        sync_module=None
    ):
        self.host_name = host_name
        self.project_name = project_name
        self._project_settings = project_settings
        self._sync_module = sync_module
        # To limit reinit of the addon
        self._sync_module_discovered = sync_module is not None
        self._log = None

    @property
    def sync_module(self):
        if not self._sync_module_discovered:
            self._sync_module_discovered = True
            manager = ModulesManager()
            self._sync_module = manager.get("sync_server")
        return self._sync_module

    @property
    def project_settings(self):
        if self._project_settings is None:
            self._project_settings = get_project_settings(self.project_name)
        return self._project_settings

    @property
    def log(self):
        if self._log is None:
            self._log = Logger.get_logger(self.__class__.__name__)
        return self._log

    @abstractmethod
    def on_enable_dirmap(self):
        """Run host dependent operation for enabling dirmap if necessary."""
        pass

    @abstractmethod
    def dirmap_routine(self, source_path, destination_path):
        """Run host dependent remapping from source_path to destination_path"""
        pass

    def process_dirmap(self, mapping=None):
        # type: (dict) -> None
        """Go through all paths in Settings and set them using `dirmap`.

            If artists has Site Sync enabled, take dirmap mapping directly from
            the User Settings when artist is syncing a workfile locally.

        """

        if not mapping:
            mapping = self.get_mappings()
        if not mapping:
            return

        self.on_enable_dirmap()

        for k, sp in enumerate(mapping["source-path"]):
            dst = mapping["destination-path"][k]
            try:
                # add trailing slash if missing
                sp = os.path.join(sp, '')
                dst = os.path.join(dst, '')
                print("{} -> {}".format(sp, dst))
                self.dirmap_routine(sp, dst)
            except IndexError:
                # missing corresponding destination path
                self.log.error((
                    "invalid dirmap mapping, missing corresponding"
                    " destination directory."
                ))
                break
            except RuntimeError:
                self.log.error(
                    "invalid path {} -> {}, mapping not registered".format(
                        sp, dst
                    )
                )
                continue

    def get_mappings(self):
        """Get translation from source-path to destination-path.

            It checks if Site Sync is enabled and user chose to use local
            site, in that case configuration in User Settings takes precedence
        """

        dirmap_label = "{}-dirmap".format(self.host_name)
        mapping_sett = self.project_settings[self.host_name].get(dirmap_label,
                                                                 {})
        local_mapping = self._get_local_sync_dirmap()
        mapping_enabled = mapping_sett.get("enabled") or bool(local_mapping)
        if not mapping_enabled:
            return {}

        mapping = (
            local_mapping
            or mapping_sett["paths"]
            or {}
        )

        if (
            not mapping
            or not mapping.get("destination-path")
            or not mapping.get("source-path")
        ):
            return {}
        self.log.info("Processing directory mapping ...")
        self.log.info("mapping:: {}".format(mapping))
        return mapping

    def _get_local_sync_dirmap(self):
        """
            Returns dirmap if synch to local project is enabled.

            Only valid mapping is from roots of remote site to local site set
            in the User Settings.

            Returns:
                dict : { "source-path": [XXX], "destination-path": [YYYY]}
        """
        project_name = self.project_name

        sync_module = self.sync_module
        mapping = {}
        if (
            sync_module is None
            or not sync_module.enabled
            or not sync_module.is_project_enabled(project_name, True)
        ):
            return mapping

        active_site = sync_module.get_local_normalized_site(
            sync_module.get_active_site(project_name))
        remote_site = sync_module.get_local_normalized_site(
            sync_module.get_remote_site(project_name))
        self.log.debug(
            "active {} - remote {}".format(active_site, remote_site)
        )

        if active_site == "local" and active_site != remote_site:
            sync_settings = sync_module.get_sync_project_setting(
                project_name,
                exclude_locals=False,
                cached=False)

            active_roots_overrides = self._get_site_root_overrides(
                sync_module, project_name, active_site)

            remote_roots_overrides = self._get_site_root_overrides(
                sync_module, project_name, remote_site)

            current_platform = platform.system().lower()
            remote_provider = sync_module.get_provider_for_site(
                project_name, remote_site
            )
            # dirmap has sense only with regular disk provider, in the workfile
            # won't be root on cloud or sftp provider so fallback to studio
            if remote_provider != "local_drive":
                remote_site = "studio"
            for root_name, active_site_dir in active_roots_overrides.items():
                remote_site_dir = (
                    remote_roots_overrides.get(root_name)
                    or sync_settings["sites"][remote_site]["root"][root_name]
                )

                if isinstance(remote_site_dir, dict):
                    remote_site_dir = remote_site_dir.get(current_platform)

                if not remote_site_dir:
                    continue

                if os.path.isdir(active_site_dir):
                    if "destination-path" not in mapping:
                        mapping["destination-path"] = []
                    mapping["destination-path"].append(active_site_dir)

                    if "source-path" not in mapping:
                        mapping["source-path"] = []
                    mapping["source-path"].append(remote_site_dir)

            self.log.debug("local sync mapping:: {}".format(mapping))
        return mapping

    def _get_site_root_overrides(
            self, sync_module, project_name, site_name):
        """Safely handle root overrides.
        SiteSync raises ValueError for non-local or studio sites.
        """
        try:
            site_roots_overrides = sync_module.get_site_root_overrides(
                project_name, site_name)
        except ValueError:
            site_roots_overrides = {}
        self.log.debug("{} roots overrides {}".format(
            site_name, site_roots_overrides))
        return site_roots_overrides
