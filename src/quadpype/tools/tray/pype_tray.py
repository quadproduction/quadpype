import collections
import os
import sys
import atexit

import platform
from typing import Optional

from qtpy import QtCore, QtGui, QtWidgets

import quadpype.version
from quadpype import resources, style
from quadpype.lib import (
    Logger,
    get_quadpype_execute_args,
    run_detached_process,
)
from quadpype.lib.user import get_quadpype_username
from quadpype.lib.quadpype_version import (
    op_version_control_available,
    get_expected_version,
    get_installed_version,
    is_current_version_studio_latest,
    is_current_version_higher_than_expected,
    get_quadpype_version,
    is_running_staging,
    is_staging_enabled
)
from quadpype.modules import TrayModulesManager
from quadpype.settings import (
    get_global_settings,
    GlobalSettingsEntity,
    ProjectSettingsEntity,
    DefaultsNotDefined,
    CORE_SETTINGS_KEY,
    MODULES_SETTINGS_KEY
)
from quadpype.tools.utils import (
    WrappedCallbackItem,
    paint_image_with_color,
    get_warning_pixmap,
    get_quadpype_qt_app,
    PixmapLabel
)

from .pype_info_widget import PypeInfoWidget

TRAY_ICON_WIDGET = None

g_tray_starter = None
g_splash_screen = None


class VersionUpdateDialog(QtWidgets.QDialog):
    restart_requested = QtCore.Signal()
    ignore_requested = QtCore.Signal()

    _min_width = 400
    _min_height = 130

    def __init__(self, parent=None):
        super().__init__(parent)

        icon = QtGui.QIcon(resources.get_app_icon_filepath())
        self.setWindowIcon(icon)
        self.setWindowFlags(
            self.windowFlags()
            | QtCore.Qt.WindowStaysOnTopHint
        )

        self.setMinimumWidth(self._min_width)
        self.setMinimumHeight(self._min_height)

        top_widget = QtWidgets.QWidget(self)

        gift_pixmap = self._get_gift_pixmap()
        gift_icon_label = PixmapLabel(gift_pixmap, top_widget)

        label_widget = QtWidgets.QLabel(top_widget)
        label_widget.setWordWrap(True)

        top_layout = QtWidgets.QHBoxLayout(top_widget)
        top_layout.setSpacing(10)
        top_layout.addWidget(gift_icon_label, 0, QtCore.Qt.AlignCenter)
        top_layout.addWidget(label_widget, 1)

        ignore_btn = QtWidgets.QPushButton(self)
        restart_btn = QtWidgets.QPushButton(self)
        restart_btn.setObjectName("TrayRestartButton")

        btns_layout = QtWidgets.QHBoxLayout()
        btns_layout.addStretch(1)
        btns_layout.addWidget(ignore_btn, 0)
        btns_layout.addWidget(restart_btn, 0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(top_widget, 0)
        layout.addStretch(1)
        layout.addLayout(btns_layout, 0)

        ignore_btn.clicked.connect(self._on_ignore)
        restart_btn.clicked.connect(self._on_reset)

        self._label_widget = label_widget
        self._gift_icon_label = gift_icon_label
        self._ignore_btn = ignore_btn
        self._restart_btn = restart_btn

        self._restart_accepted = False
        self._current_is_higher = False

        self.setStyleSheet(style.load_stylesheet())

    def _get_gift_pixmap(self):
        image_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "images",
            "gifts.png"
        )
        src_image = QtGui.QImage(image_path)
        color_value = style.get_objected_colors("font")

        return paint_image_with_color(
            src_image,
            color_value.get_qcolor()
        )

    def showEvent(self, event):
        super(VersionUpdateDialog, self).showEvent(event)
        self._restart_accepted = False

    def closeEvent(self, event):
        super(VersionUpdateDialog, self).closeEvent(event)
        if self._restart_accepted or self._current_is_higher:
            return
        # Trigger ignore requested only if restart was not clicked and current
        #   version is lower
        self.ignore_requested.emit()

    def update_versions(
        self, current_version, expected_version, current_is_higher
    ):
        if not current_is_higher:
            title = "QuadPype update is needed"
            label_message = (
                "Running QuadPype version is <b>{}</b>."
                " Your production has been updated to version <b>{}</b>."
            ).format(str(current_version), str(expected_version))
            ignore_label = "Later"
            restart_label = "Restart && Update"
        else:
            title = "QuadPype version is higher"
            label_message = (
                "Running QuadPype version is <b>{}</b>."
                " Your production uses version <b>{}</b>."
            ).format(str(current_version), str(expected_version))
            ignore_label = "Ignore"
            restart_label = "Restart && Change"

        self.setWindowTitle(title)

        self._current_is_higher = current_is_higher

        self._gift_icon_label.setVisible(not current_is_higher)

        self._label_widget.setText(label_message)
        self._ignore_btn.setText(ignore_label)
        self._restart_btn.setText(restart_label)

    def _on_ignore(self):
        self.reject()

    def _on_reset(self):
        self._restart_accepted = True
        self.restart_requested.emit()
        self.accept()


