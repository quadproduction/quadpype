from qtpy import QtWidgets, QtCore, QtGui
import sys
import os
import collections
import uuid
import json
import clique

ITEM_ID_ROLE = QtCore.Qt.UserRole + 1
ITEM_LABEL_ROLE = QtCore.Qt.UserRole + 2
ITEM_ICON_ROLE = QtCore.Qt.UserRole + 3
FILENAMES_ROLE = QtCore.Qt.UserRole + 4
DIRPATH_ROLE = QtCore.Qt.UserRole + 5
IS_DIR_ROLE = QtCore.Qt.UserRole + 6
IS_SEQUENCE_ROLE = QtCore.Qt.UserRole + 7
EXT_ROLE = QtCore.Qt.UserRole + 8

# /***********************************************************************************/
# /*********************************** UTILS *****************************************/
# /***********************************************************************************/
def get_icon_path(icon_name=None, filename=None):
    """Path to image in './images' folder."""
    if icon_name is None and filename is None:
        return None

    if filename is None:
        filename = "{}.png".format(icon_name)

    path = os.path.join(
        r"C:\Users\ccaillot\quad\quadpype\src\quadpype\tools\resources\images",
        filename
    )
    if os.path.exists(path):
        return path
    return None
def get_image(icon_name=None, filename=None):
    """Load image from './images' as QImage."""
    path = get_icon_path(icon_name, filename)
    if path:
        return QtGui.QImage(path)
    return None
def paint_image_with_color(image, color):
    """Redraw image with single color using it's alpha.

        It is expected that input image is singlecolor image with alpha.

        Args:
            image (QImage): Loaded image with alpha.
            color (QColor): Color that will be used to paint image.
        """
    width = image.width()
    height = image.height()

    alpha_mask = image.createAlphaMask()
    alpha_region = QtGui.QRegion(QtGui.QBitmap.fromImage(alpha_mask))

    pixmap = QtGui.QPixmap(width, height)
    pixmap.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(pixmap)
    render_hints = (
            QtGui.QPainter.Antialiasing
            | QtGui.QPainter.SmoothPixmapTransform
    )
    # Deprecated since 5.14
    if hasattr(QtGui.QPainter, "Antialiasing"):
        render_hints |= QtGui.QPainter.Antialiasing
    painter.setRenderHints(render_hints)

    painter.setClipRegion(alpha_region)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(color)
    painter.drawRect(QtCore.QRect(0, 0, width, height))
    painter.end()

    return pixmap
