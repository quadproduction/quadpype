import pyblish.api
import bpy

from quadpype.hosts.blender.api import action, lib
from quadpype.pipeline.publish import (
    PublishValidationError, ValidateContentsOrder)


class ValidateCameraContents(pyblish.api.InstancePlugin):
    """Validates Camera instance contents.

    A Camera instance may only hold a SINGLE camera, nothing else.
    """

    order = ValidateContentsOrder
    families = ['camera']
    hosts = ['blender']
    label = 'Validate Camera Contents'
    actions = [quadpype.hosts.blender.api.action.SelectInvalidAction]

    @staticmethod
    def get_invalid(instance):
        # get cameras
        cameras = _retrieve_cameras(instance)

        invalid = []
        if len(cameras) != 1:
            invalid.extend(cameras)

        invalid = list(set(invalid))
        return invalid

    def process(self, instance):
        """Process all the nodes in the instance"""

        invalid = self.get_invalid(instance)
        if invalid:
            raise RuntimeError("Invalid camera contents, Camera instance must have a single camera: "
                               "Found {0}: {1}".format(len(invalid), invalid))


def _retrieve_cameras(instance):
    cameras_objects = [obj for obj in instance if lib.is_camera(obj)]
    cameras_from_collection = [
        obj for collection in instance
        for obj in collection.children
        if lib.is_collection(collection) and lib.is_camera(obj)
    ]

    return cameras_objects + cameras_from_collection
