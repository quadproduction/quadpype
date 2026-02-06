import collections
import copy
import sqlite3
import threading
from pathlib import Path
import time
from qtpy import QtCore, QtGui

from quadpype.lib import StringTemplate
from quadpype.pipeline import (
    Anatomy,
    HOST_WORKFILE_EXTENSIONS,
    get_current_project_name,
    get_current_asset_name,
    get_current_task_name
)

from quadpype.settings import get_project_settings
from quadpype.pipeline.publish.lib import get_publish_workfile_representations_from_session
from .lib import get_qta_icon_by_name_and_color


DB_NAME = "workfile_cache.db"
KNOWN_EXTS = [ext for exts in HOST_WORKFILE_EXTENSIONS.values() for ext in exts]

TASK_ICON_SIZE = 16
APP_OVERLAY_ICON_SIZE = 32
APP_ICON_SIZE = 64

class WorkFileCache:
    _instance = None
    _lock = threading.Lock()
    _cache = {}
    _ttl = 60
    _updates_times = collections.defaultdict(float)
    _workfile_db_paths = collections.defaultdict(str)
    _enabled = None

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def is_enabled(self, project_name):
        if self._enabled is None:
            settings = get_project_settings(project_name)
            self._enabled = settings["global"].get("launcher", False).get("use_icons", False)

        return self._enabled

    def is_outdated(self, project_name=None):
        if not self._workfile_db_paths[project_name] or \
            not self._updates_times[project_name]:
            return True

        return time.time() - self._updates_times[project_name] > self._ttl

    def workfile_db_exists(self, project_name=None, settings=None):
        return self.get_workfile_db_path(project_name, settings).exists()

    def get_workfile_db_path(self,project_name=None, settings=None):
        if not self.is_outdated(project_name):
            return self._workfile_db_paths[project_name]

        if not settings:
            settings = get_project_settings(project_name)
        db_path_template = settings["global"]["launcher"]["workfile_cache_file_path"]
        anatomy = Anatomy(project_name=project_name)
        template_data = {
            "root" : anatomy.roots,
            "project":{
                "name":project_name
            }
        }
        db_path = Path(StringTemplate.format_template(db_path_template, template_data))
        db_path.mkdir(parents=True, exist_ok=True)

        self._workfile_db_paths[project_name] = db_path / DB_NAME

        self._updates_times[project_name] = time.time()
        return self._workfile_db_paths[project_name]

    def init_workfile_db(self, project_name):
        if not self.is_enabled(project_name):
            return None

        conn = sqlite3.connect(self.get_workfile_db_path(project_name=project_name))

        c = conn.cursor()
        c.execute('''
                CREATE TABLE IF NOT EXISTS task_files (
                    task_name TEXT,
                    asset_name TEXT,
                    ext TEXT,
                    PRIMARY KEY (task_name, asset_name, ext)
                )
        ''')
        conn.commit()
        conn.close()

    def add_task_folder(self,project_name=None, task_name=None, asset_name=None, folder=None):
        if not self.is_enabled(project_name):
            return None

        if isinstance(folder, str):
            folder =Path(folder)
        conn = sqlite3.connect(self.get_workfile_db_path(project_name=project_name))
        c = conn.cursor()

        extensions = set(f.suffix for f in folder.rglob("*") if f.is_file())

        for ext in extensions & set(KNOWN_EXTS):
            c.execute('INSERT OR REPLACE INTO task_files (task_name, asset_name, ext) VALUES (?, ?, ?)',
                      (task_name, asset_name, ext))
            print(f"{ext} added for {asset_name} on task {task_name}")
        conn.commit()
        conn.close()

    def add_task_extension(self,project_name=None, task_name=None, asset_name=None, extension=None):

        if not project_name:
            project_name = get_current_project_name()
        if not self.is_enabled(project_name):
            return None
        if not task_name:
            task_name = get_current_task_name()
        if not asset_name:
            asset_name = get_current_asset_name()

        conn = sqlite3.connect(self.get_workfile_db_path(project_name=project_name))
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO task_files (task_name, asset_name, ext) VALUES (?, ?, ?)',
                  (task_name, asset_name, extension))
        print(f"{extension} added for {asset_name} on task {task_name}")
        conn.commit()
        conn.close()

    def load_task_extensions(self,project_name, task_name, asset_name):
        if not self.is_enabled(project_name):
            return []

        if not self.is_outdated(project_name):
            entity_cache = self._cache.get((project_name, task_name, asset_name))
            if entity_cache:
                return entity_cache

        conn = sqlite3.connect(self.get_workfile_db_path(project_name=project_name))
        c = conn.cursor()
        c.execute('SELECT ext FROM task_files WHERE task_name = ? AND asset_name = ?',
                  (task_name, asset_name))
        rows = c.fetchall()
        conn.close()
        results = [row[0] for row in rows]

        self._cache[(project_name, task_name, asset_name)] = results
        return results



