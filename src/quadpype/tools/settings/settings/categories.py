import sys
import traceback
import contextlib
from abc import abstractmethod
from enum import Enum
from datetime import datetime

from qtpy import QtWidgets, QtCore
import qtawesome

from quadpype.lib import (
    get_quadpype_version,
    get_all_user_profiles
)
from quadpype.tools.utils import set_style_property
from quadpype.settings.entities import (
    GlobalSettingsEntity,
    ProjectSettingsEntity,

    GUIEntity,
    DictImmutableKeysEntity,
    DictMutableKeysEntity,
    DictConditionalEntity,
    ListEntity,
    PathEntity,
    ListStrictEntity,

    NumberEntity,
    BoolEntity,
    BaseEnumEntity,
    TextEntity,
    PasswordEntity,
    PathInput,
    RawJsonEntity,
    ColorEntity
)
from quadpype.settings.entities.exceptions import (
    DefaultsNotDefined,
    StudioDefaultsNotDefined,
    SchemaError
)
from quadpype.settings.entities.version_entity import (
    PackageVersionEntity
)

from quadpype.settings import (
    SaveWarningExc,
    PROJECT_ANATOMY_KEY,
    PROJECT_SETTINGS_KEY,
    GLOBAL_SETTINGS_KEY
)
from quadpype.settings.lib import (
    get_global_settings_last_saved_info,
    get_project_settings_last_saved_info
)
from .dialogs import SettingsLastSavedChanged, SettingsControlTaken
from .widgets import (
    ProjectListWidget,
    VersionAction
)
from .breadcrumbs_widget import (
    BreadcrumbsAddressBar,
    GlobalSettingsBreadcrumbs,
    ProjectSettingsBreadcrumbs
)
from .constants import (
    SETTINGS_PATH_KEY,
    ROOT_KEY,
    VALUE_KEY,
)
from .base import (
    ExtractHelper,
    GUIWidget,
)
from .list_item_widget import ListWidget
from .list_strict_widget import ListStrictWidget
from .dict_mutable_widget import DictMutableKeysWidget
from .dict_conditional import DictConditionalWidget
from .item_widgets import (
    BoolWidget,
    DictImmutableKeysWidget,
    TextWidget,
    PasswordWidget,
    PackageVersionWidget,
    NumberWidget,
    RawJsonWidget,
    EnumeratorWidget,
    PathWidget,
    PathInputWidget,
    GridLabelWidget
)
from .color_widget import ColorWidget


class EditMode(Enum):
    ENABLE = 1
    DISABLE = 2
    PROTECT = 3


class PageState(Enum):
    Idle = object()
    Working = object()


class IgnoreInputChangesObj:
    def __init__(self, top_widget):
        self._ignore_changes = False
        self.top_widget = top_widget

    def __bool__(self):
        return self._ignore_changes

    def set_ignore(self, ignore_changes=True):
        if self._ignore_changes == ignore_changes:
            return
        self._ignore_changes = ignore_changes
        if not ignore_changes:
            self.top_widget.hierarchical_style_update()


class StandaloneCategoryWidget(QtWidgets.QWidget):

    def __init__(self, content_widget, content_layout, parent=None):
        super().__init__(parent)

        self.content_widget = content_widget
        self.content_layout = content_layout
        self._state = PageState.Idle
        self.ignore_input_changes = IgnoreInputChangesObj(self)

    @staticmethod
    def create_ui_for_entity(category_widget, entity, entity_widget):
        return SettingsControlPanelWidget.create_ui_for_entity(category_widget, entity, entity_widget)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self.set_state(value)

    def set_state(self, state):
        if self._state == state:
            return

        self._state = state

    @property
    def is_modifying_defaults(self):
        return False

    def scroll_to(self, widget):
        pass

    def go_to_fullpath(self, full_path):
        """Full path of settings entity which can lead to different category.

        Args:
            full_path (str): Full path to settings entity. It is expected that
                path starts with category name ("global_settings" etc.).
        """
        pass

    def set_path(self, path):
        """Called from clicked widget."""
        pass

    def hierarchical_style_update(self):
        pass

    def add_widget_to_layout(self, widget, label=None):
        row = self.content_layout.rowCount()
        if not label:
            self.content_layout.addWidget(widget, row, 0, 1, 2)
        else:
            label_widget = GridLabelWidget(label, widget)
            label_widget.input_field = widget
            widget.label_widget = label_widget
            self.content_layout.addWidget(label_widget, row, 0, 1, 1)
            self.content_layout.addWidget(widget, row, 1, 1, 1)

    @contextlib.contextmanager
    def working_state_context(self):
        self.set_state(PageState.Working)
        yield
        self.set_state(PageState.Idle)


