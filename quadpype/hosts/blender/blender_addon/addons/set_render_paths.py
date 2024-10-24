import logging
import os

import bpy

from quadpype.hosts.blender.api.pipeline import get_path_from_template
from quadpype.lib import open_in_explorer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


bl_info = {
    "name": "Set Render Paths",
    "description": "Set global render output paths and update file output nodes for render layers"
                   "based on 'deadline_render' template, this need to be setted in OP",
    "author": "Quad",
    "version": (2, 0),
    "blender": (2, 80, 0),
    "category": "Render",
    "location": "View 3D > UI > Quad",
}


class VIEW3D_PT_SET_RENDER_PATHS(bpy.types.Panel):
    bl_label = "Set Render Paths"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Quad"

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.operator("render_paths.set", text="Set Render Paths")
        col.operator("render_paths.show", text="Open Last Render Folder")


class OBJECT_OT_SET_PATHS(bpy.types.Operator):
    bl_idname = "render_paths.set"
    bl_label = "Set Render Path"

    def execute(self, context):
        scene = context.scene
        scene.render.filepath = get_path_from_template(template_module='deadline_render',
                                                       template_name='global_output',
                                                       template_data={},
                                                       makedirs=True)
        log.info(f"Global output path has been set to '{scene.render.filepath}'")

        # Ensure that the scene has a node tree and it's not None
        if scene.node_tree is None:
            log.error("Scene does not have a valid node tree. Make sure compositing nodes are enabled.")
            return {'CANCELLED'}

        # Loop through all nodes type 'OUTPUT_FILE'
        output_nodes = [node for node in scene.node_tree.nodes if node.type == 'OUTPUT_FILE']
        for output_node in output_nodes:
            # Find the connected render node
            render_node = self._find_render_node(output_node.inputs)

            # Get the render layer name and the output path
            render_layer_name = render_node.layer
            output_path = get_path_from_template(template_module='deadline_render',
                                                 template_name='node_output',
                                                 template_data={'render_layer_name': render_layer_name},
                                                 bump_version=True,
                                                 makedirs=True)

            # Set the output path for the output node
            output_node.base_path = output_path
            log.info(f"File output path set to '{output_node.base_path}'.")

        return {'FINISHED'}

    def _find_render_node(self, node_inputs):
        """ recursive method to identify and find 'R_LAYERS' nodes """
        # Recursively search for a node of type 'R_LAYERS'
        for node_input in node_inputs:
            for link in node_input.links:
                target_node = link.from_node
                if target_node.type == 'R_LAYERS':
                    return target_node
                # Recursively search the inputs of the target node
                result = self._find_render_node(target_node.inputs)
                if result:
                    return result


class OBJECT_OT_OPEN_RENDER_FOLDER(bpy.types.Operator):
    bl_idname = "render_paths.show"
    bl_label = "Open Last Render Folder"

    def execute(self, context):
        latest_render_path = get_path_from_template(template_module='deadline_render',
                                                    template_name='folder')

        if not os.path.exists(latest_render_path):
            self.report({'ERROR'}, f"File '{latest_render_path}' not found")
            return {'CANCELLED'}

        open_in_explorer(latest_render_path)
        return {'FINISHED'}


def register():
    bpy.utils.register_class(VIEW3D_PT_SET_RENDER_PATHS)
    bpy.utils.register_class(OBJECT_OT_SET_PATHS)
    bpy.utils.register_class(OBJECT_OT_OPEN_RENDER_FOLDER)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_SET_RENDER_PATHS)
    bpy.utils.unregister_class(OBJECT_OT_SET_PATHS)
    bpy.utils.unregister_class(OBJECT_OT_OPEN_RENDER_FOLDER)
