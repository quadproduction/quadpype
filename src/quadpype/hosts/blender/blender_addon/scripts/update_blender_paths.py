import bpy
import re
import logging
import sys
import argparse
from pathlib import Path
from enum import Enum

logging.getLogger().setLevel(logging.INFO)


class Platform(Enum):
    LINUX = 'linux'
    WINDOWS = 'win32'
    MACOS = 'darwin'


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
    parser.add_argument("-wp", "--windows-root-path", help="Windows root path to use.", required=True)
    parser.add_argument("-lp", "--linux-root-path", help="Linux root path to use.", required=True)
    parser.add_argument("-mp", "--mac-root-path", help="Mac root path to use.", required=True)
    parser.add_argument("-s", "--set-specific-root-path", help="Replace roots paths by given one.")
    try:
        args, _ = parser.parse_known_args(
            sys.argv[sys.argv.index("--") + 1:]
        )
    except ValueError:
        logging.error("No argument received from command line. Arguments should be added after '--' tag.")
        quit()

    return args


def get_correct_path_with_platform(args, platform):
    return args.windows_root_path if platform == Platform.WINDOWS.value else \
        args.linux_root_path if platform == Platform.LINUX.value else \
        args.mac_root_path if platform == Platform.MACOS.value else None


def update_paths(name, objects_to_update, attribute, root_paths, replaced_root):
    objects_to_update = eval(objects_to_update)
    if len(objects_to_update) == 0:
        logging.info(f"[{name}] Nothing to update.")
        return

    logging.info(f"[{name}] Updating paths.")
    for single_object in objects_to_update:
        object_path = getattr(single_object, attribute, None)
        if object_path is None:
            logging.warning(f"[{name}] Does not have attribute named {attribute}. Abort path update.")
            return

        logging.info(f"[{name}] Updating property {attribute} : {object_path}.")
        setattr(single_object, attribute, replace_root(object_path, root_paths, replaced_root))
        logging.info(f"[{name}] {attribute} has been updated to : {getattr(single_object, attribute)}.")


def get_output_nodes(scene):
    if not scene.node_tree:
        logging.error("Scene does not have a valid node tree. Make sure compositing nodes are enabled.")
        return []

    return [node for node in scene.node_tree.nodes if node.type == 'OUTPUT_FILE']


def _flatten_path(path):
    return path.replace('\\\\', '\\').replace('\\', '/')


def replace_root(original_path, root_paths, replaced_root):
    return re.sub(
        pattern=fr'^({root_paths.windows})|({root_paths.linux})|({root_paths.mac})',
        repl=replaced_root,
        string=_flatten_path(original_path)
    )


def execute(args):
    if args.set_specific_root_path:
        replaced_root = _flatten_path(args.set_specific_root_path)

    else:
        replaced_root = _flatten_path(get_correct_path_with_platform(args=args, platform=sys.platform))
        if not replaced_root:
            logging.error(f"Current platform ({sys.platform}) is not supported by script. Paths can not be updated.")
            quit()

    root_paths = RootPath(
        windows_path=_flatten_path(args.windows_root_path),
        linux_path=args.linux_root_path,
        mac_path=args.mac_root_path
    )

    for objects_properties in objects_attr_to_update:
        name, objects_to_update, attribute = objects_properties
        update_paths(
            name=name,
            objects_to_update=objects_to_update,
            attribute=attribute,
            root_paths=root_paths,
            replaced_root=replaced_root
        )

    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)


execute(get_args())
