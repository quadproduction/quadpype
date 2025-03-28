import pyblish.api
from quadpype.hosts.blender.api import plugin
from quadpype.hosts.blender.api.pipeline import get_path_from_template
from quadpype.settings import get_project_settings
from quadpype.pipeline.publish import get_publish_template_name

import bpy


class SetRenderLayersPaths(
    plugin.BlenderInstancePlugin,
):
    """Increment current workfile version."""

    order = pyblish.api.IntegratorOrder - 0.1
    label = "Set render layers paths"
    hosts = ["blender"]
    families = ["render"]

    def process(self, instance):
        scene = bpy.context.scene

        if scene.node_tree is None:
            self.log.error("Scene does not have a valid node tree. Make sure compositing nodes are enabled.")
            return {'CANCELLED'}

        instance_data = instance.data
        anatomy = instance_data.get('anatomyData')
        assert anatomy, "Can't retrieve anatomy data from given instance."

        project_name = anatomy.get('task', []).get('type')
        assert project_name, "Can't retrieve project name from given instance."

        family = instance_data.get('family')
        task = anatomy.get('task', [])
        task_name = task.get('name')
        task_type = task.get('type')

        template_name = get_publish_template_name(
            project_name=project_name,
            host_name="blender",
            family=family,
            task_name=task_name,
            task_type=task_type,
            project_settings=get_project_settings(project_name),
            hero=False,
            logger=self.log
        )

        if not template_name:
            self.log.warning("Can't find corresponding publish template name. Will use default publish path.")
            template_name = "publish"

        for output_node in self._get_outputs_files_nodes(scene):
            render_node = self._find_render_node(output_node.inputs)

            render_layer_name = render_node.layer
            output_path = get_path_from_template(
                template_module=template_name,
                template_name='node_output',
                template_data={
                    'render_layer_name': render_layer_name,
                    'task': task,
                    'family': family,
                    'subset': instance_data.get('subset')
                },
                bump_version=True,
                makedirs=True
            )

            output_node.base_path = output_path
            self.log.info(f"File output path set to '{output_node.base_path}'.")

    @staticmethod
    def _get_outputs_files_nodes(scene):
        return [node for node in scene.node_tree.nodes if node.type == 'OUTPUT_FILE']

    def _find_render_node(self, node_inputs):
        """ recursive method to identify and find 'R_LAYERS' nodes """
        for node_input in node_inputs:
            for link in node_input.links:
                target_node = link.from_node
                if target_node.type == 'R_LAYERS':
                    return target_node

                result = self._find_render_node(target_node.inputs)
                if result:
                    return result
