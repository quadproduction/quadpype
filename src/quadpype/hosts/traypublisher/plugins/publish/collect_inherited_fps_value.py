# -*- coding: utf-8 -*-
import pyblish.api


class CollectInheritedFpsValue(pyblish.api.InstancePlugin):
    """Collect FPS value required for review instances.

    ExtractReview plugin requires fps on instance data which
    are missing on instances from TrayPublishes.

    """

    label = "Collect Inherited FPS value"
    order = pyblish.api.CollectorOrder + 0.491
    families = [
        "plate", "pointcache",
        "vdbcache", "online",
        "render", "review"
    ]
    hosts = ["traypublisher"]

    def process(self, instance):
        asset_entity = instance.data.get("assetEntity")
        if not asset_entity:
            self.log.debug("Asset entity is None, cannot collect FPS value")
            return

        key = "fps"
        if key in instance.data or key not in asset_entity["data"]:
            return

        value = asset_entity["data"][key]
        instance.data[key] = value

        self.log.debug("Collected FPS value: {}".format(value))
