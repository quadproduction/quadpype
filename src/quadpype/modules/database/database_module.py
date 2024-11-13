import os

from quadpype.modules import QuadPypeModule, ITrayModule


class DatabaseModule(QuadPypeModule, ITrayModule):
    name = "database"

    def initialize(self, modules_settings):
        # This module is always enabled
        self.enabled = True

        database_settings = modules_settings[self.name]

        thumbnail_root = os.getenv("QUADPYPE_THUMBNAIL_ROOT")
        if not thumbnail_root:
            thumbnail_root = database_settings["QUADPYPE_THUMBNAIL_ROOT"]

        # Database DB timeout
        quadpype_db_timeout = os.getenv("QUADPYPE_DB_TIMEOUT")
        if not quadpype_db_timeout:
            quadpype_db_timeout = database_settings["QUADPYPE_DB_TIMEOUT"]

        self.thumbnail_root = thumbnail_root
        self.quadpype_db_timeout = quadpype_db_timeout

        # Tray attributes
        self._library_loader_imported = None
        self._library_loader_window = None
        self.rest_api_obj = None

    def get_global_environments(self):
        """QuadPype global environments for pype implementation."""
        return {
            # TODO thumbnails root should be multiplafrom
            # - thumbnails root
            "QUADPYPE_THUMBNAIL_ROOT": self.thumbnail_root,
            # - Database timeout in ms
            "QUADPYPE_DB_TIMEOUT": str(self.quadpype_db_timeout),
        }

    def tray_init(self):
        # Add library tool
        self._library_loader_imported = False
        try:
            from quadpype.tools.libraryloader import LibraryLoaderWindow

            self._library_loader_imported = True
        except Exception:
            self.log.warning(
                "Couldn't load Library loader tool for tray.",
                exc_info=True
            )

    # Definition of Tray menu
    def tray_menu(self, tray_menu):
        if not self._library_loader_imported:
            return

        from qtpy import QtWidgets
        # Actions
        action_library_loader = QtWidgets.QAction(
            "Loader", tray_menu
        )

        action_library_loader.triggered.connect(self.show_library_loader)

        tray_menu.addAction(action_library_loader)

    def tray_start(self, *_a, **_kw):
        return

    def tray_exit(self, *_a, **_kw):
        return

    def show_library_loader(self):
        if self._library_loader_window is None:
            from quadpype.pipeline import install_quadpype_plugins
            self._init_library_loader()

            install_quadpype_plugins()

        self._library_loader_window.show()

        # Raise and activate the window
        # for MacOS
        self._library_loader_window.raise_()
        # for Windows
        self._library_loader_window.activateWindow()

    # Webserver module implementation
    def webserver_initialization(self, server_manager):
        """Add routes for webserver."""
        if self.tray_initialized:
            from .rest_api import QuadPypeRestApiResource
            self.rest_api_obj = QuadPypeRestApiResource(self, server_manager)

    def _init_library_loader(self):
        from qtpy import QtCore
        from quadpype.tools.libraryloader import LibraryLoaderWindow

        libraryloader = LibraryLoaderWindow(
            show_projects=True,
            show_libraries=True
        )
        # Remove always on top flag for tray
        window_flags = libraryloader.windowFlags()
        if window_flags | QtCore.Qt.WindowStaysOnTopHint:
            window_flags ^= QtCore.Qt.WindowStaysOnTopHint
            libraryloader.setWindowFlags(window_flags)
        self._library_loader_window = libraryloader
