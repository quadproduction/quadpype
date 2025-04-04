import os
import collections
import uuid
import json

from qtpy import QtWidgets, QtCore, QtGui

from quadpype.lib import FileDefItem
from quadpype.tools.utils import (
    paint_image_with_color,
    ClickableLabel,
)
# TODO change imports
from quadpype.tools.resources import get_image
from quadpype.tools.utils import (
    IconButton,
)

from quadpype.plugins.publish.extract_review import IMAGE_EXTS, VIDEO_EXTS

ITEM_ID_ROLE = QtCore.Qt.UserRole + 1
ITEM_LABEL_ROLE = QtCore.Qt.UserRole + 2
FILENAMES_ROLE = QtCore.Qt.UserRole + 4
DIRPATH_ROLE = QtCore.Qt.UserRole + 5
IS_DIR_ROLE = QtCore.Qt.UserRole + 6
IS_SEQUENCE_ROLE = QtCore.Qt.UserRole + 7
EXT_ROLE = QtCore.Qt.UserRole + 8

PURPLE_BG = QtGui.QColor(128, 0, 128, int(0.5 * 255))
ORANGE_BG = QtGui.QColor(255, 165, 0, int(0.5 * 255))
YELLOW_BG = QtGui.QColor(255, 255, 0, int(0.5 * 255))


def convert_bytes_to_json(bytes_value):
    if isinstance(bytes_value, QtCore.QByteArray):
        # Raw data are already QByteArray and we don't have to load them
        encoded_data = bytes_value
    else:
        encoded_data = QtCore.QByteArray.fromRawData(bytes_value)
    stream = QtCore.QDataStream(encoded_data, QtCore.QIODevice.ReadOnly)
    text = stream.readQString()
    try:
        return json.loads(text)
    except Exception:
        return None


def convert_data_to_bytes(data):
    bytes_value = QtCore.QByteArray()
    stream = QtCore.QDataStream(bytes_value, QtCore.QIODevice.WriteOnly)
    stream.writeQString(json.dumps(data))
    return bytes_value


class SupportLabel(QtWidgets.QLabel):
    pass


