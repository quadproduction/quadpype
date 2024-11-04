from typing import List

import bpy

from quadpype.hosts.blender.api import plugin
import quadpype.hosts.blender.api.action
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishValidationError,
    OptionalPyblishPluginMixin
)


class ValidateCameraZeroKeyframe(
    plugin.BlenderInstancePlugin,
    OptionalPyblishPluginMixin
):
    """Camera must have a keyframe at frame 0.

    Unreal shifts the first keyframe to frame 0. Forcing the camera to have
    a keyframe at frame 0 will ensure that the animation will be the same
    in Unreal and Blender.
    """

    order = ValidateContentsOrder
    hosts = ["blender"]
    families = ["camera"]
    label = "Zero Keyframe"
    actions = [quadpype.hosts.blender.api.action.SelectInvalidAction]

    @staticmethod
    def get_invalid(instance) -> List:
        invalid = []
        for obj in instance:
            if isinstance(obj, bpy.types.Object) and obj.type == "CAMERA":
                if obj.animation_data and obj.animation_data.action:
                    action = obj.animation_data.action
                    frames_set = set()
                    for fcu in action.fcurves:
                        for kp in fcu.keyframe_points:
                            frames_set.add(kp.co[0])
                    frames = list(frames_set)
                    frames.sort()
                    if frames[0] != 0.0:
                        invalid.append(obj)
        return invalid

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid(instance)
        if invalid:
            names = ", ".join(obj.name for obj in invalid)
            raise PublishValidationError(
                f"Camera must have a keyframe at frame 0: {names}"
            )
