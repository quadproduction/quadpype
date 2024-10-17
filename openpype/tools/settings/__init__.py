import sys
from qtpy import QtGui

from openpype import style
from openpype.tools.utils import get_openpype_qt_app
from .lib import (
    BTN_FIXED_SIZE,
    CHILD_OFFSET
)
from .local_settings import LocalSettingsWindow
from .settings import (
    MainWidget,
    ProjectListWidget
)


def main(user_role=None):
    if user_role is None:
        user_role = "user"

    user_role_low = user_role.lower()
    allowed_roles = ("user", "developer", "administrator")
    if user_role_low not in allowed_roles:
        raise ValueError("Invalid user role \"{}\". Expected {}".format(
            user_role, ", ".join(allowed_roles)
        ))

    app = get_openpype_qt_app()
    app.setWindowIcon(QtGui.QIcon(style.app_icon_path()))

    widget = MainWidget(user_role)
    widget.show()

    sys.exit(app.exec_())


__all__ = (
    "BTN_FIXED_SIZE",
    "CHILD_OFFSET",

    "MainWidget",
    "ProjectListWidget",
    "LocalSettingsWindow",
    "main"
)
