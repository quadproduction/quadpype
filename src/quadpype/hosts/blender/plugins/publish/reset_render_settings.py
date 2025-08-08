from typing import List

import bpy

import pyblish.api
from quadpype.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)
from quadpype.hosts.blender.api import plugin


class ResetRenderSettings(
    plugin.BlenderInstancePlugin,
    OptionalPyblishPluginMixin,
):
    """Re-set scene properties as they were before publish"""

    order = pyblish.api.IntegratorOrder - 0.09999
    hosts = ["blender"]
    families = ["render"]
    label = "Reset render settings"
    optional = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        creator_attributes = instance.data.get('creator_attributes', None)
        assert creator_attributes, "Can not retrieve creator attributes for instance. Abort process."

        scene_render_settings = instance.data.get('transientData', {}).get('scene_render_settings', None)
        assert scene_render_settings, "Can not retrieve previous scene render settings from transient data."

        scene_render_properties = scene_render_settings.get('scene_properties', None)
        assert scene_render_properties, "Can not retrieve scene render properties from previous scene."

        activated_render_layers = scene_render_settings.get('activated_render_layers', None)
        assert activated_render_layers is not None, "Can not retrieve scene activated layers from previous scene."

        for blender_attribute in scene_render_properties:
            scene_property, property_name, value = blender_attribute
            self.set_property(
                scene_property=scene_property,
                property_name=property_name,
                value=value,
            )

        for layer in bpy.context.scene.view_layers:
            layer.use = layer.name in activated_render_layers
            self.log.info(f"Layer {layer.name} has been {'enabled' if layer.use else 'disabled'}.")

    def set_property(self, scene_property, property_name, value):
        if value is None:
            self.log.warning(f"No value has been found for property {property_name}.")
            return

        if not hasattr(scene_property, property_name):
            self.log.warning(f"Cannot find property named '{property_name}' for object {scene_property}.")
            return

        setattr(scene_property, property_name, value)
        self.log.info(f"Value '{value}' has been set for property '{property_name}'.")
