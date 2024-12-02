from abc import ABCMeta, abstractmethod

from quadpype import resources


class _QuadPypeInterfaceMeta(ABCMeta):
    """QuadPypeInterface metaclass to print proper string."""

    def __str__(self):
        return "<'QuadPypeInterface.{}'>".format(self.__name__)

    def __repr__(self):
        return str(self)


class QuadPypeInterface(object, metaclass=_QuadPypeInterfaceMeta):
    """Base class of Interface that can be used as Mixin with abstract parts.

    This is way how QuadPype module or addon can tell QuadPype that contains
    implementation for specific functionality.

    Child classes of QuadPypeInterface may be used as mixin in different
    QuadPype modules, which means they have to have implemented methods defined
    in the interface. By default, the interface does not have any abstract parts.
    """

    pass


class IPluginPaths(QuadPypeInterface):
    """Module has plugin paths to return.

    Expected result is dictionary with keys "publish", "create", "load",
    "actions", "inventory", "builder" and values as list or string.
    {
        "publish": ["path/to/publish_plugins"]
    }
    """

    @abstractmethod
    def get_plugin_paths(self):
        pass

    def _get_plugin_paths_by_type(self, plugin_type):
        paths = self.get_plugin_paths()
        if not paths or plugin_type not in paths:
            return []

        paths = paths[plugin_type]
        if not paths:
            return []

        if not isinstance(paths, (list, tuple, set)):
            paths = [paths]
        return paths

    def get_create_plugin_paths(self, host_name):
        """Retrieve "create" plugin paths.

        Get the "create" plugin paths based on a host name.

        Notes:
            Default implementation uses 'get_plugin_paths' and always returns
            all "create" plugin paths.

        Args:
            host_name (str): To return the plugin paths for this host.
        """

        return self._get_plugin_paths_by_type("create")

    def get_load_plugin_paths(self, host_name):
        """Retrieve "load" plugin paths.

        Get the "load" plugin paths based on a host name.

        Notes:
            Default implementation uses 'get_plugin_paths' and always returns
            all "load" plugin paths.

        Args:
            host_name (str): To return the plugin paths for this host.
        """

        return self._get_plugin_paths_by_type("load")

    def get_publish_plugin_paths(self, host_name):
        """Retrieve "publish" plugin paths.

        Get the "publish" plugin paths based on a host name.

        Notes:
            Default implementation uses 'get_plugin_paths' and always returns
            all "publish" plugin paths.

        Args:
           host_name (str): To return the plugin paths for this host.
        """

        return self._get_plugin_paths_by_type("publish")

    def get_inventory_action_paths(self, host_name):
        """Retrieve "inventory" action paths.

        Get the "inventory" action plugin paths based on a host name.

        Notes:
            Default implementation uses 'get_plugin_paths' and always returns
            all "inventory" plugin paths.

        Args:
            host_name (str): To return the plugin paths for this host.
        """

        return self._get_plugin_paths_by_type("inventory")

    def get_builder_action_paths(self, host_name):
        """Retrieve "builder" action paths.

        Get the "builder" action plugin paths based on a host name.

        Notes:
            Default implementation uses 'get_plugin_paths' and always returns
            all "builder" plugin paths.

        Args:
           host_name (str): To return the plugin paths for this host.
        """

        return self._get_plugin_paths_by_type("builder")


class ITrayModule(QuadPypeInterface):
    """Module has special procedures when used in QuadPype Tray.

    IMPORTANT:
    The module still must be usable if it is not used in the tray, even if it
    does nothing.
    """

    tray_initialized = False
    _tray_manager = None

    @abstractmethod
    def tray_init(self):
        """Initialization part of tray implementation.

        Triggered between `initialization` and `connect_with_modules`.

        This is where GUIs should be loaded or the tray-specific parts should be
        prepared.
        """

        pass

    @abstractmethod
    def tray_menu(self, tray_menu):
        """Add module's action to the tray menu."""

        pass

    @abstractmethod
    def tray_start(self):
        """Start of the tray."""

        pass

    @abstractmethod
    def tray_exit(self):
        """Cleanup method which is executed on tray shutdown.

        This is the place where all threads should be shut.
        """

        pass

    def execute_in_main_thread(self, callback):
        """ Pushes callback to the queue or process 'callback' on a main thread

            Some callbacks need to be processed on the main thread (menu actions
            must be added on the main thread, or they won't get triggered etc.)
        """

        if not self.tray_initialized:
            # TODO: Called without initialized tray, still main thread needed
            try:
                callback()
            except Exception:  # noqa
                self.log.warning(
                    "Failed to execute {} in main thread".format(callback),
                    exc_info=True)

            return
        self.manager.tray_manager.execute_in_main_thread(callback)

    def show_tray_message(self, title, message, icon=None, msecs=None):
        """Show a tray message.

        Args:
            title (str): Title of the message.
            message (str): Content of the message.
            icon (QSystemTrayIcon.MessageIcon): Message's icon. Default is
                the "Information" icon, may differ by Qt version.
            msecs (int): Duration of message visibility in milliseconds.
                Default is 10000 msecs, may differ by Qt version.
        """

        if self._tray_manager:
            self._tray_manager.show_tray_message(title, message, icon, msecs)

    def add_doubleclick_callback(self, callback):
        if hasattr(self.manager, "add_doubleclick_callback"):
            self.manager.add_doubleclick_callback(self, callback)