class ProductionStagingDialog(QtWidgets.QDialog):
    """Tell user that he has enabled staging but is in production version.

    This is showed only when staging is enabled with '--use-staging' and it's
    version is the same as production's version.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        icon = QtGui.QIcon(resources.get_app_icon_filepath())
        self.setWindowIcon(icon)
        self.setWindowTitle("Production and Staging versions are the same")
        self.setWindowFlags(
            self.windowFlags()
            | QtCore.Qt.WindowStaysOnTopHint
        )

        top_widget = QtWidgets.QWidget(self)

        staging_pixmap = QtGui.QPixmap(fileName=resources.get_app_icon_filepath(variation_name="staging"))
        staging_icon_label = PixmapLabel(staging_pixmap, top_widget)
        message = (
            "Because production and staging versions are the same"
            " your changes and work will affect both."
        )
        content_label = QtWidgets.QLabel(message, self)
        content_label.setWordWrap(True)

        top_layout = QtWidgets.QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)
        top_layout.addWidget(
            staging_icon_label, 0,
            QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter
        )
        top_layout.addWidget(content_label, 1)

        footer_widget = QtWidgets.QWidget(self)
        ok_btn = QtWidgets.QPushButton("I understand", footer_widget)

        footer_layout = QtWidgets.QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addStretch(1)
        footer_layout.addWidget(ok_btn)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(top_widget, 0)
        main_layout.addStretch(1)
        main_layout.addWidget(footer_widget, 0)

        self.setStyleSheet(style.load_stylesheet())
        self.resize(400, 140)

        ok_btn.clicked.connect(self._on_ok_clicked)

    def _on_ok_clicked(self):
        self.close()


class BuildVersionDialog(QtWidgets.QDialog):
    """Build/Installation version is too low for current QuadPype version.

    This dialog tells to user that it's build QuadPype is too old.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        icon = QtGui.QIcon(resources.get_app_icon_filepath())
        self.setWindowIcon(icon)
        self.setWindowTitle("Outdated QuadPype installation")
        self.setWindowFlags(
            self.windowFlags()
            | QtCore.Qt.WindowStaysOnTopHint
        )

        top_widget = QtWidgets.QWidget(self)

        warning_pixmap = get_warning_pixmap()
        warning_icon_label = PixmapLabel(warning_pixmap, top_widget)

        message = (
            "Your installation of QuadPype <b>does not match minimum"
            " requirements</b>.<br/><br/>Please update QuadPype installation"
            " to newer version."
        )
        content_label = QtWidgets.QLabel(message, self)

        top_layout = QtWidgets.QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(
            warning_icon_label, 0,
            QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter
        )
        top_layout.addWidget(content_label, 1)

        footer_widget = QtWidgets.QWidget(self)
        ok_btn = QtWidgets.QPushButton("I understand", footer_widget)

        footer_layout = QtWidgets.QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addStretch(1)
        footer_layout.addWidget(ok_btn)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(top_widget, 0)
        main_layout.addStretch(1)
        main_layout.addWidget(footer_widget, 0)

        self.setStyleSheet(style.load_stylesheet())

        ok_btn.clicked.connect(self._on_ok_clicked)

    def _on_ok_clicked(self):
        self.close()


