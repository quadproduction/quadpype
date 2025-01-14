# -*- coding: utf-8 -*-
import pyblish.api


class CollectReviewInfo(pyblish.api.InstancePlugin):
    """Collect data required for review instances.

    ExtractReview plugin requires frame start/end, fps on instance data which
    are missing on instances from TrayPublishes.

    """

    label = "Collect Review Info"
    order = pyblish.api.CollectorOrder + 0.491
    families = ["review"]
    hosts = ["traypublisher"]

    def process(self, instance):
        asset_entity = instance.data.get("assetEntity")
        if instance.data.get("frameStart") is not None or not asset_entity:
            self.log.debug("Missing required data on instance")
            return

        asset_data = asset_entity["data"]
        # Store collected data for logging
        collected_data = {}
        for key in (
            "fps",
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

        if asset_entity["type"] == "asset":
            # For asset frameEnd need to be computed based on the file count of each representation
            # Setting 0 to specify this need to be computed
            collected_data["frameEnd"] = 0
            instance.data["frameEnd"] = 0

        self.log.debug("Collected data: {}".format(str(collected_data)))
