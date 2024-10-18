from qtpy import QtWidgets

from openpype.settings import MODULES_SETTINGS_KEY
from openpype.tools.settings.settings.categories import (
    StandaloneCategoryWidget
)


class LocalModulesWidgets(QtWidgets.QWidget):
    def __init__(self, system_settings_entity, parent):
        super(LocalModulesWidgets, self).__init__(parent)

        self.modules_data = {}
        self.system_settings_entity = system_settings_entity

        for module_name, entity in self.system_settings_entity[MODULES_SETTINGS_KEY].items():
            self.modules_data[module_name] = {
                "entity": entity,
                "widget": None,
                "settings_value": entity.value
            }

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.content_layout = layout

        self.fake_category_widget = StandaloneCategoryWidget(self, layout)

    def _reset_modules_widgets(self):
        while self.content_layout.count() > 0:
            item = self.content_layout.itemAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setVisible(False)
            self.content_layout.removeItem(item)

        for module_name, data in  self.modules_data.items():
            module_widget = self.fake_category_widget.create_ui_for_entity(
                self.fake_category_widget,
                data["entity"],
                self.fake_category_widget)

            module_widget.set_entity_value()

            self.modules_data[module_name]["widget"] = module_widget
            self.content_layout.addWidget(module_widget)

    def update_local_settings(self, value):
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
            value = data["entity"].value
            # Is the current value different from the official settings values?
            if value != data["settings_value"]:
                output[module_name] = value
        return output if output else None
