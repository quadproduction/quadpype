import bpy

import pyblish.api

from quadpype.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)
from quadpype.hosts.blender.api import plugin


# TODO : It really doesn't seems to be the right way to set data and
# keep them into publish files. A better option would be to
# save in a temp files and then to delete it, or even
# to think of a better way to assign data from previous setters.
class SaveScene(
    plugin.BlenderContextPlugin,
):
    """Validate that the workfile has been saved."""

    order = pyblish.api.IntegratorOrder - 0.1
    hosts = ["blender"]
    label = "Save scene after data set"
    families = ["render"]
    optional = False

    def process(self, context):
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
