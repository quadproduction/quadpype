import os
import glob
import json

import pyblish.api
from quadpype.hosts.blender.api import capture, plugin
from quadpype.hosts.blender.api.lib import maintained_time, get_viewport_shading

import bpy


class ExtractThumbnail(plugin.BlenderExtractor):
    """Extract viewport thumbnail.

    Takes review camera and creates a thumbnail based on viewport
    capture.

    """

    label = "Extract Thumbnail"
    hosts = ["blender"]
    families = ["review"]
    order = pyblish.api.ExtractorOrder + 0.01
    presets = {}

    def process(self, instance):
        self.log.info("Extracting capture..")

        if instance.data.get("thumbnailSource"):
            self.log.info("Thumbnail source found, skipping...")
            return

        stagingdir = self.staging_dir(instance)
        asset_name = instance.data["assetEntity"]["name"]
        subset = instance.data["subset"]
        filename = f"{asset_name}_{subset}"

        path = os.path.join(stagingdir, filename)

        self.log.info(f"Outputting images to {path}")

        use_viewport = False
        creator_attributes = instance.data.get('creator_attributes', {})
        render_view_type = creator_attributes.get('render_view', None)
        shader_mode = creator_attributes.get('shader_mode', "MATERIAL")
        render_overlay = creator_attributes.get('render_overlay', False)
        render_floor_grid = creator_attributes.get('render_floor_grid', None)
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

        start = instance.data.get("frameStart", bpy.context.scene.frame_start)
        family = instance.data.get("family")
        isolate = instance.data("isolate", None)

        presets = self.presets
        if isinstance(self.presets, str):
            presets = json.loads(self.presets)
        elif not isinstance(self.presets, dict):
            raise ValueError("presets must be a dict")

        preset = presets.get(family, {})

        preset.update({
            "camera": camera,
            "start_frame": start,
            "end_frame": start,
            "filename": path,
            "overwrite": True,
            "isolate": isolate,
            "use_viewport": use_viewport,
            "transparent_background": transparent_background
        })
        preset.setdefault(
            "image_settings",
            {
                "file_format": "JPEG",
                "color_mode": "RGB",
                "quality": 100,
            },
        )
        if preset.get("display_options"):
            preset["display_options"]["overlay"].update({
                "show_overlays": render_overlay,
                "show_floor": render_floor_grid,
                "show_axis_x": render_floor_grid,
                "show_axis_y": render_floor_grid
            })
            preset["display_options"]["shading"]["type"] = shader_mode
        with maintained_time():
            path = capture(**preset)

        thumbnail = os.path.basename(self._fix_output_path(path))

        self.log.info(f"thumbnail: {thumbnail}")

        instance.data.setdefault("representations", [])

        representation = {
            "name": "thumbnail",
            "ext": "jpg",
            "files": thumbnail,
            "stagingDir": stagingdir,
            "thumbnail": True
        }
        instance.data["representations"].append(representation)

    def _fix_output_path(self, filepath):
        """Workaround to return correct filepath.

        To workaround this we just glob.glob() for any file extensions and
        assume the latest modified file is the correct file and return it.

        """
        # Catch cancelled playblast
        if filepath is None:
            self.log.warning(
                "Playblast did not result in output path. "
                "Playblast is probably interrupted."
            )
            return None

        if not os.path.exists(filepath):
            files = glob.glob(f"{filepath}.*.jpg")

            if not files:
                raise RuntimeError(f"Couldn't find playblast from: {filepath}")
            filepath = max(files, key=os.path.getmtime)

        return filepath
