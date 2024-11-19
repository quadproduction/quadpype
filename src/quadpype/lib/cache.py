# -*- coding: utf-8 -*-
"""Module storing class for caching values, used for settings."""
import json
import copy
import datetime


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

    def update_data(self, data, version):
        self.data = data
        self.creation_time = datetime.datetime.now()
        self.version = version

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

    def to_json_string(self):
        return json.dumps(self.data or {})

    @property
    def is_outdated(self):
        if self.creation_time is None:
            return True
        delta = (datetime.datetime.now() - self.creation_time).seconds
        return delta > self.cache_lifetime

    def set_outdated(self):
        self.creation_time = None