def get_item_state(session, item, task_name=None, asset_name=None, app_action=None):
    """
    Will set a different icon on the icon if a WF or PublishedWF exists
    """
    search_session = copy.deepcopy(session)

    if not task_name:
        task_name = search_session.get("AVALON_TASK", None)

        if not task_name:
            return

    if not asset_name:
        asset_name = search_session.get("AVALON_ASSET", None)

        if not asset_name:
            return

    search_session.update({
        "AVALON_TASK":task_name,
        "AVALON_ASSET":asset_name
    })

    project = search_session.get("AVALON_PROJECT")

    workfile_exts = WorkFileCache().load_task_extensions(project, task_name, asset_name)

    publish_representations = get_workfile_publish_representations(search_session)

    ext = KNOWN_EXTS
    if app_action:
        ext = HOST_WORKFILE_EXTENSIONS.get(app_action.label.lower(), [])

    workfile_icon = None
    publish_workfile_icon = None

    icon = get_qta_icon_by_name_and_color("fa.pencil-square-o", "grey")
    if any(elem in ext for elem in workfile_exts):
        light_orange = QtGui.QColor(255, 200, 100)
        workfile_icon = get_qta_icon_by_name_and_color("fa.file-word-o", light_orange)
        icon = workfile_icon

    repr_ext = set()
    for repr in publish_representations:
        repr_ext.add(f".{repr['name']}")

    repr_ext = list(repr_ext)
    if any(elem in ext for elem in repr_ext):
        publish_workfile_icon = get_qta_icon_by_name_and_color("fa.check-square-o", "limegreen")
        icon = publish_workfile_icon

    if workfile_icon and publish_workfile_icon:
        icon = merge_icons_diagonal(publish_workfile_icon, workfile_icon, TASK_ICON_SIZE)

    if app_action:
        if not workfile_icon and not publish_workfile_icon:
            return
        pixmap_small = icon.pixmap(TASK_ICON_SIZE, TASK_ICON_SIZE)
        pixmap_resized = pixmap_small.scaled(APP_OVERLAY_ICON_SIZE, APP_OVERLAY_ICON_SIZE,
                                             QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        icon_large = QtGui.QIcon(pixmap_resized)
        icon = add_overlay_icon(item.icon(), icon_large, APP_ICON_SIZE, APP_OVERLAY_ICON_SIZE)

    return icon


def merge_icons_diagonal(icon1, icon2, size):
    """Create a new icon based on 2 icons split in half diagonally"""
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))

    painter = QtGui.QPainter(pixmap)

    p1 = icon1.pixmap(size, size)
    p2 = icon2.pixmap(size, size)

    path1 = QtGui.QPainterPath()
    path1.moveTo(0, 0)
    path1.lineTo(size, 0)
    path1.lineTo(0, size)
    path1.closeSubpath()
    painter.setClipPath(path1)
    painter.drawPixmap(0, 0, p1)

    path2 = QtGui.QPainterPath()
    path2.moveTo(size, size)
    path2.lineTo(size, 0)
    path2.lineTo(0, size)
    path2.closeSubpath()
    painter.setClipPath(path2)
    painter.drawPixmap(0, 0, p2)

    painter.end()
    return QtGui.QIcon(pixmap)

def add_overlay_icon(base_icon, overlay_icon, base_size, overlay_size,
                     bg_color=QtGui.QColor("black")):
    """
    Add a icon in overlay at the bottom right on top of a main icon
    """

    base_pixmap = base_icon.pixmap(base_size, base_size)

    result = QtGui.QPixmap(base_size, base_size)
    result.fill(QtGui.QColor(0,0,0,0))

    painter = QtGui.QPainter(result)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)

    painter.drawPixmap(0, 0, base_pixmap)

    x = base_size - overlay_size
    y = base_size - overlay_size

    painter.setBrush(QtGui.QBrush(bg_color))
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawRect(x, y, overlay_size, overlay_size)

    overlay_pixmap = overlay_icon.pixmap(overlay_size, overlay_size)

    painter.drawPixmap(x, y, overlay_pixmap)

    painter.end()
    return QtGui.QIcon(result)

def get_workfile_publish_representations(session):
    publish_representations = get_publish_workfile_representations_from_session(session)
    if not publish_representations:
        return []
    return publish_representations


class IconWorker(QtCore.QObject):
    finished = QtCore.Signal()
    callback = QtCore.Signal(QtGui.QStandardItem, QtGui.QIcon)  # Signal to send icon path or data
    entities_data = []

    def run(self):
        for data in self.entities_data:

            item = data['item']
            session = data['session']
            app_action = data.get('app_action')
            task_name = data.get('task_name')
            asset_name = data.get('asset_name')
            icon = get_item_state(
                session=session,
                item=item,
                app_action=app_action,
                task_name=task_name,
                asset_name=asset_name
            )
            if not icon:
                continue

            self.callback.emit(item, icon)

        self.finished.emit()


def launch_threaded_icon_worker(cls, entities_data, callback):
    cls.item_state_worker = IconWorker()
    cls.item_state_worker.entities_data = entities_data
    cls.item_state_worker.moveToThread(cls.item_state_thread)
    cls.item_state_thread.started.connect(cls.item_state_worker.run)
    cls.item_state_worker.callback.connect(callback)
    cls.item_state_worker.finished.connect(cls.item_state_thread.quit)
    cls.item_state_thread.start()
