import os

from quadpype.modules import QuadPypeModule, ITrayModule


class AvalonModule(QuadPypeModule, ITrayModule):
    label = "Loader"
    name = "avalon"

    def initialize(self, modules_settings):
        # This module is always enabled
        self.enabled = True

        avalon_settings = modules_settings[self.name]

        thumbnail_root = os.getenv("AVALON_THUMBNAIL_ROOT")
        if not thumbnail_root:
            thumbnail_root = avalon_settings["AVALON_THUMBNAIL_ROOT"]

        # Mongo timeout
        avalon_mongo_timeout = os.getenv("AVALON_TIMEOUT")
        if not avalon_mongo_timeout:
            avalon_mongo_timeout = avalon_settings["AVALON_TIMEOUT"]

        self.thumbnail_root = thumbnail_root
        self.avalon_mongo_timeout = avalon_mongo_timeout

        # Tray attributes
        self._library_loader_imported = None
        self._library_loader_window = None
        self.rest_api_obj = None

    def get_global_environments(self):
        """Avalon global environments for QuadPype implementation."""
        return {
            # TODO thumbnails root should be multiplafrom
            # - thumbnails root
            "AVALON_THUMBNAIL_ROOT": self.thumbnail_root,
            # - mongo timeout in ms
            "AVALON_TIMEOUT": str(self.avalon_mongo_timeout),
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
            self.label, tray_menu
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
            from .rest_api import AvalonRestApiResource
            self.rest_api_obj = AvalonRestApiResource(self, server_manager)

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
