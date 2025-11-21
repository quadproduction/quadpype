import functools
import traceback

from qtpy import QtWidgets

from quadpype.widgets.message_window import ScrollMessageBox


def error(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except Exception as err:
            msg = ScrollMessageBox(
                icon=QtWidgets.QMessageBox.Warning,
                title=str(err) if str(err) else "An error has occured",
                messages=[str(traceback.format_exc())],
                max_width=600
            )
            msg.exec_()

            return None

    return wrapper