def convert_bytes_to_json(bytes_value):
    if isinstance(bytes_value, QtCore.QByteArray):
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
# /***********************************************************************************/
# /********************************** ItemWidget *************************************/
# /***********************************************************************************/
class ClickableLabel(QtWidgets.QLabel):
    """Label that catch left mouse click and can trigger 'clicked' signal."""
    clicked = QtCore.Signal()

    def __init__(self, parent):
        super().__init__(parent)

        self._mouse_pressed = False

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._mouse_pressed = True
        super(ClickableLabel, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._mouse_pressed:
            self._mouse_pressed = False
            if self.rect().contains(event.pos()):
                self.clicked.emit()

        super(ClickableLabel, self).mouseReleaseEvent(event)
class PixmapLabel(QtWidgets.QLabel):
    """Label resizing image to height of font."""
    def __init__(self, pixmap, parent):
        super().__init__(parent)
        self._empty_pixmap = QtGui.QPixmap(0, 0)
        self._source_pixmap = pixmap

        self._last_width = 0
        self._last_height = 0

    def set_source_pixmap(self, pixmap):
        """Change source image."""
        self._source_pixmap = pixmap
        self._set_resized_pix()

    def _get_pix_size(self):
        size = self.fontMetrics().height()
        size += size % 2
        return size, size

    def minimumSizeHint(self):
        width, height = self._get_pix_size()
        if width != self._last_width or height != self._last_height:
            self._set_resized_pix()
        return QtCore.QSize(width, height)

    def _set_resized_pix(self):
        if self._source_pixmap is None:
            self.setPixmap(self._empty_pixmap)
            return
        width, height = self._get_pix_size()
        self.setPixmap(
            self._source_pixmap.scaled(
                width,
                height,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
        )
        self._last_width = width
        self._last_height = height

    def resizeEvent(self, event):
        self._set_resized_pix()
        super(PixmapLabel, self).resizeEvent(event)


class ItemWidget(QtWidgets.QWidget):
    context_menu_requested = QtCore.Signal(QtCore.QPoint)
    delete_requested = QtCore.Signal(list)

    def __init__(self, item_id, label, pixmap_icon, is_sequence, multivalue, parent=None):
        super().__init__(parent)
        self._item_id = item_id

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        icon_widget = PixmapLabel(pixmap_icon, self)
        label_widget = QtWidgets.QLabel(label, self)

        label_size_hint = label_widget.sizeHint()
        height = label_size_hint.height()
        actions_menu_pix = paint_image_with_color(get_image(filename="menu.png"), QtCore.Qt.white)
        self._review_pix = paint_image_with_color(get_image(filename="review.png"),
                                                  QtCore.Qt.white).scaledToHeight(height)
        self._review_disabled_pix = paint_image_with_color(get_image(filename="review_disabled.png"),
                                                           QtCore.Qt.white).scaledToHeight(height)
        delete_pix = paint_image_with_color(get_image(filename="delete.png"), QtCore.Qt.white).scaledToHeight(height)

        review_btn = ClickableLabel(self)
        review_btn.setFixedSize(height, height)
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
        layout.addWidget(icon_widget, 0)
        layout.addWidget(label_widget, 1)
        layout.addWidget(review_btn, 0)
        layout.addWidget(delete_btn, 0)
        layout.addWidget(split_btn, 0)

        review_btn.clicked.connect(self._on_review_actions_clicked)
        delete_btn.clicked.connect(self._on_delete_actions_clicked)
        split_btn.clicked.connect(self._on_split_actions_clicked)

        self._icon_widget = icon_widget
        self._label_widget = label_widget
        self._split_btn = split_btn
        self._review_btn = review_btn
        self._delete_btn = delete_btn
        self._actions_menu_pix = actions_menu_pix
        self._last_scaled_pix_height = None
        self._is_review_enabled = True

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
        self._is_review_enabled = not self._is_review_enabled
        if self._is_review_enabled:
            self._review_btn.setPixmap(self._review_pix)
        else:
            self._review_btn.setPixmap(self._review_disabled_pix)

    def _on_delete_actions_clicked(self):
        self.delete_requested.emit([self._item_id])

# /***********************************************************************************/
# /***********************************************************************************/
# /***********************************************************************************/


class DropEmpty(QtWidgets.QWidget):
    _empty_extensions = "Any file"

    def __init__(self, single_item, allow_sequences, extensions_label, parent):
        super().__init__(parent)

        drop_label_widget = QtWidgets.QLabel("Drag & Drop files here", self)

        items_label_widget = QtWidgets.QLabel(self)
        items_label_widget.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addSpacing(20)
        layout.addWidget(drop_label_widget, 0, alignment=QtCore.Qt.AlignCenter)
        layout.addSpacing(30)
        layout.addStretch(1)
        layout.addWidget(items_label_widget, 0, alignment=QtCore.Qt.AlignCenter)
        layout.addSpacing(10)

        for widget in (drop_label_widget,items_label_widget,):
            widget.setAlignment(QtCore.Qt.AlignCenter)
            widget.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        update_size_timer = QtCore.QTimer()
        update_size_timer.setInterval(10)
        update_size_timer.setSingleShot(True)

        update_size_timer.timeout.connect(self._on_update_size_timer)

        self._update_size_timer = update_size_timer

        if extensions_label and not extensions_label.startswith(" "):
            extensions_label = " " + extensions_label

        self._single_item = single_item
        self._extensions_label = extensions_label
        self._allow_sequences = allow_sequences
        self._allowed_extensions = set()
        self._allow_folders = None

        self._drop_label_widget = drop_label_widget
        self._items_label_widget = items_label_widget

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
            self._items_label_widget.setText(
                "It is not allowed to add anything here!"
            )
            return

        self._drop_label_widget.setVisible(True)
        items_label = "Multiple "
        if self._single_item:
            items_label = "Single "

        if len(allowed_items) == 1:
            extensions_label = allowed_items[0]
        elif len(allowed_items) == 2:
            extensions_label = " or ".join(allowed_items)
        else:
            last_item = allowed_items.pop(-1)
            new_last_item = " or ".join([last_item, allowed_items.pop(-1)])
            allowed_items.append(new_last_item)
            extensions_label = ", ".join(allowed_items)

        allowed_items_label = extensions_label

        items_label += allowed_items_label
        label_tooltip = None
        if self._allowed_extensions:
            items_label += " of\n{}".format(
                ", ".join(sorted(self._allowed_extensions))
            )

        if self._extensions_label:
            label_tooltip = items_label
            items_label = self._extensions_label

        if self._items_label_widget.text() == items_label:
            return

        self._items_label_widget.setToolTip(label_tooltip)
        self._items_label_widget.setText(items_label)
        self._update_size_timer.start()

    def resizeEvent(self, event):
        super(DropEmpty, self).resizeEvent(event)
        self._update_size_timer.start()

    def _on_update_size_timer(self):
        """Recalculate height of label with extensions.

        Dynamic QLabel with word wrap does not handle properly it's sizeHint
        calculations on show. This way it is recalculated. It is good practice
        to trigger this method with small offset using '_update_size_timer'.
        """

        width = self._items_label_widget.width()
        height = self._items_label_widget.heightForWidth(width)
        self._items_label_widget.setMinimumHeight(height)
        self._items_label_widget.updateGeometry()

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

class FileDefItem(object):
    def __init__(
        self,
        directory,
        filenames,
        frames = None,
        template = None,
    ):
        self.directory: str = directory

        self.filenames = []
        self.is_sequence = False
        self.template = None
        self.frames = []
        self.is_empty = True

        self.set_filenames(filenames, frames, template)

    def __str__(self):
        return json.dumps(self.to_dict())

    def __repr__(self):
        if self.is_empty:
            filename = "< empty >"
        elif self.is_sequence:
            filename = self.template
        else:
            filename = self.filenames[0]

        return "<{}: \"{}\">".format(
            self.__class__.__name__,
            os.path.join(self.directory, filename)
        )

    @property
    def label(self):
        if self.is_empty:
            return None

        if not self.is_sequence:
            return self.filenames[0]

        frame_start = self.frames[0]
        filename_template = os.path.basename(self.template)
        if len(self.frames) == 1:
            return "{} [{}]".format(filename_template, frame_start)

        frame_end = self.frames[-1]
        expected_len = (frame_end - frame_start) + 1
        if expected_len == len(self.frames):
            return "{} [{}-{}]".format(
                filename_template, frame_start, frame_end
            )

        ranges = []
        _frame_start = None
        _frame_end = None
        for frame in range(frame_start, frame_end + 1):
            if frame not in self.frames:
                add_to_ranges = _frame_start is not None
            elif _frame_start is None:
                _frame_start = _frame_end = frame
                add_to_ranges = frame == frame_end
            else:
                _frame_end = frame
                add_to_ranges = frame == frame_end

            if add_to_ranges:
                if _frame_start != _frame_end:
                    _range = "{}-{}".format(_frame_start, _frame_end)
                else:
                    _range = str(_frame_start)
                ranges.append(_range)
                _frame_start = _frame_end = None
        return "{} [{}]".format(
            filename_template, ",".join(ranges)
        )

    def split_sequence(self):
        if not self.is_sequence:
            raise ValueError("Cannot split single file item")

        paths = [
            os.path.join(self.directory, filename)
            for filename in self.filenames
        ]
        return self.from_paths(paths, False)

    @property
    def ext(self):
        if self.is_empty:
            return None
        _, ext = os.path.splitext(self.filenames[0])
        if ext:
            return ext
        return None

    @property
    def lower_ext(self):
        ext = self.ext
        if ext is not None:
            return ext.lower()
        return ext

    @property
    def is_dir(self) -> bool:
        if self.is_empty:
            return False

        # QUESTION a better way how to define folder (in init argument?)
        if self.ext:
            return False
        return True

    def set_directory(self, directory: str):
        self.directory = directory

    def set_filenames(
        self,
        filenames,
        frames= None,
        template= None,
    ):
        if frames is None:
            frames = []
        is_sequence = False
        if frames:
            is_sequence = True

        if is_sequence and not template:
            raise ValueError("Missing template for sequence")

        self.is_empty = len(filenames) == 0
        self.filenames = filenames
        self.template = template
        self.frames = frames
        self.is_sequence = is_sequence

    @classmethod
    def create_empty_item(cls):
        return cls("", [])

    @classmethod
    def from_value(
        cls,
        value,
        allow_sequences: bool
    ):
        """Convert passed value to FileDefItem objects.

        Returns:
            list: Created FileDefItem objects.
        """

        # Convert single item to iterable
        if not isinstance(value, (list, tuple, set)):
            value = [value]

        output = []
        str_filepaths = []
        for item in value:
            if isinstance(item, dict):
                item = cls.from_dict(item)

            if isinstance(item, FileDefItem):
                if not allow_sequences and item.is_sequence:
                    output.extend(item.split_sequence())
                else:
                    output.append(item)

            elif isinstance(item, str):
                str_filepaths.append(item)
            else:
                raise TypeError(
                    "Unknown type \"{}\". Can't convert to {}".format(
                        str(type(item)), cls.__name__
                    )
                )

        if str_filepaths:
            output.extend(cls.from_paths(str_filepaths, allow_sequences))

        return output

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["directory"],
            data["filenames"],
            data.get("frames"),
            data.get("template")
        )

    @classmethod
    def from_paths(
        cls,
        paths,
        allow_sequences: bool = False
    ):
        filenames_by_dir = collections.defaultdict(list)
        for path in paths:
            normalized = os.path.normpath(path)
            directory, filename = os.path.split(normalized)
            filenames_by_dir[directory].append(filename)

        output = []
        for directory, filenames in filenames_by_dir.items():
            if allow_sequences:
                cols, remainders = clique.assemble(filenames)
            else:
                cols = []
                remainders = filenames

            for remainder in remainders:
                output.append(cls(directory, [remainder]))

            for col in cols:
                frames = list(col.indexes)
                paths = [filename for filename in col]
                template = col.format("{head}{padding}{tail}")

                output.append(cls(
                    directory, paths, frames, template
                ))

        return output

    def to_dict(self):
        output = {
            "is_sequence": self.is_sequence,
            "directory": self.directory,
            "filenames": list(self.filenames),
        }
        if self.is_sequence:
            output.update({
                "template": self.template,
                "frames": list(sorted(self.frames)),
            })

        return output


class FilesModel(QtGui.QStandardItemModel):
    def __init__(self, single_item, allow_sequences):
        super().__init__()

        self._id = str(uuid.uuid4())
        self._single_item = single_item
        self._multivalue = False
        self._allow_sequences = allow_sequences

        self._items_by_id = {}
        self._file_items_by_id = {}
        self._filenames_by_dirpath = collections.defaultdict(set)
        self._items_by_dirpath = collections.defaultdict(list)

        self.rowsAboutToBeRemoved.connect(self._on_about_to_be_removed)
        self.rowsInserted.connect(self._on_insert)

    @property
    def id(self):
        return self._id

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

    def add_filepaths(self, items):
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
            root_item = self.invisibleRootItem()
            for items in new_model_items:
                root_item.appendRow(items)

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
        if file_item.is_dir:
            icon_pixmap = paint_image_with_color(
                get_image(filename="folder.png"), QtCore.Qt.white
            )
        else:
            icon_pixmap = paint_image_with_color(
                get_image(filename="file.png"), QtCore.Qt.white
            )

        item = QtGui.QStandardItem()
        item_id = str(uuid.uuid4())
        item.setData(item_id, ITEM_ID_ROLE)
        item.setData(file_item.label or "< empty >", ITEM_LABEL_ROLE)
        item.setData(file_item.filenames, FILENAMES_ROLE)
        item.setData(file_item.directory, DIRPATH_ROLE)
        item.setData(icon_pixmap, ITEM_ICON_ROLE)
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
        if parent_index.isValid():
            target_item = self.itemFromIndex(parent_index)
        else:
            target_item = self.invisibleRootItem()

        # Collect and safely move items
        items_to_move = []
        for item_id in item_ids:
            item = self._items_by_id.get(item_id)
            if item:
                row_items = self.takeRow(item.row())
                if row_items:
                    items_to_move.append(row_items[0])  # Assuming single column

        if not items_to_move:
            return False

        # Insert items into the target location
        for item in items_to_move:
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

    def on_button_clicked(self):
        print(f"Button clicked")


class FilesProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._allow_folders = False
        self._allowed_extensions = ['.jpg']
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

    def __init__(self, single_item, allow_sequences, extensions_label, parent):
        super().__init__(parent)
        self.setAcceptDrops(True)

        empty_widget = DropEmpty(
            single_item, allow_sequences, extensions_label, self
        )

        files_model = FilesModel(single_item, allow_sequences)
        files_proxy_model = FilesProxyModel()
        files_proxy_model.setSourceModel(files_model)
        files_view = FilesView(self)
        files_view.setModel(files_proxy_model)

        main_layout = QtWidgets.QVBoxLayout(self)
        stacked_layout = QtWidgets.QStackedLayout()
        stacked_layout.setContentsMargins(0, 0, 0, 0)
        stacked_layout.setStackingMode(QtWidgets.QStackedLayout.StackAll)
        stacked_layout.addWidget(empty_widget)
        stacked_layout.addWidget(files_view)
        stacked_layout.setCurrentWidget(empty_widget)
        main_layout.addLayout(stacked_layout)

        files_proxy_model.rowsInserted.connect(self._on_rows_inserted)
        files_proxy_model.rowsRemoved.connect(self._on_rows_removed)
        files_view.remove_requested.connect(self._on_remove_requested)
        files_view.context_menu_requested.connect(
            self._on_context_menu_requested
        )
        allowed_types_representations_label = QtWidgets.QLabel(f"Allowed File type for representations: jpeg, png")
        allowed_types_review_label = QtWidgets.QLabel(f"Allowed file types for review: mp4, mov ")
        main_layout.addWidget(allowed_types_representations_label)
        main_layout.addWidget(allowed_types_review_label)

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
        model = self._files_proxy_model
        item_ids = set()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            item_ids.add(index.data(ITEM_ID_ROLE))

        file_items = []
        for item_id in item_ids:
            file_item = self._files_model.get_file_item_by_id(item_id)
            if file_item is not None:
                file_items.append(file_item.to_dict())

        if not self._single_item:
            return file_items
        if file_items:
            return file_items[0]

        empty_item = FileDefItem.create_empty_item()
        return empty_item.to_dict()

    def set_filters(self, folders_allowed, exts_filter):
        self._files_proxy_model.set_allow_folders(folders_allowed)
        self._files_proxy_model.set_allowed_extensions(exts_filter)
        self._empty_widget.set_extensions(exts_filter)
        self._empty_widget.set_allow_folders(folders_allowed)

    def _on_rows_inserted(self, parent_index, start_row, end_row):
        for row in range(start_row, end_row + 1):
            index = self._files_proxy_model.index(row, 0, parent_index)
            item_id = index.data(ITEM_ID_ROLE)
            if item_id in self._widgets_by_id:
                continue
            label = index.data(ITEM_LABEL_ROLE)
            pixmap_icon = index.data(ITEM_ICON_ROLE)
            is_sequence = index.data(IS_SEQUENCE_ROLE)

            widget = ItemWidget(
                item_id,
                label,
                pixmap_icon,
                is_sequence,
                self._multivalue
            )
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

            # Filter filepaths before passing it to model
            filepaths = self._files_proxy_model.filter_valid_files(filepaths)
            if filepaths:
                self._add_filepaths(filepaths)

        if self._handle_full_data_drop(
            mime_data.data("files_widget/full_data")
        ):
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

    def _add_filepaths(self, filepaths):
        self._files_model.add_filepaths(filepaths)

    def _remove_item_by_ids(self, item_ids):
        self._files_model.remove_item_by_ids(item_ids)

    def _update_visibility(self):
        files_exists = self._files_proxy_model.rowCount() > 0
        if files_exists:
            current_widget = self._files_view
        else:
            current_widget = self._empty_widget
        self._stacked_layout.setCurrentWidget(current_widget)


class FilesDialog(QtWidgets.QDialog):
    def __init__(self, single_item, allow_sequences, extensions_label, parent=None):
        super().__init__(parent)

        # Set up the dialog
        self.setWindowTitle("Files Dialog")
        self.setMinimumSize(600, 400)

        # Create the FilesWidget instance
        self.files_widget = FilesWidget(single_item, allow_sequences, extensions_label, self)

        # Layout to hold the FilesWidget
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.files_widget)

        # Buttons for additional functionality if necessary
        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("OK", self)
        cancel_button = QtWidgets.QPushButton("Cancel", self)

        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def showEvent(self, event):
        super(FilesDialog, self).showEvent(event)

        stylesheet = self._load_stylesheet()
        self.setStyleSheet(stylesheet)

    def _load_stylesheet(self):
        """Load strylesheet and trigger all related callbacks.

        Style require more than a stylesheet string. Stylesheet string
        contains paths to resources which must be registered into Qt application
        and load fonts used in stylesheets.

        Also replace values from stylesheet data into stylesheet text.
        """
        style_path = os.path.join(r'C:\Users\ccaillot\quad\quadpype\src\quadpype\style', "style.css")
        with open(style_path, "r") as style_file:
            stylesheet = style_file.read()

        data = self._get_colors_raw_data()

        data_deque = collections.deque()
        for item in data.items():
            data_deque.append(item)

        fill_data = {}
        while data_deque:
            key, value = data_deque.popleft()
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    new_key = "{}:{}".format(key, sub_key)
                    data_deque.append((new_key, sub_value))
                continue
            fill_data[key] = value

        for key, value in fill_data.items():
            replacement_key = "{" + key + "}"
            stylesheet = stylesheet.replace(replacement_key, value)
        return stylesheet

    def _get_colors_raw_data(self):
        """Read data file with stylesheet fill values.

        Returns:
            dict: Loaded data for stylesheet.
        """
        data_path = os.path.join(r'C:\Users\ccaillot\quad\quadpype\src\quadpype\style', "data.json")
        with open(data_path, "r") as data_stream:
            data = json.load(data_stream)
        return data


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    # Example parameters for FilesWidget
    single_item = False
    allow_sequences = True
    extensions_label = "Allowed Extensions"

    # Create the dialog
    dialog = FilesDialog(single_item, allow_sequences, extensions_label)

    if dialog.exec() == QtWidgets.QDialog.Accepted:
        print("Dialog accepted!")
    else:
        print("Dialog canceled!")

    sys.exit(app.exec())