from qtpy import QtWidgets, QtCore, QtGui


def indented_print(data, indent=0):
    spaces = " " * (indent * 4)
    if not isinstance(data, dict):
        print("{}{}".format(spaces, data))
        return

    for key, value in data.items():
        print("{}{}".format(spaces, key))
        indented_print(value, indent + 1)


class SelectableMenu(QtWidgets.QMenu):

    selection_changed = QtCore.Signal()

    def mouseReleaseEvent(self, event):
        action = self.activeAction()
        if action and action.isEnabled():
            action.trigger()
            self.selection_changed.emit()
        else:
            super(SelectableMenu, self).mouseReleaseEvent(event)

    def event(self, event):
        result = super(SelectableMenu, self).event(event)
        if event.type() == QtCore.QEvent.Type.Show:
            parent = self.parent()

            move_point = parent.mapToGlobal(QtCore.QPoint(0, parent.height()))
            check_point = (
                move_point
                + QtCore.QPoint(self.width(), self.height())
            )

            screens = QtGui.QGuiApplication.screens()
            combined_rect = QtCore.QRect()
            for screen in screens:
                combined_rect = combined_rect.united(screen.geometry())

            if not combined_rect.contains(check_point):
                move_point -= QtCore.QPoint(0, parent.height() + self.height())
            self.move(move_point)

            self.updateGeometry()
            self.repaint()

        return result


class AddibleComboBox(QtWidgets.QComboBox):
    """Searchable ComboBox with empty placeholder value as first value"""

    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)

        self.setEditable(True)
        # self.setInsertPolicy(QtWidgets.QComboBox.NoInsert)

        self.lineEdit().setPlaceholderText(placeholder)
        # self.lineEdit().returnPressed.connect(self.on_return_pressed)

        # Apply completer settings
        completer = self.completer()
        completer.setCompletionMode(completer.CompletionMode.PopupCompletion)
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)

    # def on_return_pressed(self):
    #     text = self.lineEdit().text().strip()
    #     if not text:
    #         return
    #
    #     index = self.findText(text)
    #     if index < 0:
    #         self.addItems([text])
    #         index = self.findText(text)

    def populate(self, items):
        self.clear()
        # self.addItems([""])     # ensure first item is placeholder
        self.addItems(items)

    def get_valid_value(self):
        """Return the current text if it's a valid value else None

        Note: The empty placeholder value is valid and returns as ""

        """

        text = self.currentText()
        lookup = set(self.itemText(i) for i in range(self.count()))
        if text not in lookup:
            return None

        return text or None


class MultiselectEnum(QtWidgets.QWidget):

    selection_changed = QtCore.Signal()

    def __init__(self, title, parent=None):
        super().__init__(parent)
        tool_button = QtWidgets.QToolButton(self)
        tool_button.setText(title)

        tool_menu = SelectableMenu(tool_button)

        tool_button.setMenu(tool_menu)
        tool_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tool_button)

        self.setLayout(layout)

        tool_menu.selection_changed.connect(self.selection_changed)

        self.toolbutton = tool_button
        self.toolmenu = tool_menu
        self.main_layout = layout

    def populate(self, items):
        self.toolmenu.clear()
        self.addItems(items)

    def addItems(self, items):
        for item in items:
            action = self.toolmenu.addAction(item)
            action.setCheckable(True)
            action.setChecked(True)
            self.toolmenu.addAction(action)

    def items(self):
        for action in self.toolmenu.actions():
            yield action
