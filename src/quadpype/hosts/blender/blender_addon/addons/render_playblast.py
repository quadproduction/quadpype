import logging
import subprocess
import os

import bpy

from quadpype.hosts.blender.api.pipeline import get_path_from_template
from quadpype.lib import open_in_explorer, get_ffmpeg_tool_args

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


bl_info = {
    "name": "Render Playblast",
    "description": "Render sequences of images + video, with OpenGL, from viewport or camera view"
                    "based on 'deadline_render' template, this need to be setted in OP",
    "author": "Quad",
    "version": (2, 0),
    "blender": (2, 80, 0),
    "category": "Render",
    "location": "View 3D > UI> Quad",
}

RENDER_TYPES = {
    "PNG": {
        "type": "IMAGE",
        "image_format": "PNG",
        "extension": "####.png"
    }
}

# Define the Playblast Settings
class PlayblastSettings(bpy.types.PropertyGroup):
    use_camera_view: bpy.props.BoolProperty(
        name="Use Camera View",
        description="Use camera view for playblast",
        default=False
    )
    use_transparent_bg: bpy.props.BoolProperty(
        name="Use Transparent Background",
        description="Render playblast with transparent background",
        default=False
    )


# Define the Playblast UI Panel
class VIEW3D_PT_RENDER_PLAYBLAST(bpy.types.Panel):
    bl_label = "Render Playblast"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Quad"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        playblast_settings = scene.playblast_settings  # Access the PlayblastSettings

        col = layout.column()
        col.prop(playblast_settings, "use_camera_view")  # Access property from PlayblastSettings
        col.prop(playblast_settings, "use_transparent_bg")  # Access property from PlayblastSettings
        col.operator("playblast.render", text="Render Playblast")
        col.operator("playblast.open", text="Open Last Playblast Folder")


class OBJECT_OT_RENDER_PLAYBLAST(bpy.types.Operator):
    bl_idname = "playblast.render"
    bl_label = "Render Playblast"

    def execute(self, context):
        scene = context.scene
        region = self.get_view_3D_region()

        # Store the original settings to restore them later
        render_filepath = scene.render.filepath
        file_format = scene.render.image_settings.file_format
        media_type = scene.render.image_settings.media_type
        file_extension_use = scene.render.use_file_extension
        engine = scene.render.engine
        film_transparent = scene.render.film_transparent
        color_mode = scene.render.image_settings.color_mode

        # Apply camera view if needed
        if region and scene.playblast_settings.use_camera_view:
            perspective_region = region.view_perspective
            region.view_perspective = "CAMERA"

        # Disable file extension for playblast
        scene.render.use_file_extension = False

        # Render playblast for each file format
        version_to_bump = True
        for render_type, options in RENDER_TYPES.items():
            scene.render.filepath = get_path_from_template('playblast',
                                                           'path',
                                                           {'ext': options['extension']},
                                                           bump_version=version_to_bump,
                                                           makedirs=True)

            version_to_bump = False
            if options["type"] == "IMAGE":
                scene.render.image_settings.media_type = options["type"]
                scene.render.image_settings.file_format = options["image_format"]
                scene.render.use_file_extension = False

            logging.info(
                f"{'Camera view' if scene.playblast_settings.use_camera_view else 'Viewport'} "
                f"rendering at: {scene.render.filepath}"
            )

            result = bpy.ops.render.opengl(animation=True)
            if result != {"FINISHED"}:
                logging.error(f"Error rendering {render_type}")
                break

            ffmpeg_input = scene.render.filepath.replace("####", "%04d")
            mp4_output = scene.render.filepath.replace(".####.png", ".mp4")
            framerate = scene.render.fps / scene.render.fps_base

            args = get_ffmpeg_tool_args(
                "ffmpeg",
                "-y",
                "-framerate", str(framerate),
                "-i", ffmpeg_input,
                "-c:v", "libx264",
                "-crf", "18",
                "-preset", "slow",
                "-pix_fmt", "yuv420p",
                mp4_output
            )
            result = subprocess.run(args, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"MP4 success : {mp4_output}")
            else:
                print("Error FFmpeg :")
                print(result.stderr)

        # Restore the original settings
        scene.render.filepath = render_filepath
        scene.render.image_settings.media_type = media_type
        scene.render.image_settings.file_format = file_format
        scene.render.use_file_extension = file_extension_use

        # Restore color_mode safely: check if the original color_mode is allowed
        if color_mode in ['RGB', 'BW'] or (file_format == "PNG" and color_mode == "RGBA"):
            scene.render.image_settings.color_mode = color_mode
        else:
            # Fallback to RGB if the original mode is not compatible with the format
            scene.render.image_settings.color_mode = 'RGB'

        if region and scene.playblast_settings.use_camera_view:
            region.view_perspective = perspective_region

        if scene.playblast_settings.use_transparent_bg:
            # reset to memorized parameters for render
            scene.render.engine = engine
            scene.render.film_transparent = film_transparent

        return {"FINISHED"}

    def get_view_3D_region(self):
        """Find the VIEW_3D region and return its region_3d space."""
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        return space.region_3d
        return None


class OBJECT_OT_OPEN_PLAYBLAST_FOLDER(bpy.types.Operator):
    bl_idname = "playblast.open"
    bl_label = "Open Last Playblast Folder"

    def execute(self, context):
        # Get the path to the most recent playblast folder
        latest_playblast_filepath = get_path_from_template('playblast',
                                                           'folder')

        if not os.path.exists(latest_playblast_filepath):
            self.report({'ERROR'}, f"File '{latest_playblast_filepath}' not found")
            return {'CANCELLED'}

        open_in_explorer(latest_playblast_filepath)
        return {'FINISHED'}


def register():
    bpy.utils.register_class(PlayblastSettings)
    bpy.types.Scene.playblast_settings = bpy.props.PointerProperty(type=PlayblastSettings)
    bpy.utils.register_class(VIEW3D_PT_RENDER_PLAYBLAST)
    bpy.utils.register_class(OBJECT_OT_RENDER_PLAYBLAST)
    bpy.utils.register_class(OBJECT_OT_OPEN_PLAYBLAST_FOLDER)


def unregister():
    bpy.utils.unregister_class(PlayblastSettings)
    del bpy.types.Scene.playblast_settings  # Remove the property from the scene
    bpy.utils.unregister_class(VIEW3D_PT_RENDER_PLAYBLAST)
    bpy.utils.unregister_class(OBJECT_OT_RENDER_PLAYBLAST)
    bpy.utils.unregister_class(OBJECT_OT_OPEN_PLAYBLAST_FOLDER)