class TrayManager:
    """Cares about context of application.

    Load submenus, actions, separators and modules into tray's context.
    """
    def __init__(self, tray_widget, main_window):
        self.tray_widget = tray_widget
        self.main_window = main_window
        self.pype_info_widget = None
        self._restart_action = None
        self._is_init_completed = False

        self.log = Logger.get_logger(self.__class__.__name__)

        global_settings = get_global_settings()
        self.module_settings = global_settings[MODULES_SETTINGS_KEY]

        self.modules_manager = TrayModulesManager()

        self.errors = []

        self._version_dialog = None

        self.main_thread_timer = None
        self._main_thread_callbacks = collections.deque()
        self._execution_in_progress = None

    @property
    def is_init_completed(self):
        return self._is_init_completed

    @property
    def doubleclick_callback(self):
        """Double-click callback for Tray icon."""
        callback_name = self.modules_manager.doubleclick_callback
        return self.modules_manager.doubleclick_callbacks.get(callback_name)

    def execute_doubleclick(self):
        """Execute double click callback in main thread."""
        callback = self.doubleclick_callback
        if callback:
            self.execute_in_main_thread(callback)

    def validate_quadpype_version(self):
        is_running_latest_version = is_current_version_studio_latest()
        # TODO Handle situations when version can't be detected
        if is_running_latest_version is None:
            is_running_latest_version = True

        self._restart_action.setVisible(not is_running_latest_version)
        if is_running_latest_version:
            if (
                self._version_dialog is not None
                and self._version_dialog.isVisible()
            ):
                self._version_dialog.close()
            return

        installed_version = get_installed_version()
        expected_version = get_expected_version()

        # Request new build if is needed
        if (
            # Backwards compatibility
            not hasattr(expected_version, "is_compatible")
            or not expected_version.is_compatible(installed_version)
        ):
            if (
                self._version_dialog is not None
                and self._version_dialog.isVisible()
            ):
                self._version_dialog.close()

            dialog = BuildVersionDialog()
            dialog.exec_()
            return

        if self._version_dialog is None:
            self._version_dialog = VersionUpdateDialog()
            self._version_dialog.restart_requested.connect(
                self._restart_and_install
            )
            self._version_dialog.ignore_requested.connect(
                self._outdated_version_ignored
            )

        current_version = get_quadpype_version()
        current_is_higher = is_current_version_higher_than_expected()

        self._version_dialog.update_versions(
            current_version, expected_version, current_is_higher
        )
        self._version_dialog.show()
        self._version_dialog.raise_()
        self._version_dialog.activateWindow()

    def _restart_and_install(self):
        self.restart(use_expected_version=True)

    def _outdated_version_ignored(self):
        self.show_tray_message(
            "QuadPype version is outdated",
            (
                "Please update your QuadPype as soon as possible."
                " To update, restart QuadPype Tray application."
            )
        )

    def execute_in_main_thread(self, callback, *args, **kwargs):
        if isinstance(callback, WrappedCallbackItem):
            item = callback
        else:
            item = WrappedCallbackItem(callback, *args, **kwargs)

        self._main_thread_callbacks.append(item)

        return item

    def _main_thread_execution(self):
        if self._execution_in_progress:
            return
        self._execution_in_progress = True
        for _ in range(len(self._main_thread_callbacks)):
            if self._main_thread_callbacks:
                item = self._main_thread_callbacks.popleft()
                item.execute()

        self._execution_in_progress = False

    def initialize_modules(self):
        """Add modules to the tray menu."""
        from quadpype.modules import ITrayService

        # Menu header
        global_settings = get_global_settings()
        studio_name = global_settings[CORE_SETTINGS_KEY]["studio_name"]

        header_label = QtWidgets.QLabel("QuadPype : {}".format(studio_name))
        header_label.setStyleSheet(
            "background: qlineargradient(x1: 0, y1: 0, x2: 0.7, y2: 1, stop: 0 #3bebb9, stop: 1.0 #52abd7);"
            "font-weight: bold; color: #003740; margin: 0; padding: 8px 6px;")

        header_widget = QtWidgets.QWidgetAction(self.tray_widget.menu)
        header_widget.setDefaultWidget(header_label)

        self.tray_widget.menu.addAction(header_widget)

        # Username info as a non-clickable item in the menu
        # Note: Double space before the username for readability
        username_label = QtWidgets.QLabel("User :  {}".format(str(get_quadpype_username())))
        username_label.setStyleSheet("margin: 0; padding: 8px 6px;")

        username_widget = QtWidgets.QWidgetAction(self.tray_widget.menu)
        username_widget.setDefaultWidget(username_label)

        self.tray_widget.menu.addAction(username_widget)

        # Add version item (and potentially "Update & Restart" item)
        self._add_version_item()

        self.tray_widget.menu.addSeparator()

        # Add enabled modules
        self.modules_manager.initialize(self, self.tray_widget.menu)

        # Add services if they are
        services_submenu = ITrayService.services_submenu(self.tray_widget.menu)
        self.tray_widget.menu.addMenu(services_submenu)

        # Add separator
        self.tray_widget.menu.addSeparator()

        # Add Exit action to the menu
        exit_action = QtWidgets.QAction("Exit", self.tray_widget)
        exit_action.triggered.connect(self.tray_widget.exit)
        self.tray_widget.menu.addAction(exit_action)

        # Tell each module which modules were imported
        self.modules_manager.start_modules()

        # Print time report
        self.modules_manager.print_report()

        # create timer loop to check callback functions
        main_thread_timer = QtCore.QTimer()
        main_thread_timer.setInterval(300)
        main_thread_timer.timeout.connect(self._main_thread_execution)
        main_thread_timer.start()

        self.main_thread_timer = main_thread_timer

        # For storing missing settings dialog
        self._settings_validation_dialog = None

        self._is_init_completed = True

        self.execute_in_main_thread(self._validations)

    def _validations(self):
        """Run possible startup validations."""
        # TODO: Need a better way of validating settings
        # SLOW: This operation is very slow, so it's currently disabled
        # self._validate_settings_defaults()

        if not op_version_control_available():
            dialog = BuildVersionDialog()
            dialog.exec_()
        elif is_staging_enabled() and not is_running_staging():
            dialog = ProductionStagingDialog()
            dialog.exec_()

    def _validate_settings_defaults(self):
        valid = True
        try:
            GlobalSettingsEntity()
            ProjectSettingsEntity()

        except DefaultsNotDefined as exception_obj:
            self.log.error(str(exception_obj))
            valid = False

        if valid:
            return

        title = "QuadPype Settings: Some default values are missing"
        msg = (
            "Your QuadPype instance will not work as expected! \n"
            "Some default values in the settings are missing.\n\n"
            "Contact your pipeline supervisor or the QuadPype Dev Team."
        )
        msg_box = QtWidgets.QMessageBox(
            QtWidgets.QMessageBox.Warning,
            title,
            msg,
            QtWidgets.QMessageBox.Ok,
            flags=QtCore.Qt.Dialog
        )
        icon = QtGui.QIcon(resources.get_app_icon_filepath())
        msg_box.setWindowIcon(icon)
        msg_box.setStyleSheet(style.load_stylesheet())
        msg_box.buttonClicked.connect(self._post_validate_settings_defaults)

        self._settings_validation_dialog = msg_box

        msg_box.show()

    def _post_validate_settings_defaults(self):
        widget = self._settings_validation_dialog
        self._settings_validation_dialog = None
        widget.deleteLater()

    def show_tray_message(self, title, message, icon=None, msecs=None):
        """Show tray message.

        Args:
            title (str): Title of message.
            message (str): Content of message.
            icon (QSystemTrayIcon.MessageIcon): Message's icon. Default is
                Information icon, may differ by Qt version.
            msecs (int): Duration of message visibility in milliseconds.
                Default is 10000 msecs, may differ by Qt version.
        """
        args = [title, message]
        kwargs = {}
        if icon:
            kwargs["icon"] = icon
        if msecs:
            kwargs["msecs"] = msecs

        self.tray_widget.showMessage(*args, **kwargs)

    def _add_version_item(self):
        subversion = os.getenv("QUADPYPE_SUBVERSION")
        client_name = os.getenv("QUADPYPE_CLIENT")

        version_string = "Version :  {}".format(quadpype.version.__version__)  # double space for readability
        if subversion:
            version_string += " ({})".format(subversion)

        if client_name:
            version_string += ", {}".format(client_name)

        version_action = QtWidgets.QAction(version_string, self.tray_widget)
        version_action.triggered.connect(self._on_version_action)

        restart_action = QtWidgets.QAction(
            "Restart && Update", self.tray_widget
        )
        restart_action.triggered.connect(self._on_restart_action)
        restart_action.setVisible(False)

        self.tray_widget.menu.addAction(version_action)
        self.tray_widget.menu.addAction(restart_action)

        self._restart_action = restart_action

    def _on_restart_action(self):
        self.restart(use_expected_version=True)

    def restart(self, use_expected_version=False, reset_version=False):
        """Restart Tray tool.

        First creates new process with same argument and close current tray.

        Args:
            use_expected_version(bool): QuadPype version is set to expected
                version.
            reset_version(bool): QuadPype version is cleaned up so the igniter
                logic will decide which version will be used.
        """
        args = get_quadpype_execute_args()
        envs = dict(os.environ.items())

        # Create a copy of sys.argv
        additional_args = list(sys.argv)
        # Remove first argument from 'sys.argv'
        # - when running from code the first argument is 'start.py'
        # - when running from build the first argument is executable
        additional_args.pop(0)

        cleanup_additional_args = False
        if use_expected_version:
            cleanup_additional_args = True
            expected_version = get_expected_version()
            if expected_version is not None:
                reset_version = False
                envs["QUADPYPE_VERSION"] = str(expected_version)
            else:
                # Trigger reset of version if expected version was not found
                reset_version = True

        # Pop QUADPYPE_VERSION
        if reset_version:
            cleanup_additional_args = True
            envs.pop("QUADPYPE_VERSION", None)

        if cleanup_additional_args:
            _additional_args = []
            for arg in additional_args:
                if arg == "--use-staging" or arg.startswith("--use-version"):
                    continue
                _additional_args.append(arg)
            additional_args = _additional_args

        args.extend(additional_args)
        run_detached_process(args, env=envs)
        self.exit()

    def exit(self):
        self.tray_widget.exit()

    def on_exit(self):
        self.modules_manager.on_exit()

    def _on_version_action(self):
        if self.pype_info_widget is None:
            self.pype_info_widget = PypeInfoWidget()

        self.pype_info_widget.show()
        self.pype_info_widget.raise_()
        self.pype_info_widget.activateWindow()


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    """Tray widget.

    :param parent: Main widget that cares about all GUIs
    :type parent: QtWidgets.QMainWindow
    """

    doubleclick_time_ms = 400

    def __init__(self, parent):
        icon = QtGui.QIcon(resources.get_app_icon_filepath())

        super().__init__(icon, parent)

        self._exited = False

        # Store parent (the app QMainWindow)
        self.parent = parent

        # Setup menu in Tray
        self.menu = QtWidgets.QMenu()
        self.menu.setStyleSheet(style.load_stylesheet())

        # Set modules
        self.tray_man = TrayManager(self, self.parent)

        # Add menu to Context of SystemTrayIcon
        self.setContextMenu(self.menu)

        atexit.register(self.exit)

        # Add ability for left-click on the tray icon
        if platform.system().lower() == "darwin":
            # Since macOS has this ability by design we can skip
            return

        self.activated.connect(self.on_systray_activated)

        click_timer = QtCore.QTimer()
        click_timer.setInterval(self.doubleclick_time_ms)
        click_timer.timeout.connect(self._click_timer_timeout)

        self._click_timer = click_timer
        self._doubleclick = False
        self._click_pos = None

    @property
    def is_init_completed(self):
        return self.tray_man.is_init_completed

    def initialize_modules(self):
        self.tray_man.initialize_modules()

    def _click_timer_timeout(self):
        self._click_timer.stop()
        doubleclick = self._doubleclick
        # Reset bool value
        self._doubleclick = False
        if doubleclick:
            self.tray_man.execute_doubleclick()
        else:
            self._show_context_menu()

    def _show_context_menu(self):
        pos = self._click_pos
        self._click_pos = None
        if pos is None:
            pos = QtGui.QCursor().pos()
        self.contextMenu().popup(pos)

    def on_systray_activated(self, reason):
        # show contextMenu if left click
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            if self.tray_man.doubleclick_callback:
                self._click_pos = QtGui.QCursor().pos()
                self._click_timer.start()
            else:
                self._show_context_menu()

        elif reason == QtWidgets.QSystemTrayIcon.DoubleClick:
            self._doubleclick = True

    def exit(self):
        """ Exit whole application.

        - Icon won't stay in tray after exit.
        """
        if self._exited:
            return
        self._exited = True

        self.hide()
        self.tray_man.on_exit()
        QtCore.QCoreApplication.exit()


