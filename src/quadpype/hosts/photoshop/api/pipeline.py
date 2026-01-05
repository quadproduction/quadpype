import os

from qtpy import QtWidgets

import pyblish.api

from quadpype.lib import register_event_callback, Logger
from quadpype.pipeline import (
    register_loader_plugin_path,
    register_creator_plugin_path,
    AVALON_CONTAINER_ID,
)
from quadpype.tools.utils.workfile_cache import WorkFileCache
from quadpype.host import (
    HostBase,
    IWorkfileHost,
    ILoadHost,
    IPublishHost
)

from quadpype.pipeline.load import any_outdated_containers
from quadpype.hosts.photoshop import PHOTOSHOP_HOST_DIR
from quadpype.tools.utils import get_quadpype_qt_app
from quadpype.pipeline.anatomy import Anatomy
from quadpype.client.mongo.entities import get_assets
from . import lib, launch_logic

log = Logger.get_logger(__name__)

PLUGINS_DIR = os.path.join(PHOTOSHOP_HOST_DIR, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")
INVENTORY_PATH = os.path.join(PLUGINS_DIR, "inventory")
ANATOMY= Anatomy()

class PhotoshopHost(HostBase, IWorkfileHost, ILoadHost, IPublishHost, WorkFileCache):
    name = "photoshop"

    def install(self):
        """Install Photoshop-specific functionality needed for integration.

        This function is called automatically on calling
        `api.install(photoshop)`.
        """
        log.info("Installing QuadPype Photoshop...")
        pyblish.api.register_host("photoshop")

        pyblish.api.register_plugin_path(PUBLISH_PATH)
        register_loader_plugin_path(LOAD_PATH)
        register_creator_plugin_path(CREATE_PATH)
        log.info(PUBLISH_PATH)

        pyblish.api.register_callback(
            "instanceToggled", on_pyblish_instance_toggled
        )

        register_event_callback("application.launched", on_application_launch)

    def current_file(self):
        stub = _get_stub()
        try:
            full_name = stub.get_active_document_full_name()
            if full_name and full_name not in ["null", "undefined"]:
                return os.path.normpath(full_name).replace("\\", "/")
        except Exception:
            pass

        return None

    def work_root(self, session):
        return os.path.normpath(session["AVALON_WORKDIR"]).replace("\\", "/")

    def open_workfile(self, filepath):
        stub = _get_stub()
        stub.open(filepath)

        return True

    def save_workfile(self, filepath=None):
        _, ext = os.path.splitext(filepath)
        stub = _get_stub()
        stub.saveAs(filepath, ext[1:].lower(), True)
        self.add_task_extension(extension=ext)

    def get_current_workfile(self):
        return self.current_file()

    def workfile_has_unsaved_changes(self):
        stub = _get_stub()
        if self.current_file():
            return not stub.is_saved()

        return False

    def get_workfile_extensions(self):
        return [".psd", ".psb"]

    def get_containers(self):
        return ls()

    def get_context_data(self):
        """Get stored values for context (validation enable/disable etc)"""
        stub = _get_stub()
        meta = stub.get_layers_metadata()
        for item in meta:
            if item.get("id") == "publish_context":
                item.pop("id")
                return item

        return {}

    def get_current_task_name(self):
        current_task = os.getenv("AVALON_TASK")
        current_file = self.current_file()
        if not current_file:
            return current_task
        project_tasks = [k for k in ANATOMY.get("tasks", {}).keys()]

        found_task = next((f for f in project_tasks if f in current_file), None)
        return found_task if found_task else current_task

    def get_current_asset_name(self):
        current_asset = os.getenv("AVALON_ASSET")
        current_file = self.current_file()
        if not current_file:
            return current_asset
        current_project_asset_pointer = get_assets(self.get_current_project_name())
        project_assets = [a["name"] for a in current_project_asset_pointer if a["data"]["tasks"]]

        parts = os.path.normpath(current_file).split(os.sep)
        found_asset = next((f for f in project_assets if f in parts), None)
        return found_asset if found_asset else current_asset

    def update_context_data(self, data, changes):
        """Store value needed for context"""
        item = data
        item["id"] = "publish_context"
        stub = _get_stub()
        stub.imprint(item["id"], item)

    def list_instances(self):
        """List all created instances to publish from current workfile.

        Pulls from File > File Info

        Returns:
            (list) of dictionaries matching instances format
        """
        stub = _get_stub()

        if not stub:
            return []

        instances = []
        layers_meta = stub.get_layers_metadata()
        if layers_meta:
            for instance in layers_meta:
                if instance.get("id") == "pyblish.avalon.instance":
                    instances.append(instance)

        return instances

    def remove_instance(self, instance):
        """Remove instance from current workfile metadata.

        Updates metadata of current file in File > File Info and removes
        icon highlight on group layer.

        Args:
            instance (dict): instance representation from subsetmanager model
        """
        stub = _get_stub()

        if not stub:
            return

        inst_id = instance.get("instance_id") or instance.get("uuid")  # legacy
        if not inst_id:
            log.warning("No instance identifier for {}".format(instance))
            return

        stub.remove_instance(inst_id)

        if instance.get("members"):
            item = stub.get_layer(instance["members"][0])
            if item:
                stub.rename_layer(item.id,
                                  item.name.replace(stub.PUBLISH_ICON, ''))


def check_inventory():
    if not any_outdated_containers():
        return

    # Warn about outdated containers.
    _app = get_quadpype_qt_app()

    message_box = QtWidgets.QMessageBox()
    message_box.setIcon(QtWidgets.QMessageBox.Warning)
    msg = "There are outdated containers in the scene."
    message_box.setText(msg)
    message_box.exec_()


def on_application_launch():
    check_inventory()


def on_pyblish_instance_toggled(instance, old_value, new_value):
    """Toggle layer visibility on instance toggles."""
    instance[0].Visible = new_value


def ls():
    """Yields containers from active Photoshop document

    This is the host-equivalent of api.ls(), but instead of listing
    assets on disk, it lists assets already loaded in Photoshop; once loaded
    they are called 'containers'

    Yields:
        dict: container

    """
    try:
        stub = lib.stub()  # only after Photoshop is up
    except launch_logic.ConnectionNotEstablishedYet:
        print("Not connected yet, ignoring")
        return

    if not stub.get_active_document_name():
        return

    layers_meta = stub.get_layers_metadata()  # minimalize calls to PS
    for layer in stub.get_layers():
        data = stub.read(layer, layers_meta)

        # Skip non-tagged layers.
        if not data:
            continue

        # Filter to only containers.
        if "container" not in data["id"]:
            continue

        # Append transient data
        data["objectName"] = layer.name.replace(stub.LOADED_ICON, '')
        data["layer"] = layer

        yield data


def _get_stub():
    """Handle pulling stub from PS to run operations on host

    Returns:
        (PhotoshopServerStub) or None
    """
    try:
        stub = lib.stub()  # only after Photoshop is up
    except launch_logic.ConnectionNotEstablishedYet:
        print("Not connected yet, ignoring")
        return

    if not stub.get_active_document_name():
        return

    return stub


def containerise(
    name, namespace, layer, context, loader=None, suffix="_CON"
):
    """Imprint layer with metadata

    Containerisation enables a tracking of version, author and origin
    for loaded assets.

    Arguments:
        name (str): Name of resulting assembly
        namespace (str): Namespace under which to host container
        layer (PSItem): Layer to containerise
        context (dict): Asset information
        loader (str, optional): Name of loader used to produce this container.
        suffix (str, optional): Suffix of container, defaults to `_CON`.

    Returns:
        container (str): Name of container assembly
    """
    layer.name = name + suffix

    data = {
        "schema": "quadpype:container-2.0",
        "id": AVALON_CONTAINER_ID,
        "name": name,
        "namespace": namespace,
        "loader": str(loader),
        "representation": str(context["representation"]["_id"]),
        "members": [str(layer.id)]
    }
    stub = lib.stub()
    stub.imprint(layer.id, data)

    return layer


def cache_and_get_instances(creator):
    """Cache instances in shared data.

    Storing all instances as a list as legacy instances might be still present.
    Args:
        creator (Creator): Plugin which would like to get instances from host.
    Returns:
        List[]: list of all instances stored in metadata
    """
    shared_key = "quadpype.photoshop.instances"
    if shared_key not in creator.collection_shared_data:
        creator.collection_shared_data[shared_key] = \
            creator.host.list_instances()
    return creator.collection_shared_data[shared_key]
