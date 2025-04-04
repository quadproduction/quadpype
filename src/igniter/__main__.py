# -*- coding: utf-8 -*-
"""Open install dialog."""

import sys
from qtpy import QtWidgets

from .gui import DatabaseStringDialog


RESULT = 0


def get_result(res: int):
    """Sets result returned from dialog."""
    global RESULT
    RESULT = res


app = QtWidgets.QApplication(sys.argv)

d = DatabaseStringDialog()
d.finished.connect(get_result)
d.open()
app.exec()
sys.exit(RESULT)
