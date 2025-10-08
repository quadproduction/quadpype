import logging

from quadpype.hosts.blender.api.pipeline import (
    AVALON_CONTAINERS
)

from quadpype.hosts.blender.api.pipeline import (
    get_avalon_node,
    has_avalon_node
)
from quadpype.hosts.blender.api.lib import (
    get_parent_collections_for_object,
    get_selected_objects,
    get_selected_collections,
    get_all_parents
)

import bpy


def extract_ids_from_collections(collections):
    return set(
        get_avalon_node(collection).get('representation', None) for collection in collections
        if has_avalon_node(collection)
    )


def extract_data_from_collections(collections):
    return [
        get_avalon_node(collection) for collection in collections
        if has_avalon_node(collection)
    ]


def all_assets():
    avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
    if not avalon_container:
        logging.error("Can not found avalon container which contains scene assets.")
        return

    return _assets_to_items(extract_data_from_collections(avalon_container.children))


def containers_data_from_selected():
    containers = list()
    all_selected = set(get_selected_objects() + get_selected_collections())
    for blender_object in all_selected:
        if has_avalon_node(blender_object):
            containers.append(get_avalon_node(blender_object))
            continue

        all_parents = set(get_all_parents(blender_object)).union(get_parent_collections_for_object(blender_object))
        for object_parent in all_parents:
            avalon_node = get_avalon_node(object_parent)
            if not avalon_node:
                continue
            containers.append(avalon_node)

    return containers


def selected_assets():
    return _assets_to_items(containers_data_from_selected())


def _assets_to_items(assets_data):
    asset_view_items = []
    for asset_data in assets_data:
        label = asset_data["objectName"]
        asset_view_items.append({
            "label": label,
            "namespaces": ['test'],
            "looks": ["testLook"]
        })

    return asset_view_items
