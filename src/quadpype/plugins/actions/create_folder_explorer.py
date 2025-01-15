import os
from string import Formatter

from quadpype.client import (
    get_project,
    get_asset_by_name,
)
from quadpype.pipeline import (
    Anatomy,
    LauncherAction,
)
from quadpype.pipeline.template_data import get_template_data


class CreateTaskPath(LauncherAction):
    name = "create_task_path"
    label = "Create Folder"
    icon = "plus-square"
    color="#008000"
    order = 600

    def is_compatible(self, session):
        """Resolve Path, and return True if the path doesn't exist"""
        # Skip if no asset is selected
        if not bool(session.get("AVALON_ASSET")):
            return False

        project_name = session.get("AVALON_PROJECT", None)
        asset_name = session.get("AVALON_ASSET", None)
        task_name = session.get("AVALON_TASK", None)

        path = self._get_workdir(project_name, asset_name, task_name)

        # Return True if path doesn't exist
        return not(os.path.exists(path))

    def process(self, session, **kwargs):
        from qtpy.QtWidgets import QMessageBox

        # informative popup window
        popup = QMessageBox()

        project_name = session["AVALON_PROJECT"]
        asset_name = session["AVALON_ASSET"]
        task_name = session.get("AVALON_TASK", None)

        path = self._get_workdir(project_name, asset_name, task_name)

        # copy to clipboard + create dir
        self.copy_path_to_clipboard(path)
        os.makedirs(path)

        popup_msg = "Folder for {}".format(asset_name)
        if task_name:
            popup_msg = "{} / {}".format(popup_msg, task_name)

        popup_msg = "{} has been created.\nPath copied into clipboard.".format(popup_msg)
        popup.setWindowTitle("Folder Created")
        popup.setText(popup_msg)
        popup.setIcon(QMessageBox.Information)
        popup.setStandardButtons(QMessageBox.Ok)

        popup.exec()


    def _find_first_filled_path(self, path):
        if not path:
            return ""

        fields = set()
        for item in Formatter().parse(path):
            _, field_name, format_spec, conversion = item
            if not field_name:
                continue
            conversion = "!{}".format(conversion) if conversion else ""
            format_spec = ":{}".format(format_spec) if format_spec else ""
            orig_key = "{{{}{}{}}}".format(
                field_name, conversion, format_spec)
            fields.add(orig_key)

        for field in fields:
            path = path.split(field, 1)[0]
        return path

    def _get_workdir(self, project_name, asset_name, task_name):

        project = get_project(project_name)
        asset = get_asset_by_name(project_name, asset_name)

        data = get_template_data(project, asset, task_name)

        anatomy = Anatomy(project_name)
        workdir = anatomy.templates_obj["work"]["folder"].format(data)

        # Remove any potential un-formatted parts of the path
        valid_workdir = self._find_first_filled_path(workdir)

        # Path is not filled at all
        if not valid_workdir:
            raise AssertionError("Failed to calculate workdir.")

        # Normalize
        valid_workdir = os.path.normpath(valid_workdir)

        if valid_workdir:
            return valid_workdir

        return ""

    @staticmethod
    def copy_path_to_clipboard(path):
        from qtpy import QtWidgets

        path = path.replace("\\", "/")
        print(f"Created and Copied to clipboard: {path}")
        app = QtWidgets.QApplication.instance()
        assert app, "Must have running QApplication instance"

        # Set to Clipboard
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(os.path.normpath(path))
