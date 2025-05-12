from typing import List

import bpy

import pyblish.api
from quadpype.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)
import quadpype.hosts.blender.api.action
from quadpype.hosts.blender.api import plugin
from quadpype.hosts.blender.api.pipeline import get_path_from_template


class SetNodesOutputsPaths(
    plugin.BlenderContextPlugin,
    OptionalPyblishPluginMixin,
):
    """Validate that the objects in the instance are in Object Mode."""

    order = pyblish.api.IntegratorOrder - 0.2
    hosts = ["blender"]
    families = ["render"]
    label = "Set nodes outputs paths"
    actions = [quadpype.hosts.blender.api.action.SelectInvalidAction]
    optional = True

    def process(self, context):
        if not self.is_active(context.data):
            return

        scene = bpy.context.scene
        if scene.node_tree is None:
            self.log.error("Scene does not have a valid node tree. Make sure compositing nodes are enabled.")
            return {'CANCELLED'}

        anatomy_data = context.data['anatomyData']
        quadpype_output_node = "QuadPype File Output"
        for output_node in _get_output_nodes(scene):
            render_node = _find_render_node(output_node.inputs)

            if output_node.name == quadpype_output_node:
                self.log.info(f"Ignoring node called '{quadpype_output_node}'")
                continue

            anatomy_data['render_layer_name'] = render_node.layer

            output_path = get_path_from_template(
                template_module='deadline_render',
                template_name='node_output',
                template_data=anatomy_data,
                bump_version=True,
                makedirs=True
            )

            output_node.base_path = output_path
            self.log.info(f"File output path set to '{output_node.base_path}'.")

        return {'FINISHED'}


def _get_output_nodes(scene):
    return [node for node in scene.node_tree.nodes if node.type == 'OUTPUT_FILE']


def _find_render_node(node_inputs):
    """ recursive method to identify and find 'R_LAYERS' nodes """
    # Recursively search for a node of type 'R_LAYERS'
    for node_input in node_inputs:
        for link in node_input.links:
            target_node = link.from_node
            if target_node.type == 'R_LAYERS':
                return target_node
            # Recursively search the inputs of the target node
            result = _find_render_node(target_node.inputs)
            if result:
                return result
