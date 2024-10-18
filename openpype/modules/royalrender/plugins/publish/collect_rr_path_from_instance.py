# -*- coding: utf-8 -*-
import pyblish.api

from openpype.settings import (
    MODULES_SETTINGS_KEY,
    PROJECT_SETTINGS_KEY,
    SYSTEM_SETTINGS_KEY
)


class CollectRRPathFromInstance(pyblish.api.InstancePlugin):
    """Collect RR Path from instance."""

    order = pyblish.api.CollectorOrder
    label = "Collect Royal Render path name from the Instance"
    families = ["render", "prerender", "renderlayer"]

    def process(self, instance):
        instance.data["rrPathName"] = self._collect_rr_path_name(instance)
        self.log.info(
            "Using '{}' for submission.".format(instance.data["rrPathName"]))

    @staticmethod
    def _collect_rr_path_name(instance):
        # type: (pyblish.api.Instance) -> str
        """Get Royal Render pat name from render instance."""
        rr_settings = (
            instance.context.data
            [SYSTEM_SETTINGS_KEY]
            [MODULES_SETTINGS_KEY]
            ["royalrender"]
        )
        if not instance.data.get("rrPaths"):
            return "default"
        try:
            default_servers = rr_settings["rr_paths"]
            project_servers = (
                instance.context.data
                [PROJECT_SETTINGS_KEY]
                ["royalrender"]
                ["rr_paths"]
            )
            rr_servers = {
                k: default_servers[k]
                for k in project_servers
                if k in default_servers
            }

        except (AttributeError, KeyError):
            # Handle situation were we had only one url for royal render.
            return rr_settings["rr_paths"]["default"]

        return list(rr_servers.keys())[int(instance.data.get("rrPaths"))]