class BlankControlPanelWidget(QtWidgets.QWidget):
    state_changed = QtCore.Signal()
    saved = QtCore.Signal(QtWidgets.QWidget)
    restart_required_trigger = QtCore.Signal()
    reset_started = QtCore.Signal()
    reset_finished = QtCore.Signal()
    full_path_requested = QtCore.Signal(str, str)

    def __init__(self, controller, parent=None):
        super().__init__(parent)

        self._controller = controller
        self._state = PageState.Idle

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self.set_state(value)

    def set_state(self, state):
        if self._state == state:
            return

        self._state = state
        self.state_changed.emit()

        # Process events so emitted signal is processed
        app = QtWidgets.QApplication.instance()
        if app:
            app.processEvents()

    @abstractmethod
    def _on_reset_start(self):
        raise NotImplementedError("Abstract method not implemented")

    @abstractmethod
    def _on_reset_success(self):
        raise NotImplementedError("Abstract method not implemented")

    @abstractmethod
    def _on_reset_crash(self):
        raise NotImplementedError("Abstract method not implemented")

    @abstractmethod
    def reset(self):
        raise NotImplementedError("Abstract method not implemented")

    @abstractmethod
    def on_saved(self, saved_tab_widget):
        """Callback on any tab widget save."""
        raise NotImplementedError("Abstract method not implemented")

    def contain_category_key(self, category):
        """Parent widget ask if category of full path lead to this widget.

        Args:
            category (str): The category name.

        Returns:
            bool: Passed category lead to this widget.
        """
        return False


class BaseControlPanelWidget(BlankControlPanelWidget):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)

        self.conf_wrapper_widget = None
        self.scroll_widget = None

        self.breadcrumbs_bar = None
        self.breadcrumbs_model = None

        self.main_layout = None

        self.content_layout = None
        self.content_widget = None

        self.footer_widget = None
        self.footer_layout = None
        self.footer_left_label = None
        self.footer_right_label = None

        self._footer_btn_text = "Save"

        self.footer_btn = None
        self.refresh_btn = None

        self._labels_alignment = QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter

    def _add_developer_ui(self):
        pass

    @abstractmethod
    def _on_footer_button_pressed(self):
        raise NotImplementedError("This method should have been implemented on the subclass")

    @abstractmethod
    def _on_refresh_button_pressed(self):
        raise NotImplementedError("This method should have been implemented on the subclass")

    @abstractmethod
    def _on_path_edited(self, path):
        raise NotImplementedError("This method should have been implemented on the subclass")

    def create_ui(self):
        self.conf_wrapper_widget = QtWidgets.QSplitter(self)
        configurations_widget = QtWidgets.QWidget(self.conf_wrapper_widget)

        # Breadcrumbs/Path widget
        breadcrumbs_widget = QtWidgets.QWidget(self)
        breadcrumbs_label = QtWidgets.QLabel("Path:", breadcrumbs_widget)
        self.breadcrumbs_bar = BreadcrumbsAddressBar(breadcrumbs_widget)

        refresh_icon = qtawesome.icon("fa.refresh", color="white")
        self.refresh_btn = QtWidgets.QPushButton(breadcrumbs_widget)
        self.refresh_btn.setIcon(refresh_icon)

        breadcrumbs_layout = QtWidgets.QHBoxLayout(breadcrumbs_widget)
        breadcrumbs_layout.setContentsMargins(5, 5, 5, 5)
        breadcrumbs_layout.setSpacing(5)
        breadcrumbs_layout.addWidget(breadcrumbs_label, 0)
        breadcrumbs_layout.addWidget(self.breadcrumbs_bar, 1)
        breadcrumbs_layout.addWidget(self.refresh_btn, 0)

        # Widgets representing settings entities
        self.scroll_widget = QtWidgets.QScrollArea(configurations_widget)
        self.content_widget = QtWidgets.QWidget(self.scroll_widget)
        self.scroll_widget.setWidgetResizable(True)
        self.scroll_widget.setWidget(self.content_widget)

        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(3, 3, 3, 3)
        self.content_layout.setSpacing(5)
        self.content_layout.setAlignment(QtCore.Qt.AlignTop)

        # Footer widget
        self.footer_widget = QtWidgets.QWidget(self)
        self.footer_widget.setObjectName("SettingsFooter")

        # Footer info labels
        self.footer_left_label = QtWidgets.QLabel(self.footer_widget)
        self.footer_left_label.setAlignment(self._labels_alignment)
        self.footer_right_label = QtWidgets.QLabel(self.footer_widget)
        self.footer_right_label.setAlignment(self._labels_alignment)

        self.footer_btn = QtWidgets.QPushButton(self._footer_btn_text, self.footer_widget)

        self.footer_layout = QtWidgets.QHBoxLayout(self.footer_widget)
        self.footer_layout.setContentsMargins(5, 5, 5, 5)
        if self._controller.user_role == "developer":
            self._add_developer_ui()

        self.footer_layout.addWidget(self.footer_left_label, 1)
        self.footer_layout.addWidget(self.footer_right_label, 0)
        self.footer_layout.addWidget(self.footer_btn, 0)

        configurations_layout = QtWidgets.QVBoxLayout(configurations_widget)
        configurations_layout.setContentsMargins(0, 0, 0, 0)
        configurations_layout.setSpacing(0)

        configurations_layout.addWidget(self.scroll_widget, 1)

        self.conf_wrapper_widget.addWidget(configurations_widget)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_layout.addWidget(breadcrumbs_widget, 0)
        self.main_layout.addWidget(self.conf_wrapper_widget, 1)
        self.main_layout.addWidget(self.footer_widget, 0)

        # Add callbacks / onclick events
        self.footer_btn.clicked.connect(self._on_footer_button_pressed)
        self.refresh_btn.clicked.connect(self._on_refresh_button_pressed)
        self.breadcrumbs_bar.path_edited.connect(self._on_path_edited)


