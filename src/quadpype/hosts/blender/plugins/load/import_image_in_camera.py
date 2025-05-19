"""Load an asset in Blender from an Alembic file."""

from typing import Dict, List, Optional
from quadpype.hosts.blender.api import plugin, lib
import bpy


def blender_camera_bg_image_importer(image_filepath, replace_last_bg  = False):
    """
    Will add or reload an image in the camera background

    image_filepath: path to the image to load
    replace_last_bg(bool): If False will add an image background, if True, will replace the last imported image background
    """
    imported_image = bpy.data.images.load(image_filepath)

    camera = bpy.context.scene.camera
    if not camera:
        raise ValueError("No camera has been found in scene. Can't import image as camera background.")

    camera.data.show_background_images = True
    if replace_last_bg and len(camera.data.background_images):
        background = camera.data.background_images[-1]
    else:
        background = camera.data.background_images.new()
    imported_image.source = 'FILE'
    background.source = 'IMAGE'
    background.image = imported_image

    print(f"Image at path {imported_image.filepath} has been correctly loaded in scene as camera background.")


class ImageCameraLoader(plugin.BlenderLoader):
    """Replace Last Image in Blender as background in camera in the last imported one.

    Create background image for active camera and assign selected image.
    """

    families = ["image", "render", "review"]
    representations = ["png"]

    label = "Replace Last Image in Camera"
    icon = "refresh"
    color = "orange"

    def process_asset(
        self, context: dict, name: str, namespace: Optional[str] = None,
        options: Optional[Dict] = None
    ) -> Optional[List]:

        """
        Arguments:
            name: Use pre-defined name
            namespace: Use pre-defined namespace
            context: Full parenthood of representation to load
            options: Additional settings dictionary
        """
        image_filepath = self.filepath_from_context(context)
        blender_camera_bg_image_importer(image_filepath, replace_last_bg =True)


class ImageCameraAdder(plugin.BlenderLoader):
    """Add Image in Blender as background in camera.

    Create background image for active camera and assign selected image in a new background_images.
    """

    families = ["image", "render", "review"]
    representations = ["png"]

    label = "Add Image in Camera"
    icon = "file-image-o"
    color = "green"

    def process_asset(
        self, context: dict, name: str, namespace: Optional[str] = None,
        options: Optional[Dict] = None
    ) -> Optional[List]:

        """
        Arguments:
            name: Use pre-defined name
            namespace: Use pre-defined namespace
            context: Full parenthood of representation to load
            options: Additional settings dictionary
        """
        image_filepath = self.filepath_from_context(context)
        blender_camera_bg_image_importer(image_filepath, replace_last_bg =False)
