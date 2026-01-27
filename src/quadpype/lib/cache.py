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
        self.project_last_sync = None

        self.name = "undefined"
        self.entity = "undefined"

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

    def _creation_time_is_registered(self):
        return self.creation_time is not None

    def _cache_is_expired(self):

        if self.creation_time is None:
            return True

        delta = (datetime.now(timezone.utc) - self.creation_time).seconds
        return delta > self.cache_lifetime

    def _sync_is_needed(self, project_last_update):
        return not self.project_last_sync or \
            project_last_update > self.project_last_sync

    @property
    def is_outdated(self):
        # If no data is cached, we consider it outdated as it needs to be filled
        if not self.data:
            return True

        # If cache is not expired, we stop verification immediately
        if not self._cache_is_expired():
            return False

        # We immediatly update creation time to let next calls wait for cache expiry
        self.update_creation_time()

        # First we retrieve projects last updates from database (and consider outdated if nothing is found)
        project_last_update = get_project_last_update(project_name=self.name, entity=self.entity)
        if not project_last_update:
            return True

        # We compare local sync time to database last sync to determine if sync is needed
        # Then we retrieve project local last sync
        if not self.project_last_sync:
            self.projects_last_sync = get_projects_last_sync()
            self.project_last_sync = self.projects_last_sync.get(self.name)

        # Ultimately we determine if sync is needed by checking :
        # - If local sync time exists (we sync if not)
        # - If db sync time is more recent than local sync time (we sync if so)
        if self._sync_is_needed(project_last_update):
            update_project_last_sync(self.projects_last_sync, self.name)
            write_project_last_sync(self.projects_last_sync)
            return True

        return False

    def set_outdated(self):
        self.creation_time = None


class CoreSettingsCacheValues(CacheValues):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "core"
        self.entity = "settings"


class GlobalSettingsCacheValues(CacheValues):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "global"
        self.entity = "settings"


class UserSettingsCacheValues(CacheValues):
    def __init__(self, name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = name
        self.name = f"user:{self.user_id}"
        self.entity = "settings"


class ProjectSettingsCacheValues(CacheValues):
    def __init__(self, project_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = project_name if project_name else "project_default"
        self.entity = "settings"


class ProjectAnatomyCacheValues(CacheValues):
    def __init__(self, project_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = project_name if project_name else "project_default"
        self.entity = "anatomy"


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
                    "name": {"$in": projects_names}
                }
            }
        ]
        return {
            result["name"]: result["timestamp"]
            for result in list(collection.aggregate(query))
        }


def get_project_last_update(project_name=None, entity=None):
        """ Get last update timestamp for specific project / entity from database
        Args:
            projects_names (list[str]): list of projects names

        Returns:
            dict: each project name with his corresponding last update timestamp
        """
        if not project_name and not entity:
            logging.warning("Needs at least project_name or entity to get last update timestamp.")
            return None

        collection = get_quadpype_collection("projects_updates_logs")

        matches = {}
        if project_name:
            matches['name'] = project_name

        if entity:
            matches['entity'] = entity

        query = [
            {
                "$match": matches
            }
        ]
        return {
            result["name"]: result["timestamp"]
            for result in list(collection.aggregate(query))
        }


def sync_is_needed(projects_local_last_sync, projects_last_updates, name):
        project_db_last_sync_timestamp = projects_last_updates.get(name, 0)
        if not project_db_last_sync_timestamp:
            return True

        project_local_last_sync_timestamp = projects_local_last_sync.get(name, 0)
        if not project_db_last_sync_timestamp:
            return True

        if project_db_last_sync_timestamp > project_local_last_sync_timestamp:
            logging.info(f"New updates found from entity {name}. Sync should be triggered.")
            return True

        logging.info(
            f"Local sync is more recent than project db update for entity {name}. "
            f"Sync will be canceled."
        )
        return False