class SettingsControlPanelWidget(BaseControlPanelWidget):
    footer_label_data = {
        "restart_required": {
            "text": "Your changes require restart of all running QuadPype processes to take affect.",
            "tooltip": "Please close all running QuadPype processes.",
            "style_class": ""
        },
        "protected_settings": {
            "text": "Running version is different from the production version. You cannot save the Global Settings.",
            "tooltip": "This mandatory restriction is to avoid unwanted issues.",
            "style_class": "SettingsSystemProtected",
        },
        "outdated_version": {
            "text": "The settings are loaded from an older version.",
            "tooltip": "Please check that all settings are still correct (blue colour\n"
                       "indicates potential changes in the new version) and save your\n"
                       "settings to update them to you current running QuadPype version.",
            "style_class": "SettingsOutdatedSourceVersion",
        }
    }

    source_version_tooltip = "Using settings of current QuadPype version"

    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)

        self._controller.event_system.add_callback(
            "edit.mode.changed",
            self._edit_mode_changed
        )

        self.entity = None
        self._edit_mode = EditMode.ENABLE
        self._last_saved_info = None
        self._reset_crashed = False
        self._read_only = False

        self._hide_studio_overrides = False
        self._updating_root = False
        self._use_version = None
        self._current_version = get_quadpype_version()

        self.ignore_input_changes = IgnoreInputChangesObj(self)

        self.keys = []
        self.input_fields = []

        # UI related members
        self.modify_defaults_checkbox = None
        self._is_loaded_version_outdated = False

        self.initialize_attributes()

        self.create_ui()

    @staticmethod
    def create_ui_for_entity(category_widget, entity, entity_widget):
        args = (category_widget, entity, entity_widget)
        if isinstance(entity, GUIEntity):
            return GUIWidget(*args)

        elif isinstance(entity, DictConditionalEntity):
            return DictConditionalWidget(*args)

        elif isinstance(entity, DictImmutableKeysEntity):
            return DictImmutableKeysWidget(*args)

        elif isinstance(entity, BoolEntity):
            return BoolWidget(*args)

        elif isinstance(entity, PackageVersionEntity):
            return PackageVersionWidget(*args)

        elif isinstance(entity, PasswordEntity):
            # Order of this elif (before the TextEntity one) because
            # PasswordEntity inherit from TextEntity
            return PasswordWidget(*args)

        elif isinstance(entity, TextEntity):
            return TextWidget(*args)

        elif isinstance(entity, NumberEntity):
            return NumberWidget(*args)

        elif isinstance(entity, RawJsonEntity):
            return RawJsonWidget(*args)

        elif isinstance(entity, ColorEntity):
            return ColorWidget(*args)

        elif isinstance(entity, BaseEnumEntity):
            return EnumeratorWidget(*args)

        elif isinstance(entity, PathEntity):
            return PathWidget(*args)

        elif isinstance(entity, PathInput):
            return PathInputWidget(*args)

        elif isinstance(entity, ListEntity):
            return ListWidget(*args)

        elif isinstance(entity, DictMutableKeysEntity):
            return DictMutableKeysWidget(*args)

        elif isinstance(entity, ListStrictEntity):
            return ListStrictWidget(*args)

        label = "<{}>: {} ({})".format(
            entity.__class__.__name__, entity.path, entity.value
        )
        raise TypeError("Unknown type: {}".format(label))

    def _edit_mode_changed(self, event):
        self.set_edit_mode(event["edit_mode"])

    def set_read_only(self, status):
        self._read_only = status
        for input_field in self.input_fields:
            input_field.set_read_only(self._read_only)

    def set_edit_mode(self, mode):
        if mode == self._edit_mode:
            return

        was_disabled = (self._edit_mode == EditMode.DISABLE)
        self._edit_mode = mode

        self.footer_btn.setEnabled(mode == EditMode.ENABLE and not self._reset_crashed)

        self.set_read_only((mode != EditMode.ENABLE))

        if mode == EditMode.DISABLE:
            tooltip = (
                "Someone else has opened settings UI."
                "\nTry hit refresh to check if settings are already available."
            )
        elif mode == EditMode.PROTECT:
            tooltip = (
                "Global settings can only be saved with the QuadPype production version."
            )
        else:
            tooltip = "Save settings"

        self.footer_btn.setToolTip(tooltip)

        # Reset when last saved information has changed
        if was_disabled and not self._check_last_saved_info():
            self.reset()

    def initialize_attributes(self):
        return

    @property
    def is_modifying_defaults(self):
        if self.modify_defaults_checkbox is None:
            return False
        return self.modify_defaults_checkbox.isChecked()

    def create_ui(self):
        super().create_ui()

        # Using the footer_right_label to display the version of loaded settings
        self.footer_right_label.setObjectName("SourceVersionLabel")
        set_style_property(self.footer_right_label, "state", "")
        self.footer_right_label.setToolTip(self.source_version_tooltip)

        self.ui_tweaks()

    def ui_tweaks(self):
        return

    def _on_path_edited(self, path):
        for input_field in self.input_fields:
            if input_field.make_sure_is_visible(path, True):
                break

    def scroll_to(self, widget):
        if widget:
            # Process events which happened before ensurence
            # - that is because some widgets could be not visible before
            #   this method was called and have incorrect size
            QtWidgets.QApplication.processEvents()
            # Scroll to widget
            self.scroll_widget.ensureWidgetVisible(widget)

    def go_to_fullpath(self, full_path):
        """Full path of settings entity which can lead to different category.

        Args:
            full_path (str): Full path to settings entity. It is expected that
                path starts with category name ("global_settings" etc.).
        """
        if not full_path:
            return
        items = full_path.split("/")
        category = items[0]
        path = ""
        if len(items) > 1:
            path = "/".join(items[1:])
        self.full_path_requested.emit(category, path)

    def set_category_path(self, category, path):
        """Change path of widget based on category full path."""
        pass

    def change_path(self, path):
        """Change path and go to widget."""
        self.breadcrumbs_bar.change_path(path)

    def set_path(self, path):
        """Called from clicked widget."""
        self.breadcrumbs_bar.set_path(path)

    @abstractmethod
    def _on_modify_defaults(self):
        pass

    def _add_developer_ui(self):
        modify_defaults_checkbox = QtWidgets.QCheckBox(self.footer_widget)
        modify_defaults_checkbox.setChecked(self._hide_studio_overrides)
        label_widget = QtWidgets.QLabel(
            "Modify defaults", self.footer_widget
        )

        self.footer_layout.addWidget(label_widget, 0)
        self.footer_layout.addWidget(modify_defaults_checkbox, 0)

        modify_defaults_checkbox.stateChanged.connect(
            self._on_modify_defaults
        )
        self.modify_defaults_checkbox = modify_defaults_checkbox

    def get_invalid(self):
        invalid = []
        for input_field in self.input_fields:
            invalid.extend(input_field.get_invalid())
        return invalid

    def hierarchical_style_update(self):
        for input_field in self.input_fields:
            input_field.hierarchical_style_update()

    def _on_entity_change(self):
        self.hierarchical_style_update()

    def add_widget_to_layout(self, widget, label_widget=None):
        if label_widget:
            raise NotImplementedError(
                "`add_widget_to_layout` on Category item can't accept labels"
            )
        self.content_layout.addWidget(widget, 0)

    @contextlib.contextmanager
    def working_state_context(self):
        self.set_state(PageState.Working)
        yield
        self.set_state(PageState.Idle)

    def save(self):
        if not self._edit_mode:
            return

        if not self.items_are_valid():
            return

        try:
            self.entity.save()
            self._use_version = None

            # NOTE There are relations to previous entities and C++ callbacks
            #   so it is easier to just use new entity and recreate UI but
            #   would be nice to change this and add cleanup part so this is
            #   not required.
            self.reset()

        except SaveWarningExc as exc:
            warnings = [
                "<b>Settings were saved but few issues happened.</b>"
            ]
            for item in exc.warnings:
                warnings.append(item.replace("\n", "<br>"))

            msg = "<br><br>".join(warnings)

            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Save warnings")
            dialog.setText(msg)
            dialog.setIcon(QtWidgets.QMessageBox.Warning)
            dialog.exec_()

            self.reset()

        except Exception as exc:
            formatted_traceback = traceback.format_exception(*sys.exc_info())
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Unexpected error")
            msg = "Unexpected error happened!\n\nError: {}".format(str(exc))
            dialog.setText(msg)
            dialog.setDetailedText("\n".join(formatted_traceback))
            dialog.setIcon(QtWidgets.QMessageBox.Critical)

            line_widths = set()
            metrics = dialog.fontMetrics()
            for line in formatted_traceback:
                line_widths.add(metrics.width(line))
            max_width = max(line_widths)

            spacer = QtWidgets.QSpacerItem(
                max_width, 0,
                QtWidgets.QSizePolicy.Minimum,
                QtWidgets.QSizePolicy.Expanding
            )
            layout: QtWidgets.QGridLayout = dialog.layout()  # noqa
            layout.addItem(
                spacer, layout.rowCount(), 0, 1, layout.columnCount()
            )
            dialog.exec_()

    @abstractmethod
    def _create_root_entity(self):
        raise NotImplementedError(
            "`create_root_entity` method not implemented"
        )

    def _on_require_restart_change(self):
        self._update_labels_visibility()

    def reset(self):
        self.reset_started.emit()
        self.set_state(PageState.Working)

        self._on_reset_start()

        self.input_fields = []

        while self.content_layout.count() != 0:
            widget = self.content_layout.itemAt(0).widget()
            if widget is not None:
                widget.setVisible(False)

            self.content_layout.removeWidget(widget)
            widget.deleteLater()

        dialog = None
        self._updating_root = True
        source_version = ""
        try:
            self._create_root_entity()

            self.entity.add_require_restart_change_callback(
                self._on_require_restart_change
            )

            # SLOW: This is very slow and impact waiting time when switching projects in settings
            self.add_children_gui()

            self.ignore_input_changes.set_ignore(True)

            # SLOW: This is very slow and impact waiting time when switching projects in settings
            for input_field in self.input_fields:
                input_field.set_entity_value()

            self.ignore_input_changes.set_ignore(False)
            source_version = self.entity.source_version

        except DefaultsNotDefined:
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Missing default values")
            dialog.setText((
                "Default values are not set and you"
                " don't have permissions to modify them."
                " Please contact QuadPype team."
            ))
            dialog.setIcon(QtWidgets.QMessageBox.Critical)

        except SchemaError as exc:
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Schema error")
            msg = "Implementation bug!\n\nError: {}".format(str(exc))
            dialog.setText(msg)
            dialog.setIcon(QtWidgets.QMessageBox.Warning)

        except Exception as exc:
            formatted_traceback = traceback.format_exception(*sys.exc_info())
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Unexpected error")
            msg = "Unexpected error happened!\n\nError: {}".format(str(exc))
            dialog.setText(msg)
            dialog.setDetailedText("\n".join(formatted_traceback))
            dialog.setIcon(QtWidgets.QMessageBox.Critical)

            line_widths = set()
            metrics = dialog.fontMetrics()
            for line in formatted_traceback:
                line_widths.add(metrics.width(line))
            max_width = max(line_widths)

            spacer = QtWidgets.QSpacerItem(
                max_width, 0,
                QtWidgets.QSizePolicy.Minimum,
                QtWidgets.QSizePolicy.Expanding
            )
            layout: QtWidgets.QGridLayout = dialog.layout()  # noqa
            layout.addItem(
                spacer, layout.rowCount(), 0, 1, layout.columnCount()
            )

        self._updating_root = False

        # Update source version label
        state_value = ""
        tooltip = ""
        outdated = False
        if source_version:
            if source_version != self._current_version:
                state_value = "different"
                tooltip = self.footer_label_data["outdated_version"]["tooltip"]
                outdated = True
            else:
                state_value = "same"
                tooltip = self.source_version_tooltip

        self._is_loaded_version_outdated = outdated
        self.footer_right_label.setText(source_version)
        self.footer_right_label.setToolTip(tooltip)
        set_style_property(self.footer_right_label, "state", state_value)
        self._update_labels_visibility()

        self.set_state(PageState.Idle)

        if dialog:
            dialog.exec_()
            self._on_reset_crash()
        else:
            self._on_reset_success()
        self.reset_finished.emit()

    def _on_source_version_change(self, version):
        if self._updating_root:
            return

        if version == self._current_version:
            version = None

        self._use_version = version
        QtCore.QTimer.singleShot(20, self.reset)

    def add_context_actions(self, menu):
        if not self.entity or self.is_modifying_defaults:
            return

        versions = self.entity.get_available_studio_versions(sorted=True)
        if not versions:
            return

        submenu = QtWidgets.QMenu("Use settings from version", menu)
        for version in reversed(versions):
            action = VersionAction(version, submenu)
            action.version_triggered.connect(
                self._on_context_version_trigger
            )
            submenu.addAction(action)

        menu.addMenu(submenu)

        extract_action = QtWidgets.QAction("Extract to file", menu)
        extract_action.triggered.connect(self._on_extract_to_file)

        menu.addAction(extract_action)

    def _on_context_version_trigger(self, version):
        self._on_source_version_change(version)

    def _on_extract_to_file(self):
        filepath = ExtractHelper.ask_for_save_filepath(self)
        if not filepath:
            return

        settings_data = {
            SETTINGS_PATH_KEY: self.entity.root_key,
            ROOT_KEY: self.entity.root_key,
            VALUE_KEY: self.entity.value
        }
        project_name = 0
        if hasattr(self, "project_name"):
            project_name = self.project_name

        ExtractHelper.extract_settings_to_json(
            filepath, settings_data, project_name
        )

    def _on_apply_settings_from_project(self, project_name):
        self.entity.change_project(project_name, None, only_settings=True)

    def _on_reset_crash(self):
        self._reset_crashed = True
        self.footer_btn.setEnabled(False)

        if self.breadcrumbs_model is not None:
            self.breadcrumbs_model.set_entity(None)

    def _on_reset_success(self):
        self._reset_crashed = False
        if not self.footer_btn.isEnabled():
            self.footer_btn.setEnabled(self._edit_mode == EditMode.ENABLE)

        if self.breadcrumbs_model is not None:
            path = self.breadcrumbs_bar.path()
            self.breadcrumbs_bar.set_path("")
            self.breadcrumbs_model.set_entity(self.entity)
            self.breadcrumbs_bar.change_path(path)

    def add_children_gui(self):
        for child_obj in self.entity.children:
            item = self.create_ui_for_entity(self, child_obj, self)
            self.input_fields.append(item)

        # Add spacer to stretch children guis
        self.content_layout.addWidget(
            QtWidgets.QWidget(self.content_widget), 1
        )

    def items_are_valid(self):
        invalid_items = self.get_invalid()
        if not invalid_items:
            return True

        msg_box = QtWidgets.QMessageBox(
            QtWidgets.QMessageBox.Warning,
            "Invalid input",
            (
                "There is invalid value in one of inputs."
                " Please lead red color and fix them."
            ),
            parent=self
        )
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.exec_()

        first_invalid_item = invalid_items[0]
        self.scroll_widget.ensureWidgetVisible(first_invalid_item)
        if first_invalid_item.isVisible():
            first_invalid_item.setFocus()
        return False

    def on_saved(self, saved_tab_widget):
        """Callback on any tab widget save."""
        return

    def _check_last_saved_info(self):
        raise NotImplementedError(
            "{} does not have implemented '_check_last_saved_info'".format(self.__class__.__name__)
        )

    def _save(self):
        self._controller.update_last_opened_info()
        if not self._controller.opened_info:
            dialog = SettingsControlTaken(self._last_saved_info, self)
            dialog.exec_()
            return

        if not self._check_last_saved_info():
            dialog = SettingsLastSavedChanged(self._last_saved_info, self)
            dialog.exec_()
            if dialog.result() == 0:
                return

        # Don't trigger restart if defaults are modified
        if self.is_modifying_defaults:
            require_restart = False
        else:
            require_restart = self.entity.require_restart

        self.set_state(PageState.Working)

        if self.items_are_valid():
            self.save()

        self.set_state(PageState.Idle)

        self.saved.emit(self)

        if require_restart:
            self.restart_required_trigger.emit()

    def _on_footer_button_pressed(self):
        """For settings panels this means the save button has been pressed"""
        self._save()

    def _update_labels_visibility(self):
        if self.is_modifying_defaults or self.entity is None:
            require_restart = False
        else:
            require_restart = self.entity.require_restart

        status = None
        if require_restart:
            status = "restart_required"
        elif self._edit_mode == EditMode.PROTECT:
            status = "protected_settings"
        elif self._is_loaded_version_outdated:
            status = "outdated_version"

        if not status:
            self.footer_left_label.setText("")
            return

        label_data = self.footer_label_data[status]
        self.footer_left_label.setText(label_data["text"])
        self.footer_left_label.setToolTip(label_data["tooltip"])

        label_object_name = label_data["style_class"]
        if label_object_name:
            self.footer_left_label.setObjectName(label_object_name)
            self.footer_left_label.style().polish(self.footer_left_label)

    def _on_refresh_button_pressed(self):
        self.reset()

    def _on_hide_studio_overrides(self, state):
        self._hide_studio_overrides = (state == QtCore.Qt.Checked)


