import sys
import time
import traceback
import contextlib

from abc import abstractmethod
from enum import Enum
from datetime import datetime

from qtpy import QtWidgets, QtSvgWidgets, QtCore, QtGui
import qtawesome

from quadpype import resources
from quadpype.events import send_event, get_event_doc
from quadpype.lib import (
    get_quadpype_version,
    get_all_user_profiles,
    get_user_id
)
from quadpype.tools.utils import set_style_property

from quadpype.settings import (
    ADDONS_SETTINGS_KEY,
    get_global_settings,
)
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
from .address_bar_widgets import (
    AddressBar,
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
        """Parent widget ask if the category of the full path leads to this widget.

        Args:
            category (str): The category name.

        Returns:
            bool: Passed if the category leads to this widget.
        """
        return False


class BaseControlPanelWidget(BlankControlPanelWidget):
    address_bar_class = BreadcrumbsAddressBar

    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)

        self.conf_wrapper_widget = None
        self.scroll_widget = None

        self.address_bar_label = None
        self.address_bar = None
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

        self._labels_alignment = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter

    def _add_developer_ui(self):
        pass

    @abstractmethod
    def _on_footer_button_pressed(self):
        raise NotImplementedError("This method should have been implemented on the subclass")

    @abstractmethod
    def _on_refresh_button_pressed(self):
        raise NotImplementedError("This method should have been implemented on the subclass")

    @abstractmethod
    def _on_path_focus_in(self):
        raise NotImplementedError("This method should have been implemented on the subclass")

    @abstractmethod
    def _on_path_edited(self, path):
        raise NotImplementedError("This method should have been implemented on the subclass")

    def create_ui(self):
        self.conf_wrapper_widget = QtWidgets.QSplitter(self)
        configurations_widget = QtWidgets.QWidget(self.conf_wrapper_widget)

        # Breadcrumbs/Path widget
        breadcrumbs_widget = QtWidgets.QWidget(self)
        self.address_bar_label = QtWidgets.QLabel("Path:", breadcrumbs_widget)
        self.address_bar = self.address_bar_class(breadcrumbs_widget)

        refresh_icon = qtawesome.icon("fa.refresh", color="white")
        self.refresh_btn = QtWidgets.QPushButton(breadcrumbs_widget)
        self.refresh_btn.setIcon(refresh_icon)

        breadcrumbs_layout = QtWidgets.QHBoxLayout(breadcrumbs_widget)
        breadcrumbs_layout.setContentsMargins(5, 5, 5, 5)
        breadcrumbs_layout.setSpacing(5)
        breadcrumbs_layout.addWidget(self.address_bar_label, 0)
        breadcrumbs_layout.addWidget(self.address_bar, 1)
        breadcrumbs_layout.addWidget(self.refresh_btn, 0)

        # Widgets representing settings entities
        self.scroll_widget = QtWidgets.QScrollArea(configurations_widget)
        self.content_widget = QtWidgets.QWidget(self.scroll_widget)
        self.scroll_widget.setWidgetResizable(True)
        self.scroll_widget.setWidget(self.content_widget)

        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(3, 3, 3, 3)
        self.content_layout.setSpacing(5)
        self.content_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

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
        self.address_bar.path_focus_in.connect(self._on_path_focus_in)
        self.address_bar.path_edited.connect(self._on_path_edited)


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

    @property
    def current_version(self):
        return self._current_version

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

    def _on_path_focus_in(self):
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
        """Change the path of the widget based on the category full path."""
        pass

    def change_path(self, path):
        """Change the path and go to the widget."""
        self.address_bar.change_path(path)

    def set_path(self, path):
        """Called from clicked widget."""
        self.address_bar.set_path(path)

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
            #   so it is easier to just use new entity and recreate the UI but
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
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            dialog.exec_()

            self.reset()

        except Exception as exc:
            formatted_traceback = traceback.format_exception(*sys.exc_info())
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Unexpected error")
            msg = "Unexpected error happened!\n\nError: {}".format(str(exc))
            dialog.setText(msg)
            dialog.setDetailedText("\n".join(formatted_traceback))
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)

            line_widths = set()
            metrics = dialog.fontMetrics()
            for line in formatted_traceback:
                line_widths.add(metrics.horizontalAdvance(line))
            max_width = max(line_widths)

            spacer = QtWidgets.QSpacerItem(
                max_width, 0,
                QtWidgets.QSizePolicy.Policy.Minimum,
                QtWidgets.QSizePolicy.Policy.Expanding
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
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)

        except SchemaError as exc:
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Schema error")
            msg = "Implementation bug!\n\nError: {}".format(str(exc))
            dialog.setText(msg)
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Warning)

        except Exception as exc:
            formatted_traceback = traceback.format_exception(*sys.exc_info())
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Unexpected error")
            msg = "Unexpected error happened!\n\nError: {}".format(str(exc))
            dialog.setText(msg)
            dialog.setDetailedText("\n".join(formatted_traceback))
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)

            line_widths = set()
            metrics = dialog.fontMetrics()
            for line in formatted_traceback:
                line_widths.add(metrics.horizontalAdvance(line))
            max_width = max(line_widths)

            spacer = QtWidgets.QSpacerItem(
                max_width, 0,
                QtWidgets.QSizePolicy.Policy.Minimum,
                QtWidgets.QSizePolicy.Policy.Expanding
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
            path = self.address_bar.path()
            self.address_bar.set_path("")
            self.breadcrumbs_model.set_entity(self.entity)
            self.address_bar.change_path(path)

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
            QtWidgets.QMessageBox.Icon.Warning,
            "Invalid input",
            (
                "There is invalid value in one of inputs."
                " Please lead red color and fix them."
            ),
            parent=self
        )
        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
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
        """For the settings panels, this means the save button has been pressed"""
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
        self._hide_studio_overrides = (state == QtCore.Qt.CheckState.Checked)


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
        self.address_bar.change_path(path)

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
        self.address_bar.set_model(self.breadcrumbs_model)

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

        self.address_bar.change_path(path)

    def initialize_attributes(self):
        self.project_name = None

    def ui_tweaks(self):
        self.breadcrumbs_model = ProjectSettingsBreadcrumbs()
        self.address_bar.set_model(self.breadcrumbs_model)

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


class CustomDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, icon_text_spacing=10, parent=None):
        super().__init__(parent)
        self.icon_text_spacing = icon_text_spacing

    def paint(self, painter, option, index):
        """
        Custom painting to support two-line word wrap with truncation.
        """
        # Get item data
        model = index.model()
        item = model.itemFromIndex(index)
        if not item:
            return

        # Save the current pen color to restore later
        original_pen_color = painter.pen().color()
        original_brush = painter.brush()

        # Check for hover state (hovering over item)
        is_hovered = option.state & QtWidgets.QStyle.State_MouseOver

        # Get icon and text
        icon = item.icon()
        text = item.text()

        if is_hovered:
            # Draw background color
            painter.setBrush(QtCore.Qt.lightGray)
            painter.drawRect(option.rect)

            # Change text color on hover
            painter.setPen(QtCore.Qt.red)

        # Calculate icon rectangle (horizontally centered)
        icon_width = option.decorationSize.width()
        icon_height = option.decorationSize.height()
        icon_x = option.rect.x() + (option.rect.width() - icon_width) // 2
        icon_y = option.rect.y()
        icon_rect = QtCore.QRect(icon_x, icon_y, icon_width, icon_height)

        # Calculate text rectangle below the icon
        text_x = option.rect.x()
        text_y = icon_y + icon_height + self.icon_text_spacing
        text_rect = QtCore.QRect(
            text_x, text_y, option.rect.width(), option.rect.height() - icon_height - self.icon_text_spacing
        )

        # Draw the icon
        if not icon.isNull():
            icon.paint(painter, icon_rect, QtCore.Qt.AlignCenter)

        # Prepare to render the text
        font_metrics = painter.fontMetrics()
        lines = self.word_wrap(text, font_metrics, text_rect.width(), max_lines=2)

        # Draw each line
        line_height = font_metrics.lineSpacing()
        for i, line in enumerate(lines):
            line_y = text_rect.y() + i * line_height
            painter.drawText(
                QtCore.QRect(text_rect.x(), line_y, text_rect.width(), line_height),
                QtCore.Qt.AlignCenter, line
            )

        # Restore the original pen color
        painter.setPen(original_pen_color)

        # Restore the original brush after custom painting
        painter.setBrush(original_brush)

    @staticmethod
    def word_wrap(text, font_metrics, max_width, max_lines=2):
        """
        Simulates word wrapping and returns a list of lines.

        Parameters:
            - text: The input string to wrap.
            - font_metrics: QFontMetrics object for measuring text.
            - max_width: Maximum width of each line.
            - max_lines: Maximum number of lines allowed.

        Returns:
            A list of wrapped lines (up to max_lines).
        """
        if max_lines <= 1:
            return font_metrics.elidedText(text, QtCore.Qt.ElideRight, max_width)

        words = text.split()
        lines = []
        current_line = ""

        for index, word in enumerate(words):
            # Check if adding the next word exceeds the width
            test_line = f"{current_line} {word}".strip()
            if font_metrics.horizontalAdvance(test_line) <= max_width:
                current_line = test_line
            else:
                # Push the current line if not empty
                if current_line:
                    lines.append(current_line)

                if len(lines) == max_lines - 1:
                    # Put everything remaining words on the last line
                    current_line = " ".join(words[index:])

                    # Elide the line if needed
                    if font_metrics.horizontalAdvance(current_line) > max_width:
                        current_line = font_metrics.elidedText(current_line, QtCore.Qt.ElideRight, max_width)

                    break
                else:
                    # Start a new line
                    current_line = word

        # Add the last line
        lines.append(current_line)

        return lines

    def sizeHint(self, option, index):
        """
        Adjust the size hint to accommodate icon, spacing, and text wrapping.
        """
        base_size = super().sizeHint(option, index)
        font_metrics = option.fontMetrics
        line_height = font_metrics.lineSpacing()  # Height of one text line
        text_height = line_height * 2  # Two lines of text at most
        total_height = base_size.height() + self.icon_text_spacing + text_height
        return QtCore.QSize(base_size.width(), total_height)


class CustomDeuxDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def initStyleOption(self, option, index):
        lines = self.word_wrap(option.text, option.fontMetrics, option.rect.width(), max_lines=2)
        if len(lines) == 1:
            option.text = lines[0]
        else:
            option.text = "\n".join(lines)

        super().initStyleOption(option, index)

    @staticmethod
    def word_wrap(text, font_metrics, max_width, max_lines=2):
        """
        Simulates word wrapping and returns a list of lines.

        Parameters:
            - text: The input string to wrap.
            - font_metrics: QFontMetrics object for measuring text.
            - max_width: Maximum width of each line.
            - max_lines: Maximum number of lines allowed.

        Returns:
            A list of wrapped lines (up to max_lines).
        """
        if max_lines <= 1:
            return font_metrics.elidedText(text, QtCore.Qt.ElideRight, max_width)

        words = text.split()
        lines = []
        current_line = ""

        for index, word in enumerate(words):
            # Check if adding the next word exceeds the width
            test_line = f"{current_line} {word}".strip()
            if font_metrics.horizontalAdvance(test_line) <= max_width:
                current_line = test_line
            else:
                # Push the current line if not empty
                if current_line:
                    lines.append(current_line)

                if len(lines) == max_lines - 1:
                    # Put everything remaining words on the last line
                    current_line = " ".join(words[index:])

                    # Elide the line if needed
                    if font_metrics.horizontalAdvance(current_line) > max_width:
                        current_line = font_metrics.elidedText(current_line, QtCore.Qt.ElideRight, max_width)

                    break
                else:
                    # Start a new line
                    current_line = word

        # Add the last line
        lines.append(current_line)

        return lines

    # def sizeHint(self, option, index):
    #     """
    #     Adjust the size hint to accommodate icon, spacing, and text wrapping.
    #     """
    #     base_size = super().sizeHint(option, index)
    #     font_metrics = option.fontMetrics
    #     line_height = font_metrics.lineSpacing()  # Height of one text line
    #     text_height = line_height * 2  # Two lines of text at most
    #     total_height = base_size.height() + self.icon_text_spacing + text_height
    #     return QtCore.QSize(base_size.width(), total_height)


