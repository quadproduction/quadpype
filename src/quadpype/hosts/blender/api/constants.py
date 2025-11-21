import os
import bpy
import sys
import quadpype.hosts.blender

HOST_DIR = os.path.dirname(os.path.abspath(quadpype.hosts.blender.__file__))
PLUGINS_DIR = os.path.join(HOST_DIR, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")

ORIGINAL_EXCEPTHOOK = sys.excepthook

AVALON_INSTANCES = "AVALON_INSTANCES"
AVALON_CONTAINERS = "AVALON_CONTAINERS"
AVALON_PROPERTY = 'avalon'
IS_HEADLESS = bpy.app.background

SNAPSHOT_PROPERTY = '_snapshot'
SNAPSHOT_POSE_BONE = 'pose_bones'
SNAPSHOT_CUSTOM_PROPERTIES = 'custom_properties'
DEFAULT_VARIANT_NAME = "Main"
