from qtpy import QtWidgets, QtCore, QtGui

from quadpype.widgets import BaseToolDialog
from quadpype.style import (
    load_stylesheet,
    app_icon_path
)
from quadpype.hosts.aftereffects import api
from quadpype.hosts.aftereffects.plugins.publish import collect_render
from quadpype.hosts.aftereffects.plugins.create.create_render import RenderCreator
from quadpype.pipeline import get_current_project_name
from quadpype.pipeline.context_tools import get_current_context
from quadpype.settings import get_project_settings
from quadpype.hosts.aftereffects.api.pipeline import cache_and_get_instances


class AutoAssembleShotsToSequenceDialog(BaseToolDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stub = api.get_stub()
        self.host = api.AfterEffectsHost()
        self.shot_instances = list()
        self.sequence_instance = dict()
        self.generate_window()

    def generate_window(self):
        app_label = "QuadPype"
        self.setWindowTitle("{} Auto Assemble Shots to Sequence".format(app_label))
        icon = QtGui.QIcon(app_icon_path())
        self.setWindowIcon(icon)
        self.setStyleSheet(load_stylesheet())

        if self.can_stay_on_top:
            self.setWindowFlags(
                self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint
            )
        self.layout = QtWidgets.QVBoxLayout()

        self.layout.addWidget(QtWidgets.QLabel("Following shots:"))

        self.layout_shots = QtWidgets.QVBoxLayout()
        self.set_shots_list_widget()
        self.layout.addLayout(self.layout_shots)

        self.layout_seq = QtWidgets.QVBoxLayout()
        self.set_seq_list_widget()
        self.layout.addLayout(self.layout_seq)

        self.apply_btn = QtWidgets.QPushButton()
        self.apply_btn.setFixedHeight(40)
        self.apply_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogResetButton))
        self.layout.addWidget(self.apply_btn)

        self.refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        self.layout.addWidget(self.refresh_btn)

        self.setLayout(self.layout)

        self.apply_btn.clicked.connect(self.assemble_shots_in_sequence)
        self.update_apply_btn()

    def set_shots_list_widget(self):
        self.clear_layout(self.layout_shots)
        self.shots_list_widget = QtWidgets.QListWidget()
        self.get_shot_comps()
        if self.shot_instances:
            self.shots_list_widget.clear()
            for entry in self.shot_instances:
                if not self.stub.get_item(entry['members'][0]):
                    item = QtWidgets.QListWidgetItem(f"● {entry['asset']} Comp Not Found")
                    item.setForeground(QtGui.QColor("red"))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsSelectable)
                else:
                    item = QtWidgets.QListWidgetItem(f"● {entry['asset']}")
                    item.setData(QtCore.Qt.UserRole, entry)
                self.shots_list_widget.addItem(item)

            self.shots_list_widget.setFixedHeight(self.shots_list_widget.sizeHintForRow(0) * (len(self.shot_instances)+2))
            self.shots_list_widget.itemClicked.connect(self.on_item_clicked)
            self.layout_shots.addWidget(self.shots_list_widget)
        else:
            no_shots_label = QtWidgets.QLabel("No Instance Comp Shots Found")
            no_shots_label.setStyleSheet("color: red; font-weight: bold;")
            self.layout_shots.addWidget(no_shots_label)

    def set_seq_list_widget(self):
        self.clear_layout(self.layout_seq)
        self.seq_list_widget = QtWidgets.QListWidget()
        self.get_sequence_comp()
        if self.sequence_instance:
            self.seq_list_widget.clear()
            self.layout_seq.addWidget(QtWidgets.QLabel(f"Will be assembled back-to-back in the compostion:"))
            if not self.stub.get_item(self.sequence_instance['members'][0]):
                item = QtWidgets.QListWidgetItem(f"➽ {self.sequence_instance.get('subset', '')} Comp Not Found")
                item.setForeground(QtGui.QColor("red"))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsSelectable)
            else:
                item = QtWidgets.QListWidgetItem(f"➽ {self.sequence_instance.get('subset', '')}")
                item.setData(QtCore.Qt.UserRole, self.sequence_instance)

            self.seq_list_widget.addItem(item)

            self.seq_list_widget.setFixedHeight(self.seq_list_widget.sizeHintForRow(0))
            self.seq_list_widget.itemClicked.connect(self.on_item_clicked)
            self.layout_seq.addWidget(self.seq_list_widget)
        else:
            no_seq_label = QtWidgets.QLabel("No Instance Comp Sequence Found")
            no_seq_label.setStyleSheet("color: red; font-weight: bold;")
            self.layout_seq.addWidget(no_seq_label)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self.clear_layout(item.layout())

    def get_sequence_comp(self):
        current_task = self.host.get_current_task_name()
        for instance in self.host.list_instances():
            if instance["task"] == current_task:
                self.sequence_instance = instance

    def get_shot_comps(self):
        current_task = self.host.get_current_task_name()
        for instance in self.host.list_instances():
            if instance["task"] == current_task or instance["family"] != "render":
                continue
            if instance in self.shot_instances:
                continue
            self.shot_instances.append(instance)

    def on_item_clicked(self, item):
        entry = item.data(QtCore.Qt.UserRole)
        self.stub.open_comp_by_id(entry.get("members", [""])[0])

    def refresh(self):
        self.set_shots_list_widget()
        self.set_seq_list_widget()
        self.update_apply_btn()

    def all_instances_exist(self):
        for shot_instance in self.shot_instances:
            if not self.stub.get_item(shot_instance.get("members", [""])[0]):
                return False
        if not self.stub.get_item(self.sequence_instance.get("members", [""])[0]):
            return False
        return True

    def update_apply_btn(self):
        if not self.all_instances_exist() or not self.shot_instances or not self.sequence_instance:
            self.apply_btn.setEnabled(False)
            self.apply_btn.setText("Missing Instance in AE")
            return
        self.apply_btn.setEnabled(True)
        self.apply_btn.setText("Assemble Shots")

    def assemble_shots_in_sequence(self):
        shots_data = dict()
        for shot_instance in self.shot_instances:
            shot_properties = (self.stub.get_comp_properties(shot_instance.get("members", [""])[0]))
            shots_data[shot_properties.id] = {
                "frameStart":shot_properties.frameStart,
                "framesDuration":shot_properties.framesDuration,
                "frameRate":shot_properties.frameRate,
                "height":shot_properties.height,
                "width":shot_properties.width
            }

        frame_start = min(entry['frameStart'] for entry in shots_data.values())
        fps = min(entry['frameRate'] for entry in shots_data.values())
        total_duration = sum(entry['framesDuration'] for entry in shots_data.values())
        max_height = max(entry['height'] for entry in shots_data.values())
        max_width = max(entry['width'] for entry in shots_data.values())

        self.stub.set_comp_properties(
            comp_id=self.sequence_instance.get("members", [""])[0],
            start=frame_start,
            duration=total_duration,
            frame_rate=fps,
            width=max_width,
            height=max_height
        )

        self.stub.assemble_shots_in_seq_comp(
            seq_comp_id=self.sequence_instance.get("members", [""])[0],
            shots_data=shots_data
        )
