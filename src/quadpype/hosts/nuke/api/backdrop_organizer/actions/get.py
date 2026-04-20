import nuke
from typing import Union
from copy import deepcopy
from collections import defaultdict

from quadpype.settings import get_project_settings
from quadpype.pipeline import (
    get_current_project_name,
    get_current_host_name,
    format_data,
    get_workfile_build_template,
    get_create_build_template,
    get_resolved_name,
    split_hierarchy
)
from quadpype.lib import filter_profiles
from quadpype.pipeline.workfile.workfile_template_builder import TemplateProfileNotFound

from . import filter, check, convert, calculate, constants
from ..entities import Node, Backdrop

"""
get.py
------
Provides retrieval utilities for Nuke nodes, backdrops, settings, and layer data.

Covers project settings resolution (main backdrop profiles, load/publish templates,
render layer hierarchies), Nuke element access (nodes, backdrops, knob values),
layer extraction from Read nodes (EXR, PSD), and pipeline-specific queries
(parent backdrops, downstream/upstream traversal, representation-linked nodes).
"""

#---------Get settings---------
def main_backdrops_profiles() -> dict:
    project_settings = get_project_settings(get_current_project_name())
    try:
        profiles = (
            project_settings
            [get_current_host_name()]
            ["load"]
            ["main_backdrops_manager"]
            ["backdrop_profiles"]
        )
    except Exception:
        raise KeyError("Project has no template set for backdrop_profiles")

    return profiles

def backdrop_load_profile_by_task(data: dict, task: str = None) -> dict:
    data = template_data(data)
    profiles = get_workfile_build_template("working_hierarchy_templates_by_tasks")
    profile_key = {
        "task_types": data["task"]["name"] if not task else task,
        "families": data["family"]
    }

    profile = filter_profiles(profiles, profile_key)
    if not profile:
        raise TemplateProfileNotFound

    return profile

def backdrop_load_templates(data: dict, profile: dict = None) -> list[str]:
    if not profile:
        profile = backdrop_load_profile_by_task(data)
    return profile.get("templates", [])

def resolved_backdrop_load_hierarchies(
        data: dict,
        profile: dict = None,
        templates: list[str] = None) -> list[str]:

    if not templates:
        templates = backdrop_load_templates(data, profile)
    return [
        resolved_name(
            data=template_data(data),
            template=template,
            unique_number=data["unique_number"]
        )
        for template in templates
    ]

def renderlayer_backdrop_template() -> str:
    project_settings = get_project_settings(get_current_project_name())
    try:
        renderlayer_template = (
            project_settings
            [get_current_host_name()]
            ["load"]
            ["renderLayerLoader"]
            ["backdrop_name_template"]
        )
    except Exception:
        raise KeyError("Project has no template set for renderLayerLoader")

    return renderlayer_template

def resolved_renderlayergroup_backdrop_template(data: dict, template: str = None, options: dict = None) -> str:
    if not template:
        template = renderlayer_backdrop_template()

    resolve_data = deepcopy(data)
    resolve_data = template_data(resolve_data)
    resolve_data["subset_group"] = options["subset_group"]

    return resolved_name(
            data=resolve_data,
            template=template,
            unique_number=data["unique_number"]
        )

def full_renderlayergroup_backdrop_templates(
        data: dict,
        profile: dict = None,
        templates: list[str] = None) -> list[str]:

    if not templates:
        templates = backdrop_load_templates(data, profile)

    renderlayer_template = renderlayer_backdrop_template()

    new_templates = []
    for hierarchy in templates:
        parts = hierarchy.split("/")
        parts.insert(-1, renderlayer_template)
        new_templates.append("/".join(parts))

    return new_templates

def resolved_backdrop_load_renderlayergroup_hierarchies(
        data: dict, profile: dict = None, templates: list[str] = None, options: dict = None) -> list[str]:

    if not templates:
        templates = full_renderlayergroup_backdrop_templates(data, profile=profile)

    resolve_data = deepcopy(data)
    resolve_data = template_data(resolve_data)
    resolve_data["subset_group"] = options["subset_group"]

    return [
        resolved_name(
            data=resolve_data,
            template=template,
            unique_number=data["unique_number"]
        )
        for template in templates
    ]

def backdrop_publish_profile_by_task(data: dict) -> dict:
    profiles = get_create_build_template()
    profile_key = {
        "families": data["family"]
    }

    profile = filter_profiles(profiles, profile_key)
    if not profile:
        raise TemplateProfileNotFound

    return profile

def backdrop_publish_templates(data: dict, profile: dict = None) -> list[str]:
    if not profile:
        profile = backdrop_publish_profile_by_task(data)
    return profile.get("templates", [])

def resolved_backdrop_publish_hierarchies(
        data: dict,
        profile: dict = None,
        templates: list[str] = None) -> list[str]:
    if not templates:
        templates = backdrop_publish_templates(data, profile)
    return [
        resolved_name(
            data=data,
            template=template
        )
        for template in templates
    ]