class UserActionsModel(QtGui.QStandardItemModel):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.default_icon = qtawesome.icon("fa.cube", color="white")

        self._registered_actions = list()
        self.items_by_id = {}

    def update_actions(self):
        self.items_by_id.clear()
        # Validate actions based on compatibility
        self.clear()

        action_popup = {
            "name": "display_popup",
        }
        toto1 = QtGui.QStandardItem(self.default_icon, "Send Popup Message")
        toto1.setData("Display a popup message on the user screen", QtCore.Qt.ToolTipRole)
        toto1.setData(action_popup, QtCore.Qt.UserRole)
        toto1.setSizeHint(QtCore.QSize(90, 100))
        self.items_by_id["toto1"] = toto1

        action_display = {
            "name": "display_notification",
        }
        tata1 = QtGui.QStandardItem(self.default_icon, "Send Tray Notification")
        tata1.setData("Display a tray notification on the user screen", QtCore.Qt.ToolTipRole)
        tata1.setData(action_display, QtCore.Qt.UserRole)
        tata1.setSizeHint(QtCore.QSize(90, 100))
        self.items_by_id["tata1"] = tata1

        action_change_role = {
            "name": "change_role",
        }
        toto2 = QtGui.QStandardItem(self.default_icon, "Change Role")
        toto2.setData("Change the role of the user", QtCore.Qt.ToolTipRole)
        toto2.setData(action_change_role, QtCore.Qt.UserRole)
        toto2.setSizeHint(QtCore.QSize(90, 100))
        self.items_by_id["toto2"] = toto2

        action_delete = {
            "name": "delete_user",
        }
        tata2 = QtGui.QStandardItem(self.default_icon, "Delete User")
        tata2.setData("Delete the user", QtCore.Qt.ToolTipRole)
        tata2.setData(action_delete, QtCore.Qt.UserRole)
        tata2.setSizeHint(QtCore.QSize(90, 100))
        self.items_by_id["tata2"] = tata2

        self.beginResetModel()

        for item in self.items_by_id.values():
            self.appendRow(item)

        self.endResetModel()


class UserActionsListView(QtWidgets.QListView):
    def __init__(self, parent=None):
        super().__init__(parent)

    def wheelEvent(self, event):
        event.ignore()


class UserActionsWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedHeight(120)

        view = UserActionsListView(self)
        view.setProperty("mode", "icon")
        view.setObjectName("IconView")
        view.setViewMode(QtWidgets.QListView.IconMode)
        view.setResizeMode(QtWidgets.QListView.Fixed)
        view.setSelectionMode(QtWidgets.QListView.NoSelection)
        view.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        # Force horizontal layout with no wrapping
        view.setFlow(QtWidgets.QListView.LeftToRight)  # Horizontal layout
        view.setWrapping(False)

        # Set horizontal scroll only
        view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        view.setGridSize(QtCore.QSize(90, 100))
        view.setIconSize(QtCore.QSize(40, 40))
        view.setWordWrap(True)

        self.model = UserActionsModel(self)
        view.setModel(self.model)

        # Set custom delegate
        view.setItemDelegate(CustomDeuxDelegate(self))

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(view)

        self.view = view

        self.view.clicked.connect(self.on_item_clicked)

    def on_item_clicked(self, index):
        if not index or not index.isValid():
            return

        action = index.data(QtCore.Qt.UserRole)
        print(action["name"])

    def update_actions(self):
        self.model.update_actions()


