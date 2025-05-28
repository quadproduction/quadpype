# -*- coding: utf-8 -*-
"""Validate scene settings.
Requires:
    instance    -> assetEntity
    instance    -> anatomyData
"""
import os
import re

import pyblish.api

from quadpype.pipeline.settings import extract_width_and_height
from quadpype.pipeline.publish import RepairAction
from quadpype.pipeline import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)

from quadpype.hosts.aftereffects.api import get_asset_settings
from quadpype.hosts.aftereffects.api.lib import set_settings


# class ValidateSceneSettingsRepair(pyblish.api.Action):
#     """Repair the instance asset with value from Context."""
#
#     label = "Repair"
#     icon = "wrench"
#     on = "failed"
#
#     def process(self, context, plugin):
#         # Get the errored instances
#         failed = []
#         for result in context.data["results"]:
#             if (result["error"] is not None and result["instance"] is not None
#                     and result["instance"] not in failed):
#                 failed.append(result["instance"])
#
#         # Apply pyblish.logic to get the instances for the plug-in
#         instances = pyblish.api.instances_by_plugin(failed, plugin)
#         stub = get_stub()
#         for instance in instances:
#             data = stub.read(instance[0])
#
#             data["asset"] = get_current_asset_name()
#             stub.imprint(instance[0].instance_id, data)


