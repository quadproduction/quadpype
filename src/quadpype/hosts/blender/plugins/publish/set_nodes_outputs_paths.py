from typing import List
from pathlib import Path

import bpy

import pyblish.api
from quadpype.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)
import quadpype.hosts.blender.api.action
from quadpype.hosts.blender.api import plugin
from quadpype.hosts.blender.api.pipeline import get_path_from_template
from quadpype.pipeline.publish.lib import get_template_name_profiles
from quadpype.pipeline.publish import get_publish_template_name
from quadpype.pipeline import Anatomy
from quadpype.lib import filter_profiles, StringTemplate, version_up, get_version_from_path
from quadpype.settings import get_project_settings
from quadpype.client import get_version_by_name



class SetNodesOutputsPaths(
    plugin.BlenderInstancePlugin,
    OptionalPyblishPluginMixin,
):
    """Validate that the objects in the instance are in Object Mode."""

    order = pyblish.api.IntegratorOrder - 0.3
    hosts = ["blender"]
    families = ["render"]
    label = "Set nodes outputs paths"
    optional = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        scene = bpy.context.scene
        if scene.node_tree is None:
            raise RuntimeError("Scene does not have a valid node tree. Make sure compositing nodes are enabled.")

        anatomy_data = instance.data['anatomyData']
        family = instance.data["family"]

        project_name = anatomy_data.get('project', {}).get('name', None)
        if not project_name:
            raise RuntimeError("Can not retrieve project name from template_data. Can not get path from template.")

        profiles = get_template_name_profiles(
            project_name, get_project_settings(project_name), self.log
        )

        task = anatomy_data.get('task')
        if not task:
            raise RuntimeError("Can not retrieve task from template_data. Can not get path from template.")

        filter_criteria = {
            "hosts": anatomy_data["app"],
            "families": family,
            "task_names": task.get('name', None),
            "task_types": task.get('type', None),
        }
        profile = filter_profiles(profiles, filter_criteria, logger=self.log)

        quadpype_output_node = "QuadPype File Output"
        for output_node in _get_output_nodes(scene):
            render_node = _find_render_node(output_node.inputs)

            if output_node.name == quadpype_output_node:
                self.log.info(f"Ignoring node called '{quadpype_output_node}'")
                continue

            anatomy = Anatomy()
            templates = anatomy.templates.get(profile['template_name'])
            if not templates:
                raise NotImplemented(f"'{profile['template_name']}' template need to be setted in your project settings")

            output_path = StringTemplate.format_template(
                template=templates['node_output'],
                data={
                    'root': anatomy.roots,
                    'family': family,
                    'subset': instance.data["subset"],
                    'render_layer_name': render_node.layer,
                    **anatomy_data
                },
            )

            bumped_version_filepath = version_up(output_path)
            version = get_version_from_path(bumped_version_filepath)
            anatomy_data['version'] = version

            output_path = StringTemplate.format_template(
                template=templates['node_output'],
                data={
                    'root': anatomy.roots,
                    'family': family,
                    'subset': instance.data["subset"],
                    'render_layer_name': render_node.layer,
                    **anatomy_data
                },
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