class CheckUsersOnlineThread(QtCore.QThread):
    apply_online_icon_to_user = QtCore.Signal(list, str)  # Signal to apply icon to users

    def __init__(self, manager):
        super(CheckUsersOnlineThread, self).__init__(manager)
        self._manager = manager
        self._wait_time_secs = 5.0
        self._refresh_rate_secs = 0.5

    def run(self):
        not_yet_responded_users = list(self._manager.users_data.keys())
        # Remove the current user from the list
        not_yet_responded_users.remove(self._manager.current_user_id)

        event_id = send_event(
            "/ping",
            "post",
            expire_in_secs=5,
            expect_responses=True,
        )
        start_time = time.monotonic()

        while True:
            if not self._manager.is_running:
                return

            time.sleep(self._refresh_rate_secs)

            event_doc = get_event_doc(event_id)

            new_responses_users = []
            if event_doc["responses"]:
                for response in event_doc["responses"]:
                    curr_response_user_id = response["user_id"]
                    if curr_response_user_id in not_yet_responded_users:
                        # It's a new response!
                        new_responses_users.append(curr_response_user_id)

                        # Remove form the list of users that dit not yet responded
                        not_yet_responded_users.remove(curr_response_user_id)

                if new_responses_users:
                    # Emit signal for users who responded
                    self.apply_online_icon_to_user.emit(new_responses_users, "online_icon")

            if time.monotonic() - start_time >= self._wait_time_secs:
                break

        if not_yet_responded_users:
            # Emit signal for users who did not respond in the allowed response time
            self.apply_online_icon_to_user.emit(not_yet_responded_users, "offline_icon")


class SortUserRoleItem(QtWidgets.QTableWidgetItem):
    def __lt__(self, other):
        return str(self.data(QtCore.Qt.ItemDataRole.UserRole)) < str(other.data(QtCore.Qt.ItemDataRole.UserRole))