class ValidateSceneSettings(OptionalPyblishPluginMixin,
                            pyblish.api.InstancePlugin):
    """Ensures that Composition Settings (right mouse on comp) are same as
    task in QuadPype.

    By default checks only duration - how many frames should be rendered.
    Compares:
        Frame start - Frame end + 1 against duration in Composition Settings.

    If this complains:
        Check error message where is discrepancy.
        Check/modify rendered Composition Settings.

    If you know what you are doing run publishing again, uncheck this
    validation before Validation phase.
    """

    """
        Dev docu:
        Could be configured by 'presets/plugins/aftereffects/publish'

        skip_timelines_check - fill task name for which skip validation of
            frameStart
            frameEnd
            fps
            handleStart
            handleEnd
        skip_resolution_check - fill entity type ('asset') to skip validation
            resolutionWidth
            resolutionHeight
            TODO support in extension is missing for now

         By defaults validates duration (how many frames should be published)
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Scene Settings"
    families = ["render.farm", "render.local", "render"]
    hosts = ["aftereffects"]
    actions = [RepairAction]
    optional = True

    skip_timelines_check = [".*"]  # * >> skip for all
    skip_resolution_check = [".*"]

    def process(self, instance):
        """Plugin entry point."""
        # Skip the instance if is not active by data on the instance
        if not self.is_active(instance.data):
            return

        publish_attributes = instance.data.get("publish_attributes")
        auto_set_resolution_state = publish_attributes.get("AutoSetResolution", {}).get("active", None)

        asset_doc = instance.data["assetEntity"]
        expected_settings = get_asset_settings(asset_doc)

        resolution_override = instance.data.get("creator_attributes", {}).get('resolution')
        width, height = extract_width_and_height(resolution_override)
        if width and height and not self._resolutions_are_identical(expected_settings, width, height):
            self.log.info(
                f"Resolution data has been replaced by following values : \n"
                f"- 'resolutionWidth': {expected_settings['resolutionWidth']} -> {width}\n"
                f"- 'resolutionHeight' : {expected_settings['resolutionHeight']} -> {height}"
            )

            expected_settings['resolutionWidth'] = width
            expected_settings['resolutionHeight'] = height

        self.log.info("config from DB::{}".format(expected_settings))

        task_name = instance.data["anatomyData"]["task"]["name"]

        not_empty = self.skip_resolution_check != ['']
        if auto_set_resolution_state is True:
            self.log.info("Skipping resolution check because auto set resolution is active.")
            self.remove_resolution_data_from_settings(expected_settings)

        elif not_empty and any(re.search(pattern, task_name)
                for pattern in self.skip_resolution_check):
            self.log.debug(
                f"Skipping resolution check for task name: {task_name}"
            )
            self.remove_resolution_data_from_settings(expected_settings)

        if any(re.search(pattern, task_name)
                for pattern in self.skip_timelines_check):
            self.log.debug(
                f"Skipping frames check for task name: {task_name}"
            )
            expected_settings.pop('fps', None)
            expected_settings.pop('frameStart', None)
            expected_settings.pop('frameEnd', None)
            expected_settings.pop('handleStart', None)
            expected_settings.pop('handleEnd', None)

        # handle case where ftrack uses only two decimal places
        # 23.976023976023978 vs. 23.98
        fps = instance.data.get("fps")
        if fps:
            if isinstance(fps, float):
                fps = float(
                    "{:.2f}".format(fps))
            expected_settings["fps"] = fps

        duration = (
            instance.data.get("frameEndHandle")
            - instance.data.get("frameStartHandle")
            + 1
        )

        self.log.debug(f"Validating attributes: {expected_settings}")

        current_settings = {
            "fps": fps,
            "frameStart": instance.data.get("frameStart"),
            "frameEnd": instance.data.get("frameEnd"),
            "handleStart": instance.data.get("handleStart"),
            "handleEnd": instance.data.get("handleEnd"),
            "frameStartHandle": instance.data.get("frameStartHandle"),
            "frameEndHandle": instance.data.get("frameEndHandle"),
            "resolutionWidth": instance.data.get("resolutionWidth"),
            "resolutionHeight": instance.data.get("resolutionHeight"),
            "duration": duration
        }
        self.log.debug(f"Comp attributes: {current_settings}")

        invalid_settings = []
        invalid_keys = set()
        for key, value in expected_settings.items():
            if value != current_settings[key]:
                msg = "'{}' expected: '{}'  found: '{}'".format(
                    key, value, current_settings[key])

                if key == "duration" and expected_settings.get("handleStart"):
                    msg += (
                        "Handles included in calculation. Remove "
                        "handles in DB or extend frame range in "
                        "Composition Setting."
                    )

                invalid_settings.append(msg)
                invalid_keys.add(key)

        if invalid_settings:
            msg = "Found invalid settings:\n{}".format(
                "\n".join(invalid_settings)
            )

            invalid_keys_str = ",".join(invalid_keys)
            break_str = "<br/>"
            invalid_setting_str = "<b>Found invalid settings:</b><br/>{}".\
                format(break_str.join(invalid_settings))

            formatting_data = {
                "invalid_setting_str": invalid_setting_str,
                "invalid_keys_str": invalid_keys_str
            }
            raise PublishXmlValidationError(self, msg,
                                            formatting_data=formatting_data)

        if not os.path.exists(instance.data.get("source")):
            scene_url = instance.data.get("source")
            msg = "Scene file {} not found (saved under wrong name)".format(
                scene_url
            )
            formatting_data = {
                "scene_url": scene_url
            }
            raise PublishXmlValidationError(self, msg, key="file_not_found",
                                            formatting_data=formatting_data)

    @staticmethod
    def _resolutions_are_identical(settings, width, height):
        write_width = settings['resolutionWidth']
        write_height = settings['resolutionHeight']
        return int(width) == int(write_width) and int(height) == int(write_height)

    @staticmethod
    def remove_resolution_data_from_settings(settings):
        settings.pop("resolutionWidth")
        settings.pop("resolutionHeight")

    @classmethod
    def repair(cls, instance):
        instance_data = instance.data
        resolution_override = instance_data.get("creator_attributes", {}).get('resolution')
        if not resolution_override:
            cls.log.warning('Can not find resolution creator attribute from instance data. Process has been aborted.')
            return False

        width, height = extract_width_and_height(resolution_override)
        set_settings(
            frames=False,
            resolution=True,
            comp_ids=[instance_data["comp_id"]],
            print_msg=False,
            override_width=width,
            override_height=height
        )

        cls.log.info(f"Resolution for comp with '{instance_data['comp_id']}' has been set to '{resolution_override}'.")
