# -*- coding: utf-8 -*-
"""Module storing class for caching values, used for settings."""
import json
import copy
import tempfile
import time
import logging
import threading
import sqlite3


from datetime import datetime, timezone
from pathlib import Path
import yaml

from quadpype.client import get_quadpype_collection


SYNCS_LOGS_FILE = "sync_logs.yaml"


# Singleton for in-memory SQLite DB
class  CacheMemoryDatabase:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_times (
                name TEXT,
                updated_entity TEXT,
                timestamp REAL,
                PRIMARY KEY (name, updated_entity)
            )
        """)
        self.conn.commit()

    def get_all(self):
        cur = self.conn.execute("SELECT name, updated_entity, timestamp FROM sync_times")
        return [
            {
                "name": row[0],
                "updated_entity": row[1],
                "timestamp": row[2]
            } for row in cur.fetchall()
        ]

    def get(self, name, entity):
        cur = self.conn.execute(
            "SELECT timestamp FROM sync_times WHERE name = ? AND updated_entity = ?",
            (name, entity)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def get_specific(self, names=None, entities=None):
        query = "SELECT name, updated_entity, timestamp FROM sync_times WHERE 1=1"
        params = []

        if names:
            query += f" AND name IN ({','.join(['?']*len(names))})"
            params.extend(names)

        if entities:
            query += f" AND updated_entity IN ({','.join(['?']*len(entities))})"
            params.extend(entities)

        cur = self.conn.execute(query, params)
        return [
            {
                "name": row[0],
                "updated_entity": row[1],
                "timestamp": row[2]
            } for row in cur.fetchall()
        ]

    def create(self, name, entity, timestamp):
        self.conn.execute(
            "INSERT INTO sync_times (name, updated_entity, timestamp) VALUES (?, ?, ?)",
            (name, entity, timestamp)
        )
        self.conn.commit()

    def update(self, name, entity, timestamp):
        cur = self.conn.execute(
            "UPDATE sync_times SET timestamp = ? WHERE name = ? AND updated_entity = ?",
            (timestamp, name, entity)
        )
        self.conn.commit()

        # If no row was updated, insert a new one
        if cur.rowcount == 0:
            self.create(name, entity, timestamp)


def get_entity_last_sync(name, entity):
    return CacheMemoryDatabase().get(name, entity)


def get_specific_entities_last_sync(names=None, entities=None):
    return CacheMemoryDatabase().get_specific(names, entities)


def get_all_entities_last_sync():
    return CacheMemoryDatabase().get_all()


def update_entity_last_sync(name, entity, timestamp):
    CacheMemoryDatabase().update(
        name=name,
        entity=entity,
        timestamp=timestamp
    )


class CacheValues:
    cache_lifetime = 10

    def __init__(self):
        self.data = None
        self.creation_time = None
        self.version = None
        self.last_saved_info = None
        self.project_last_sync = None

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

    def update_entity_last_sync(self):
        self.project_last_sync = time.time()

    @property
    def is_outdated(self):
        # If no data is cached, we consider it outdated as it needs to be filled
        if not self.data:
            return True

        # If cache is not expired, we stop verification immediately
        if not self._cache_is_expired():
            self.update_creation_time()
            return False

        # First we retrieve projects last updates from database (and consider outdated if nothing is found)
        project_last_update = get_project_last_update(name=self.name, entity=self.entity)
        if not project_last_update:
            return True

        # We compare local sync time to database last sync to determine if sync is needed
        # Then we retrieve project local last sync
        if not self.project_last_sync:
            self.project_last_sync = get_entity_last_sync(name=self.name, entity=self.entity)

        # Ultimately we determine if sync is needed by checking :
        # - If local sync time exists (we sync if not)
        # - If db sync time is more recent than local sync time (we sync if so)
        if self._sync_is_needed(project_last_update):
            self.update_entity_last_sync()
            return True

        self.update_creation_time()
        return False

    def set_outdated(self):
        self.creation_time = None


class CoreSettingsCacheValues(CacheValues):
    def __init__(self, *args, **kwargs):
        self.name = "core"
        self.entity = "settings"
        super().__init__(*args, **kwargs)


class GlobalSettingsCacheValues(CacheValues):
    def __init__(self, *args, **kwargs):
        self.name = "global"
        self.entity = "settings"
        super().__init__(*args, **kwargs)


class UserSettingsCacheValues(CacheValues):
    def __init__(self, name=None, *args, **kwargs):
        self.name = name
        self.entity = "settings"
        super().__init__(*args, **kwargs)


class ProjectSettingsCacheValues(CacheValues):
    def __init__(self, project_name=None, *args, **kwargs):
        self.name = project_name if project_name else "project_default"
        self.entity = "settings"
        super().__init__(*args, **kwargs)


class ProjectAnatomyCacheValues(CacheValues):
    def __init__(self, project_name=None, *args, **kwargs):
        self.name = project_name if project_name else "project_default"
        self.entity = "anatomy"
        super().__init__(*args, **kwargs)


def get_projects_last_updates(names, entity):
    """ Get last update timestamp for each project from database
    Args:
        names (list[str]): list of entities names
        entity (str): Updated entity type name

    Returns:
        dict: each project name with his corresponding last update timestamp
    """
    collection = get_quadpype_collection("projects_updates_logs")
    query = [
        {
            "$match":
            {
                "name": {"$in": names},
                "updated_entity": entity
            }
        }
    ]
    return {
        result["name"]: result["timestamp"]
        for result in list(collection.aggregate(query))
    }


def get_project_last_update(name=None, entity=None):
    """ Get last update timestamp for specific project / entity from database
    Args:
        name (str): list of projects names
        entity (str): Updated entity type name

    Returns:
        dict: each project name with his corresponding last update timestamp
    """
    if not name and not entity:
        logging.warning("Needs at least name or entity to get last update timestamp.")
        return None

    collection = get_quadpype_collection("projects_updates_logs")
    matches = {}
    if name:
        matches['name'] = name

    if entity:
        matches['updated_entity'] = entity

    query = [
        {
            "$match": matches
        }
    ]
    return next(iter(collection.aggregate(query)), {}).get("timestamp", None)


def sync_is_needed(entities_local_last_sync, entities_last_updates, name):
    if entities_local_last_sync is None:
        return True

    entity_db_last_sync_timestamp = entities_last_updates.get(name, 0)
    if not entity_db_last_sync_timestamp:
        return True

    if entity_db_last_sync_timestamp > entities_local_last_sync:
        logging.info(f"New updates found from entity {name}. Sync should be triggered.")
        return True

    logging.info(
        f"Local sync is more recent than entity db update for entity {name}. "
        f"Sync will be canceled."
    )
    return False
