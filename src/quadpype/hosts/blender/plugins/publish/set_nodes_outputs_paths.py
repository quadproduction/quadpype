from pathlib import Path

import bpy
import re
from copy import copy

import pyblish.api
from quadpype.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)

from quadpype.hosts.blender.api import plugin
from quadpype.pipeline.publish.lib import get_template_name_profiles
from quadpype.pipeline import Anatomy
from quadpype.lib import filter_profiles, StringTemplate, version_up, get_version_from_path, get_last_version_from_path
from quadpype.settings import get_project_settings


PATH_REGEX_BEFORE_VERSION = r'^(.*?)/[^/]*\{version[^a-zA-Z}]*\}'


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

        anatomy = Anatomy()
        templates = anatomy.templates.get(profile['template_name'])
        if not templates:
            raise NotImplemented(f"'{profile['template_name']}' template need to be setted in your project settings")

        updated_anatomy_data = copy(anatomy_data)
        updated_anatomy_data.update(
            {
                'root': anatomy.roots,
                'family': family,
                'subset': instance.data["subset"],
            }
        )

        quadpype_suffix = "quadpype"

        for output_node in _get_output_nodes(scene):
            render_node = _find_render_node(output_node.inputs)

            if output_node.name.lower().startswith(quadpype_suffix):
                self.log.info(f"Ignoring node called '{output_node.name}'")
                continue

            updated_anatomy_data['render_layer_name'] = render_node.layer

            output_path = StringTemplate.format_template(
                template=templates['node_output'],
                data=updated_anatomy_data,
            )

            # If folder doesn't exists, it means that we render this layer for the first time
            # and we can keep the previous path as generated with version retrieved from instance
            if Path(output_path).parent.exists():

                last_version_filename = get_last_version_from_path(
                    path_dir=_get_version_folder_parent(
                        output_template=templates['node_output'],
                        template_data=updated_anatomy_data
                    ),
                    filter=[updated_anatomy_data['asset'], render_node.layer],
                    search_in_subdirectories=True
                )

                if not last_version_filename:
                    raise RuntimeError(
                        f"An error has occured when trying to determine last version "
                        f"from rendered layer named {render_node.layer}"
                    )

                last_version_number = int(get_version_from_path(last_version_filename))
                output_path = StringTemplate.format_template(
                    template=templates['node_output'],
                    data={
                        **updated_anatomy_data,
                        'version': last_version_number+1
                    },
                )

            output_node.base_path = output_path
            self.log.info(f"File output path set to '{output_node.base_path}'.")

        return


def _get_version_folder_parent(output_template, template_data):
    node_folder_path_match = re.match(PATH_REGEX_BEFORE_VERSION, output_template)
    assert node_folder_path_match, "Can not determine render layer folder withtout version from template."

    return StringTemplate.format_template(
        template=node_folder_path_match.group(1),
        data=template_data,
    )


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
