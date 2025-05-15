from typing import List

import bpy

import pyblish.api
from quadpype.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)
import quadpype.hosts.blender.api.action
from quadpype.hosts.blender.api import plugin
from quadpype.hosts.blender.api.pipeline import get_path_from_template
from quadpype.pipeline.publish.lib import get_template_name_profiles
from quadpype.lib import filter_profiles
from quadpype.settings import get_project_settings



class SetRenderSettings(
    plugin.BlenderInstancePlugin,
    OptionalPyblishPluginMixin,
):
    """Validate that the objects in the instance are in Object Mode."""

    order = pyblish.api.IntegratorOrder - 0.2
    hosts = ["blender"]
    families = ["render"]
    label = "Set render settings"
    optional = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        creator_attributes = instance.data.get('creator_attributes', None)
        assert creator_attributes, "Can not retrieve creator attributes for instance. Abort process."

        scene = bpy.context.scene
        properties_and_attributes = {
            scene.render: ['use_single_layer', 'use_simplify', 'use_motion_blur', 'use_border'],
            scene: ['use_nodes'],
            scene.cycles: ['device']
        }

        for blender_attribute, blender_properties in properties_and_attributes.items():
            for single_property in blender_properties:
                self.set_property(
                    scene_property=blender_attribute,
                    property_name=single_property,
                    value=creator_attributes.get(single_property, None),
                )

        layers_to_render = creator_attributes.get('render_layers', None)
        if layers_to_render is None:
            self.log.warning("Can not find render layers attribute from creator attributes.")
            return

        assert layers_to_render, "Render layers attribute retrieved from creator is empty. Nothing will be rendered."

        for layer in bpy.context.scene.view_layers:
            layer.use = layer.name in layers_to_render
            self.log.info(f"Layer {layer.name} has been {'enabled' if layer.use else 'disabled'}.")

        raise RuntimeError

    def set_property(self, scene_property, property_name, value):
        if value is None:
            self.log.warning(f"No value has been found for property {property_name}.")
            return

        if not hasattr(scene_property, property_name):
            self.log.warning(f"Cannot find property named '{property_name}' for object {scene_property}.")
            return

        setattr(scene_property, property_name, value)
        self.log.info(f"Value '{value}' has been set for property '{property_name}'.")
