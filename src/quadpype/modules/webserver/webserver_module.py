"""WebServerModule spawns aiohttp server in asyncio loop.

Main usage of the module is in QuadPype tray where make sense to add ability
of other modules to add theirs routes. Module which would want to use that
option must have implemented method `webserver_initialization` which must
expect `WebServerManager` object where is possible to add routes or paths
with handlers.

WebServerManager is by default created only in tray.

It is possible to create server manager without using module logic at all
using `create_new_server_manager`. That can be handy for standalone scripts
with predefined host and port and separated routes and logic.

Running multiple servers in one process is not recommended and probably won't
work as expected. It is because of few limitations connected to asyncio module.

When module's `_create_server_manager` is called it is also set environment
variable "QUADPYPE_WEBSERVER_URL". Which should lead to root access point
of server.
"""

import os
import socket

from quadpype import resources
from quadpype.lib import get_app_registry
from quadpype.modules import QuadPypeModule, ITrayService, AddOnPriority


class WebServerModule(QuadPypeModule, ITrayService):
    name = "webserver"
    label = "Web Server"
    priority = AddOnPriority.CRITICAL

    webserver_url_env = "QUADPYPE_WEBSERVER_URL"

    def __init__(self, manager, settings):
        super().__init__(manager, settings)

        self.server_manager = None
        self._host_listener = None

        self.port = 0
        self.default_host = "127.0.0.1"
        self.webserver_url = None

    def initialize(self, _module_settings):
        self.enabled = True

    def connect_with_modules(self, enabled_modules):
        if not self.server_manager:
            return

        for module in enabled_modules:
            if not hasattr(module, "webserver_initialization"):
                continue

            try:
                module.webserver_initialization(self.server_manager)
            except Exception:  # noqa
                self.log.warning(
                    (
                        "Failed to connect module \"{}\" to webserver."
                    ).format(module.name),
                    exc_info=True
                )

    def tray_init(self):
        self.port = self.find_free_port()

        self._create_server_manager()
        self._add_resources_statics()
        self._add_listeners()

    def tray_start(self):
        self.start_server()

    def tray_exit(self):
        self.stop_server()

    def _add_resources_statics(self):
        static_prefix = "/res"
        self.server_manager.add_static(static_prefix, resources.RESOURCES_DIR)

        os.environ["QUADPYPE_STATICS_SERVER"] = "{}{}".format(
            self.webserver_url, static_prefix
        )

    def _add_listeners(self):
        from quadpype_modules.webserver import host_console_listener

        self._host_listener = host_console_listener.HostListener(
            self.server_manager, self
        )

    def start_server(self):
        if self.server_manager:
            self.server_manager.start_server()

    def stop_server(self):
        if self.server_manager:
            self.server_manager.stop_server()

    @staticmethod
    def create_new_server_manager(host=None, port=None):
        """Create webserver manager for passed port and host.

        Args:
            host(str): Host name or IP address. Default is the 'localhost' ip: '127.0.0.1'.
            port(int): Port on which wil webserver listen.

        Returns:
            WebServerManager: Prepared manager.
        """
        from .server import WebServerManager

        return WebServerManager(host, port)

    def _create_server_manager(self):
        if self.server_manager:
            return

        self.server_manager = self.create_new_server_manager(self.default_host, self.port)
        self.server_manager.on_stop_callbacks.append(
            self.set_service_failed_icon
        )

        webserver_url = self.server_manager.url
        self.webserver_url = webserver_url

        # Save the webserver url into the current environment variables
        # and in the registry file on disk
        os.environ[self.webserver_url_env] = str(webserver_url)
        app_registry = get_app_registry()
        app_registry.set_item("webserver_url", webserver_url)


    @staticmethod
    def find_free_port(
        port_from=None, port_to=None, exclude_ports=None, host=None
    ):
        """Find available socket port from entered range.

        It is also possible to only check if entered port is available.

        Args:
            port_from (int): Port number which is checked as first.
            port_to (int): Last port that is checked in sequence from entered
                `port_from`. Only `port_from` is checked if is not entered.
                Nothing is processed if is equeal to `port_from`!
            exclude_ports (list, tuple, set): List of ports that won't be
                checked form entered range.
            host (str): Host where will check for free ports. Set to
                "localhost" by default.
        """
        if port_from is None:
            port_from = 8079

        if port_to is None:
            port_to = 65535

        # Excluded ports (e.g. reserved for other servers/clients)
        if exclude_ports is None:
            exclude_ports = []

        # Default host is localhost but it is possible to look for other hosts
        if host is None:
            host = "localhost"

        found_port = None
        for port in range(port_from, port_to + 1):
            if port in exclude_ports:
                continue

            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind((host, port))
                found_port = port

            except socket.error:
                continue

            finally:
                if sock:
                    sock.close()

            if found_port is not None:
                break

        return found_port