class GlobalSettingsWidget(SettingsControlPanelWidget):
    def __init__(self, controller, parent=None):
        self._actions = []
        self.breadcrumbs_model = None
        super().__init__(controller, parent)

    def _check_last_saved_info(self):
        if self.is_modifying_defaults:
            return True

        last_saved_info = get_global_settings_last_saved_info()
        return self._last_saved_info == last_saved_info

    def contain_category_key(self, category):
        if category == GLOBAL_SETTINGS_KEY:
            return True
        return False

    def set_category_path(self, category, path):
        self.breadcrumbs_bar.change_path(path)

    def _create_root_entity(self):
        entity = GlobalSettingsEntity(
            set_studio_state=False, source_version=self._use_version
        )
        entity.on_change_callbacks.append(self._on_entity_change)
        self.entity = entity
        last_saved_info = None
        if not self.is_modifying_defaults:
            last_saved_info = get_global_settings_last_saved_info()
        self._last_saved_info = last_saved_info
        try:
            if self.is_modifying_defaults:
                entity.set_defaults_state()
            else:
                entity.set_studio_state()

            if self.modify_defaults_checkbox:
                self.modify_defaults_checkbox.setEnabled(True)
        except DefaultsNotDefined:
            if not self.modify_defaults_checkbox:
                raise

            entity.set_defaults_state()
            self.modify_defaults_checkbox.setChecked(True)
            self.modify_defaults_checkbox.setEnabled(False)

    def ui_tweaks(self):
        self.breadcrumbs_model = GlobalSettingsBreadcrumbs()
        self.breadcrumbs_bar.set_model(self.breadcrumbs_model)

    def _on_modify_defaults(self):
        if self.is_modifying_defaults:
            if not self.entity.is_in_defaults_state():
                self.reset()
        else:
            if not self.entity.is_in_studio_state():
                self.reset()

    def add_children_gui(self):
        super(GlobalSettingsWidget, self).add_children_gui()

        # The Read-Only logic is currently only relevant for
        # Global Settings (not for Project)
        for input_field in self.input_fields:
            input_field.set_read_only(self._read_only)

    def _on_reset_start(self):
        pass


