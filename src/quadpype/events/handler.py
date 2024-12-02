# -*- coding: utf-8 -*-
"""Module storing the class and logic of the QuadPype Events Handler."""
import os
import time
import functools

from typing import Optional
from datetime import datetime, timezone, timedelta

import pymongo
import requests
from qtpy import QtCore, QtWidgets

from quadpype.lib import (
    get_user_profile,
    get_app_registry,
    get_timestamp_str,
    get_datetime_from_timestamp_str
)
from quadpype.client.mongo import QuadPypeMongoConnection


_EVENT_HANDLER = None
CHECK_NEW_EVENTS_INTERVAL_SECONDS = 120
MINIMUM_EVENT_EXPIRE_IN_SECONDS = CHECK_NEW_EVENTS_INTERVAL_SECONDS + 10


class EventHandlerWorker(QtCore.QThread):
    task_completed = QtCore.Signal(int)

    def __init__(self, manager, parent=None):
        """Initialize the worker thread."""
        if parent is None:
            parent = QtWidgets.QApplication.instance()

        super(EventHandlerWorker, self).__init__(parent)

        self._manager = manager

        self._webserver_url = self._manager.webserver.url

        # Get info about the timestamp of the last handled event
        self._last_handled_event_timestamp = self._manager.app_registry.get_item(
            "last_handled_event_timestamp", fallback=0
        )

        # If no event seems to have ever been handled, set the EPOCH time
        if self._last_handled_event_timestamp == 0:
            self._last_handled_event_timestamp = \
                datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        else:
            self._last_handled_event_timestamp = get_datetime_from_timestamp_str(
                self._last_handled_event_timestamp
            )

    def run(self):
        start_time = time.time()

        # Retrieve the new events to process
        db_cursor = self._manager.collection.find({
            "timestamp": {
                "$gt": self._last_handled_event_timestamp
            }
        }).sort("timestamp", 1)

        # Process the events
        current_timestamp = datetime.now()
        for doc in db_cursor:
            if not self._manager.is_running:
                break
            if "expire_at" in doc and doc["expire_at"] > current_timestamp:
                # This event is expired, skip
                self._last_handled_event_timestamp = doc["timestamp"]
                continue

            route = doc["route"]
            if not route.startwith("/"):
                route = "/" + route

            url_with_route = self._webserver_url + route

            # Send the event to the webserver API
            funct = getattr(requests, doc["type"])
            if not doc["content"]:
                response = funct(url_with_route)
            else:
                response = funct(url_with_route, **doc["content"])

            # Update the last handled timestamp
            self._last_handled_event_timestamp = doc["timestamp"]

        if db_cursor.retrieved > 0:
            # Update the local app registry
            # To keep track and properly retrieve the next events after that
            self._manager.app_registry.set_item(
                "last_handled_event_timestamp",
                get_timestamp_str(self._last_handled_event_timestamp))

        if not self._manager.is_running:
            # Simply exit without emiting the signal
            return

        elapsed_time = round(time.time() - start_time)
        waiting_time = max(0, CHECK_NEW_EVENTS_INTERVAL_SECONDS - elapsed_time)
        waiting_time_msec = waiting_time * 1000

        self.task_completed.emit(waiting_time_msec)


