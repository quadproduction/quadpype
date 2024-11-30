from qtpy import QtWidgets

from quadpype.settings import ADDONS_SETTINGS_KEY
from quadpype.tools.settings.settings.categories import (
    StandaloneCategoryWidget
)


class LocalModulesWidgets(QtWidgets.QWidget):
    def __init__(self, global_settings_entity, parent):
        super().__init__(parent)

        self.modules_data = {}
        self.global_settings_entity = global_settings_entity

        for entity in self.global_settings_entity[ADDONS_SETTINGS_KEY].children:
            entity_name = entity.key if entity.gui_type is False else str(entity.id)
            entity_value = entity.value if entity.gui_type is False else None
            self.modules_data[entity_name] = {
                "entity": entity,
                "widget": None,
                "is_gui": entity.gui_type,
                "settings_value": entity_value
            }

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.content_layout = layout

        self.fake_category_widget = StandaloneCategoryWidget(self, layout)

    def _reset_modules_widgets(self):
        while self.content_layout.count() > 0:
            item = self.content_layout.itemAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setVisible(False)
            self.content_layout.removeItem(item)

        for module_name, data in self.modules_data.items():
            module_widget = self.fake_category_widget.create_ui_for_entity(
                self.fake_category_widget,
                data["entity"],
                self.fake_category_widget)

            module_widget.set_entity_value()

            self.modules_data[module_name]["widget"] = module_widget

    def update_user_settings(self, value):
        if not value:
            value = {}

        self._reset_modules_widgets()

        for module_name, data in self.modules_data.items():
            curr_value = value.get(module_name)
            if curr_value is None:
                continue

            data["widget"].entity.set(curr_value)
            data["widget"].set_entity_value()

    def settings_value(self):
        output = {}
        for module_name, data in self.modules_data.items():
            if data["is_gui"]:
                continue

            value = data["entity"].value
            # Is the current value different from the official settings values?
            if value != data["settings_value"]:
                output[module_name] = value

        return output if output else None
