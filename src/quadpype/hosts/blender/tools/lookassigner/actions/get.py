import logging
import bpy
from collections import defaultdict

from quadpype.hosts.blender.api.pipeline import (
    AVALON_CONTAINERS,
    get_avalon_node,
)
from quadpype.client import get_representations, get_representation_by_id
from quadpype.pipeline import (
    get_current_project_name,
)

from . import extract, filter_by


def all_assets():
    avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
    assert avalon_container, "Can not found avalon container which contains scene assets."

    return _assets_to_items(extract.data_from_collections(avalon_container.children))


def selected_assets():
    return _assets_to_items(extract.containers_data_from_selected())


def objects_from_collection_name(collection_name):
    return bpy.data.collections[collection_name].objects if bpy.data.collections.get(collection_name) else []


def _assets_to_items(assets_data):
    project_name = get_current_project_name()
    assert project_name, "Can not retrieve project name for current scene."

    fields = {"_id", "name", "context.variant", "context.version"}

    asset_view_items = []

    namespaces_by_assets = defaultdict(list)
    for asset_data in filter_by.allowed_families(assets_data):
        namespaces_by_assets[asset_data['asset']].append(
            {
                'namespace': asset_data['namespace'],
                'collection_name': asset_data['objectName']
            }
        )

    for asset_name, assets_data in namespaces_by_assets.items():

        shader_repr = get_representations(
            project_name,
            representation_names={"shader"},
            context_filters={"asset": asset_name},
            fields=fields
        )

        if not shader_repr:
            logging.warning(f"Can not retrieve any shader representation linked to asset named '{asset_name}'")
            continue

        flattened_representations = _flatten_from_context(list(shader_repr))
        valid_representations = filter_by.valid_representations(flattened_representations)
        grouped_shaders = filter_by.identical_subsets(valid_representations)

        asset_view_items.append({
            "name": asset_name,
            "asset": asset_name,
            "assets_data": assets_data,
            "looks": [
                filter_by.last_version(shader_variant) for shader_variant in grouped_shaders
            ]
        })

    return asset_view_items


def _flatten_from_context(representations):
    for representation in representations:
        for attrib, value in representation.get('context', {}).items():
            representation[attrib] = value

        del representation['context']

    return representations
