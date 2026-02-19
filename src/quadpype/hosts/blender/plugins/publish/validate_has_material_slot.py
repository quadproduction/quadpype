from typing import List

import bpy

from quadpype.pipeline.publish import (
    RepairAction,
    ValidateContentsOrder,
    OptionalPyblishPluginMixin,
    PublishValidationError
)

from quadpype.hosts.blender.api import plugin

class ValidateObjectsHaveMaterial(
    plugin.BlenderInstancePlugin,
    OptionalPyblishPluginMixin,
):
    """Validate that the objects have minimum a material slot, even empty."""

    order = ValidateContentsOrder
    hosts = ["blender"]
    families = ["model", "rig", "layout", "blendScene"]
    label = "Objects Have Material Slot"
    actions = [RepairAction]
    optional = True

    @staticmethod
    def has_material_slot(obj: bpy.types.Object) -> bool:
        if len(obj.material_slots) == 0:
            return False
        return True

    @classmethod
    def get_invalid(cls, instance) -> List:
        invalid = []
        for obj in instance:
            if isinstance(obj, bpy.types.Object) and obj.type == 'MESH':
                if not cls.has_material_slot(obj):
                    invalid.append(obj)
        return invalid

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                f"Objects found in instance without material slot: {invalid}"
            )

    @classmethod
    def repair(cls, instance):
        invalid = cls.get_invalid(instance)
        for obj in invalid:
            obj.data.materials.append(None)
            cls.log.info(f"Material slot added to {obj.name}")
