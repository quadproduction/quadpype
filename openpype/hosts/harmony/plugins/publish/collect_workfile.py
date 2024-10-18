# -*- coding: utf-8 -*-
"""Collect current workfile from Harmony."""
import os
import pyblish.api

from openpype.settings import PROJECT_SETTINGS_KEY
from openpype.pipeline.create import get_subset_name


class CollectWorkfile(pyblish.api.ContextPlugin):
    """Collect current script for publish."""

    order = pyblish.api.CollectorOrder + 0.1
    label = "Collect Workfile"
    hosts = ["harmony"]

    def process(self, context):
        """Plugin entry point."""
        family = "workfile"
        basename = os.path.basename(context.data["currentFile"])
        subset = get_subset_name(
            family,
            "",
            context.data["anatomyData"]["task"]["name"],
            context.data["assetEntity"],
            context.data["anatomyData"]["project"]["name"],
            host_name=context.data["hostName"],
            project_settings=context.data[PROJECT_SETTINGS_KEY]
        )

        # Create instance
        instance = context.create_instance(subset)
        instance.data.update({
            "subset": subset,
            "label": basename,
            "name": basename,
            "family": family,
            "families": [family],
            "representations": [],
            "asset": context.data["asset"]
        })
