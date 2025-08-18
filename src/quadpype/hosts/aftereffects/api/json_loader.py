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

    for layer in layers:
        layer_name = layer.get('name', None)
        if not layer_name:
            log.warning("Can not retrieve layer name for current layer in json file content.")
            continue

        links = layer.get('link', [])
        marker_index = []
        for instance in links:
            image_index = instance.get('images', None)
            if image_index is None:
                continue
            marker_index.extend(image_index)

        for index in marker_index:
            stub.add_marker_to_layer(composition_id, layer_name, index)
            log.info(f"Marker has been applied at frame {index} on layer named {layer_name}.")

    return
