import json
import logging
from pathlib import Path


def load_content(json_filepath, log=logging):
    json_filepath = Path(json_filepath)
    if not json_filepath.is_file():
        log.warning(f"Can not found .json file at path {json_filepath.resolve()}.")
        return

    with open(json_filepath, 'r') as file:
        return json.load(file)


def apply_intervals(json_data, composition_id, stub, log=logging):
    layers = json_data.get('project', {}).get('clip', {}).get('layers', None)
    if not layers:
        log.warning(f"Can not extract layers data from given json file content.")
        return

    layers_with_indexes = list()
    for layer in layers:
        layer_name = layer.get('name', None)
        if not layer_name:
            log.warning("Can not retrieve layer name for current layer in json file content.")
            continue

        links = layer.get('link', [])
        marker_indexes = []
        for instance in links:
            image_index = instance.get('images', None)
            if image_index is None:
                continue
            marker_indexes.extend(image_index)

        layers_with_indexes.append(
            {
                'layer_name': layer_name,
                'indexes': marker_indexes
            }
        )

    stub.add_markers_to_layers(composition_id, layers_with_indexes)
    log.info(f"Marker has been applied for {len(layers_with_indexes)} layers.")

    return
