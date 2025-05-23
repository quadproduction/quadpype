import os
import json
import bpy

from quadpype.pipeline import publish
from quadpype.hosts.blender.api import plugin, lib


class ExtractCameraABC(
    plugin.BlenderExtractor, publish.OptionalPyblishPluginMixin
):
    """Extract camera as ABC."""

    label = "Extract Camera (ABC)"
    hosts = ["blender"]
    families = ["camera"]
    optional = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        # Define extract output file path
        stagingdir = self.staging_dir(instance)
        asset_name = instance.data["assetEntity"]["name"]
        subset = instance.data["subset"]
        instance_name = f"{asset_name}_{subset}"
        filename = f"{instance_name}.abc"
        filepath = os.path.join(stagingdir, filename)
        jsonname = f"{instance.name}.json"
        json_path = os.path.join(stagingdir, jsonname)

        # Perform extraction
        self.log.info("Performing extraction..")

        plugin.deselect_all()

        asset_group = instance.data["transientData"]["instance_node"]

        selected = lib.get_asset_children(asset_group)
        if not selected:
            self.log.error("Extraction failed: No child objects found in the asset group.")
            return

        active = selected[0]
        camera = lib.get_and_select_camera(selected)

        # Create focal value dict throught time for blender
        if camera:
            camera_data_dict = {"focal_data": {}}
            # save current frame to reset it after the dict creation
            currentframe = bpy.context.scene.frame_current

            for frame in range (bpy.context.scene.frame_start, (bpy.context.scene.frame_end+1)):
                bpy.context.scene.frame_set(frame)
                camera_data_dict["focal_data"][frame] = camera.lens

            # reset old current frame
            bpy.context.scene.frame_set(currentframe)

            # Performe json extraction
            # Serializing json
            json_object = json.dumps(camera_data_dict, indent=4)

            # Writing to json
            with open(json_path, "w") as outfile:
                outfile.write(json_object)

        context = plugin.create_blender_context(
            active=active, selected=selected)

        scene_overrides = {
            "unit_settings.scale_length": instance.data.get("unitScale"),
        }
        # Skip None value overrides
        scene_overrides = {
            key: value for key, value in scene_overrides.items()
            if value is not None
        }

        with lib.attribute_overrides(bpy.context.scene, scene_overrides):
            with bpy.context.temp_override(**context):
                # We export the abc
                bpy.ops.wm.alembic_export(
                    filepath=filepath,
                    selected=True,
                    flatten=True,
                    start=instance.data["frameStartHandle"],
                    end=instance.data["frameEndHandle"]
                )

        plugin.deselect_all()

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'abc',
            'ext': 'abc',
            'files': filename,
            "stagingDir": stagingdir,
        }
        instance.data["representations"].append(representation)

        json_representation = {
            'name': 'jsonCam',
            'ext': 'json',
            'files': jsonname,
            "stagingDir": stagingdir,
        }
        instance.data["representations"].append(json_representation)
        self.log.info("Extracted instance '%s' to: %s\nExtracted instance '%s' to: %s",
                      instance.name, representation, jsonname, json_representation)