def split_backdrop_hierarchy(hierarchy: list[str]) -> list[str]:
    return split_hierarchy(hierarchy)


#---------Get template data---------
def resolved_name(data: dict, template: str, **additional_data) -> str:
    return get_resolved_name(
        data=data,
        template=template,
        **additional_data
    )

def template_data(data: dict) -> dict:
    return format_data(
            original_data=data.get("representation", data),
            filter_variant=True,
            app=get_current_host_name()
        )


#---------Nuke Element---------
def knob_value(node: Node, knob: str) -> Union[str, int, bool, dict]:
    return node.nuke_entity[knob].value()

def nodes_in_backdrops(backdrop: Backdrop) -> list[Union[Node, Backdrop]]:
    return [convert.node(n) for n in backdrop.get_nodes()]

def node(name: str) -> Node:
    """Convert a given nuke.Node by its name to a Node"""
    if not nuke.toNode(name):
        return None
    return Node(nuke_entity=nuke.toNode(name))

def backdrop(name: str) -> Backdrop:
    """Convert a given nuke.Backdrop by its name to a Backdrop"""
    if not nuke.toNode(name) or not check.is_nuke_backdrop(nuke.toNode(name)):
        return None
    return Backdrop(nuke_entity=nuke.toNode(name))

def layers_from_node(read_node: nuke.Node, ext: str) -> dict:
    if not check.is_decompose_layer_compatible(ext):
        return {}

    layer_dict = defaultdict(dict)
    rgba_layer = None
    metadata = read_node.nuke_entity.metadata()

    if check.is_psd(ext):
        for k, v in metadata.items():
            if not k.startswith('input/psd/layers/'):
                continue
            parts = k.split('/')
            if len(parts) < 5:
                continue
            index = parts[3]
            attr = parts[4]
            layer_dict[index][attr] = v

    elif check.is_exr(ext):
        all_layer_names = read_node.nuke_entity.channels()
        if not all_layer_names:
            raise RuntimeError("No layers found in the selected Read node.")
        layers = {ch.split('.')[0] for ch in all_layer_names if ch.split('.')[0] != constants.RGBA}
        rgba_layer = {ch.split('.')[0] for ch in all_layer_names if ch.split('.')[0] == constants.RGBA}
        for index, layer in enumerate(sorted(layers)):
                layer_dict[index]["name"] = layer

    filtered_layers = [layer_data for layer_data in layer_dict.values()
                       if not any(key.startswith("divider") for key in layer_data)]

    if not filtered_layers and not rgba_layer:
        raise RuntimeError("No layers found in the selected Read node. \nAre you sure this is a layered file?")

    if filtered_layers:
        return_dict = {str(i): layer for i, layer in enumerate(filtered_layers)}
        return dict(sorted(return_dict.items(), key=lambda x: int(x[0]), reverse=True))
    if rgba_layer:
        return {"0": {"name": constants.RGBA}}

def layers_to_delete(old_layers_data: dict, new_layers_data: dict) -> dict:
    old_layers_to_delete = dict()
    new_layer_names = [layer_data["name"] for layer_data in new_layers_data.values()]

    for position, old_layer_data in old_layers_data.items():
        if old_layer_data["name"] not in new_layer_names:
            old_layers_to_delete[position] = old_layer_data

    return old_layers_to_delete

def layers_to_add(old_layers_data: dict, new_layers_data: dict) -> dict:
    new_layers_to_add = dict()
    old_layer_names = [layer_data["name"] for layer_data in old_layers_data.values()]

    for position, new_layer_data in new_layers_data.items():
        if new_layer_data["name"] not in old_layer_names:
            new_layers_to_add[position] = new_layer_data

    return new_layers_to_add

def backdrops_containing_node(node: Node) -> list[Backdrop]:
    backdrops = [convert.node(n) for n in nuke.allNodes("BackdropNode")]
    backdrops = filter.pipe_backdrop(backdrops)

    nx, ny = node.position
    nw, nh = node.size

    result = []
    for bd in backdrops:
        bx, by = bd.position
        bw, bh = bd.size

        if bx <= nx and by <= ny and (bx + bw) >= (nx + nw) and (by + bh) >= (ny + nh):
            result.append(bd)

    return result

def downstream_nodes(node: Node, visited: set = None):
    if visited is None:
        visited = set()
    for dep in node.nuke_entity.dependent():
        dep = convert.node(dep)
        if dep not in visited:
            visited.add(dep)
            downstream_nodes(dep, visited)
    return visited

def upstream_nodes(node: Node, visited: set = None):
    if visited is None:
        visited = set()
    for i in range(node.nuke_entity.inputs()):
        inp = node.nuke_entity.input(i)
        if inp and inp not in visited:
            visited.add(convert.node(inp))
            upstream_nodes(inp, visited)
    return visited


