import os

from quadpype.lib import get_quadpype_execute_args
from quadpype.lib.execute import run_detached_process
from quadpype.modules import (
    click_wrap,
    QuadPypeModule,
    ITrayAction,
    IHostAddon,
)

TRAYPUBLISH_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class TrayPublishAddon(QuadPypeModule, IHostAddon, ITrayAction):
    label = "Publisher"
    name = "tray_publisher"
    host_name = "traypublisher"

    def initialize(self, modules_settings):
        self.enabled = True
        self.publish_paths = [
            os.path.join(TRAYPUBLISH_ROOT_DIR, "plugins", "publish")
        ]

    def tray_init(self):
        return

    def on_action_trigger(self):
        self.run_tray_publisher()

    def connect_with_modules(self, enabled_modules):
        """Collect publish paths from other modules."""
        publish_paths = self.manager.collect_plugin_paths()["publish"]
        self.publish_paths.extend(publish_paths)

    def run_tray_publisher(self):
        args = get_quadpype_execute_args(
            "module", self.name, "launch"
        )
        run_detached_process(args)

    def cli(self, click_group):
        click_group.add_command(cli_main.to_click_obj())


@click_wrap.group(
    TrayPublishAddon.name,
    help="Tray Publisher related commands.")
def cli_main():
    pass


@cli_main.command()
def launch():
    """Launch TrayPublish tool UI."""

    from quadpype.tools import traypublisher

    traypublisher.main()
