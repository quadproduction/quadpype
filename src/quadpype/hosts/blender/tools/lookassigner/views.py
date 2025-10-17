from qtpy import QtWidgets, QtCore


class View(QtWidgets.QTreeView):
    data_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setAlternatingRowColors(False)
        self.setSortingEnabled(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

    def get_indices(self):
        """Get the selected rows"""
        selection_model = self.selectionModel()
        return selection_model.selectedRows()
