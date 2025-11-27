import sys
import os
import bpy
import argparse
import logging
from pathlib import Path


def execute():
    blender_addons_folder_path = get_addons_folder_path()
    blender_system_scripts_paths = get_system_scripts_folders_paths()

    enable_user_addons(
        blender_addons_folder_path,
        blender_system_scripts_paths
    )
    bpy.ops.wm.save_userpref()


def get_python_addon_file(path):
    return next(iter(_list_python_files_in_dir(path)))


def _list_python_files_in_dir(path):
    return [
        file_path for file_path in path.glob('**/*') if
        file_path.is_file() and
        file_path.suffix == '.py'
    ]


def _list_addons_folders(paths):
    return [
        folder for path in paths if path.exists()
        for folder in path.iterdir() if folder.is_dir() and folder.stem == "addons"
    ]


def get_addons_folder_path():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender-addons-folder", help="Blender installed addons folder path")
    args, _ = parser.parse_known_args(
        sys.argv[sys.argv.index("--") + 1:]
    )
    return Path(args.blender_addons_folder)


def get_system_scripts_folders_paths():
    return [
        Path(system_script_path) for system_script_path in
        os.environ.get('BLENDER_SYSTEM_SCRIPTS', '').split(';')
    ]


def _extract_folders(folder_path):
    return [
        folder for folder in folder_path.iterdir()
        if folder.is_dir() and
        not folder.stem.startswith('__') and
        not folder.stem.endswith('__')
    ]


def enable_user_addons(blender_addons_folder_path, blender_system_scripts_paths):
    addons_to_enable = set()
    for addon in _list_python_files_in_dir(blender_addons_folder_path):
        addons_to_enable.add(addon.stem)

    for addons_folder in _list_addons_folders(blender_system_scripts_paths):
        for single_addon_path in _extract_folders(addons_folder):
            addons_to_enable.add(single_addon_path.stem)

    for addon in addons_to_enable:
        logging.info(f"Enabling addon named '{addon}'...")
        try:
            bpy.ops.preferences.addon_enable(module=addon)
        except Exception:
            logging.info(f"An error has occurred when installing addon. It may be not usable.")
            continue
        logging.info(f"Addon enabled.")


execute()