class EventsHandlerManager:
    """Class handling QuadPype events."""
    non_mandatory_event_max_lifespan = 3600

    def __init__(self):
        self._user_profile = get_user_profile()
        self._app_registry = get_app_registry()
        self._is_running = False

        self._webserver = None

        # Get database connection
        self._db_client = QuadPypeMongoConnection.get_mongo_client()

        self._database = self._db_client[os.environ["QUADPYPE_DATABASE_NAME"]]
        self._collection_name = "events"

        # Create or retrieve the collection
        if self._collection_name not in self._database.list_collection_names():
            self._database.create_collection(self._collection_name)
            self._collection = self._database[self._collection_name]
            self._collection.create_index(
                [("expire_at", pymongo.ASCENDING)],
                expireAfterSeconds=self.non_mandatory_event_max_lifespan
            )
        else:
            self._collection = self._database[self._collection_name]

        self._worker_thread = None

        # Timer to wait before re-triggering the worker
        self._timer = QtCore.QTimer(QtWidgets.QApplication.instance())
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_worker)

    @property
    def user_profile(self):
        return self._user_profile

    @property
    def app_registry(self):
        return self._app_registry

    @property
    def collection(self):
        return self._collection

    @property
    def webserver(self):
        return self._webserver

    @property
    def is_running(self):
        return self._is_running

    def _start_worker(self):
        if self._worker_thread.isRunning():
            raise RuntimeError("The Event Worker is already running.")

        if not self._webserver.is_running:
            raise RuntimeError("Webserver is not running. Cannot start the worker thread.")

        self._is_running = True
        self._worker_thread.start(QtCore.QThread.HighestPriority)

    def _restart_worker(self, waiting_time_msec):
        self._timer.start(waiting_time_msec)

    def start(self):
        if self._worker_thread:
            raise RuntimeError("The Event Handler cannot be started multiple times.")
        if not self._webserver:
            raise RuntimeError("Webserver not set. Cannot start the event handler.")

        self._worker_thread = EventHandlerWorker(self)
        self._worker_thread.task_completed.connect(self._restart_worker)

        if not self._webserver.is_running:
            # The webserver is not yet running, wait a bit before starting the loop
            waiting_time_msec = 10 * 1000
            self._timer.start(waiting_time_msec)
        else:
            self._start_worker()

    def stop(self):
        if self._timer.isActive():
            self._timer.stop()
        if self._worker_thread.isRunning():
            self._is_running = False
            self._worker_thread.wait()

    def set_webserver(self, webserver):
        self._webserver = webserver


def get_event_handler() -> EventsHandlerManager:
    global _EVENT_HANDLER
    if _EVENT_HANDLER is None:
        _EVENT_HANDLER = EventsHandlerManager()

    return _EVENT_HANDLER


def require_events_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        get_event_handler()
        return func(*args, **kwargs)
    return wrapper


def _validate_event_values(event_route: str,
                           event_type: str,
                           content: Optional[dict],
                           target_users: list,
                           target_groups: list,
                           expire_in: Optional[int]):
    """Function to validate event values before submitting the event."""
    if not isinstance(event_route, str) or not event_route.strip():
        return False, "The event 'route' need to be a not empty string."

    if not isinstance(event_type, str) or not event_type.strip():
        return False, "The event 'type' need to be a not empty string."

    if content is not None and not isinstance(content, dict):
        return False, "The event 'content' can only be None or a valid dict."

    if not isinstance(target_users, list):
        return False, "The event 'target_users' can only be None or a list."

    if not isinstance(target_groups, list):
        return False, "The event 'target_groups' can only be None or a list."

    if expire_in is not None and not isinstance(expire_in, int) or expire_in <= 0:
        return False, "The event 'expire_in' can only be None or a strictly positive integer."


@require_events_handler
def register_event(event_route: str,
                   event_type: str,
                   content: Optional[dict],
                   target_users: Optional[list] = None,
                   target_groups: Optional[list] = None,
                   expire_in: Optional[int] = None):
    if target_users is None:
        target_users = []
    elif isinstance(target_users, str):
        target_users = [target_users]

    if target_groups is None:
        target_groups = []
    elif isinstance(target_groups, str):
        target_groups = [target_groups]

    # Ensure the events values are correct before adding the event in the database
    is_valid, invalid_msg = _validate_event_values(
        event_route, event_type, content, target_users, target_groups, expire_in)

    if not is_valid:
        raise ValueError(invalid_msg)

    timestamp = datetime.now()
    event = {
        "timestamp": timestamp,
        "route": event_route,
        "type": event_type,
        "target_users": target_users,
        "target_groups": target_groups,
        "content": content,
    }

    if expire_in is not None:
        expire_in += MINIMUM_EVENT_EXPIRE_IN_SECONDS
        event["expire_at"] = timestamp + timedelta(seconds=expire_in)

    _EVENT_HANDLER.collection.insert_one(event)
