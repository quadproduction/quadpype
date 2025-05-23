import bpy

import pyblish.api
from quadpype.hosts.blender.api import plugin
from quadpype.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)


class ValidateRenderCameraIsSet(
    plugin.BlenderInstancePlugin,
    OptionalPyblishPluginMixin
):
    """Validate that there is a camera set as active for rendering."""

    order = pyblish.api.ValidatorOrder
    hosts = ["blender"]
    families = ["render"]
    label = "Validate Render Camera Is Set"
    optional = False

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        if not bpy.context.scene.camera:
            raise PublishValidationError("No camera is active for rendering.")
