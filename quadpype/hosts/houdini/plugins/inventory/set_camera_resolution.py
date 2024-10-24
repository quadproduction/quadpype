from quadpype.pipeline import InventoryAction
from quadpype.hosts.houdini.api.lib import (
    get_camera_from_container,
    set_camera_resolution
)
from quadpype.pipeline.context_tools import get_current_project_asset


class SetCameraResolution(InventoryAction):

    label = "Set Camera Resolution"
    icon = "desktop"
    color = "orange"

    @staticmethod
    def is_compatible(container):
        return (
            container.get("loader") == "CameraLoader"
        )

    def process(self, containers):
        asset_doc = get_current_project_asset()
        for container in containers:
            node = container["node"]
            camera = get_camera_from_container(node)
            set_camera_resolution(camera, asset_doc)
