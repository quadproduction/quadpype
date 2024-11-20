# -*- coding: utf-8 -*-
"""Progress window to show when QuadPype is updating/installing locally."""
import os
import logging as log

from pathlib import Path
from qtpy import QtCore, QtGui, QtWidgets

from .update_thread import UpdateThread
from .bootstrap import PackageVersion, ZXPExtensionData
from .nice_progress_bar import NiceProgressBar
from .tools import load_stylesheet, get_app_icon_path, get_fonts_dir_path


class UpdateWindow(QtWidgets.QDialog):
    """QuadPype update window."""

    _width = 500
    _height = 100

    def __init__(self, version: PackageVersion, zxp_hosts: [ZXPExtensionData], parent=None):
        super().__init__(parent)
        self._quadpype_version = version
        self._zxp_hosts = zxp_hosts
        self._result_version_path = None
        self._log = log.getLogger(str(__class__))

        self.setWindowTitle(
            f"QuadPype is updating ..."
        )
        self.setModal(True)
        self.setWindowFlags(
            QtCore.Qt.WindowMinimizeButtonHint
        )

        fonts_dir = Path(get_fonts_dir_path())
        roboto_font_path = str(fonts_dir.joinpath("RobotoMono-Regular.ttf"))
        poppins_font_path = str(fonts_dir.joinpath("Poppins"))
        icon_path = get_app_icon_path()

        # Install fonts
        QtGui.QFontDatabase.addApplicationFont(roboto_font_path)
        for filename in os.listdir(poppins_font_path):
            if os.path.splitext(filename)[1] == ".ttf":
                QtGui.QFontDatabase.addApplicationFont(filename)

        # Load logo
        pixmap_app_logo = QtGui.QPixmap(icon_path)
        # Set logo as icon of the window
        self.setWindowIcon(QtGui.QIcon(pixmap_app_logo))

        self._pixmap_app_logo = pixmap_app_logo

        self._update_thread = None

        self._init_ui()

        # Set stylesheet
        self.setStyleSheet(load_stylesheet())
        self._run_update()

    def _init_ui(self):

        # Main info
        # --------------------------------------------------------------------
        main_label = QtWidgets.QLabel(
            f"<b>QuadPype</b> is updating to {self._quadpype_version}", self)
        main_label.setWordWrap(True)
        main_label.setObjectName("MainLabel")

        # Progress bar
        # --------------------------------------------------------------------
        progress_bar = NiceProgressBar(self)
        progress_bar.setAlignment(QtCore.Qt.AlignCenter)
        progress_bar.setTextVisible(False)

        # add all to main
        main = QtWidgets.QVBoxLayout(self)
        main.addSpacing(15)
        main.addWidget(main_label, 0)
        main.addSpacing(15)
        main.addWidget(progress_bar, 0)
        main.addSpacing(15)

        self._main_label = main_label
        self._progress_bar = progress_bar

    def showEvent(self, event):
        super().showEvent(event)
        current_size = self.size()
        new_size = QtCore.QSize(
            max(current_size.width(), self._width),
            max(current_size.height(), self._height)
        )
        if current_size != new_size:
            self.resize(new_size)

    def _run_update(self):
        """Start install process.

        This will once again validate entered path and mongo if ok, start
        working thread that will do actual job.
        """
        # Check if install thread is not already running
        if self._update_thread and self._update_thread.isRunning():
            return
        self._progress_bar.setRange(0, 0)
        update_thread = UpdateThread(self)
        update_thread.set_version(self._quadpype_version)
        update_thread.set_zxp_hosts(self._zxp_hosts)
        update_thread.log_signal.connect(self._print)
        update_thread.step_text_signal.connect(self.update_step_text)
        update_thread.progress_signal.connect(self._update_progress)
        update_thread.finished.connect(self._installation_finished)

        self._update_thread = update_thread

        update_thread.start()

    def get_version_path(self):
        return self._result_version_path

    def _installation_finished(self):
        status = self._update_thread.result()
        self._result_version_path = status
        self._progress_bar.setRange(0, 1)
        self._update_progress(100)
        QtWidgets.QApplication.processEvents()
        self.done(int(QtWidgets.QDialog.Accepted))
        if self._update_thread.isRunning():
            self._update_thread.quit()
        self.close()

    def _update_progress(self, progress: int):
        # not updating progress as we are not able to determine it
        # correctly now. Progress bar is set to un-deterministic mode
        # until we are able to get progress in better way.
        """
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setValue(progress)
        text_visible = self._progress_bar.isTextVisible()
        if progress == 0:
            if text_visible:
                self._progress_bar.setTextVisible(False)
        elif not text_visible:
            self._progress_bar.setTextVisible(True)
        """
        return

    def _print(self, message: str, error: bool = False) -> None:
        """Print the message in the console.

        Args:
            message (str): message.
            error (bool): if True, print it red.
        """
        if error:
            self._log.error(message)
        else:
            self._log.info(message)

    def update_step_text(self, text: str) -> None:
        """Print the message in the console.

        Args:
            text (str): Text describing the current step.
        """
        self._main_label.setText(text)
