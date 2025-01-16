# -*- coding: utf-8 -*-
import pyblish.api

from quadpype.pipeline import OptionalPyblishPluginMixin


class CollectInheritedFrameRange(pyblish.api.InstancePlugin, OptionalPyblishPluginMixin):
    """Collect frame range data required for review instances.

    ExtractReview plugin requires frame start/end data which
    are missing on instances from TrayPublishes.

    """

    label = "Collect Inherited Frame Range"
    order = pyblish.api.CollectorOrder + 0.491
    families = [
        "plate", "pointcache",
        "vdbcache", "online",
        "render", "review", "image"
    ]
    hosts = ["traypublisher"]
    optional = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        asset_entity = instance.data.get("assetEntity")
        if not asset_entity:
            self.log.debug("Asset entity is None, cannot collect frame range data")
            return

        asset_data = asset_entity["data"]
        # Store collected data for logging
        collected_data = {}
        for key in (
            "frameStart",
            "frameEnd",
            "handleStart",
            "handleEnd",
        ):
            if key in instance.data or key not in asset_data:
                continue
            value = asset_data[key]
            collected_data[key] = value
            instance.data[key] = value

        self.log.debug("Collected data: {}".format(str(collected_data)))
