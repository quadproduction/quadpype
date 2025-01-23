from typing import List

import bpy


import quadpype.hosts.blender.api.action
from quadpype.pipeline import OptionalPyblishPluginMixin
from quadpype.hosts.blender.api import plugin
from quadpype.pipeline.publish import (
    PublishValidationError,
    ValidateContentsOrder
)


class ValidateNoColonsInName(
    plugin.BlenderInstancePlugin,
    OptionalPyblishPluginMixin
):
    """There cannot be colons in names

    Object or bone names cannot include colons. Other software do not
    handle colons correctly.

    """

    order = ValidateContentsOrder
    hosts = ["blender"]
    families = ["model", "rig"]
    label = "No Colons in names"
    actions = [quadpype.hosts.blender.api.action.SelectInvalidAction]

    @staticmethod
    def get_invalid(instance) -> List:
        invalid = []
        for obj in instance:
            if ':' in obj.name:
                invalid.append(obj)
            if isinstance(obj, bpy.types.Object) and obj.type == 'ARMATURE':
                for bone in obj.data.bones:
                    if ':' in bone.name:
                        invalid.append(obj)
                        break
        return invalid

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid(instance)
        if invalid:
            names = ", ".join(obj.name for obj in invalid)
            raise PublishValidationError(
                f"Objects found with colon in name: {names}"
            )
