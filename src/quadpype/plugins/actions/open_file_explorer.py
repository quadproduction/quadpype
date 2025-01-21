import os
from string import Formatter

from quadpype.client import (
    get_project,
    get_asset_by_name,
)
from quadpype.pipeline import (
    Anatomy,
    LauncherTaskAction,
)
from quadpype.pipeline.template_data import get_template_data
from quadpype.lib import open_in_explorer


class OpenTaskPath(LauncherTaskAction):
    name = "open_task_path"
    label = "Explore here"
    icon = "folder-open"
    order = 500

    def process(self, session, **kwargs):
        from qtpy import QtCore, QtWidgets

        path = self.get_workdir(session)
        if not path:
            # An error occurs while retrieving the workdir path
            self.show_message_box(
                "Open Work Directory",
                "Operation Failed\nCannot properly determine the work directory.\n\nDirectory not created.",
                icon_type="error")
            return

        if not path.exists():
            # Create work directory
            path.mkdir(parents=True, exist_ok=True)

        app = QtWidgets.QApplication.instance()
        ctrl_pressed = QtCore.Qt.ControlModifier & app.keyboardModifiers()
        if ctrl_pressed:
            # Copy the path to clipboard
            self.copy_path_to_clipboard(path)
        else:
            open_in_explorer(path)

        # Returning True to force an action discovery update
        return True
