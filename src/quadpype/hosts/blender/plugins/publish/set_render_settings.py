from typing import List

import bpy

import pyblish.api
from quadpype.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)
from quadpype.hosts.blender.api import plugin


class SetRenderSettings(
    plugin.BlenderInstancePlugin,
    OptionalPyblishPluginMixin,
):
    """Activate or deactivate scene settings based on subset inputs"""

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

        layers_to_render = creator_attributes.get('render_layers', None)
        if layers_to_render is None:
            self.log.warning("Can not find render layers attribute from creator attributes.")
            instance.data['transientData']['scene_render_settings'] = False
            return

        assert layers_to_render != [], "No render layers has been selected from publish. Nothing will be rendered."

        scene = bpy.context.scene
        properties_and_attributes = {
            scene.render: ['use_single_layer', 'use_simplify', 'use_motion_blur', 'use_border'],
            scene: ['use_nodes'],
            scene.cycles: ['device']
        }

        scene_properties = self.get_scene_attributes(properties_and_attributes)
        activated_render_layers = [layer for layer in bpy.context.scene.view_layers if layer.use]
        instance.data['transientData']['scene_render_settings'] = {
            'scene_properties': scene_properties,
            'activated_render_layers': activated_render_layers
        }

        for blender_attribute, blender_properties in properties_and_attributes.items():
            for single_property in blender_properties:
                self.set_property(
                    scene_property=blender_attribute,
                    property_name=single_property,
                    value=creator_attributes.get(single_property, None),
                )

        for layer in bpy.context.scene.view_layers:
            layer.use = layer.name in layers_to_render
            self.log.info(f"Layer {layer.name} has been {'enabled' if layer.use else 'disabled'}.")

    def get_scene_attributes(self, properties_and_attributes):
        retrieved_attributes = list()
        for blender_attribute, blender_properties in properties_and_attributes.items():
            for single_property in blender_properties:
                retrieved_attributes.append(
                    [
                        blender_attribute,
                        single_property,
                        self.get_property(blender_attribute, single_property)
                    ]
                )
        return retrieved_attributes

    def get_property(self, scene_property, property_name):
        value = getattr(scene_property, property_name, None)
        if value is None:
            self.log.warning(f"Cannot find property named '{property_name}' for object {scene_property}.")
            return

        return value

    def set_property(self, scene_property, property_name, value):
        if value is None:
            self.log.warning(f"No value has been found for property {property_name}.")
            return

        if not hasattr(scene_property, property_name):
            self.log.warning(f"Cannot find property named '{property_name}' for object {scene_property}.")
            return

        setattr(scene_property, property_name, value)
        self.log.info(f"Value '{value}' has been set for property '{property_name}'.")
