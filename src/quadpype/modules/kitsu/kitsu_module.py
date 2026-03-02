"""Kitsu module."""

import os

from quadpype.modules import (
    click_wrap,
    QuadPypeModule,
    IPluginPaths,
    ITrayService,
)


class KitsuModule(QuadPypeModule, IPluginPaths, ITrayService):
    """Kitsu module class."""

    label = "Kitsu"
    name = "kitsu"

    def initialize(self, settings):
        """Initialization of module."""
        module_settings = settings[self.name]

        # Enabled by settings
        self.enabled = module_settings.get("enabled", False)

        # Add API URL schema
        kitsu_url = module_settings["server"].strip()
        if kitsu_url:
            # Ensure web url
            if not kitsu_url.startswith("http"):
                kitsu_url = "https://" + kitsu_url

            # Check for "/api" url validity
            if not kitsu_url.endswith("api"):
                kitsu_url = "{}{}api".format(
                    kitsu_url, "" if kitsu_url.endswith("/") else "/"
                )

        self.server_url = kitsu_url

        # UI which must not be created at this time
        self._dialog = None

    def tray_init(self):
        """Tray init."""

        self._create_dialog()

    def tray_start(self):
        """Tray start."""
        from .utils.credentials import (
            load_credentials,
            validate_credentials,
            set_credentials_envs,
        )

        login, password = load_credentials()

        # Check credentials, ask them if needed
        if validate_credentials(login, password):
            set_credentials_envs(login, password)
        else:
            self.show_dialog()

    def tray_exit(self):
        return

    def get_global_environments(self):
        """Kitsu's global environments."""
        return {"KITSU_SERVER": self.server_url}

    def _create_dialog(self):
        # Don't recreate dialog if already exists
        if self._dialog is not None:
            return

        from .kitsu_widgets import KitsuPasswordDialog

        self._dialog = KitsuPasswordDialog()

    def show_dialog(self):
        """Show dialog to log-in."""

        # Make sure dialog is created
        self._create_dialog()

        # Show dialog
        self._dialog.open()

    def on_action_trigger(self):
        """Implementation of abstract method for `ITrayAction`."""
        self.show_dialog()

    def get_plugin_paths(self):
        """Implementation of abstract method for `IPluginPaths`."""
        current_dir = os.path.dirname(os.path.abspath(__file__))

        return {
            "publish": [os.path.join(current_dir, "plugins", "publish")],
            "actions": [os.path.join(current_dir, "actions")],
        }

    def cli(self, click_group):
        click_group.add_command(cli_main.to_click_obj())


@click_wrap.group(KitsuModule.name, help="Kitsu dynamic cli commands.")
def cli_main():
    pass


@cli_main.command()
@click_wrap.option("--login", envvar="KITSU_LOGIN", help="Kitsu login")
@click_wrap.option(
    "--password", envvar="KITSU_PWD", help="Password for kitsu username"
)
def push_to_zou(login, password):
    """Synchronize Zou database (Kitsu backend) with QuadPype database.

    Args:
        login (str): Kitsu user login
        password (str): Kitsu user password
    """
    from .utils.update_zou_with_op import sync_zou

    sync_zou(login, password)


@cli_main.command()
@click_wrap.option("-l", "--login", envvar="KITSU_LOGIN", help="Kitsu login")
@click_wrap.option(
    "-p", "--password", envvar="KITSU_PWD", help="Password for kitsu username"
)
@click_wrap.option(
    "-exl",
    "--exclude-project",
    "exclude_projects",
    multiple=True,
    default=[],
    help="List of kitsu project names to exclude from the sync",
)
@click_wrap.option(
    "-inc",
    "--include-project",
    "include_projects",
    multiple=True,
    default=[],
    help="List of kitsu project names to include from the sync, by default all projects are synced",
)
@click_wrap.option(
    "-lo",
    "--listen-only",
    "listen_only",
    is_flag=True,
    default=False,
    help="Listen to events only without any syncing",
)
@click_wrap.option(
    "-act",
    "--sync-quick-active-projects",
    "sync_quick_active_projects",
    is_flag=True,
    default=False,
    help="Sync projects with specific active projects collection for quick access",
)
def sync_service(login, password, exclude_projects, include_projects, listen_only, sync_quick_active_projects):
    """Synchronize QuadPype database from Zou sever database.

    Args:
        login (str): Kitsu user login
        password (str): Kitsu user password
        exclude_projects (tuple): List of kitsu project names to exclude from the sync
        include_projects (tuple): List of kitsu project names to include from the sync, by default all projects are synced
        listen_only (bool): run listen only without any syncing
    """
    from .utils.update_op_with_zou import sync_all_projects
    from .utils.sync_service import start_listeners

    exclude_projects = set(exclude_projects)
    include_projects = set(include_projects)

    if not listen_only:
        sync_all_projects(login, password, exclude_projects, include_projects, sync_quick_active_projects)

    start_listeners(login, password, sync_quick_active_projects)
