import json
import logging
from pathlib import Path


def load_content(json_filepath, log=logging):
    json_filepath = Path(json_filepath)
    if not json_filepath.is_file():
        log.warning(f"Can not found .json file at path {json_filepath.resolve()}.")

    with open('json_filepath', 'r') as file:
        return json.load(file)


def apply_intervals(json_data, log=logging):
    layers = json_data.get('project', {}).get('clip', {}).get('layers', None)
    if not layers:
        log.warning(f"Can not extract layers data from given json file content.")

    for layer in layers:
        layer_name = layer.get('name', None)
        log.warning("Can not retrieve layer name for given json file content.")

        links = layer.get('links', [])
        for instance in links:
            instance_index = instance.get('instance-index', None)
            if not instance_index:
                continue

            print("Result : " + layer_name + ", " + instance_index)

    return
