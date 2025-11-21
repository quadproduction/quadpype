import inspect
import bpy
import logging

from quadpype.hosts.blender.api import plugin, action

from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishValidationError,
    OptionalPyblishPluginMixin,
    RepairAction
)

from quadpype.hosts.blender.api import (
    get_objects_in_collection,
    is_collection,
    has_materials
)


class ValidateShaders(plugin.BlenderInstancePlugin, OptionalPyblishPluginMixin):
    """Validates that objects has shaders.
    """

    order = ValidateContentsOrder
    families = ['look']
    hosts = ['blender']
    label = 'Validate Shaders'
    optional = False

    def is_invalid(self, instance):
        return not any(
            [
                obj for obj in instance
                if isinstance(obj, bpy.types.Material)
            ]
        )

    def process(self, instance):
        if not self.is_active(instance.data):
            return
        invalid = self.is_invalid(instance)
        if invalid:
            raise PublishValidationError(
                f"Instance needs to contains at least one material is be published as look.",
                description=self.get_description()
            )

    @staticmethod
    def get_description():
        return inspect.cleandoc(
            """## At least one material is needed to perform publish.

            Add at least one shader on one of the selected objects.
            """
        )