class ITrayAction(ITrayModule):
    """Implementation of Tray action.

    Add action to the tray menu which will trigger `on_action_trigger`.
    It is expected to be used for showing tools.

    Methods `tray_start`, `tray_exit` and `connect_with_modules` are overridden
    as it's not expected that action will use them. But it is possible if
    necessary.
    """

    submenu = None
    _submenus = {}
    _action_item = None

    @property
    @abstractmethod
    def label(self):
        """Service label showed in the menu."""
        pass

    @abstractmethod
    def on_action_trigger(self):
        """What happens on actions clicks."""
        pass

    def tray_menu(self, tray_menu):
        from qtpy import QtWidgets

        if self.submenu:
            menu = self.get_submenu(tray_menu, self.submenu)
            action = QtWidgets.QAction(self.label, menu)
            menu.addAction(action)
            if not menu.menuAction().isVisible():
                menu.menuAction().setVisible(True)
        else:
            action = QtWidgets.QAction(self.label, tray_menu)
            tray_menu.addAction(action)

        action.triggered.connect(self.on_action_trigger)
        self._action_item = action

    def tray_start(self):
        return

    def tray_exit(self):
        return

    @staticmethod
    def get_submenu(tray_menu, submenu_name):
        if submenu_name not in ITrayAction._submenus:
            from qtpy import QtWidgets

            submenu = QtWidgets.QMenu(submenu_name, tray_menu)
            submenu.menuAction().setVisible(False)
            tray_menu.addMenu(submenu)
            ITrayAction._submenus[submenu_name] = submenu
        return ITrayAction._submenus[submenu_name]


class ITrayService(ITrayModule):
    # Module's property
    menu_action = None

    # Class properties
    _services_submenu = None
    _icon_failed = None
    _icon_running = None
    _icon_idle = None

    @property
    @abstractmethod
    def label(self):
        """Service label showed in the menu."""
        pass

    @staticmethod
    def services_submenu(tray_menu):
        if ITrayService._services_submenu is None:
            from qtpy import QtWidgets

            services_submenu = QtWidgets.QMenu("Services", tray_menu)
            services_submenu.menuAction().setVisible(False)
            ITrayService._services_submenu = services_submenu
        return ITrayService._services_submenu

    @staticmethod
    def add_service_action(action):
        ITrayService._services_submenu.addAction(action)
        if not ITrayService._services_submenu.menuAction().isVisible():
            ITrayService._services_submenu.menuAction().setVisible(True)

    @staticmethod
    def _load_service_icons():
        from qtpy import QtGui

        ITrayService._icon_failed = QtGui.QIcon(
            resources.get_resource("icons", "circle_red.png")
        )
        ITrayService._icon_running = QtGui.QIcon(
            resources.get_resource("icons", "circle_green.png")
        )
        ITrayService._icon_idle = QtGui.QIcon(
            resources.get_resource("icons", "circle_orange.png")
        )

    @staticmethod
    def get_icon_running():
        if ITrayService._icon_running is None:
            ITrayService._load_service_icons()
        return ITrayService._icon_running

    @staticmethod
    def get_icon_idle():
        if ITrayService._icon_idle is None:
            ITrayService._load_service_icons()
        return ITrayService._icon_idle

    @staticmethod
    def get_icon_failed():
        if ITrayService._icon_failed is None:
            ITrayService._load_service_icons()
        return ITrayService._icon_failed

    def tray_menu(self, tray_menu):
        from qtpy import QtWidgets

        action = QtWidgets.QAction(
            self.label,
            self.services_submenu(tray_menu)
        )
        self.menu_action = action

        self.add_service_action(action)

        self.set_service_running_icon()

    def set_service_running_icon(self):
        """Change icon of an QAction to green circle."""

        if self.menu_action:
            self.menu_action.setIcon(self.get_icon_running())

    def set_service_failed_icon(self):
        """Change icon of an QAction to red circle."""

        if self.menu_action:
            self.menu_action.setIcon(self.get_icon_failed())

    def set_service_idle_icon(self):
        """Change icon of an QAction to orange circle."""

        if self.menu_action:
            self.menu_action.setIcon(self.get_icon_idle())


class ISettingsChangeListener(QuadPypeInterface):
    """Module tries to listen to settings changes.

    Only settings changes in the current process are propagated.
    Changes made in other processes or machines won't trigger the callbacks.

    """

    @abstractmethod
    def on_global_settings_save(
        self, old_value, new_value, changes, new_value_metadata
    ):
        pass

    @abstractmethod
    def on_project_settings_save(
        self, old_value, new_value, changes, project_name, new_value_metadata
    ):
        pass

    @abstractmethod
    def on_project_anatomy_save(
        self, old_value, new_value, changes, project_name, new_value_metadata
    ):
        pass


class IHostAddon(QuadPypeInterface):
    """Addon, which also contain a host implementation."""

    @property
    @abstractmethod
    def host_name(self):
        """Name of host which module represents."""

        pass

    def get_workfile_extensions(self):
        """Define the workfile extensions for host.

        Not all hosts support workfiles, thus this is an optional implementation.

        Returns:
            List[str]: Extensions used for workfiles with dot.
        """

        return []
