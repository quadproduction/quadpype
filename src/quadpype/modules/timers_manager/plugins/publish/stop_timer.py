"""
Requires:
    context -> global_settings
    context -> quadpypeModules
"""


import pyblish.api

from quadpype.settings import ADDONS_SETTINGS_KEY, GLOBAL_SETTINGS_KEY


class StopTimer(pyblish.api.ContextPlugin):
    label = "Stop Timer"
    order = pyblish.api.ExtractorOrder - 0.49
    hosts = ["*"]

    def process(self, context):
        timers_manager = context.data["quadpypeModules"]["timers_manager"]
        if not timers_manager.enabled:
            self.log.debug("TimersManager is disabled")
            return

        modules_settings = context.data[GLOBAL_SETTINGS_KEY][ADDONS_SETTINGS_KEY]
        if not modules_settings["timers_manager"]["disregard_publishing"]:
            self.log.debug("Publish is not affecting running timers.")
            return

        timers_manager.stop_timer_with_webserver(self.log)
