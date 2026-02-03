# -*- coding: utf-8 -*-
"""Module storing class for caching values, used for settings."""
import json
import copy
import time

from datetime import datetime, timezone

from quadpype.client import get_project_last_update


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

        # Then we determine if sync is needed by checking :
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
