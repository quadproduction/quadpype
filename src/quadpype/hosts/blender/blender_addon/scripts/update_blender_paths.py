import bpy
import json
import re
import logging
import sys
import argparse
from pathlib import Path
from enum import Enum

logging.getLogger().setLevel(logging.INFO)


class Platform(Enum):
    linux = 'linux'
    win32 = 'windows'
    darwin = 'darwin'


# Object type (for logging), then access property / function, then attribute to update
objects_attr_to_update = [
    ["Render nodes", "get_output_nodes(bpy.context.scene)", "base_path"],
    ["Cache files", "bpy.data.cache_files", "filepath"],
    ["Image Files", "bpy.data.images", "filepath"],
    ["VDB Files", "bpy.data.volumes", "filepath"],
    ["Modifiers", "[mod for obj in bpy.data.objects for mod in obj.modifiers]", "simulation_bake_directory"]
]


class RootPath:
    windows: str = ''
    linux: str = ''
    mac: str = ''

    def __init__(self, windows_path, linux_path, mac_path):
        self.windows = windows_path
        self.linux = linux_path
        self.mac = mac_path


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--root-anatomy", help="Roots paths by category and os.", required=True)
    parser.add_argument(
        "-c", "--convert-to-os",
        help="If filled, will convert path to given os data from root anatomy"
    )

    try:
        args, _ = parser.parse_known_args(
            sys.argv[sys.argv.index("--") + 1:]
        )
    except ValueError:
        logging.error("No argument received from command line. Arguments should be added after '--' tag.")
        quit()

    return args


def get_correct_path_with_platform(paths, platform):
    return _flatten_path(paths[Platform[platform].value])


def update_paths(name, objects_to_update, attribute, root_paths, replaced_root, replaced_paths):
    objects_to_update = eval(objects_to_update)
    if len(objects_to_update) == 0:
        logging.info(f"[{name}] Nothing to update.")
        return

    logging.info(f"[{name}] Updating paths.")
    for single_object in objects_to_update:
        object_path = _flatten_path(getattr(single_object, attribute, None))
        if object_path is None:
            logging.warning(f"[{name}] Does not have attribute named {attribute}. Abort path update.")
            continue

        if object_path in replaced_paths:
            logging.info(f"[{name}] Path for file {Path(object_path).stem} has already been updated.")
            continue

        logging.info(f"[{name}] Updating property {attribute} : {object_path}")
        updated_path = replace_root(object_path, root_paths, replaced_root)
        if updated_path == object_path:
            logging.info(
                f"[{name}] Path for file {Path(object_path).stem} has not passed filter "
                f"and has not been updated."
            )
            continue

        setattr(single_object, attribute, updated_path)
        replaced_paths.append(updated_path)
        logging.info(f"[{name}] {attribute} has been updated to : {updated_path}.")


def get_output_nodes(scene):
    if not scene.node_tree:
        logging.error("Scene does not have a valid node tree. Make sure compositing nodes are enabled.")
        return []

    return [node for node in scene.node_tree.nodes if node.type == 'OUTPUT_FILE']


def _flatten_path(path):
    return path.replace('\\\\', '\\').replace('\\', '/') if path else None


def replace_root(original_path, root_paths, replaced_root):
    return re.sub(
        pattern=fr'^({root_paths.windows})|({root_paths.linux})|({root_paths.mac})',
        repl=replaced_root,
        string=original_path
    )


def execute(args):
    root_paths = json.loads(args.root_anatomy)
    replaced_paths = list()
    for root_category, root_paths in root_paths.items():
        category_label = f"Treating category named '{root_category}'."
        print('-'*len(category_label))
        logging.info(category_label)
        print('-'*len(category_label))
        if args.convert_to_os:
            replaced_root = root_paths[Platform[args.convert_to_os].value]

        else:
            replaced_root = _flatten_path(
                get_correct_path_with_platform(
                    paths=root_paths,
                    platform=sys.platform
                )
            )
            if not replaced_root:
                logging.error(
                    f"Current platform ({sys.platform}) is not supported by script. Paths can not be updated.")
                quit()

        root_paths = RootPath(
            windows_path=_flatten_path(root_paths['windows']),
            linux_path=root_paths['linux'],
            mac_path=root_paths['darwin']
        )

        for objects_properties in objects_attr_to_update:
            name, objects_to_update, attribute = objects_properties
            update_paths(
                name=name,
                objects_to_update=objects_to_update,
                attribute=attribute,
                root_paths=root_paths,
                replaced_root=replaced_root,
                replaced_paths=replaced_paths
            )

    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)


execute(get_args())
