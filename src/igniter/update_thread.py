# -*- coding: utf-8 -*-
"""Working thread for update."""
from qtpy import QtCore

from .bootstrap_repos import (
    BootstrapRepos,
    QuadPypeVersion,
    ZXPExtensionData
)


class UpdateThread(QtCore.QThread):
    """Install Worker thread.

    This class takes care of finding QuadPype version on user entered path
    (or loading this path from database). If nothing is entered by user,
    QuadPype will create its zip files from repositories that comes with it.

    If path contains plain repositories, they are zipped and installed to
    user data dir.

    """
    progress_signal = QtCore.Signal(int)
    log_signal = QtCore.Signal((str, bool))
    step_text_signal = QtCore.Signal(str)

    def __init__(self, parent=None):
        self._result = None
        self._quadpype_version = None
        self._zxp_hosts = []
        super().__init__(parent)

    def set_version(self, quadpype_version: QuadPypeVersion):
        self._quadpype_version = quadpype_version

    def set_zxp_hosts(self, zxp_hosts: [ZXPExtensionData]):
        self._zxp_hosts = zxp_hosts

    def result(self):
        """Result of finished installation."""
        return self._result

    def _set_result(self, value):
        if self._result is not None:
            raise AssertionError("BUG: Result was set more than once!")
        self._result = value

    def run(self):
        """Thread entry point.

        Using :class:`BootstrapRepos` to either install QuadPype as zip files
        or copy them from location specified by user or retrieved from
        database.
        """
        bs = BootstrapRepos(progress_callback=self.set_progress,
                            log_signal=self.log_signal,
                            step_text_signal=self.step_text_signal)

        bs.set_data_dir(QuadPypeVersion.get_local_quadpype_path())

        # Adding the conditions to be able to show this window to update the ZXP extensions
        # without needing to install an QuadPype version
        if not bs.is_inside_user_data(self._quadpype_version.path) and self._quadpype_version.path.is_file():
            version_path = bs.install_version(self._quadpype_version)
        else:
            version_path = self._quadpype_version.path

        bs.update_zxp_extensions(self._quadpype_version, self._zxp_hosts)

        self._set_result(version_path)

    def set_progress(self, progress: int) -> None:
        """Helper to set progress bar.

        Args:
            progress (int): Progress in percents.

        """
        self.progress_signal.emit(progress)