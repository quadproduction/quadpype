import inspect
import pyblish.api

import bpy

from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishValidationError,
    OptionalPyblishPluginMixin,
    RepairAction
)
from quadpype.hosts.blender.api.action import SelectInvalidAction, GenerateUUIDsOnInvalidAction

from quadpype.hosts.blender.api.lib import get_id, is_collection


class ValidateNodeIDs(pyblish.api.InstancePlugin):
    """Validate entities have a Id.

    When IDs are missing from objects *save your scene* and they should be
    automatically generated because IDs are created on non-referenced nodes
    in Blender upon scene save.

    """

    order = ValidateContentsOrder
    label = 'Objects have ID'
    hosts = ['blender']
    families = ["model",
                "look",
                "rig",
                "pointcache",
                "animation",
                "yetiRig",
                "assembly",
                "look"]

    actions = [SelectInvalidAction, GenerateUUIDsOnInvalidAction]

    def process(self, instance):
        """Process all meshes"""

        # Ensure all nodes have a cbId
        invalid = self.get_invalid(instance)
        if invalid:
            names = "\n".join(
                "- {}".format(entity) for entity in invalid
            )
            raise PublishValidationError(
                f"Entities found without IDs : {names}",
                description=self.get_description()
            )

    @staticmethod
    def get_description():
        return inspect.cleandoc(
            """## All objects in scene should have unique identifier.

            Save scene again to generate missing ids.
            """
        )

    @classmethod
    def get_invalid(cls, instance):
        """Return the member entities that are invalid"""
        invalid = [obj for obj in instance if not get_id(obj) and not is_collection(obj)]

        return invalid
