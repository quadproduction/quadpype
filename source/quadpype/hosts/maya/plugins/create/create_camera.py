from quadpype.hosts.maya.api import (
    lib,
    plugin
)
from quadpype.lib import BoolDef


class CreateCamera(plugin.MayaCreator):
    """Single baked camera"""

    identifier = "io.quadpype.creators.maya.camera"
    label = "Camera"
    family = "camera"
    icon = "video-camera"

    def get_instance_attr_defs(self):

        defs = lib.collect_animation_defs()

        defs.extend([
            BoolDef("bakeToWorldSpace",
                    label="Bake to World-Space",
                    tooltip="Bake to World-Space",
                    default=True),
        ])

        return defs


class CreateCameraRig(plugin.MayaCreator):
    """Complex hierarchy with camera."""

    identifier = "io.quadpype.creators.maya.camerarig"
    label = "Camera Rig"
    family = "camerarig"
    icon = "video-camera"