class QuadPypeTrayStarter(QtCore.QObject):
    def __init__(self, app):
        super().__init__()

        app.setQuitOnLastWindowClosed(False)
        self._app = app
        self._splash = None
        self._splash_animation = None

        main_window = QtWidgets.QMainWindow()
        global TRAY_ICON_WIDGET
        TRAY_ICON_WIDGET = SystemTrayIcon(main_window)

        launch_ops_timed_loop = QtCore.QTimer()
        launch_ops_timed_loop.setInterval(100)
        launch_ops_timed_loop.start()

        launch_ops_timed_loop.timeout.connect(self._execute_launch_operations)

        self._main_window = main_window
        self._tray_widget = TRAY_ICON_WIDGET
        self._launch_phase = 0
        self._launch_ops_timed_loop = launch_ops_timed_loop

    def _execute_launch_operations(self):
        if self._launch_phase == 0:
            self._launch_phase += 1

            self._tray_widget.show()

            # Create the splash screen
            self._splash = self._create_splash()
            self._splash.show()

            # Create the opacity effect
            opacity_effect = QtWidgets.QGraphicsOpacityEffect(self._splash)
            opacity_effect.setOpacity(0.0)
            self._splash.setGraphicsEffect(opacity_effect)

            # Create the fade in animation
            self._splash_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
            self._splash_animation.setDuration(500)  # Duration in milliseconds
            self._splash_animation.setStartValue(0.0)
            self._splash_animation.setEndValue(1.0)
            self._splash_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)

            # Start animation
            self._splash_animation.start(QtCore.QPropertyAnimation.DeleteWhenStopped)

            # Wait until the fade in animation is done
            while self._splash_animation.state() != QtCore.QAbstractAnimation.Stopped:
                QtWidgets.QApplication.processEvents()

            # Make sure tray and splash are painted out
            QtWidgets.QApplication.processEvents()
        elif self._launch_phase == 1:
            self._launch_phase += 1

            # Second processing of events to make sure splash is painted
            QtWidgets.QApplication.processEvents()

            # Start the initialization of all the enabled modules
            self._tray_widget.initialize_modules()
        elif self._tray_widget.is_init_completed:
            # QuadPype is fully initialized, fade out the splash screen
            opacity_effect = QtWidgets.QGraphicsOpacityEffect(self._splash)
            self._splash.setGraphicsEffect(opacity_effect)

            # Create the fade out animation
            self._splash_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
            self._splash_animation.setDuration(500)  # Duration in milliseconds
            self._splash_animation.setStartValue(1.0)
            self._splash_animation.setEndValue(0.0)
            self._splash_animation.setEasingCurve(QtCore.QEasingCurve.OutQuad)

            # Hide it at the end of the animation
            self._splash_animation.finished.connect(self._splash.hide)

            # Start animation
            self._splash_animation.start(QtCore.QPropertyAnimation.DeleteWhenStopped)

            # Wait until the fade out animation is done
            while self._splash_animation.state() != QtCore.QAbstractAnimation.Stopped:
                QtWidgets.QApplication.processEvents()

            # Launch is completed, stop the timed loop
            self._launch_ops_timed_loop.stop()

    @staticmethod
    def _create_splash():
        splash_pix = QtGui.QPixmap(resources.get_app_splash_filepath())
        splash = QtWidgets.QSplashScreen(splash_pix)
        splash.setEnabled(False)
        splash.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint
        )

        return splash

def main():
    app = get_quadpype_qt_app()

    global g_tray_starter
    # Storing the tray starter in a global variable
    # to ensure the timed loop will continue running properly
    g_tray_starter = QuadPypeTrayStarter(app)

    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            u"pype_tray"
        )

    sys.exit(app.exec_())


def get_tray_icon_widget() -> Optional[SystemTrayIcon]:
    return TRAY_ICON_WIDGET