class UserManagerWidget(BaseControlPanelWidget):
    address_bar_class = AddressBar

    _ws_profile_prefix = "last_workstation_profile/"
    _tracker_login_prefix = "tracker_logins/"
    _table_column_data = [
        ("_is_online", "Online"),
        (_ws_profile_prefix + "username", "Username"),
        ("user_id", "ID"),
        ("role", "Role"),
        ("_tracker_logins", "Generated in constructor"),
        ("last_connection_timestamp", "Last Connection"),
        (_ws_profile_prefix + "workstation_name", "Last Workstation Name")
    ]

    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)

        self._footer_btn_text = "Enjoy!"

        self._curr_user_id = get_user_id()
        self.users_data = {}

        self.table_widget = None
        self.actions_widget = None
        self._is_running = True
        self._selected_user_id = None
        self._current_sort_column = 1
        self._current_sort_order = QtCore.Qt.SortOrder.AscendingOrder

        self._spin_icon = resources.get_resource("icons", "spin.svg")

        user_online_icon = QtGui.QPixmap(resources.get_resource("icons", "circle_green.png"))
        self._user_online_icon = user_online_icon.scaled(24, 24,
                                                         QtCore.Qt.KeepAspectRatio,
                                                         QtCore.Qt.SmoothTransformation)
        user_offline_icon = QtGui.QPixmap(resources.get_resource("icons", "circle_red.png"))
        self._user_offline_icon = user_offline_icon.scaled(24, 24,
                                                           QtCore.Qt.KeepAspectRatio,
                                                           QtCore.Qt.SmoothTransformation)

        self._check_users_online_thread = CheckUsersOnlineThread(self)
        self._check_users_online_thread.apply_online_icon_to_user.connect(self._update_online_icon_for_users)

        # Generate the column template
        self.table_column_data = {}
        for (column_id, column_display_name) in self._table_column_data:
            if column_id == "_tracker_logins":
                # Handle special column
                active_trackers = self._get_active_trackers()
                for tracker_name in active_trackers:
                    tracker_column_id = self._tracker_login_prefix + tracker_name
                    self.table_column_data[tracker_column_id] = f"{tracker_name.capitalize()} Login"

                continue  # To skip adding this placeholder column_id

            self.table_column_data[column_id] = column_display_name

        self._column_count = len(self.table_column_data.keys())

        self.create_ui()

    @staticmethod
    def _get_active_trackers():
        # Currently no proper function to do that in a lib module
        active_trackers = []
        global_settings = get_global_settings()

        tracker_names = ["ftrack", "kitsu"]
        for tracker_name in tracker_names:
            if global_settings[ADDONS_SETTINGS_KEY][tracker_name]["enabled"] and \
                    global_settings[ADDONS_SETTINGS_KEY][tracker_name]["server"]:
                active_trackers.append(tracker_name)

        return active_trackers

    @property
    def current_user_id(self):
        return self._curr_user_id

    @property
    def is_running(self):
        return self._is_running

    @property
    def user_online_icon(self):
        return self._user_online_icon

    @property
    def user_offline_icon(self):
        return self._user_offline_icon

    def create_loader_widget(self):
        loader_container = QtWidgets.QWidget()
        loader_layout = QtWidgets.QHBoxLayout(loader_container)
        loader_layout.setContentsMargins(0, 0, 0, 0)
        loader_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Add the SVG widget to the layout
        loader_svg = QtSvgWidgets.QSvgWidget(self._spin_icon)
        loader_svg.setFixedSize(24, 24)
        loader_layout.addWidget(loader_svg)

        return loader_container

    def update_column_widths(self):
        available_width = self.parent().width()
        self.table_widget.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
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

        for column_index in range(columns_count - 1):
            self.table_widget.horizontalHeader().setSectionResizeMode(column_index,
                                                                      QtWidgets.QHeaderView.ResizeMode.Fixed)
            self.table_widget.setColumnWidth(column_index, columns_size[column_index] + additional_width_column)

        if additional_width_column:
            # This means, without adding width, the sum of column wouldn't take the full width
            # Stretching the last column to ensure the row will be fully filled
            last_column_index = columns_count - 1
            self.table_widget.horizontalHeader().setSectionResizeMode(last_column_index,
                                                                      QtWidgets.QHeaderView.ResizeMode.Stretch)

    @staticmethod
    def _create_icon_widget(icon_pixmap):
        online_icon_widget = QtWidgets.QLabel()
        online_icon_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        online_icon_widget.setPixmap(icon_pixmap)

        return online_icon_widget

    def get_row_index_by_user_id(self, user_id):
        items = self.table_widget.findItems(user_id, QtCore.Qt.MatchExactly)
        if items:
            return items[0].row()
        return -1

    def _disable_sorting(self):
        self._current_sort_column = self.table_widget.horizontalHeader().sortIndicatorSection()
        self._current_sort_order = self.table_widget.horizontalHeader().sortIndicatorOrder()

        self.table_widget.setSortingEnabled(False)

    def _enable_sorting(self):
        self.table_widget.horizontalHeader().setSortIndicator(
            self._current_sort_column,
            self._current_sort_order
        )

        self.table_widget.setSortingEnabled(True)

    def _update_online_icon_for_users(self, user_list, icon_name):
        self._disable_sorting()
        if icon_name == "online_icon":
            sorting_value_prefix = "0_"
            icon = self._user_online_icon
        elif icon_name == "offline_icon":
            sorting_value_prefix = "2_"
            icon = self._user_offline_icon
        else:
            return

        for user_id in user_list:
            user_row = self.get_row_index_by_user_id(user_id)

            # Properly clean the cell icon (if present)
            cell_widget = self.table_widget.cellWidget(user_row, 0)
            if cell_widget:
                self.table_widget.removeCellWidget(user_row, 0)
                cell_widget.deleteLater()

            self.table_widget.setCellWidget(user_row, 0, self._create_icon_widget(icon))

            # Update the hidden sorting item
            # this is to be able to sort by online status
            sorting_value = sorting_value_prefix+self.users_data[user_id][self._ws_profile_prefix+"username"]

            item = self.table_widget.item(user_row, 0)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, sorting_value)

        self._enable_sorting()

    def _add_users_to_table(self):
        for row_index, (user_id, user_data) in enumerate(self.users_data.items()):
            self.table_widget.insertRow(row_index)

            for column_index, (key, cell_data) in enumerate(user_data.items()):
                if column_index >= self._column_count:
                    # Skipping the extra data added for other purposes than table content
                    continue

                if isinstance(cell_data, str):
                    item = QtWidgets.QTableWidgetItem(cell_data)
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                else:
                    sorting_value_prefix = "1_"
                    if isinstance(cell_data, QtWidgets.QLabel):
                        # This means this is the current user
                        sorting_value_prefix = "0_"

                    sorting_value = sorting_value_prefix+user_data[self._ws_profile_prefix+"username"]

                    item = SortUserRoleItem()
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, sorting_value)
                    self.table_widget.setCellWidget(row_index, column_index, cell_data)

                self.table_widget.setItem(row_index, column_index, item)

    def _update_user_list(self):
        if self._check_users_online_thread.isRunning():
            # Stop the thread that updates the user online status
            self._check_users_online_thread.quit()

        self._disable_sorting()

        # Cleanup the stored data
        self.users_data = {}

        # Remove all the rows (if any)
        self.table_widget.setRowCount(0)

        # Get the user profiles
        user_profiles = get_all_user_profiles()

        # Populate the table
        for index, user_profile in enumerate(user_profiles):
            user_id = user_profile["user_id"]
            user_data = {}

            # Aggregate the user data
            last_workstation_profile = \
                user_profile["workstation_profiles"][user_profile["last_workstation_profile_index"]]

            for user_profile_key in self.table_column_data:
                if user_profile_key == "_is_online":
                    if self._curr_user_id == user_id:
                        cell_value = self._create_icon_widget(self._user_online_icon)
                    else:
                        cell_value = self.create_loader_widget()
                elif user_profile_key.startswith(self._ws_profile_prefix):
                    cell_value = last_workstation_profile[user_profile_key.removeprefix(self._ws_profile_prefix)]
                else:
                    splitted = user_profile_key.split("/")
                    cell_value = user_profile
                    for curr_key in splitted:
                        if curr_key not in cell_value:
                            # Protection to avoid crash if a key isn't in the user profile
                            cell_value = ""
                            break
                        cell_value = cell_value[curr_key]

                if isinstance(cell_value, datetime):
                    # Convert datetime to string (close to the ISO 8601 standard)
                    cell_value = cell_value.strftime("%Y-%m-%d, %H:%M:%S")

                user_data[user_profile_key] = cell_value

            self.users_data[user_id] = user_data

        check_online_status = True
        if user_profiles.retrieved == 0:
            # No profile found, this should be impossible unless the
            # collection has been cleared while QuadPype was running

            # Inserting an empty row to avoid issues
            self.users_data["dummy"] = {curr_index: "" for curr_index in range(len(self.table_column_data))}

            check_online_status = False

        self._add_users_to_table()

        # Re-apply the selection (selected row)
        if self._selected_user_id:
            current_row_index = self.get_row_index_by_user_id(self._selected_user_id)
        else:
            current_row_index = 0
        self.table_widget.selectRow(current_row_index)

        self._enable_sorting()

        if check_online_status:
            self._check_users_online_thread.start(QtCore.QThread.HighestPriority)

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

        self.actions_widget.update_actions()

    def create_ui(self):
        super().create_ui()

        self.address_bar_label.setText("Search:")

        # First creating the actions widget
        self.actions_widget = UserActionsWidget(self.content_widget)

        # Then the table user list widget
        self.table_widget = QtWidgets.QTableWidget(self.content_widget)

        self.table_widget.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table_widget.verticalHeader().hide()
        self.table_widget.setColumnCount(len(self.table_column_data))
        self.table_widget.setHorizontalHeaderLabels(list(self.table_column_data.values()))

        # Set selection mode to only allow single row selection
        self.table_widget.setSelectionMode(QtWidgets.QTableWidget.SelectionMode.SingleSelection)
        self.table_widget.setSelectionBehavior(QtWidgets.QTableWidget.SelectionBehavior.SelectRows)

        self.table_widget.selectionModel().selectionChanged.connect(self.on_selection_changed)

        self.table_widget.setSortingEnabled(True)

        # Initially sort by the "Username" column (index 1)
        self.table_widget.sortItems(1)

        self._update_user_list()

        # Add the user list widget to the layout
        self.content_layout.addWidget(self.table_widget, stretch=1)

        # Then add the actions widget to the layout
        self.content_layout.addWidget(self.actions_widget)

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

    def find_users_from_input(self, input_text):
        users = []

        if not input_text:
            # Nothing
            return users

        search_column_id = "user_id"
        search_term = input_text
        if ":" in input_text:
            # Advance search
            column_input, search_term = input_text.split(":", maxsplit=1)
            if not column_input or not search_term:
                # Invalid
                return None

            search_column_id = None
            search_term = search_term.strip()

            column_input = column_input.strip().lower()
            for column_id, column_name in self.table_column_data.items():
                column_name_with_underscores = column_name.lower().replace(" ", "_")
                column_name_with_dashes = column_name.lower().replace(" ", "-")
                column_name_without_spaces = column_name.lower().replace(" ", "")

                valid_column_names = [
                    column_id,
                    column_name.lower(),
                    column_name_with_underscores,
                    column_name_with_dashes,
                    column_name_without_spaces
                ]
                if column_input in valid_column_names:
                    search_column_id = column_id
                    break

            if not search_column_id:
                # Invalid column identifier
                return None

        for user_id, user_data in self.users_data.items():
            if search_column_id == "user_id" and search_term == user_id:
                users.append(user_id)
                break
            for key, cell_data in user_data.items():
                if search_column_id == key and search_term == cell_data:
                    users.append(user_id)
                    break

        return users

    def _on_path_focus_in(self):
        self.address_bar.path_input.setProperty("style", "normal")
        self.address_bar.path_input.style().polish(self.address_bar.path_input)

    def select_user(self, user_id):
        if user_id:
            user_row_index = self.get_row_index_by_user_id(user_id)
            self._selected_user_id = user_id
            self.table_widget.selectRow(user_row_index)
        else:
            self.table_widget.clearSelection()

        self.actions_widget.update_actions()

    def _on_path_edited(self, path):
        address_bar_style = "normal"
        users = self.find_users_from_input(path)

        if users is None:
            address_bar_style = "error"
        elif not users:
            address_bar_style = "warning"

        self.address_bar.path_input.setProperty("style", address_bar_style)
        self.address_bar.path_input.style().unpolish(self.address_bar.path_input)
        self.address_bar.path_input.style().polish(self.address_bar.path_input)

        if not users:
            # No match
            return

        if len(users) == 1:
            # A single match
            self.select_user(users[0])
            return

        # Multiple matches
        self.select_user(None)
        # TODO: Handle this case
        # for matching_user_id in users:
        #     user_row_index = self.get_row_index_by_user_id(matching_user_id)
        #     for column_index in range(self._column_count):
        #         table_item = self.table_widget.item(user_row_index, column_index)
        #         table_item.setProperty("style", "highlighted")

    def _on_refresh_button_pressed(self):
        self._update_user_list()

    def _on_footer_button_pressed(self):
        pass

    def closeEvent(self, event):
        # Clean up thread before the widget is removed / closed
        self._is_running = False
        if self._check_users_online_thread and self._check_users_online_thread.isRunning():
            self._check_users_online_thread.wait()
        super().closeEvent(event)

    def __del__(self):
        self._is_running = False
        # Ensure thread cleanup in case the widget is destroyed
        if self._check_users_online_thread and self._check_users_online_thread.isRunning():
            self._check_users_online_thread.quit()