class ProjectSettingsWidget(SettingsControlPanelWidget):
    def __init__(self, controller, parent=None):
        self.project_name = None
        self.protect_attrs = False
        self.project_list_widget = None
        super().__init__(controller, parent)

    def set_edit_mode(self, enabled):
        super(ProjectSettingsWidget, self).set_edit_mode(enabled)
        self.project_list_widget.set_edit_mode(enabled)

    def _check_last_saved_info(self):
        if self.is_modifying_defaults:
            return True

        last_saved_info = get_project_settings_last_saved_info(self.project_name)
        return self._last_saved_info == last_saved_info

    def contain_category_key(self, category):
        if category in (PROJECT_SETTINGS_KEY, PROJECT_ANATOMY_KEY):
            return True
        return False

    def set_category_path(self, category, path):
        if path:
            path_items = path.split("/")
            if path_items[0] not in (PROJECT_SETTINGS_KEY, PROJECT_ANATOMY_KEY):
                path = "/".join([category, path])
        else:
            path = category

        self.breadcrumbs_bar.change_path(path)

    def initialize_attributes(self):
        self.project_name = None

    def ui_tweaks(self):
        self.breadcrumbs_model = ProjectSettingsBreadcrumbs()
        self.breadcrumbs_bar.set_model(self.breadcrumbs_model)

        project_list_widget = ProjectListWidget(self)

        self.conf_wrapper_widget.insertWidget(0, project_list_widget)
        self.conf_wrapper_widget.setStretchFactor(0, 0)
        self.conf_wrapper_widget.setStretchFactor(1, 1)

        project_list_widget.project_changed.connect(self._on_project_change)
        project_list_widget.version_change_requested.connect(
            self._on_source_version_change
        )
        project_list_widget.extract_to_file_requested.connect(
            self._on_extract_to_file
        )
        project_list_widget.apply_from_project_requested.connect(
            self._on_apply_settings_from_project
        )

        self.project_list_widget = project_list_widget

    def get_project_names(self):
        if self.is_modifying_defaults:
            return []
        return self.project_list_widget.get_project_names()

    def on_saved(self, saved_tab_widget):
        """Callback on any tab widget save."""
        pass

    def _on_context_version_trigger(self, version):
        self.project_list_widget.select_project(None)
        super(ProjectSettingsWidget, self)._on_context_version_trigger(version)

    def _on_reset_start(self):
        self.project_list_widget.refresh()

    def _on_reset_crash(self):
        self._set_enabled_project_list(False)
        super(ProjectSettingsWidget, self)._on_reset_crash()

    def _on_reset_success(self):
        self._set_enabled_project_list(True)
        super(ProjectSettingsWidget, self)._on_reset_success()

    def _set_enabled_project_list(self, enabled):
        if enabled and self.is_modifying_defaults:
            enabled = False
        if self.project_list_widget.isEnabled() != enabled:
            self.project_list_widget.setEnabled(enabled)

    def _create_root_entity(self):
        entity = ProjectSettingsEntity(
            change_state=False, source_version=self._use_version
        )
        entity.on_change_callbacks.append(self._on_entity_change)
        self.project_list_widget.set_entity(entity)
        self.entity = entity

        last_saved_info = None
        if not self.is_modifying_defaults:
            last_saved_info = get_project_settings_last_saved_info(self.project_name)
        self._last_saved_info = last_saved_info
        try:
            if self.is_modifying_defaults:
                self.entity.set_defaults_state()

            elif self.project_name is None:
                self.entity.set_studio_state()

            else:
                self.entity.change_project(
                    self.project_name, self._use_version
                )

            if self.modify_defaults_checkbox:
                self.modify_defaults_checkbox.setEnabled(True)

            self._set_enabled_project_list(True)
        except DefaultsNotDefined:
            if not self.modify_defaults_checkbox:
                raise

            self.entity.set_defaults_state()
            self.modify_defaults_checkbox.setChecked(True)
            self.modify_defaults_checkbox.setEnabled(False)
            self._set_enabled_project_list(False)
        except StudioDefaultsNotDefined:
            self.project_list_widget.select_default_project()

    def _on_project_change(self):
        project_name = self.project_list_widget.project_name()
        if project_name == self.project_name:
            return

        self.project_name = project_name

        self.set_state(PageState.Working)

        self.reset()

        self.set_state(PageState.Idle)

    def _on_modify_defaults(self):
        if self.is_modifying_defaults:
            self._set_enabled_project_list(False)
            if not self.entity.is_in_defaults_state():
                self.reset()
        else:
            self._set_enabled_project_list(True)
            if not self.entity.is_in_studio_state():
                self.reset()


