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
    validate_database_connection
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
        self._database_uri = None
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

        # user did not entered URI
        if self._database_uri:
            self.message.emit("Saving database connection string ...", False)
            bs.secure_registry.set_item("DatabaseUri", self._database_uri)

        elif os.getenv("QUADPYPE_DB_URI"):
            self._database_uri = os.getenv("QUADPYPE_DB_URI")
        else:
            # try to get it from settings registry
            try:
                self._database_uri = bs.secure_registry.get_item(
                    "DatabaseUri")
            except ValueError:
                self.message.emit(
                    "!!! We need a database URI to proceed.", True)
                self._set_result(-1)
                return
        os.environ["QUADPYPE_DB_URI"] = self._database_uri

        if not validate_database_connection(self._database_uri):
            self.message.emit(f"Cannot connect to {self._database_uri}", True)
            self._set_result(-1)
            return

        global_settings = get_quadpype_global_settings(self._database_uri)
        data_dir = get_local_quadpype_path_from_settings(global_settings)
        bs.set_data_dir(data_dir)

        self.message.emit(
            f"Detecting installed QuadPype versions in {bs.data_dir}",
            False)
        detected = bs.find_quadpype(include_zips=True)
        if not detected and getattr(sys, 'frozen', False):
            self.message.emit("None detected.", True)
            self.message.emit(("We will use QuadPype coming with "
                               "installer."), False)
            quadpype_version = bs.create_version_from_frozen_code()
            if not quadpype_version:
                self.message.emit(
                    f"!!! Install failed - {quadpype_version}", True)
                self._set_result(-1)
                return
            self.message.emit(f"Using: {quadpype_version}", False)
            bs.install_version(quadpype_version)
            self.message.emit(f"Installed as {quadpype_version}", False)
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

    def set_database_uri(self, database_uri: str) -> None:
        """Helper to set the database URI.

        Args:
            database_uri (str): Database URI.

        """
        self._database_uri = database_uri

    def set_progress(self, progress: int) -> None:
        """Helper to set progress bar.

        Args:
            progress (int): Progress in percents.

        """
        self.progress.emit(progress)
