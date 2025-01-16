from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets

from quadpype.pipeline import LauncherTaskAction


class CreateTaskPath(LauncherTaskAction):
    name = "create_task_path"
    label = "Create Folder"
    icon = "plus-square"
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
            self.show_message_box(
                "Work Directory Creation",
                "Creation Failed!\nCannot properly determine the work directory.\n\nDirectory not created.",
                icon_type="error"
            )
            return

        # Create work directory
        path.mkdir(parents=True, exist_ok=True)

        # Copy to clipboard
        self.copy_path_to_clipboard(path)

        # Display popup
        asset_name = session["AVALON_ASSET"]
        task_name = session.get("AVALON_TASK", None)
        popup_msg = f"Directory creation performed.\nWork directory for \"{asset_name}"
        if task_name:
            popup_msg += f"/{task_name}"
        popup_msg += "\" has been created.\n\nPath copied into clipboard."

        self.show_message_box("Work Directory Creation", popup_msg)

        # Returning True to force an action discovery update
        return True
