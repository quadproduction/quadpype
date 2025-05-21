"""Load an asset in Blender from an Alembic file."""

from typing import Dict, List, Optional
from quadpype.hosts.blender.api import plugin, lib
import bpy


def blender_camera_bg_video_importer(video_filepath, replace_last_bg = False):
    """
    Will add or reload an image sequence in the camera background

    video_filepath: path to the video to load
    replace_last_bg(bool): If False will add an image background, if True, will replace the last imported image background
    """
    imported_video = bpy.data.movieclips.load(video_filepath)

    camera = bpy.context.scene.camera
    if not camera:
        raise ValueError("No camera has been found in scene. Can't import video as camera background.")

    camera.data.show_background_images = True
    if replace_last_bg and len(camera.data.background_images):
        background = camera.data.background_images[-1]
    else:
        background = camera.data.background_images.new()

    background.source = 'MOVIE_CLIP'
    background.clip = imported_video

    print(f"Video at path {imported_video.filepath} has been correctly loaded in scene as camera background.")


class ImageVideoLoader(plugin.BlenderLoader):
    """Replace Last Video in Blender in the last imported one.

    Create background movie clip for active camera and assign selected video.
    """

    families = ["image", "render", "review"]
    representations = ["mp4", "avi", "h264_mp4", "h264_png"]

    label = "Replace Last Video In Camera"
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
        video_filepath = self.filepath_from_context(context)
        blender_camera_bg_video_importer(video_filepath, replace_last_bg=True)


class ImageVideoAdder(plugin.BlenderLoader):
    """Add Video in Blender.

    Add background movie clip for active camera and assign selected video.
    """
    families = ["image", "render", "review"]
    representations = ["mp4", "avi", "h264_mp4", "h264_png"]

    label = "Add Video In Camera"
    icon = "file-video-o"
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
        video_filepath = self.filepath_from_context(context)
        blender_camera_bg_video_importer(video_filepath, replace_last_bg=False)
