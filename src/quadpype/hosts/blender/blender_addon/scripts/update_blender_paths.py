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


def update_render_layers_paths(windows_path, linux_path, mac_path, replaced_root):
    scene = bpy.context.scene

    if scene.node_tree is None:
        logging.error("Scene does not have a valid node tree. Make sure compositing nodes are enabled.")
        return

    for output_node in get_output_nodes(scene):
        logging.info(f"Updating render output path : {output_node.base_path}")
        output_node.base_path = replace_root(output_node.base_path, windows_path, linux_path, mac_path, replaced_root)
        logging.info(f"Render output path has been updated to : {output_node.base_path}")


def get_output_nodes(scene):
    return [node for node in scene.node_tree.nodes if node.type == 'OUTPUT_FILE']


def _flatten_path(path):
    return path.replace('\\', '\\\\')


def replace_root(original_path, windows_path, linux_path, mac_path, replaced_root):
    return re.sub(
        pattern=fr'^({windows_path})|({linux_path})|({mac_path})',
        repl=replaced_root,
        string=original_path
    )


def execute(args):
    if args.set_specific_root_path:
        replaced_root = _flatten_path(args.set_specific_root_path)

    else:
        replaced_root = _flatten_path(get_correct_path_with_platform(args=args, platform=sys.platform))
        if not replaced_root:
            logging.error(f"Current platform ({sys.platform}) is not supported by script. Paths can not be updated.")
            quit()

    # Flatten windows path to remove double slashes
    windows_root_path = _flatten_path(args.windows_root_path)
    linux_root_path = _flatten_path(args.linux_root_path)
    mac_root_path = _flatten_path(args.mac_root_path)

    update_render_layers_paths(
        windows_path=windows_root_path,
        linux_path=linux_root_path,
        mac_path=mac_root_path,
        replaced_root=replaced_root
    )

    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)


execute(get_args())
