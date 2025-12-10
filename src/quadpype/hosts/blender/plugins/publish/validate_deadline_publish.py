import os
from pathlib import Path

import bpy

from quadpype.pipeline.publish import (
    RepairAction,
    ValidateContentsOrder,
    PublishValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.blender.api import plugin
from quadpype.hosts.blender.api.render_lib import update_render_product
from quadpype.hosts.blender.api.lib import get_node_tree
from quadpype.hosts.blender.api.render_lib import get_output_paths, set_output_paths


def get_composite_outputs_nodes():
    """Get composite output node for validation

    Returns:
        node: composite output node
    """
    tree = get_node_tree()
    output_type = "CompositorNodeOutputFile"
    outputs_nodes = list()
    # Remove all output nodes that include "QuadPype" in the name.
    # There should be only one.
    for node in tree.nodes:
        if node.bl_idname == output_type and "QuadPype" in node.name:
            outputs_nodes.append(node)

    return outputs_nodes


class ValidateDeadlinePublish(
    plugin.BlenderInstancePlugin,
    OptionalPyblishPluginMixin
):
    """Validates Render File Directory is different in every submission
    """

    order = ValidateContentsOrder
    families = ["render"]
    hosts = ["blender"]
    label = "Validate Render Output for Deadline"
    optional = True
    actions = [RepairAction]

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid(instance)
        if invalid:
            bullet_point_invalid_statement = "\n".join(
                "- {}".format(err) for err in invalid
            )
            report = (
                "Render Output has invalid values(s).\n\n"
                f"{bullet_point_invalid_statement}\n\n"
            )
            raise PublishValidationError(
                report,
                title="Invalid value(s) for Render Output")

    @classmethod
    def get_invalid(cls, instance):
        invalid = []
        outputs_nodes = get_composite_outputs_nodes()
        if not outputs_nodes:
            msg = "No output node found in the compositor tree."
            invalid.append(msg)

        asset_name = instance.data.get('asset', None)
        task = instance.data.get('task', None)
        assert asset_name and task, "Can not generate layer render path because data is missing from container node."

        file_name = f"{asset_name}_{task}"

        for output_node in outputs_nodes:
            output_path = get_output_paths(output_node)
            if file_name not in output_path:
                msg = (
                    f"Render output folder with path {output_path} doesn't match the blender scene name! "
                    f"Use Repair action to fix the folder file path."
                )
                invalid.append(msg)
        if not bpy.context.scene.render.filepath:
            msg = (
                "No render filepath set in the scene!"
                "Use Repair action to fix the render filepath."
            )
            invalid.append(msg)
        return invalid

    @classmethod
    def repair(cls, instance):
        container = instance.data["transientData"]["instance_node"]
        outputs_nodes = get_composite_outputs_nodes()
        render_data = container.get("render_data")
        render_product = render_data.get("render_product")
        aov_file_product = render_data.get("aov_file_product")
        aov_sep = render_data.get("aov_separator")

        instance_per_layer = render_data.get("instance_per_layer")

        asset_name = instance.data.get('asset', None)
        task = instance.data.get('task', None)
        assert asset_name and task, "Can not generate layer render path because data is missing from container node."

        filepath = Path(bpy.data.filepath)
        assert filepath, "Workfile not saved. Please save the file first."

        dirpath = filepath.parent

        filename = f"{asset_name}_{task}"
        render_folder = render_data.get("render_folder")
        output_path = Path(dirpath, render_folder, filename).as_posix()

        for output_node in outputs_nodes:
            orig_output_path = get_output_paths(output_node)

            orig_output_dir = os.path.dirname(orig_output_path)
            new_output_dir = orig_output_path.replace(orig_output_dir, output_path)

            set_output_paths(output_node, new_output_dir)

        new_output_dir = (
            Path(output_path).parent
        )

        updated_render_product = update_render_product(
            container.name, new_output_dir,
            render_product, aov_sep,
            instance_per_layer=instance_per_layer
        )
        render_data["render_product"] = updated_render_product
        if aov_file_product:
            updated_aov_file_product = update_render_product(
                container.name, new_output_dir,
                aov_file_product, aov_sep
            )
            render_data["aov_file_product"] = updated_aov_file_product

        tmp_render_path = os.path.join(os.getenv("AVALON_WORKDIR"), "renders", "tmp")
        tmp_render_path = tmp_render_path.replace("\\", "/")
        os.makedirs(tmp_render_path, exist_ok=True)
        bpy.context.scene.render.filepath = f"{tmp_render_path}/"

        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
        cls.log.debug("Reset the render output folder...")
