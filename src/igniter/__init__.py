# -*- coding: utf-8 -*-
"""Open install dialog."""

import os
import sys

os.chdir(os.path.dirname(__file__))  # for override sys.path in Deadline

from .version import __version__ as version


def _get_qt_app():
    from qtpy import QtWidgets, QtCore

    is_event_loop_running = True

    app = QtWidgets.QApplication.instance()
    if app is not None:
        return app, is_event_loop_running

    for attr_name in (
        "AA_EnableHighDpiScaling",
        "AA_UseHighDpiPixmaps",
    ):
        attr = getattr(QtCore.Qt, attr_name, None)
        if attr is not None:
            QtWidgets.QApplication.setAttribute(attr)

    policy = os.getenv("QT_SCALE_FACTOR_ROUNDING_POLICY")
    if (
        hasattr(QtWidgets.QApplication, "setHighDpiScaleFactorRoundingPolicy")
        and not policy
    ):
        QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
            QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    # Since it's a new QApplication the event loop isn't running yet
    is_event_loop_running = False

    return QtWidgets.QApplication(sys.argv), is_event_loop_running


def ask_database_connection_string(log=None):
    """Show the GUI dialog."""
    if os.getenv("QUADPYPE_HEADLESS_MODE"):
        error_msg = "!!! Can't open dialog in headless mode. Exiting."
        if log:
            log(error_msg)
        else:
            print(error_msg)
        sys.exit(1)
    from .gui import DatabaseStringDialog

    app, is_event_loop_running = _get_qt_app()

    d = DatabaseStringDialog(log)
    d.open()

    if not is_event_loop_running:
        app.exec_()
    else:
        d.exec_()

    return d.result()


def open_zxp_update_window(running_version_fullpath, zxp_hosts=None):
    """Open ZXP update window."""
    if zxp_hosts is None:
        zxp_hosts = []
    if os.getenv("QUADPYPE_HEADLESS_MODE"):
        print("!!! Can't open dialog in headless mode. Exiting.")
        sys.exit(1)

    from .gui import ZXPUpdateWindow

    app, is_event_loop_running = _get_qt_app()

    d = ZXPUpdateWindow(
        version_fullpath=running_version_fullpath,
        zxp_hosts=zxp_hosts
    )
    d.open()

    if not is_event_loop_running:
        app.exec_()
    else:
        d.exec_()


def show_message_dialog(title, message):
    """Show dialog with a message and title to user."""
    if os.getenv("QUADPYPE_HEADLESS_MODE"):
        print("!!! Can't open dialog in headless mode. Exiting.")
        sys.exit(1)

    from .gui import MessageDialog

    app, is_event_loop_running = _get_qt_app()

    dialog = MessageDialog(title, message)
    dialog.open()

    if not is_event_loop_running:
        app.exec_()
    else:
        dialog.exec_()


__all__ = [
    "ask_database_connection_string",
    "open_zxp_update_window",
    "show_message_dialog",
    "version"
]
