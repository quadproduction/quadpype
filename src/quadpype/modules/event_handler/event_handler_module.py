# -*- coding: utf-8 -*-
"""Module storing the class and logic of the QuadPype Events Handler."""
from quadpype.modules import QuadPypeModule, ITrayService


class EventHandlerModule(QuadPypeModule, ITrayService):
    """Class handling QuadPype events."""
    name = "event_handler"
    label = "Events Handler"

    def __init__(self, manager, settings):
        super().__init__(manager, settings)

        self._event_handler = None
        self._module_settings = settings

    def initialize(self, _module_settings):
        self.enabled = True

    def tray_init(self):
        from quadpype.events import get_event_handler

        self._event_handler = get_event_handler()

    def tray_exit(self):
        if self._event_handler:
            self._event_handler.stop()

    def tray_start(self):
        if not self._event_handler or self._event_handler.is_running():
            return
        self._event_handler.start()

    def webserver_initialization(self, server_manager):
        """Add routes for syncs."""
        if self.tray_initialized:
            self._event_handler.set_webserver(server_manager)
