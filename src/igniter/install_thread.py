# -*- coding: utf-8 -*-
"""Working thread for installer."""
import os
import sys
from pathlib import Path

from qtpy import QtCore

from .bootstrap_repos import (
    BootstrapRepos,
    QuadPypeVersionInvalid,
    QuadPypeVersionIOError,
    QuadPypeVersionExists,
    QuadPypeVersion
)

from .tools import (
    get_quadpype_global_settings,
    get_local_quadpype_path_from_settings,
    validate_mongo_connection,
    is_running_locally
)


class InstallThread(QtCore.QThread):
    """Install Worker thread.

    This class takes care of finding QuadPype version on user entered path
    (or loading this path from database). If nothing is entered by user,
    QuadPype will create its zip files from repositories that comes with it.

    If path contains plain repositories, they are zipped and installed to
    user data dir.

    """
    progress = QtCore.Signal(int)
    message = QtCore.Signal((str, bool))

    def __init__(self, parent=None,):
        self._mongo = None
        self._result = None

        super().__init__(parent)

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
        self.message.emit("Installing QuadPype ...", False)

        # find local version of QuadPype
        bs = BootstrapRepos(
            progress_callback=self.set_progress, log_signal=self.message)
        local_version = QuadPypeVersion.get_installed_version_str()

        if self._mongo:
            self.message.emit("Saving mongo connection string ...", False)
            bs.secure_registry.set_item("quadpypeMongo", self._mongo)
        elif os.getenv("QUADPYPE_MONGO"):
            self._mongo = os.getenv("QUADPYPE_MONGO")
        else:
            # try to get it from settings registry
            try:
                self._mongo = bs.secure_registry.get_item(
                    "quadpypeMongo")
            except ValueError:
                self.message.emit(
                    "!!! We need MongoDB URL to proceed.", True)
                self._set_result(-1)
                return
        os.environ["QUADPYPE_MONGO"] = self._mongo

        if not validate_mongo_connection(self._mongo):
            self.message.emit(f"Cannot connect to {self._mongo}", True)
            self._set_result(-1)
            return

        global_settings = get_quadpype_global_settings(self._mongo)
        data_dir = get_local_quadpype_path_from_settings(global_settings)
        bs.set_data_dir(data_dir)

        self.message.emit(
            f"Detecting QuadPype Patch versions in {bs.data_dir}",
            False)
        detected = bs.find_quadpype(include_zips=True)
        if not detected and (getattr(sys, 'frozen', False) or is_running_locally()):
            self.message.emit("None detected.", True)
            self.message.emit(("We will use QuadPype coming with "
                               "installer."), False)
            self.progress.emit(100)
            self._set_result(1)
            return

        if detected and not QuadPypeVersion.get_installed_version().is_compatible(detected[-1]):  # noqa: E501
            self.message.emit((
                f"Latest detected version {detected[-1]} "
                "is not compatible with the currently running "
                f"{local_version}"
            ), True)
            self.message.emit((
                "Filtering detected versions to compatible ones..."
            ), False)

        # filter results to get only compatible versions
        detected = [
            version for version in detected
            if version.is_compatible(
                QuadPypeVersion.get_installed_version())
        ]

        if detected:
            if QuadPypeVersion(
                    version=local_version, path=Path()) < detected[-1]:
                self.message.emit((
                    f"Latest installed version {detected[-1]} is newer "
                    f"then currently running {local_version}"
                ), False)
                self.message.emit("Skipping QuadPype install ...", False)
                if detected[-1].path.suffix.lower() == ".zip":
                    bs.extract_quadpype(detected[-1])
                self._set_result(0)
                return

            if QuadPypeVersion(version=local_version).get_main_version() == detected[-1].get_main_version():  # noqa: E501
                self.message.emit((
                    f"Latest installed version is the same as "
                    f"currently running {local_version}"
                ), False)
                self.message.emit("Skipping QuadPype install ...", False)
                self._set_result(0)
                return

        self.message.emit((
            "All installed versions are older then "
            f"currently running one {local_version}"
        ), False)

        self.message.emit("None detected.", False)

        self.message.emit(
            f"We will use local QuadPype version {local_version}", False)

        local_quadpype = bs.create_version_from_live_code()
        if not local_quadpype:
            self.message.emit(
                f"!!! Install failed - {local_quadpype}", True)
            self._set_result(-1)
            return

        try:
            bs.install_version(local_quadpype)
        except (QuadPypeVersionExists,
                QuadPypeVersionInvalid,
                QuadPypeVersionIOError) as e:
            self.message.emit(f"Installed failed: ", True)
            self.message.emit(str(e), True)
            self._set_result(-1)
            return

        self.message.emit(f"Installed as {local_quadpype}", False)
        self.progress.emit(100)
        self._set_result(1)
        return

    def set_path(self, path: str) -> None:
        """Helper to set path.

        Args:
            path (str): Path to set.

        """
        self._path = path

    def set_mongo(self, mongo: str) -> None:
        """Helper to set mongo url.

        Args:
            mongo (str): Mongodb url.

        """
        self._mongo = mongo

    def set_progress(self, progress: int) -> None:
        """Helper to set progress bar.

        Args:
            progress (int): Progress in percents.

        """
        self.progress.emit(progress)
