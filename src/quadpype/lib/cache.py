# -*- coding: utf-8 -*-
"""Module storing class for caching values, used for settings."""
import json
import copy
import tempfile
import time
import logging

from datetime import datetime, timezone
from pathlib import Path
import yaml

from quadpype.client import get_quadpype_collection


SYNCS_LOGS_FILE = "sync_logs.yaml"


class CacheValues:
    cache_lifetime = 10

    def __init__(self):
        self.data = None
        self.creation_time = None
        self.version = None
        self.last_saved_info = None

    def data_copy(self):
        if not self.data:
            return {}
        return copy.deepcopy(self.data)

    def update_creation_time(self):
        self.creation_time = datetime.now(timezone.utc)

    def update_data(self, data, version):
        self.data = data
        self.version = version
        self.update_creation_time()

    def update_last_saved_info(self, last_saved_info):
        self.last_saved_info = last_saved_info

    def update_from_document(self, document, version):
        data = {}
        if document:
            if "data" in document:
                data = document["data"]
            elif "value" in document:
                value = document["value"]
                if value:
                    data = json.loads(value)

        self.data = data
        self.version = version
        self.update_creation_time()

    def to_json_string(self):
        return json.dumps(self.data or {})

    @property
    def is_outdated(self):
        if self.creation_time is None:
            return True
        delta = (datetime.now(timezone.utc) - self.creation_time).seconds
        return delta > self.cache_lifetime

    def set_outdated(self):
        self.creation_time = None

class ProjectCacheValues(CacheValues):
    def __init__(self, project_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_name = project_name

    @property
    def is_outdated(self):
        if not super().is_outdated:
            return False

        super().update_creation_time()


def get_projects_last_sync():
    sync_file_path = Path(tempfile.gettempdir(), SYNCS_LOGS_FILE)
    if not sync_file_path.exists():
        return {}

    with open(sync_file_path, 'r', encoding='utf-8') as sync_file:
        logging.info(f"Loaded projects synchronisation times files at path : {sync_file_path}")
        return yaml.safe_load(sync_file)


def write_project_last_sync(projects_last_sync):
    sync_file_path = Path(tempfile.gettempdir(), SYNCS_LOGS_FILE)
    with open(sync_file_path, 'w', encoding='utf-8') as sync_file:
        yaml.dump(projects_last_sync, sync_file)

    logging.info(f"New synchronization time data written at path : {sync_file_path}")


def update_project_last_sync(projects_last_sync, project_name):
    projects_last_sync[project_name] = time.time()


def get_projects_last_updates(projects_names):
        """ Get last update timestamp for each project from database
        Args:
            projects_names (list[str]): list of projects names

        Returns:
            dict: each project name with his corresponding last update timestamp
        """
        collection = get_quadpype_collection("projects_updates_logs")
        query = [
            {
                "$match":
                {
                    "project_name": {"$in": projects_names}
                }
            }
        ]
        return {
            result["project_name"]: result["timestamp"]
            for result in list(collection.aggregate(query))
        }


def sync_is_needed(projects_local_last_sync, projects_last_updates, project_name):
        project_db_last_sync_timestamp = projects_last_updates.get(project_name, 0)
        if not project_db_last_sync_timestamp:
            return True

        project_local_last_sync_timestamp = projects_local_last_sync.get(project_name, 0)
        if not project_db_last_sync_timestamp:
            return True

        if project_db_last_sync_timestamp > project_local_last_sync_timestamp:
            logging.info(f"New updates found from project {project_name}. Sync should be triggered.")
            return True

        logging.info(
            f"Local sync is more recent than project db update for project {project_name}. "
            f"Sync will be canceled."
        )
        return False
