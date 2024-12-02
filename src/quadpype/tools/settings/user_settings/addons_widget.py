from qtpy import QtWidgets

from quadpype.settings import ADDONS_SETTINGS_KEY
from quadpype.tools.settings.settings.categories import (
    StandaloneCategoryWidget
)


class LocalAddonsWidgets(QtWidgets.QWidget):
    def __init__(self, global_settings_entity, parent):
        super().__init__(parent)

        self.addons_data = {}
        self.global_settings_entity = global_settings_entity

        for entity in self.global_settings_entity[ADDONS_SETTINGS_KEY].children:
            entity_name = entity.key if entity.gui_type is False else str(entity.id)
            entity_value = entity.value if entity.gui_type is False else None
            self.addons_data[entity_name] = {
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

    def _reset_addons_widgets(self):
        while self.content_layout.count() > 0:
            item = self.content_layout.itemAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setVisible(False)
            self.content_layout.removeItem(item)

        for addon_name, data in self.addons_data.items():
            addon_widget = self.fake_category_widget.create_ui_for_entity(
                self.fake_category_widget,
                data["entity"],
                self.fake_category_widget)

            addon_widget.set_entity_value()

            self.addons_data[addon_name]["widget"] = addon_widget

    def update_user_settings(self, value):
        if not value:
            value = {}

        self._reset_addons_widgets()

        for addon_name, data in self.addons_data.items():
            curr_value = value.get(addon_name)
            if curr_value is None:
                continue

            data["widget"].entity.set(curr_value)
            data["widget"].set_entity_value()

    def settings_value(self):
        output = {}
        for addon_name, data in self.addons_data.items():
            if data["is_gui"]:
                continue

            value = data["entity"].value
            # Is the current value different from the official settings values?
            if value != data["settings_value"]:
                output[addon_name] = value

        return output if output else None
