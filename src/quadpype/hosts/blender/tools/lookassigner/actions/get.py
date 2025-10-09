import logging
import bpy

from quadpype.hosts.blender.api.pipeline import (
    AVALON_CONTAINERS
)
from quadpype.client import get_representations
from quadpype.pipeline import (
    get_current_project_name
)

from . import extract, filter


def all_assets():
    avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
    if not avalon_container:
        logging.error("Can not found avalon container which contains scene assets.")
        return

    return _assets_to_items(extract.data_from_collections(avalon_container.children))


def selected_assets():
    return _assets_to_items(extract.containers_data_from_selected())


def _assets_to_items(assets_data):
    project_name = get_current_project_name()
    fields = {"_id", "name", "context.variant", "context.version"}

    asset_view_items = []
    for asset_data in assets_data:

        asset_name = asset_data.get("asset", None)
        if not asset_name:
            logging.warning("Can not get asset name from retrieved container.")
            continue

        shader_repr = get_representations(
            project_name,
            representation_names={"shader"},
            context_filters={"asset": asset_name},
            fields=fields
        )

        if not shader_repr:
            logging.warning(f"Can not retrieve any shader representation linked to asset named {asset_name}")
            continue

        flattened_representations = _flatten_from_context(list(shader_repr))
        valid_representations = filter.valid_representations(flattened_representations)
        grouped_shaders = filter.identical_subsets(valid_representations)

        asset_view_items.append({
            "label": asset_name,
            "namespaces": ['test'],
            "looks": [
                filter.last_version(shader_variant) for shader_variant in grouped_shaders
            ]
        })

    return asset_view_items


def _flatten_from_context(representations):
    for representation in representations:
        for attrib, value in representation.get('context', {}).items():
            representation[attrib] = value

        del representation['context']

    return representations
