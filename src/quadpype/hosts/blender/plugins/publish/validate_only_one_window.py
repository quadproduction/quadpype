import inspect
import bpy

from quadpype.hosts.blender.api import plugin

from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishValidationError
)


class ValidateOnlyOneWindow(
    plugin.BlenderInstancePlugin
):
    """Only one blender window is accepted when publishing reviews"""

    order = ValidateContentsOrder
    hosts = ["blender"]
    families = ["review"]
    label = "Validate Only One Window"

    @classmethod
    def get_invalid(cls):
        invalid = False
        if len(bpy.context.window_manager.windows[:]) != 1:
            invalid = True
        return invalid

    def process(self, instance):
        invalid = self.get_invalid()
        if invalid:
            raise PublishValidationError(
                "More than one window is open !",
                description=self.get_description()
            )

    def get_description(self):
        return inspect.cleandoc(
            """## Blender can't have multiple windows openned for render reviews.

            Please, close to have only one window.
            """
        )
