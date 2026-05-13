import os

import pyblish.api

from quadpype.pipeline import (
    PublishXmlValidationError
)
from quadpype.hosts.aftereffects.api import get_stub


# class ValidateLayersNameLengthSelect(pyblish.api.Action):
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


# class ValidateLayersNameLengthCutName


"""class ValidateLayersNameLength(pyblish.api.InstancePlugin):


    order = pyblish.api.ValidatorOrder
    label = "Validate Layers Name Length"
    families = ["render.farm", "render.local", "render"]
    hosts = ["aftereffects"]
    #actions = [ValidateLayersNameLengthSelect, ValidateLayersNameLengthCutName]
    # optional = True
    # active = True
    invalid_layers = None

    def collect_invalid_layers(self, layers):
        invalid = []

        for layer in layers:
            if len(layer['name']) > 31:
                invalid.append(layer)
            if layer.get('layers'):
                invalid += self.collect_invalid_layers(layer['layers'])
        return invalid

    def process(self, instance):
        stub = get_stub()
        result = stub.get_active_comp_with_inner_layers()
        #self.log.warning(result)

        invalid_layers = self.collect_invalid_layers(result[0]['layers'])
        #self.log.warning(invalid_layers)

        msg = "\n\nThe layers name are too long:"

        for layer in invalid_layers:
            msg += f"\n {layer['name']} ({len(layer['name'])}) characters."

        if invalid_layers:
            if not instance.context.data.get('transientData'):
                instance.context.data['transientData'] = dict()
            instance.context.data['transientData'][self.__class__.__name__] = invalid_layers
            raise PublishXmlValidationError(self, msg)

    @classmethod
    def repair(cls, instance):
        cls.invalid_layers

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

        instance.data["resolutionWidth"] = width
        instance.data["resolutionHeight"] = height
        cls.log.info(f"Resolution for comp with '{instance_data['comp_id']}' has been set to '{resolution_override}'.")"""
