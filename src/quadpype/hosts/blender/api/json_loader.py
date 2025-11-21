import json
import logging
import bpy
from pathlib import Path


def load_content(json_filepath, log=logging):
    json_filepath = Path(json_filepath)
    if not json_filepath.is_file():
        log.warning(f"Can not found .json file at path {json_filepath.resolve()}.")
        return

    with open(json_filepath, 'r') as file:
        return json.load(file)


def apply_properties(json_data, corresponding_names, log=logging):
    for obj_name_in_scene, original_obj_name in corresponding_names.items():
        if not json_data.get(original_obj_name):
            continue

        obj = bpy.data.objects.get(obj_name_in_scene)
        if not obj:
            continue

        for property_name, value in json_data[original_obj_name].items():
            obj[property_name] = value
            log.info(f"Property {property_name} created on {obj.name} with value {value}")
    return