class ProjectManagerWidget(BaseControlPanelWidget):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)

    def _on_reset_start(self):
        return

    def _on_reset_success(self):
        return

    def _on_reset_crash(self):
        return

    def reset(self):
        self.reset_started.emit()
        self.set_state(PageState.Working)
        self._on_reset_start()
        self.set_state(PageState.Idle)
        self._on_reset_success()
        self.reset_finished.emit()

    def on_saved(self, saved_tab_widget):
        pass


class UserManagerWidget(BaseControlPanelWidget):
    _ws_profile_prefix = "last_workstation_profile/"
    table_column_data = {
        _ws_profile_prefix + "username": "Username",
        "user_id": "ID",
        "role": "Role",
        "last_connection_timestamp": "Last Connection",
        _ws_profile_prefix + "workstation_name": "Last Workstation Name"
    }

    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)

        self._footer_btn_text = "Enjoy!"
        self.table_widget = None

        self._selected_user_id = None

        self.create_ui()

    def update_column_widths(self):
        available_width = self.parent().width()
        self.table_widget.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        columns_size = {}
        columns_size_sum = 0
        additional_width_column = 0
        columns_count = self.table_widget.columnCount()
        for column_index in range(columns_count):
            min_size = self.table_widget.horizontalHeader().sectionSize(column_index)
            columns_size[column_index] = min_size
            columns_size_sum += min_size

        if columns_size_sum < available_width:
            additional_width_column = int((available_width - columns_size_sum) / columns_count)

        for column_index in range(columns_count-1):
            self.table_widget.horizontalHeader().setSectionResizeMode(column_index, QtWidgets.QHeaderView.Fixed)
            self.table_widget.setColumnWidth(column_index, columns_size[column_index] + additional_width_column)

        if additional_width_column:
            # This means, without adding width, the sum of column wouldn't take the full width
            # Stretching the last column to ensure the row will be fully filled
            last_column_index = columns_count-1
            self.table_widget.horizontalHeader().setSectionResizeMode(last_column_index, QtWidgets.QHeaderView.Stretch)

    def add_user_row(self, user_data):
        row_index = self.table_widget.rowCount()
        self.table_widget.insertRow(row_index)

        for column_index, cell_data in enumerate(user_data):
            item = QtWidgets.QTableWidgetItem(cell_data)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_widget.setItem(row_index, column_index, item)

    def _update_user_list(self):
        # Remove all the rows (if any)
        self.table_widget.setRowCount(0)

        # Get the user profiles
        user_profiles = get_all_user_profiles()

        # Populate the table
        for user_profile in user_profiles:
            user_data = []

            # Aggregate the user data
            last_workstation_profile = \
                user_profile["workstation_profiles"][user_profile["last_workstation_profile_index"]]
            for user_profile_key in self.table_column_data:
                if user_profile_key.startswith(self._ws_profile_prefix):
                    user_profile_key = user_profile_key.removeprefix(self._ws_profile_prefix)
                    cell_value = last_workstation_profile[user_profile_key]
                else:
                    cell_value = user_profile[user_profile_key]

                if isinstance(cell_value, datetime):
                    # Convert datetime to string (close to the ISO 8601 standard)
                    cell_value = cell_value.strftime("%Y-%m-%d, %H:%M:%S")

                user_data.append(cell_value)

            self.add_user_row(user_data)

        if user_profiles.retrieved == 0:
            # No profile found, this should be impossible unless the
            # collection has been cleared while QuadPype was running

            # Inserting an empty row to avoid issues:
            user_data = [""] * len(self.table_column_data)
            self.add_user_row(user_data)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_column_widths()

    def on_selection_changed(self):
        selected_items = self.table_widget.selectedItems()
        if not selected_items:
            self._selected_user_id = None
        else:
            # The full row is selected every time, the user_id is the index 1 element.
            self._selected_user_id = selected_items[1].text()

    def create_ui(self):
        super().create_ui()

        self.table_widget = QtWidgets.QTableWidget(self.content_widget)

        self.table_widget.verticalHeader().hide()
        self.table_widget.setColumnCount(len(self.table_column_data))
        self.table_widget.setHorizontalHeaderLabels(self.table_column_data.values())

        # Set selection mode to only allow single row selection
        self.table_widget.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.table_widget.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)

        self.table_widget.selectionModel().selectionChanged.connect(self.on_selection_changed)

        self.table_widget.setSortingEnabled(True)

        self._update_user_list()

        # Initially sort by the "Username" column (index 0)
        self.table_widget.sortItems(0)

        # Select the first row by default (so there is always a row selected)
        self.table_widget.selectRow(0)

        self.content_layout.addWidget(self.table_widget, stretch=1)

    def _on_reset_start(self):
        return

    def _on_reset_success(self):
        return

    def _on_reset_crash(self):
        return

    def reset(self):
        self.reset_started.emit()
        self.set_state(PageState.Working)
        self._on_reset_start()
        self.set_state(PageState.Idle)
        self._on_reset_success()
        self.reset_finished.emit()

    def on_saved(self, saved_tab_widget):
        pass

    def _on_path_edited(self, path):
        pass

    def _on_refresh_button_pressed(self):
        self._update_user_list()

    def _on_footer_button_pressed(self):
        pass