#---------Specific Element---------
def nodes_in_mains_backdrops() -> dict[str, list[Node]]:
    return_nodes_in_main_bd = dict()
    for backdrop_profile in main_backdrops_profiles():
        return_nodes_in_main_bd[backdrop_profile["name"]] = nodes_in_backdrops(
            backdrop(backdrop_profile["name"])
        )
    return return_nodes_in_main_bd

def parent_backdrop_from_pipe_backdrop(pipe_backdrop: Backdrop) -> Backdrop:
    return backdrop(knob_value(pipe_backdrop, constants.PARENT_BACKDROP))

def main_backdrop_from_parent_backdrop(start_backdrop: Backdrop) -> Backdrop:
    parent_backdrop = parent_backdrop_from_pipe_backdrop(start_backdrop)
    visited = set()
    while not check.is_main_backdrop(parent_backdrop):
        if parent_backdrop in visited:
            raise RuntimeError(f"Circular backdrop dependency detected: {parent_backdrop.name}")
        visited.add(parent_backdrop)
        parent_backdrop = parent_backdrop_from_pipe_backdrop(parent_backdrop)
        if parent_backdrop is None:
            raise RuntimeError("Reached a backdrop with no parent before finding main backdrop")

    return parent_backdrop

def backdrop_before_main_from_parent_backdrop(start_backdrop: Backdrop) -> Backdrop:
    actual_backdrop = start_backdrop
    parent_backdrop = parent_backdrop_from_pipe_backdrop(actual_backdrop)
    visited = list()
    while not check.is_main_backdrop(parent_backdrop):
        actual_backdrop = parent_backdrop
        if actual_backdrop in visited:
            raise RuntimeError(f"Circular backdrop dependency detected: {actual_backdrop.name}")
        visited.append(actual_backdrop)
        parent_backdrop = parent_backdrop_from_pipe_backdrop(actual_backdrop)
        if parent_backdrop is None:
            raise RuntimeError("Reached a backdrop with no parent before finding main backdrop")

    return actual_backdrop

def renderlayergroup_backdrop_in_hierarchy(
        data: dict,
        hierarchy: list[Backdrop],
        options: dict) -> Union[Backdrop, None]:
    renderlayergroup_backdrop_name = resolved_renderlayergroup_backdrop_template(data, options=options)
    for backdrop in hierarchy:
        if backdrop.name == renderlayergroup_backdrop_name:
            return backdrop
    return None

def _pipe_backdrops_to_the_right(backdrop: Backdrop) -> list[Backdrop]:
    return_backdrops =[]
    main_backdrop = main_backdrop_from_parent_backdrop(backdrop)
    pipe_backdrops_in_main = filter.pipe_backdrop(
        [n for n in nodes_in_backdrops(main_backdrop)]
    )
    if backdrop in pipe_backdrops_in_main:
        pipe_backdrops_in_main.remove(backdrop)

    backdrop_x, _, backdrop_w, _ = calculate.bounds(backdrop)
    ref_x = backdrop_x + backdrop_w

    pipe_backdrops_in_main = filter.backdrops_just_before_main(pipe_backdrops_in_main)

    for pipe_backdrop in pipe_backdrops_in_main:
        bd_in_main_x = pipe_backdrop.x
        if ref_x < bd_in_main_x:
            return_backdrops.append(pipe_backdrop)

    return return_backdrops

def pipe_nodes_to_the_right(backdrop: Backdrop) -> list[Union[Node, Backdrop]]:
    backdrops_to_the_right = _pipe_backdrops_to_the_right(backdrop)
    nodes_to_the_right = [node for backdrop in backdrops_to_the_right for node in
                          nodes_in_backdrops(backdrop)]
    nodes_to_the_right.extend(backdrops_to_the_right)
    return nodes_to_the_right

def pipe_nodes_to_the_right_in_renderlayergroup(
        backdrop: Backdrop,
        renderlayergroup_backdrop: Backdrop
) -> list[Union[Node, Backdrop]]:
    pipe_backdrops_in_group = filter.pipe_backdrop(
        [n for n in nodes_in_backdrops(renderlayergroup_backdrop)]
    )

    matching_backdrop = matching_nuke_entity(backdrop, pipe_backdrops_in_group)
    if matching_backdrop:
        pipe_backdrops_in_group.remove(matching_backdrop)

    nodes = [node for backdrop in pipe_backdrops_in_group for node in
                          nodes_in_backdrops(backdrop)]
    nodes.extend(pipe_backdrops_in_group)

    backdrop_x, _, backdrop_w, _ = calculate.bounds(backdrop)
    ref_x = backdrop_x + backdrop_w

    nodes_to_the_right = []
    for node in nodes:
        node_x = node.x
        if ref_x < node_x:
            nodes_to_the_right.append(node)
    return nodes_to_the_right

def nodes_linked_to_representation(representation_name):
    all_nodes = [convert.node(n) for n in nuke.allNodes()]
    linked_nodes = filter.linked_to_representation(all_nodes, representation_name)
    return linked_nodes

def matching_nuke_entity(obj, objects_list):
    return next((o for o in objects_list if o.nuke_entity == obj.nuke_entity), None)
