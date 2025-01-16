from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets

from quadpype.pipeline import LauncherTaskAction


class CreateTaskPath(LauncherTaskAction):
    name = "create_task_path"
    label = "Create Folder"
    icon = "plus-square"
    color = "#008000"
    order = 600

    def is_compatible(self, session):
        is_compatible = super(CreateTaskPath, self).is_compatible(session)
        if not is_compatible:
            return False

        path = self.get_workdir(session)

        # Return True if the path doesn't exist
        # Since the goal of this action is to create the workdir
        return path and not path.exists()

    def process(self, session, **kwargs):
        path = self.get_workdir(session)

        if not path:
            # An error occurs while retrieving the workdir path
            self.show_message_box("Creation Failed",
                                  "Cannot properly determine the work directory.\nDirectory not created.")
            return

        # Create work directory
        path.mkdir(parents=True, exist_ok=True)

        # Copy to clipboard
        self.copy_path_to_clipboard(path)

        # Display popup
        asset_name = session["AVALON_ASSET"]
        task_name = session.get("AVALON_TASK", None)
        popup_msg = "Work directory for {}".format(asset_name)
        if task_name:
            popup_msg += " / {}".format(popup_msg, task_name)
        popup_msg += " has been created.\nPath copied into clipboard."

        popup_ret_code = self.show_message_box("Work Directory Created", popup_msg)

        if popup_ret_code == QtWidgets.QMessageBox.Ok:
            return True
