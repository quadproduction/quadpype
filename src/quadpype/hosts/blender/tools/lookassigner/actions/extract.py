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


def ids_from_collections(collections):
    return set(
        get_avalon_node(collection).get('representation', None) for collection in collections
        if has_avalon_node(collection)
    )


def data_from_collections(collections):
    return [
        get_avalon_node(collection) for collection in collections
        if has_avalon_node(collection)
    ]


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
