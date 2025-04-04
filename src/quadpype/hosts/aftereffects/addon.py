from quadpype.modules import QuadPypeModule, IHostAddon


class AfterEffectsAddon(QuadPypeModule, IHostAddon):
    name = "aftereffects"
    host_name = "aftereffects"

    def initialize(self, module_settings):
        self.enabled = True

    def add_implementation_envs(self, env, _app):
        """Modify environments to contain all required for implementation."""
        defaults = {
            "QUADPYPE_LOG_NO_COLORS": "True",
            "QUADPYPE_WEBSOCKET_URL": "ws://localhost:8071/ws/"
        }
        for key, value in defaults.items():
            if not env.get(key):
                env[key] = value

    def get_workfile_extensions(self):
        return [".aep"]
