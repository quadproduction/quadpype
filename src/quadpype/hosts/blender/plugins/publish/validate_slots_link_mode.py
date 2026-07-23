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
    """Validate that material slots are in object mode, even empty."""

    order = ValidateContentsOrder
    hosts = ["blender"]
    families = ["png"]
    label = "Material Slots in Object Link"
    actions = [RepairAction]
    optional = True

    @staticmethod
    def is_material_slot_linked_object(obj: bpy.types.Object) -> bool:
        for slot in obj.material_slots:
            if slot.link == "OBJECT" and slot.material != None :
                return True
        return False

    @staticmethod
    def is_material_slot_linked_data(obj: bpy.types.Object) -> bool:
        for slot in obj.material_slots:
            if slot.link == "DATA":
                return True
        return False

    @classmethod
    def get_invalid(cls, instance) -> List:
        invalid = []
        for obj in instance:
            if isinstance(obj, bpy.types.Object) and obj.type == 'MESH':
                if cls.is_material_slot_linked_data(obj) or cls.is_material_slot_linked_object :
                    invalid.append(obj)
                    print(f"===INVALID SLOT : {invalid}===")
        return invalid

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                f"Objects in instance must have only one empty material slot in OBJECT mode: INVALID OBJECT : {invalid}"
            )

    @classmethod
    def repair(cls, instance):
        invalid = cls.get_invalid(instance)
        for obj in invalid:
            for slot in obj.material_slots:
                if slot.link == "DATA" or slot.link == "OBJECT":
                    print(f"===SLOT PLEIN : {slot.name} sur {obj.name}===")
                    slot.material = None
                    slot.link = "OBJECT"
                    print(f"=== SLOT VIDE sur {obj.name}===")
