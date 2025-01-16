import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from qtpy import QtWidgets, QtGui

from quadpype import style
from quadpype import resources
from quadpype.lib import (
    ApplicationExecutableNotFound,
    ApplicationLaunchFailed,
    TemplateUnsolved
)
from quadpype.pipeline import Anatomy
from quadpype.pipeline.template_data import get_template_data
from quadpype.pipeline.plugin_discover import (
    discover,
    register_plugin,
    register_plugin_path,
    deregister_plugin,
    deregister_plugin_path
)
from quadpype.client import (
    get_project,
    get_asset_by_name,
)

from .load.utils import get_representation_path_from_context


class BaseLauncherAction(ABC):
    """Base class to define a Launcher action"""
    name = None
    label = None
    icon = None
    color = None
    order = 0

    _log = None

    _required_session_keys = (
        "AVALON_PROJECT",
        "AVALON_ASSET",
        "AVALON_TASK"
    )

    @property
    def log(self):
        if self._log is None:
            self._log = logging.getLogger("LauncherAction")
            self._log.propagate = True
        return self._log

    def is_compatible(self, session):
        """Return whether the class is compatible with the Session.

        Args:
            session (dict[str, Union[str, None]]): Session data with
                AVALON_PROJECT, AVALON_ASSET and AVALON_TASK.
        """
        for key in self._required_session_keys:
            if key not in session:
                return False
        return True

    @staticmethod
    def show_message_box(title, message, details=None):
        dialog = QtWidgets.QMessageBox()
        icon = QtGui.QIcon(resources.get_app_icon_filepath())
        dialog.setWindowIcon(icon)
        dialog.setStyleSheet(style.load_stylesheet())
        dialog.setWindowTitle("QuadPype: " + title)
        dialog.setText(message)
        if details:
            dialog.setDetailedText(details)
        return dialog.exec_()

    @abstractmethod
    def process(self, session, **kwargs):
        raise NotImplementedError("This method needs to be implemented by the subclass")


class LauncherAction(BaseLauncherAction, ABC):
    """Class use to define a Launcher action"""


class LauncherTaskAction(LauncherAction, ABC):
    _required_session_keys = (
        "AVALON_PROJECT",
        "AVALON_ASSET"
    )

    def get_workdir(self, session):
        project_name = session["AVALON_PROJECT"]
        asset_name = session["AVALON_ASSET"]
        task_name = session.get("AVALON_TASK", None)

        project = get_project(project_name)
        asset = get_asset_by_name(project_name, asset_name)

        workdir_data = get_template_data(project, asset, task_name)

        anatomy = Anatomy(project_name)
        try:
            workdir_path = anatomy.templates_obj["work"]["folder"].format_strict(workdir_data)
        except TemplateUnsolved as e:
            self.log.error(e)
            return None

        return Path(workdir_path.normalized())

    @staticmethod
    def copy_path_to_clipboard(path):
        path = path.replace("\\", "/")
        print(f"Copied to clipboard: {path}")
        app = QtWidgets.QApplication.instance()
        assert app, "Must have running QApplication instance"

        # Set to Clipboard
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(os.path.normpath(path))


class ApplicationAction(BaseLauncherAction):
    """QuadPype's application launcher

    Application action based on QuadPype's ApplicationManager system.
    """

    # Application object
    application = None
    # Action attributes
    label_variant = None
    group = None
    data = {}

    def process(self, session, **kwargs):
        """Process the full Application action"""

        project_name = session["AVALON_PROJECT"]
        asset_name = session["AVALON_ASSET"]
        task_name = session["AVALON_TASK"]
        try:
            self.application.launch(
                project_name=project_name,
                asset_name=asset_name,
                task_name=task_name,
                **self.data
            )

        except ApplicationExecutableNotFound as exc:
            details = exc.details
            msg = exc.msg
            log_msg = str(msg)
            if details:
                log_msg += "\n" + details
            self.log.warning(log_msg)
            self.show_message_box(
                "Application executable not found", msg, details
            )

        except ApplicationLaunchFailed as exc:
            msg = str(exc)
            self.log.warning(msg, exc_info=True)
            self.show_message_box("Application launch failed", msg)


class InventoryAction(object):
    """A custom action for the scene inventory tool

    If registered the action will be visible in the Right Mouse Button menu
    under the submenu "Actions".

    """

    label = None
    icon = None
    color = None
    order = 0

    log = logging.getLogger("InventoryAction")
    log.propagate = True

    @staticmethod
    def is_compatible(container):
        """Override function in a custom class

        This method is specifically used to ensure the action can operate on
        the container.

        Args:
            container(dict): the data of a loaded asset, see host.ls()

        Returns:
            bool
        """
        return bool(container.get("objectName"))

    def process(self, containers):
        """Override function in a custom class

        This method will receive all containers even those which are
        incompatible. It is advised to create a small filter along the lines
        of this example:

        valid_containers = filter(self.is_compatible(c) for c in containers)

        The return value will need to be a True-ish value to trigger
        the data_changed signal in order to refresh the view.

        You can return a list of container names to trigger GUI to select
        treeview items.

        You can return a dict to carry extra GUI options. For example:
            {
                "objectNames": [container names...],
                "options": {"mode": "toggle",
                            "clear": False}
            }
        Currently workable GUI options are:
            - clear (bool): Clear current selection before selecting by action.
                            Default `True`.
            - mode (str): selection mode, use one of these:
                          "select", "deselect", "toggle". Default is "select".

        Args:
            containers (list): list of dictionaries

        Return:
            bool, list or dict

        """
        return True

    @classmethod
    def filepath_from_context(cls, context):
        return get_representation_path_from_context(context)


# Launcher action
def discover_launcher_actions():
    return discover(LauncherAction)


def register_launcher_action(plugin):
    return register_plugin(LauncherAction, plugin)


def register_launcher_action_path(path):
    return register_plugin_path(LauncherAction, path)


# Inventory action
def discover_inventory_actions():
    actions = discover(InventoryAction)
    filtered_actions = []
    for action in actions:
        if action is not InventoryAction:
            filtered_actions.append(action)

    return filtered_actions


def register_inventory_action(plugin):
    return register_plugin(InventoryAction, plugin)


def deregister_inventory_action(plugin):
    deregister_plugin(InventoryAction, plugin)


def register_inventory_action_path(path):
    return register_plugin_path(InventoryAction, path)


def deregister_inventory_action_path(path):
    return deregister_plugin_path(InventoryAction, path)