class DropEmpty(QtWidgets.QWidget):
    _empty_extensions = "Any file"

    def __init__(self, single_item, allow_sequences, extensions_label, parent):
        super().__init__(parent)

        drop_label_widget = QtWidgets.QLabel("Drag & Drop files here", self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addSpacing(20)
        layout.addWidget(drop_label_widget, 0, alignment=QtCore.Qt.AlignCenter)
        layout.addSpacing(30)
        layout.addStretch(1)

        drop_label_widget.setAlignment(QtCore.Qt.AlignCenter)
        drop_label_widget.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        update_size_timer = QtCore.QTimer()
        update_size_timer.setInterval(10)
        update_size_timer.setSingleShot(True)

        self._update_size_timer = update_size_timer

        if extensions_label and not extensions_label.startswith(" "):
            extensions_label = " " + extensions_label

        self._single_item = single_item
        self._extensions_label = extensions_label
        self._allow_sequences = allow_sequences
        self._allowed_extensions = set()
        self._allow_folders = None

        self._drop_label_widget = drop_label_widget

        self.set_allow_folders(False)

    def set_extensions(self, extensions):
        if extensions:
            extensions = {
                ext.replace(".", "")
                for ext in extensions
            }
        if extensions == self._allowed_extensions:
            return
        self._allowed_extensions = extensions

        self._update_items_label()

    def set_allow_folders(self, allowed):
        if self._allow_folders == allowed:
            return

        self._allow_folders = allowed
        self._update_items_label()

    def _update_items_label(self):
        allowed_items = []
        if self._allow_folders:
            allowed_items.append("folder")

        if self._allowed_extensions:
            allowed_items.append("file")
            if self._allow_sequences:
                allowed_items.append("sequence")

        if not self._single_item:
            allowed_items = [item + "s" for item in allowed_items]

        if not allowed_items:
            self._drop_label_widget.setVisible(False)
            return

        self._drop_label_widget.setVisible(True)
        self._update_size_timer.start()

    def resizeEvent(self, event):
        super(DropEmpty, self).resizeEvent(event)
        self._update_size_timer.start()

    def paintEvent(self, event):
        super(DropEmpty, self).paintEvent(event)

        pen = QtGui.QPen()
        pen.setBrush(QtCore.Qt.darkGray)
        pen.setStyle(QtCore.Qt.DashLine)
        pen.setWidth(1)

        content_margins = self.layout().contentsMargins()
        rect = self.rect()
        left_m = content_margins.left() + pen.width()
        top_m = content_margins.top() + pen.width()
        new_rect = QtCore.QRect(
            left_m,
            top_m,
            (
                    rect.width()
                    - (left_m + content_margins.right() + pen.width())
            ),
            (
                    rect.height()
                    - (top_m + content_margins.bottom() + pen.width())
            )
        )

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(pen)
        painter.drawRect(new_rect)


class ButtonStandardItem(QtGui.QStandardItemModel):
    def __init__(self, icon_path, parent=None):
        super().__init__(parent)
        pixmap = paint_image_with_color(get_image(filename=icon_path), QtCore.Qt.white)
        self.setIcon(QtGui.QIcon(pixmap))


class FilesModel(QtGui.QStandardItemModel):
    def __init__(self, single_item, allow_sequences, allow_reviews):
        super().__init__()

        self._id = str(uuid.uuid4())
        self._single_item = single_item
        self._multivalue = False
        self._allow_sequences = allow_sequences
        self._allow_reviews = allow_reviews

        self._items_by_id = {}
        self._file_items_by_id = {}
        self._filenames_by_dirpath = collections.defaultdict(set)
        self._items_by_dirpath = collections.defaultdict(list)

        self.rowsAboutToBeRemoved.connect(self._on_about_to_be_removed)
        self.rowsInserted.connect(self._on_insert)

    @property
    def id(self):
        return self._id

    def get_root_items(self):
        return [item for item in self._all_items if item.is_root()]

    def _on_about_to_be_removed(self, parent_index, start, end):
        """Make sure that removed items are removed from items mapping.

        Connected with '_on_insert'. When user drag item and drop it to same
        view the item is actually removed and creqted again but it happens in
        inner calls of Qt.
        """

        for row in range(start, end + 1):
            index = self.index(row, 0, parent_index)
            item_id = index.data(ITEM_ID_ROLE)
            if item_id is not None:
                self._items_by_id.pop(item_id, None)

    def _on_insert(self, parent_index, start, end):
        """Make sure new added items are stored in items mapping.

        Connected to '_on_about_to_be_removed'. Some items are not created
        using '_create_item' but are recreated using Qt. So the item is not in
        mapping and if it would not lead to same item pointer.
        """

        for row in range(start, end + 1):
            index = self.index(start, end, parent_index)
            item_id = index.data(ITEM_ID_ROLE)
            if item_id not in self._items_by_id:
                self._items_by_id[item_id] = self.item(row)

    def set_multivalue(self, multivalue):
        """Disable filtering."""

        if self._multivalue == multivalue:
            return
        self._multivalue = multivalue

    def add_filepaths(self, items, parent_item_index=None):
        if not items:
            return

        if self._multivalue:
            _items = []
            for item in items:
                if isinstance(item, (tuple, list, set)):
                    _items.extend(item)
                else:
                    _items.append(item)
            items = _items

        file_items = FileDefItem.from_value(items, self._allow_sequences)
        if not file_items:
            return

        if not self._multivalue and self._single_item:
            file_items = [file_items[0]]
            current_ids = list(self._file_items_by_id.keys())
            if current_ids:
                self.remove_item_by_ids(current_ids)

        new_model_items = []
        for file_item in file_items:
            item_id, model_item = self._create_item(file_item)
            new_model_items.append([model_item])
            self._file_items_by_id[item_id] = file_item
            self._items_by_id[item_id] = model_item

        if new_model_items:
            if parent_item_index is None or not parent_item_index.isValid() or not self._allow_reviews:
                parent_item = self.invisibleRootItem()
            else:
                parent_item = self.itemFromIndex(parent_item_index)

            # Ensure the first item is the parent, and others are children
            for idx, items in enumerate(new_model_items):
                if idx == 0:
                    parent_item.appendRow(items)
                else:
                    first_model_item = new_model_items[0][0]
                    first_model_item.appendRow(items)

    def remove_item_by_ids(self, item_ids):
        if not item_ids:
            return

        items_to_remove = []
        for item_id in set(item_ids):
            item = self._items_by_id.pop(item_id, None)
            if item:
                self._file_items_by_id.pop(item_id, None)
                items_to_remove.append(item)

        for item in items_to_remove:
            parent_item = item.parent() or self.invisibleRootItem()
            parent_item.removeRow(item.row())

    def get_file_item_by_id(self, item_id):
        return self._file_items_by_id.get(item_id)

    def _create_item(self, file_item):
        item = QtGui.QStandardItem()
        item_id = str(uuid.uuid4())
        item.setData(item_id, ITEM_ID_ROLE)
        item.setData(file_item.label or "< empty >", ITEM_LABEL_ROLE)
        item.setData(file_item.filenames, FILENAMES_ROLE)
        item.setData(file_item.directory, DIRPATH_ROLE)
        item.setData(file_item.lower_ext, EXT_ROLE)
        item.setData(file_item.is_dir, IS_DIR_ROLE)
        item.setData(file_item.is_sequence, IS_SEQUENCE_ROLE)

        return item_id, item

    def mimeData(self, indexes):
        item_ids = [
            index.data(ITEM_ID_ROLE)
            for index in indexes
        ]

        item_ids_data = convert_data_to_bytes(item_ids)
        mime_data = super(FilesModel, self).mimeData(indexes)
        mime_data.setData("files_widget/internal_move", item_ids_data)

        file_items = []
        for item_id in item_ids:
            file_item = self.get_file_item_by_id(item_id)
            if file_item:
                file_items.append(file_item.to_dict())

        full_item_data = convert_data_to_bytes({
            "items": file_items,
            "id": self._id
        })
        mime_data.setData("files_widget/full_data", full_item_data)
        return mime_data

    def dropMimeData(self, mime_data, action, row, col, parent_index):
        if action != QtCore.Qt.MoveAction:
            return False

        # Retrieve item IDs from mime data
        item_ids = convert_bytes_to_json(mime_data.data("files_widget/internal_move"))
        if item_ids is None:
            return False

        # Find the target parent item
        if parent_index.isValid() and self._allow_reviews:
            target_item = self.itemFromIndex(parent_index)
        else:
            target_item = self.invisibleRootItem()

        # Collect and safely move items
        items_to_move = []
        for item_id in item_ids:
            item = self._items_by_id.get(item_id)
            if item:
                parent_item = item.parent() or self.invisibleRootItem()
                row_items = parent_item.takeRow(item.row())
                if row_items:
                    items_to_move.append(row_items[0])  # Assuming single column

        if not items_to_move:
            return False

        # Ensure no nested structures; flatten if necessary
        for item in items_to_move:
            # If the item has children, flatten them to the root level
            while item.hasChildren():
                child = item.takeRow(0)[0]  # Take the first child
                self.invisibleRootItem().appendRow(child)
                self._items_by_id[child.data(ITEM_ID_ROLE)] = child

            # Add the item to the new parent (or root if target is invisibleRootItem)
            target_item.appendRow(item)
            self._items_by_id[item.data(ITEM_ID_ROLE)] = item
        return True

    def canDropMimeData(self, mime_data, action, row, col, parent_index):
        # Allow only root-level drops
        if parent_index.isValid():
            target_item = self.itemFromIndex(parent_index)
            if target_item.parent() is not None:
                return False
        return super().canDropMimeData(mime_data, action, row, col, parent_index)


class FilesProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._allow_folders = False
        self._allowed_extensions = None
        self._multivalue = False

    def set_multivalue(self, multivalue):
        """Disable filtering."""

        if self._multivalue == multivalue:
            return
        self._multivalue = multivalue
        self.invalidateFilter()

    def set_allow_folders(self, allow=None):
        if allow is None:
            allow = not self._allow_folders

        if allow == self._allow_folders:
            return
        self._allow_folders = allow
        self.invalidateFilter()

    def set_allowed_extensions(self, extensions=None):
        if extensions is not None:
            _extensions = set()
            if self.sourceModel()._allow_reviews:
                extensions = extensions.union(IMAGE_EXTS).union(VIDEO_EXTS)
            for ext in set(extensions):
                if not ext.startswith("."):
                    ext = ".{}".format(ext)
                _extensions.add(ext.lower())
            extensions = _extensions

        if self._allowed_extensions != extensions:
            self._allowed_extensions = extensions
            self.invalidateFilter()

    def are_valid_files(self, filepaths):
        for filepath in filepaths:
            if os.path.isfile(filepath):
                _, ext = os.path.splitext(filepath)
                if ext.lower() in self._allowed_extensions:
                    return True

            elif self._allow_folders:
                return True
        return False

    def filter_valid_files(self, filepaths):
        filtered_paths = []
        for filepath in filepaths:
            if os.path.isfile(filepath):
                _, ext = os.path.splitext(filepath)
                if ext.lower() in self._allowed_extensions:
                    filtered_paths.append(filepath)

            elif self._allow_folders:
                filtered_paths.append(filepath)
        return filtered_paths

    def filterAcceptsRow(self, row, parent_index):
        # Skip filtering if multivalue is set
        if self._multivalue:
            return True

        model = self.sourceModel()
        index = model.index(row, self.filterKeyColumn(), parent_index)
        # First check if item is folder and if folders are enabled
        if index.data(IS_DIR_ROLE):
            if not self._allow_folders:
                return False
            return True

        # Check if there are any allowed extensions
        if self._allowed_extensions is None:
            return False

        if index.data(EXT_ROLE) not in self._allowed_extensions:
            return False
        return True

    def lessThan(self, left, right):
        left_comparison = left.data(DIRPATH_ROLE)
        right_comparison = right.data(DIRPATH_ROLE)
        if left_comparison == right_comparison:
            left_comparison = left.data(ITEM_LABEL_ROLE)
            right_comparison = right.data(ITEM_LABEL_ROLE)

        if sorted((left_comparison, right_comparison))[0] == left_comparison:
            return True
        return False

    def mapToSourceIndex(self, proxyIndex):
        return self.mapToSource(proxyIndex)


class ItemWidget(QtWidgets.QWidget):
    context_menu_requested = QtCore.Signal(QtCore.QPoint)
    delete_requested = QtCore.Signal(list)
    review_value_changed = QtCore.Signal()

    def __init__(self, item_id, label, is_sequence, multivalue, model_index, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._item_id = item_id
        self._allow_reviews = model_index.model().sourceModel()._allow_reviews
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        label_widget = QtWidgets.QLabel(label, self)

        label_size_hint = label_widget.sizeHint()
        height = label_size_hint.height()
        actions_menu_pix = paint_image_with_color(get_image(filename="menu.png"), QtCore.Qt.white)
        self._review_pix = paint_image_with_color(get_image(filename="review.png"), QtCore.Qt.white).scaledToHeight(height)
        self._review_disabled_pix = paint_image_with_color(get_image(filename="review_disabled.png"), QtCore.Qt.white).scaledToHeight(height)
        delete_pix = paint_image_with_color(get_image(filename="delete.png"), QtCore.Qt.white).scaledToHeight(height)

        review_btn = ClickableLabel(self)
        review_btn.setFixedSize(height, height)
        if self._allow_reviews:
            review_btn.setPixmap(self._review_pix)

        delete_btn = ClickableLabel(self)
        delete_btn.setFixedSize(height, height)
        delete_btn.setPixmap(delete_pix)

        split_btn = ClickableLabel(self)
        split_btn.setFixedSize(height, height)
        split_btn.setPixmap(actions_menu_pix)
        if multivalue:
            split_btn.setVisible(False)
        else:
            split_btn.setVisible(is_sequence)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(label_widget, 1)
        if self._allow_reviews:
            layout.addWidget(review_btn, 0)
            review_btn.clicked.connect(self._on_review_actions_clicked)
        layout.addWidget(delete_btn, 0)
        layout.addWidget(split_btn, 0)

        delete_btn.clicked.connect(self._on_delete_actions_clicked)
        split_btn.clicked.connect(self._on_split_actions_clicked)

        self._item = QtCore.QPersistentModelIndex(model_index)
        self._label_widget = label_widget
        self._split_btn = split_btn
        self._review_btn = review_btn or None
        self._delete_btn = delete_btn
        self._actions_menu_pix = actions_menu_pix
        self._last_scaled_pix_height = None
        self._review_state = True
        self._is_representation_enabled = True

        self.update_visibility()

    def update_visibility(self):
        """Update visibility of the buttons based on the rules."""
        parent_is_valid = self._item.parent().isValid()
        has_children = self._item.model().hasChildren(self._item)
        source_model = self._item.model().sourceModel()
        file_item = source_model.get_file_item_by_id(self._item_id)

        if parent_is_valid:
            if self._allow_reviews:
                self._review_btn.setVisible(False)
            file_item.set_representation(False)
            return

        if not has_children:
            if self._allow_reviews:
                self._review_btn.setVisible(True)
        else:
            if self._allow_reviews:
                self._review_btn.setVisible(False)
            file_item.set_review(False)
        file_item.set_representation(True)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        rect = self.rect()

        parent_is_valid = self._item.parent().isValid() if self._item else False
        has_children = self._item.model().hasChildren(self._item) if self._item else False
        is_review = self._item.model().sourceModel().get_file_item_by_id(self._item_id).is_review
        is_representation = self._item.model().sourceModel().get_file_item_by_id(self._item_id).is_representation

        if is_representation:
            color = QtGui.QColor(PURPLE_BG)

        if parent_is_valid and is_review:
            color = QtGui.QColor(YELLOW_BG)

        if is_representation and is_review and not has_children:
            color = QtGui.QColor(ORANGE_BG)

        # Paint the background
        painter.fillRect(rect, color)
        super().paintEvent(event)

    def _update_btn_size(self):
        label_size_hint = self._label_widget.sizeHint()
        height = label_size_hint.height()
        if height == self._last_scaled_pix_height:
            return
        self._last_scaled_pix_height = height
        self._split_btn.setFixedSize(height, height)
        pix = self._actions_menu_pix.scaled(
            height, height,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        self._split_btn.setPixmap(pix)

    def activate_review_btn(self):
        source_model = self._item.model().sourceModel()
        source_model.get_file_item_by_id(self._item_id).set_review(True)
        self._review_btn.setPixmap(self._review_pix)
        self._review_state = False

    def desactivate_review_btn(self):
        source_model = self._item.model().sourceModel()
        source_model.get_file_item_by_id(self._item_id).set_review(False)
        self._review_btn.setPixmap(self._review_disabled_pix)
        self._review_state = True

    def showEvent(self, event):
        super(ItemWidget, self).showEvent(event)
        self._update_btn_size()

    def resizeEvent(self, event):
        super(ItemWidget, self).resizeEvent(event)
        self._update_btn_size()

    def _on_split_actions_clicked(self):
        pos = self._split_btn.rect().bottomLeft()
        point = self._split_btn.mapToGlobal(pos)
        self.context_menu_requested.emit(point)

    def _on_review_actions_clicked(self):
        if self._review_state:
            self.activate_review_btn()
        else:
            self.desactivate_review_btn()
        self.update()
        self.review_value_changed.emit()

    def _on_delete_actions_clicked(self):
        self.delete_requested.emit([self._item_id])


class InViewButton(IconButton):
    pass


class FilesView(QtWidgets.QTreeView):
    """View showing instances and their groups."""

    remove_requested = QtCore.Signal()
    context_menu_requested = QtCore.Signal(QtCore.QPoint)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.customContextMenuRequested.connect(self._on_context_menu_request)
        self._multivalue = False
        self.header().hide()
        self.setDropIndicatorShown(True)

    def setModel(self, model):
        """Override setModel to connect signals after model is set."""
        super().setModel(model)

    def set_multivalue(self, multivalue):
        """Disable remove button on multivalue."""

        self._multivalue = multivalue

    def has_selected_item_ids(self):
        """Is any index selected."""
        for index in self.selectionModel().selectedIndexes():
            instance_id = index.data(ITEM_ID_ROLE)
            if instance_id is not None:
                return True
        return False

    def get_selected_item_ids(self):
        """Ids of selected instances."""

        selected_item_ids = set()
        for index in self.selectionModel().selectedIndexes():
            instance_id = index.data(ITEM_ID_ROLE)
            if instance_id is not None:
                selected_item_ids.add(instance_id)
        return selected_item_ids

    def has_selected_sequence(self):
        for index in self.selectionModel().selectedIndexes():
            if index.data(IS_SEQUENCE_ROLE):
                return True
        return False

    def event(self, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if (
                event.key() == QtCore.Qt.Key_Delete
                and self.has_selected_item_ids()
            ):
                self.remove_requested.emit()
                return True

        return super(FilesView, self).event(event)

    def _on_context_menu_request(self, pos):
        index = self.indexAt(pos)
        if index.isValid():
            point = self.viewport().mapToGlobal(pos)
            self.context_menu_requested.emit(point)


class FilesWidget(QtWidgets.QFrame):
    value_changed = QtCore.Signal()

    def __init__(self, single_item, allow_sequences, extensions_label, allow_reviews, parent):
        super().__init__(parent)
        self.setAcceptDrops(True)

        empty_widget = DropEmpty(
            single_item, allow_sequences, extensions_label, self
        )

        files_model = FilesModel(single_item, allow_sequences, allow_reviews)
        files_proxy_model = FilesProxyModel()
        files_proxy_model.setSourceModel(files_model)
        files_view = FilesView(self)
        files_view.setModel(files_proxy_model)

        main_layout = QtWidgets.QVBoxLayout(self)
        allowed_files_representation_layout = QtWidgets.QHBoxLayout()
        allowed_files_review_layout = QtWidgets.QHBoxLayout()
        color_legend_layout = QtWidgets.QHBoxLayout()
        stacked_layout = QtWidgets.QStackedLayout()
        stacked_layout.setContentsMargins(0, 0, 0, 0)
        stacked_layout.setStackingMode(QtWidgets.QStackedLayout.StackAll)
        stacked_layout.addWidget(empty_widget)
        stacked_layout.addWidget(files_view)
        stacked_layout.setCurrentWidget(empty_widget)
        main_layout.addLayout(stacked_layout)

        files_proxy_model.rowsInserted.connect(self._on_rows_inserted)
        files_proxy_model.dataChanged.connect(self._update_visibility)
        files_proxy_model.rowsRemoved.connect(self._on_rows_removed)
        files_view.remove_requested.connect(self._on_remove_requested)
        files_view.context_menu_requested.connect(self._on_context_menu_requested)

        instruction_label = QtWidgets.QLabel("<i>Drag & drop to add or re-organize elements</i>")
        instruction_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        main_layout.addWidget(instruction_label, alignment=QtGui.Qt.AlignCenter)

        representations_label = QtWidgets.QLabel(f"Allowed File type for representations:")
        representations_label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        self.allowed_representations_label = QtWidgets.QLabel()
        self.allowed_representations_label.setWordWrap(True)
        self.allowed_representations_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                                         QtWidgets.QSizePolicy.Preferred)

        review_label = QtWidgets.QLabel(f"Allowed File type for reviews:")
        review_label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        self.allowed_reviews_label = QtWidgets.QLabel(', '.join(IMAGE_EXTS+VIDEO_EXTS))
        self.allowed_reviews_label.setWordWrap(True)
        self.allowed_reviews_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                                 QtWidgets.QSizePolicy.Preferred)

        allowed_files_representation_layout.addWidget(representations_label, 0, alignment=QtGui.Qt.AlignTop | QtGui.Qt.AlignLeft)
        allowed_files_representation_layout.addWidget(self.allowed_representations_label, 1)
        main_layout.addLayout(allowed_files_representation_layout)

        if allow_reviews:
            allowed_files_review_layout.addWidget(review_label, 0, alignment=QtGui.Qt.AlignTop | QtGui.Qt.AlignLeft)
            allowed_files_review_layout.addWidget(self.allowed_reviews_label, 1)
            main_layout.addLayout(allowed_files_review_layout)

        color_legend_label = QtWidgets.QLabel()
        color_legend_label.setPixmap(self._create_legend_pixmap())
        color_legend_layout.addWidget(color_legend_label)
        main_layout.addLayout(color_legend_layout)

        self._in_set_value = False
        self._single_item = single_item
        self._multivalue = False

        self._empty_widget = empty_widget
        self._files_model = files_model
        self._files_proxy_model = files_proxy_model
        self._files_view = files_view

        self._widgets_by_id = {}

        self._layout = main_layout
        self._stacked_layout = stacked_layout

    @staticmethod
    def _create_legend_pixmap():
        width, height = 300, 100

        pixmap = QtGui.QPixmap(width, height)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)

        items = [
            (PURPLE_BG, "Representation elements"),
            (ORANGE_BG, "Representation & review (same file) elements"),
            (YELLOW_BG, "Review elements"),
        ]

        font = QtGui.QFont("Poppins", 10)
        painter.setFont(font)

        x_offset, y_offset = 10, 10
        rect_size = 20

        for qcolor, label in items:
            # Draw color box
            painter.setBrush(qcolor)
            painter.setPen(QtGui.QColor("#bfccd6"))
            painter.drawRect(x_offset, y_offset, rect_size, rect_size)

            # Draw label text
            painter.setPen(QtGui.QColor("#bfccd6"))
            painter.drawText(x_offset + rect_size + 10, y_offset + rect_size - 5, label)
            y_offset += rect_size + 10

        painter.end()
        return pixmap

    def _set_multivalue(self, multivalue):
        if self._multivalue is multivalue:
            return
        self._multivalue = multivalue
        self._files_view.set_multivalue(multivalue)
        self._files_model.set_multivalue(multivalue)
        self._files_proxy_model.set_multivalue(multivalue)
        self.setEnabled(not multivalue)

    def set_value(self, value, multivalue):
        self._in_set_value = True

        widget_ids = set(self._widgets_by_id.keys())
        self._remove_item_by_ids(widget_ids)

        self._set_multivalue(multivalue)

        self._add_filepaths(value)

        self._in_set_value = False

    def current_value(self):
        file_items_data = []

        # Iterate over all rows in the model
        for row in range(self._files_proxy_model.rowCount()):
            index = self._files_proxy_model.index(row, 0)

            # Check if the current item is a root item (no parent)
            parent_index = self._files_proxy_model.parent(index)
            if not parent_index.isValid():  # This is a root item
                item = self._files_model.get_file_item_by_id(index.data(ITEM_ID_ROLE))  # Get the corresponding file item

                if item:
                    item_dict = item.to_dict()
                    children_data = []
                    if self._files_proxy_model.rowCount(index) > 0:  # Has children
                        for child_row in range(self._files_proxy_model.rowCount(index)):
                            child_index = self._files_proxy_model.index(child_row, 0, index)
                            child_item_id = child_index.data(ITEM_ID_ROLE)
                            child_item = self._files_model.get_file_item_by_id(child_item_id)
                            if child_item:
                                children_data.append(child_item.to_dict())
                    elif item.is_review:
                        children_data.append(item.to_dict())
                    item_dict['reviewable'] = children_data

                    file_items_data.append(item_dict)
        # Return the data or an empty item if no root items exist
        if file_items_data:
            return file_items_data

        empty_item = FileDefItem.create_empty_item()
        return empty_item.to_dict()

    def set_filters(self, folders_allowed, exts_filter):
        self._files_proxy_model.set_allow_folders(folders_allowed)
        self._files_proxy_model.set_allowed_extensions(exts_filter)
        self.allowed_representations_label.setText(", ".join(ext.strip('.') for ext in exts_filter))
        self._empty_widget.set_extensions(exts_filter)
        self._empty_widget.set_allow_folders(folders_allowed)

    def _on_rows_inserted(self, parent_index, start_row, end_row):
        for row in range(start_row, end_row + 1):
            index = self._files_proxy_model.index(row, 0, parent_index)
            item_id = index.data(ITEM_ID_ROLE)
            if item_id in self._widgets_by_id:
                continue
            label = index.data(ITEM_LABEL_ROLE)
            is_sequence = index.data(IS_SEQUENCE_ROLE)
            widget = ItemWidget(
                item_id,
                label,
                is_sequence,
                self._multivalue,
                index
            )
            widget.review_value_changed.connect(self.value_changed.emit)
            file_item = self._files_model.get_file_item_by_id(item_id)
            if file_item.is_review:
                widget.activate_review_btn()
            else:
                widget.desactivate_review_btn()
            widget.context_menu_requested.connect(
                self._on_context_menu_requested
            )
            widget.delete_requested.connect(
                self._remove_item_by_ids
            )
            self._files_view.setIndexWidget(index, widget)
            self._files_proxy_model.setData(
                index, widget.sizeHint(), QtCore.Qt.SizeHintRole
            )
            self._widgets_by_id[item_id] = widget

        if not self._in_set_value:
            self.value_changed.emit()

        self._update_visibility()

    def _on_rows_removed(self, parent_index, start_row, end_row):
        available_item_ids = set()
        for row in range(self._files_proxy_model.rowCount()):
            index = self._files_proxy_model.index(row, 0)
            item_id = index.data(ITEM_ID_ROLE)
            available_item_ids.add(item_id)

        widget_ids = set(self._widgets_by_id.keys())
        for item_id in available_item_ids:
            if item_id in widget_ids:
                widget_ids.remove(item_id)

        for item_id in widget_ids:
            widget = self._widgets_by_id.pop(item_id)
            widget.setVisible(False)
            widget.destroy()

        if not self._in_set_value:
            self.value_changed.emit()
        self._update_visibility()

    def _on_split_request(self):
        if self._multivalue:
            return

        item_ids = self._files_view.get_selected_item_ids()
        if not item_ids:
            return

        for item_id in item_ids:
            file_item = self._files_model.get_file_item_by_id(item_id)
            if not file_item:
                return

            new_items = file_item.split_sequence()
            self._add_filepaths(new_items)
        self._remove_item_by_ids(item_ids)
        self._update_visibility()

    def _on_remove_requested(self):
        if self._multivalue:
            return

        items_to_delete = self._files_view.get_selected_item_ids()
        if items_to_delete:
            self._remove_item_by_ids(items_to_delete)

    def _on_context_menu_requested(self, pos):
        if self._multivalue:
            return

        menu = QtWidgets.QMenu(self._files_view)

        if self._files_view.has_selected_sequence():
            split_action = QtWidgets.QAction("Split sequence", menu)
            split_action.triggered.connect(self._on_split_request)
            menu.addAction(split_action)

        remove_action = QtWidgets.QAction("Remove", menu)
        remove_action.triggered.connect(self._on_remove_requested)
        menu.addAction(remove_action)

        menu.popup(pos)

    def dragEnterEvent(self, event):
        if self._multivalue:
            return

        mime_data = event.mimeData()
        if mime_data.hasUrls():
            filepaths = []
            for url in mime_data.urls():
                filepath = url.toLocalFile()
                if os.path.exists(filepath):
                    filepaths.append(filepath)

            if self._files_proxy_model.are_valid_files(filepaths):
                event.setDropAction(QtCore.Qt.CopyAction)
                event.accept()

        full_data_value = mime_data.data("files_widget/full_data")
        if self._handle_full_data_drag(full_data_value):
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()

    def dragLeaveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        if self._multivalue:
            return

        mime_data = event.mimeData()

        if mime_data.hasUrls():
            event.accept()
            filepaths = []
            for url in mime_data.urls():
                filepath = url.toLocalFile()
                if os.path.exists(filepath):
                    filepaths.append(filepath)

            filepaths = self._files_proxy_model.filter_valid_files(filepaths)

            if filepaths:
                parent_index = self._files_view.indexAt(event.pos())
                parent_index_source = self._files_proxy_model.mapToSourceIndex(parent_index)

                # This is a child item, so we reject the drop
                if parent_index_source.isValid() and parent_index_source.parent().isValid():
                    event.ignore()
                    return

                self._files_model.add_filepaths(filepaths, parent_index_source)

        if self._handle_full_data_drop(mime_data.data("files_widget/full_data")):
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()

        super(FilesWidget, self).dropEvent(event)

    def _handle_full_data_drag(self, value):
        if value is None:
            return False

        full_data = convert_bytes_to_json(value)
        if full_data is None:
            return False

        if full_data["id"] == self._files_model.id:
            return False
        return True

    def _handle_full_data_drop(self, value):
        if value is None:
            return False

        full_data = convert_bytes_to_json(value)
        if full_data is None:
            return False

        if full_data["id"] == self._files_model.id:
            return False

        for item in full_data["items"]:
            filepaths = [
                os.path.join(item["directory"], filename)
                for filename in item["filenames"]
            ]
            filepaths = self._files_proxy_model.filter_valid_files(filepaths)
            if filepaths:
                self._add_filepaths(filepaths)

        if self._copy_modifiers_enabled():
            return False
        return True

    def _copy_modifiers_enabled(self):
        if (
            QtWidgets.QApplication.keyboardModifiers()
            & QtCore.Qt.ControlModifier
        ):
            return True
        return False

    def _add_filepaths(self, filepaths, parent_item=None):
        self._files_model.add_filepaths(filepaths, parent_item)

    def _remove_item_by_ids(self, item_ids):
        self._files_model.remove_item_by_ids(item_ids)

    def _update_visibility(self):
        files_exists = self._files_proxy_model.rowCount() > 0
        if files_exists:
            current_widget = self._files_view
            for row in range(self._files_proxy_model.rowCount()):
                index = self._files_proxy_model.index(row, 0)
                widget = self._files_view.indexWidget(index)
                if isinstance(widget, ItemWidget):
                    widget.update_visibility()
        else:
            current_widget = self._empty_widget
        self._stacked_layout.setCurrentWidget(current_widget)
