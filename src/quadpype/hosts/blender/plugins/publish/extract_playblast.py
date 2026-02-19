import os
import copy
import clique

import bpy

import pyblish.api
from quadpype.settings import PROJECT_SETTINGS_KEY
from quadpype.pipeline.settings import RES_SEPARATOR

from quadpype.hosts.blender.api import capture, plugin
from quadpype.hosts.blender.api.lib import maintained_time, get_viewport_shading


def parse_resolution(resolution):
    try:
        width, height = resolution.split("x")
        return int(width), int(height)
    except (ValueError, AttributeError):
        return None, None


class ExtractPlayblast(
    plugin.BlenderExtractor
):
    """
    Extract viewport playblast.

    Takes review camera and creates review Quicktime video based on viewport
    capture.
    """

    label = "Extract Playblast"
    hosts = ["blender"]
    families = ["review"]

    order = pyblish.api.ExtractorOrder + 0.01

    def process(self, instance):

        instance.data.setdefault("representations", [])

        # get scene fps
        fps = instance.data.get("fps")
        if fps is None:
            fps = bpy.context.scene.render.fps
            instance.data["fps"] = fps

        self.log.info(f"fps: {fps}")

        use_viewport = False
        creator_attributes = instance.data.get('creator_attributes', {})

        # If start and end frames cannot be determined,
        # get them from Blender timeline.
        start = creator_attributes.get("frameStart", bpy.context.scene.frame_start)
        end = creator_attributes.get("frameEnd", bpy.context.scene.frame_end)
        instance.data["frameStart"] = start
        instance.data["frameEnd"] = end

        self.log.info(f"start: {start}, end: {end}")
        assert end >= start, "Invalid time range!"

        resolution = creator_attributes.get('resolution', None)
        width, height = parse_resolution(resolution)

        render_view_type = creator_attributes.get('render_view', None)
        shader_mode = creator_attributes.get('shader_mode', "MATERIAL")
        render_overlay = creator_attributes.get('render_overlay', False)
        render_floor_grid = creator_attributes.get('render_floor_grid', None)
        generate_image_sequence = creator_attributes.get('generate_image_sequence', True)
        transparent_background = creator_attributes.get('use_transparent_background', False)
        if not render_view_type or render_view_type != "viewport":
            camera = instance.data("review_camera", None)
        else:
            camera = "AUTO"
            use_viewport = True

        if shader_mode == "Viewport":
            shader_mode = get_viewport_shading()
            if shader_mode == "RENDERED":
                self.log.warning("Shading mode set to RENDERED, impossible for playblast, auto switch to MATERIAL")
                shader_mode = "MATERIAL"

        # get isolate objects list
        isolate = instance.data("isolate", None)

        # get output path
        stagingdir = self.staging_dir(instance)
        asset_name = instance.data["assetEntity"]["name"]
        subset = instance.data["subset"]
        filename = f"{asset_name}_{subset}"

        path = os.path.join(stagingdir, filename)

        self.log.info(f"Outputting images to {path}")

        project_settings = instance.context.data[PROJECT_SETTINGS_KEY]["blender"]
        presets = project_settings["publish"]["ExtractPlayblast"]["presets"]
        preset = copy.deepcopy(presets.get("default"))
        preset.update({
            "camera": camera,
            "width": width,
            "height": height,
            "start_frame": start,
            "end_frame": end,
            "filename": path,
            "overwrite": True,
            "isolate": isolate,
            "use_viewport": use_viewport,
            "transparent_background": transparent_background
        })

        preset["display_options"]["overlay"].update({
            "show_overlays": render_overlay,
            "show_floor": render_floor_grid,
            "show_axis_x": render_floor_grid,
            "show_axis_y": render_floor_grid
        })
        preset["display_options"]["shading"]["type"] = shader_mode

        preset.setdefault(
            "image_settings",
            {
                "media_type": "IMAGE",
                "file_format": "PNG",
                "color_mode": "RGB",
                "color_depth": "8",
                "compression": 15,
            },
        )

        # Generate the PNG sequence
        if generate_image_sequence:
            with maintained_time():
                path = capture(**preset)

            self.log.info(f"playblast path {path}")

            collected_files = os.listdir(stagingdir)
            collections, remainder = clique.assemble(
                collected_files,
                patterns=[f"{filename}\\.{clique.DIGITS_PATTERN}\\.png$"],
                minimum_items=1
            )

            if len(collections) > 1:
                raise RuntimeError(
                    f"More than one collection found in stagingdir: {stagingdir}"
                )
            elif len(collections) == 0:
                raise RuntimeError(
                    f"No collection found in stagingdir: {stagingdir}"
                )

            frame_collection = collections[0]

            self.log.info(f"We found collection of interest {frame_collection}")

            # `instance.data["files"]` must be `str` if single frame
            files = list(frame_collection)
            if len(files) == 1:
                files = files[0]

            tags = []
            if not instance.data.get("keepImages") and not generate_image_sequence:
                tags.append("delete")

            representation = {
                "name": "png",
                "ext": "png",
                "files": files,
                "stagingDir": stagingdir,
                "frameStart": start,
                "frameEnd": end,
                "fps": fps,
                "tags": tags,
                "camera_name": camera
            }
            instance.data.get("representations", []).append(representation)

        # Generate the MP4 file
        preset["image_settings"] = {
                "media_type": "VIDEO",
                "color_mode": "RGB",
                "ffmpeg": {
                    "format": "MPEG4",
                    "codec": "H264"
                }
            }

        with maintained_time():
            path = capture(**preset)

        self.log.info(f"playblast path {path}")

        collected_files = os.listdir(stagingdir)
        files = [filename for filename in collected_files if filename.lower().endswith(".mp4")]
        if len(files) == 1:
            files = files[0]
        tags = ["review"]

        representation = {
            "name": "mp4",
            "ext": "mp4",
            "files": files,
            "stagingDir": stagingdir,
            "frameStart": start,
            "frameEnd": end,
            "fps": fps,
            "tags": tags,
            "camera_name": camera
        }
        instance.data.get("representations", []).append(representation)
