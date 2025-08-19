# -*- coding: utf-8 -*-
"""Collect render data."""

import os
import re

import bpy
import pyblish.api

from quadpype.pipeline.create import get_subset_name

from quadpype.hosts.blender.api import colorspace, plugin

class CollectBlenderRender(plugin.BlenderInstancePlugin):
    """Gather all publishable render instances."""

    order = pyblish.api.CollectorOrder + 0.01
    hosts = ["blender"]
    families = ["render", "renderlayer"]
    label = "Collect Render"
    sync_workfile_version = False

    @staticmethod
    def generate_expected_files(
        render_product, frame_start, frame_end, frame_step, ext
    ):
        """
        Generate the expected files for the render product for the beauty
        render. This returns a list of files that should be rendered. It
        replaces the sequence of `#` with the frame number.
        """
        expected_files = {}
        aov_files = []
        for render_name, render_file in render_product:
            path = os.path.dirname(render_file)
            file = os.path.basename(render_file)

            for frame in range(frame_start, frame_end + 1, frame_step):
                frame_str = str(frame).rjust(4, "0")
                filename = re.sub("#+", frame_str, file)
                expected_file = f"{os.path.join(path, filename)}.{ext}"
                aov_files.append(expected_file.replace("\\", "/"))

            expected_files[render_name] = [
                aov for aov in aov_files if render_name in aov
            ]

        return expected_files

    def process(self, instance):
        instance_node = instance.data["transientData"]["instance_node"]
        render_data = instance_node.get("render_data")

        assert render_data, "No render data found."

        render_product = render_data.get("render_product")
        aov_file_product = render_data.get("aov_file_product")
        ext = render_data.get("image_format")
        multilayer = render_data.get("multilayer_exr")
        instance_per_layer = render_data.get("instance_per_layer")
        review = render_data.get("review", False)

        frame_start = instance.data["frameStartHandle"]
        frame_end = instance.data["frameEndHandle"]

        layers_to_render = instance.data.get('creator_attributes', {}).get('render_layers', None)
        if layers_to_render is None:
            self.log.warning("Can not find render layers attribute from creator attributes.")

        expected_files = next((rn_product for rn_product in render_product.values()), None)
        expected_beauty = self.generate_expected_files(
            expected_files, int(frame_start), int(frame_end),
            int(bpy.context.scene.frame_step), ext)

        # Todo : update farm info when rendering global scene
        instance.data.update({
            "families": ["render", "render.farm"],
            "subsetGroup": instance.data["subset"],
            "forceSubsetGroup": True,
            "frameStart": frame_start,
            "frameEnd": frame_end,
            "productType": "render",
            "frameStartHandle": frame_start,
            "frameEndHandle": frame_end,
            "fps": instance.context.data["fps"],
            "byFrameStep": bpy.context.scene.frame_step,
            "review": review,
            "multipartExr": ext == "exr" and multilayer,
            "farm": False if instance_per_layer else True,
            "expectedFiles": [expected_beauty],
            # OCIO not currently implemented in Blender, but the following
            # settings are required by the schema, so it is hardcoded.
            # TODO: Implement OCIO in Blender
            "colorspaceConfig": "",
            "colorspaceDisplay": "sRGB",
            "colorspaceView": "ACES 1.0 SDR-video",
            "renderProducts": colorspace.ARenderProduct(
                frame_start=frame_start,
                frame_end=frame_end
            ),
        })

        if not instance_per_layer:
            return

        instance.data["integrate"] = False
        self.create_renderlayer_instance(
            instance, render_product,
            aov_file_product, ext, multilayer,
            frame_start, frame_end, review,
            layers_to_render)

    def create_renderlayer_instance(self, instance, render_product,
                                    aov_file_product, ext, multilayer,
                                    frame_start, frame_end, review,
                                    layers_to_render):
        context = instance.context
        prod_type = "render"
        project_name = instance.context.data["projectName"]
        task_name = instance.data.get("task")
        render_layer_family = "renderlayer"

        layers = [
            layer for layer in bpy.context.scene.view_layers
            if layer.name in layers_to_render
        ] if layers_to_render else bpy.context.scene.view_layers

        for view_layer in layers:
            viewlayer_name = view_layer.name
            rn_product = render_product.get(viewlayer_name, None)
            if not rn_product:
                self.log.warning(
                    f"Can not found render data for layer named '{viewlayer_name}'. "
                    f"Will not create instance."
                )
                continue

            aov_product = aov_file_product[viewlayer_name] if aov_file_product else {}
            viewlayer_product_name = get_subset_name(
                render_layer_family,
                instance.data['variant'],
                task_name,
                instance.context.data["assetEntity"],
                project_name=project_name,
                dynamic_data={"render_layer_name": viewlayer_name},
            )

            if viewlayer_name not in viewlayer_product_name:
                self.log.warning(
                    "Corresponding template found is not using render layer name. "
                    "Hardcoded subset name will be used toi avoid duplicates."
                )
                viewlayer_product_name += f"_{viewlayer_name}"

            rn_layer_instance = context.create_instance(viewlayer_product_name)
            rn_layer_instance.data.update(instance.data)

            expected_beauty = self.generate_expected_files(
                rn_product, int(frame_start), int(frame_end),
                int(bpy.context.scene.frame_step), ext)

            expected_aovs = self.generate_expected_files(
                aov_product, int(frame_start), int(frame_end),
                int(bpy.context.scene.frame_step), ext)

            expected_files = expected_beauty | expected_aovs
            rn_layer_instance.data.update({
                "name": viewlayer_product_name,
                "label": viewlayer_product_name,
                "subset": viewlayer_product_name,
                "forceSubset": True,
                "subsetGroup": instance.data["subset"],
                "forceSubsetGroup": True,
                "family": render_layer_family,
                "families": ["renderlayer"],
                "fps": context.data["fps"],
                "byFrameStep": instance.data["creator_attributes"].get("step", 1),
                "review": review,
                "multipartExr": ext == "exr" and multilayer,
                "farm": True,
                "productName": viewlayer_product_name,
                "productType": prod_type,
                "expectedFiles": [expected_files],
                "frameStart": instance.data["frameStart"],
                "frameEnd": instance.data["frameEnd"],
                "frameStartHandle": frame_start,
                "frameEndHandle": frame_end,
                "task": instance.data["task"],
                # OCIO not currently implemented in Blender, but the following
                # settings are required by the schema, so it is hardcoded.
                # TODO: Implement OCIO in Blender
                "colorspaceConfig": "",
                "colorspaceDisplay": "sRGB",
                "colorspaceView": "ACES 1.0 SDR-video",
                "renderProducts": colorspace.ARenderProduct(
                    frame_start=frame_start,
                    frame_end=frame_end
                ),
                "publish_attributes": instance.data["publish_attributes"]
            })
            instance.append(rn_layer_instance)
