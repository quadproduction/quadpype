from qtpy import QtWidgets, QtGui

from quadpype import style

from quadpype.settings import (
    GlobalSettingsEntity,
    ProjectSettingsEntity,

    GENERAL_SETTINGS_KEY,
    ENV_SETTINGS_KEY,
    APPS_SETTINGS_KEY,
    ADDONS_SETTINGS_KEY,
    PROJECTS_SETTINGS_KEY
)
from quadpype.lib import (
    Logger,
    get_user_settings,
    save_user_settings
)
from quadpype.tools.settings import CHILD_OFFSET
from quadpype.tools.utils import MessageOverlayObject
from quadpype.modules import ModulesManager

from .widgets import (
    ExpandingWidget
)
from .mongo_widget import QuadPypeMongoWidget
from .general_widget import LocalGeneralWidgets
from .experimental_widget import (
    LocalExperimentalToolsWidgets,
    LOCAL_EXPERIMENTAL_KEY
)
from .apps_widget import LocalApplicationsWidgets
from .addons_widget import LocalAddonsWidgets
from .environments_widget import LocalEnvironmentsWidgets
from .projects_widget import ProjectSettingsWidget

log = Logger.get_logger(__name__)


class UserSettingsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.global_settings = GlobalSettingsEntity()
        self.project_settings = ProjectSettingsEntity()
        self.modules_manager = ModulesManager()

        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.pype_mongo_widget = None
        self.general_widget = None
        self.experimental_widget = None
        self.envs_widget = None
        self.apps_widget = None
        self.addons_widget = None
        self.projects_widget = None

        self._create_mongo_url_ui()
        self._create_general_ui()
        self._create_experimental_ui()
        self._create_environments_ui()
        self._create_addons_ui()
        self._create_apps_ui()
        self._create_projects_ui()

        self.main_layout.addStretch(1)

    def _create_mongo_url_ui(self):
        pype_mongo_expand_widget = ExpandingWidget("QuadPype Mongo URL", self)
        pype_mongo_content = QtWidgets.QWidget(self)
        pype_mongo_layout = QtWidgets.QVBoxLayout(pype_mongo_content)
        pype_mongo_layout.setContentsMargins(CHILD_OFFSET, 5, 0, 0)
        pype_mongo_expand_widget.set_content_widget(pype_mongo_content)

        pype_mongo_widget = QuadPypeMongoWidget(self)
        pype_mongo_layout.addWidget(pype_mongo_widget)

        self.main_layout.addWidget(pype_mongo_expand_widget)

        self.pype_mongo_widget = pype_mongo_widget

    def _create_general_ui(self):
        # General
        general_expand_widget = ExpandingWidget("General", self)

        general_content = QtWidgets.QWidget(self)
        general_layout = QtWidgets.QVBoxLayout(general_content)
        general_layout.setContentsMargins(CHILD_OFFSET, 5, 0, 0)
        general_expand_widget.set_content_widget(general_content)

        general_widget = LocalGeneralWidgets(general_content)
        general_layout.addWidget(general_widget)

        self.main_layout.addWidget(general_expand_widget)

        self.general_widget = general_widget

    def _create_experimental_ui(self):
        # General
        experimental_expand_widget = ExpandingWidget(
            "Experimental tools", self
        )

        experimental_content = QtWidgets.QWidget(self)
        experimental_layout = QtWidgets.QVBoxLayout(experimental_content)
        experimental_layout.setContentsMargins(CHILD_OFFSET, 5, 0, 0)
        experimental_expand_widget.set_content_widget(experimental_content)

        experimental_widget = LocalExperimentalToolsWidgets(
            experimental_content
        )
        experimental_layout.addWidget(experimental_widget)

        self.main_layout.addWidget(experimental_expand_widget)

        self.experimental_widget = experimental_widget

    def _create_environments_ui(self):
        envs_expand_widget = ExpandingWidget("Environments", self)
        envs_content = QtWidgets.QWidget(self)
        envs_layout = QtWidgets.QVBoxLayout(envs_content)
        envs_layout.setContentsMargins(CHILD_OFFSET, 5, 0, 0)
        envs_expand_widget.set_content_widget(envs_content)

        envs_widget = LocalEnvironmentsWidgets(
            self.global_settings, envs_content
        )
        envs_layout.addWidget(envs_widget)

        self.main_layout.addWidget(envs_expand_widget)

        self.envs_widget = envs_widget

    def _create_addons_ui(self):
        addons_expand_widget = ExpandingWidget("Add-ons", self)

        addons_content = QtWidgets.QWidget(self)
        addons_layout = QtWidgets.QVBoxLayout(addons_content)
        addons_layout.setContentsMargins(CHILD_OFFSET, 5, 0, 0)
        addons_expand_widget.set_content_widget(addons_content)

        addons_widget = LocalAddonsWidgets(
            self.global_settings, addons_content
        )
        addons_layout.addWidget(addons_widget)

        self.main_layout.addWidget(addons_expand_widget)

        self.addons_widget = addons_widget

    def _create_apps_ui(self):
        # Applications
        apps_expand_widget = ExpandingWidget("Applications", self)

        apps_content = QtWidgets.QWidget(self)
        apps_layout = QtWidgets.QVBoxLayout(apps_content)
        apps_layout.setContentsMargins(CHILD_OFFSET, 5, 0, 0)
        apps_expand_widget.set_content_widget(apps_content)

        apps_widget = LocalApplicationsWidgets(
            self.global_settings, apps_content
        )
        apps_layout.addWidget(apps_widget)

        self.main_layout.addWidget(apps_expand_widget)

        self.apps_widget = apps_widget

    def _create_projects_ui(self):
        projects_expand_widget = ExpandingWidget("Projects settings", self)
        projects_content = QtWidgets.QWidget(self)
        projects_layout = QtWidgets.QVBoxLayout(projects_content)
        projects_layout.setContentsMargins(CHILD_OFFSET, 5, 0, 0)
        projects_expand_widget.set_content_widget(projects_content)

        projects_widget = ProjectSettingsWidget(
            self.modules_manager, self.project_settings, self
        )
        projects_layout.addWidget(projects_widget)

        self.main_layout.addWidget(projects_expand_widget)

        self.projects_widget = projects_widget

    def update_user_settings(self, value):
        if not value:
            value = {}

        self.global_settings.reset()
        self.project_settings.reset()

        self.general_widget.update_user_settings(
            value.get(GENERAL_SETTINGS_KEY)
        )
        self.envs_widget.update_user_settings(
            value.get(ENV_SETTINGS_KEY)
        )
        self.addons_widget.update_user_settings(
            value.get(ADDONS_SETTINGS_KEY)
        )
        self.apps_widget.update_user_settings(
            value.get(APPS_SETTINGS_KEY)
        )
        self.projects_widget.update_user_settings(
            value.get(PROJECTS_SETTINGS_KEY)
        )
        self.experimental_widget.update_user_settings(
            value.get(LOCAL_EXPERIMENTAL_KEY)
        )

    def settings_value(self):
        output = {}
        general_value = self.general_widget.settings_value()
        if general_value:
            output[GENERAL_SETTINGS_KEY] = general_value

        envs_value = self.envs_widget.settings_value()
        if envs_value:
            output[ENV_SETTINGS_KEY] = envs_value

        addons_value = self.addons_widget.settings_value()
        if addons_value:
            output[ADDONS_SETTINGS_KEY] = addons_value

        app_value = self.apps_widget.settings_value()
        if app_value:
            output[APPS_SETTINGS_KEY] = app_value

        projects_value = self.projects_widget.settings_value()
        if projects_value:
            output[PROJECTS_SETTINGS_KEY] = projects_value

        experimental_value = self.experimental_widget.settings_value()
        if experimental_value:
            output[LOCAL_EXPERIMENTAL_KEY] = experimental_value
        return output


class UserSettingsWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._reset_on_show = True

        self.resize(1000, 600)

        self.setWindowTitle("QuadPype User Settings")

        overlay_object = MessageOverlayObject(self)

        stylesheet = style.load_stylesheet()
        self.setStyleSheet(stylesheet)
        self.setWindowIcon(QtGui.QIcon(style.app_icon_path()))

        scroll_widget = QtWidgets.QScrollArea(self)
        scroll_widget.setObjectName("GroupWidget")
        scroll_widget.setWidgetResizable(True)

        footer = QtWidgets.QWidget(self)

        save_btn = QtWidgets.QPushButton("Save", footer)
        reset_btn = QtWidgets.QPushButton("Reset", footer)

        footer_layout = QtWidgets.QHBoxLayout(footer)
        footer_layout.addWidget(reset_btn, 0)
        footer_layout.addStretch(1)
        footer_layout.addWidget(save_btn, 0)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_widget, 1)
        main_layout.addWidget(footer, 0)

        save_btn.clicked.connect(self._on_save_clicked)
        reset_btn.clicked.connect(self._on_reset_clicked)

        self._overlay_object = overlay_object
        # Do not create user settings widget in init phase as it's using
        #   settings objects that must be OK to be able to create this widget
        #   - we want to show dialog if anything goes wrong
        #   - without resetting, nothing is shown
        self._settings_widget = None
        self._scroll_widget = scroll_widget
        self.reset_btn = reset_btn
        self.save_btn = save_btn

    def showEvent(self, event):
        super(UserSettingsWindow, self).showEvent(event)
        if self._reset_on_show:
            self.reset()

    def reset(self):
        if self._reset_on_show:
            self._reset_on_show = False

        error_msg = None
        try:
            # Create settings widget if is not created yet
            if self._settings_widget is None:
                self._settings_widget = UserSettingsWidget(
                    self._scroll_widget
                )
                self._scroll_widget.setWidget(self._settings_widget)

            value = get_user_settings()
            self._settings_widget.update_user_settings(value)

        except Exception as exc:
            log.warning(
                "Failed to create user settings window", exc_info=True
            )
            error_msg = str(exc)

        crashed = error_msg is not None
        # Enable/Disable save button if crashed or not
        self.save_btn.setEnabled(not crashed)
        # Show/Hide settings widget if crashed or not
        if self._settings_widget:
            self._settings_widget.setVisible(not crashed)

        if not crashed:
            return

        # Show a popup with the error message
        title = "Something went wrong"
        msg = (
            "Bug: Loading of settings failed."
            " Please contact your project manager or the Quad Dev team."
            "\n\nError message:\n{}"
        ).format(error_msg)

        dialog = QtWidgets.QMessageBox(
            QtWidgets.QMessageBox.Icon.Critical,
            title,
            msg,
            QtWidgets.QMessageBox.StandardButton.Ok,
            self
        )
        dialog.exec_()

    def _on_reset_clicked(self):
        self.reset()
        self._overlay_object.add_message("Refreshed...")

    def _on_save_clicked(self):
        value = self._settings_widget.settings_value()
        save_user_settings(value)
        self._overlay_object.add_message("Saved...", message_type="success")
        self.reset()
