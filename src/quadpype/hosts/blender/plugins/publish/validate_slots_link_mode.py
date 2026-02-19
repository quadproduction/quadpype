from typing import List

import bpy

from quadpype.pipeline.publish import (
    RepairAction,
    ValidateContentsOrder,
    OptionalPyblishPluginMixin,
    PublishValidationError
)

from quadpype.hosts.blender.api import plugin

class ValidateMaterialSlotLinkMode(
    plugin.BlenderInstancePlugin,
    OptionalPyblishPluginMixin,
):
    """Validate that material slots are inb object mode, even empty."""

    order = ValidateContentsOrder
    hosts = ["blender"]
    families = ["model", "rig", "layout", "blendScene"]
    label = "Material Slots in Object Link"
    actions = [RepairAction]
    optional = True

    @staticmethod
    def is_material_slot_linked_object(obj: bpy.types.Object) -> bool:
        for slot in obj.material_slots:
            if slot.link != "OBJECT":
                return False
        return True

    @classmethod
    def get_invalid(cls, instance) -> List:
        invalid = []
        for obj in instance:
            if isinstance(obj, bpy.types.Object) and obj.type == 'MESH':
                if not cls.is_material_slot_linked_object(obj):
                    invalid.append(obj)
        return invalid

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                f"Objects found in instance without material slot in OBJECT mode: {invalid}"
            )

    @classmethod
    def repair(cls, instance):
        invalid = cls.get_invalid(instance)
        for obj in invalid:
            for slot in obj.material_slots:
                slot.link = "OBJECT"
