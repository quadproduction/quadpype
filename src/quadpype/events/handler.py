# -*- coding: utf-8 -*-
"""Module storing the class and logic of the QuadPype Events Handler."""
import os
import json
import functools

from time import sleep
from typing import Optional
from datetime import datetime, timezone, timedelta

import pymongo
import pymongo.errors
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

DEFAULT_RESPONSES_WAITING_TIME_SECS = 3


class EventHandlerWorker(QtCore.QThread):

    def __init__(self, manager, parent=None):
        """Initialize the worker thread."""
        if parent is None:
            parent = QtWidgets.QApplication.instance()

        super(EventHandlerWorker, self).__init__(parent)

        self._manager = manager

        self._curr_user_id = self._manager.user_profile["user_id"]

        self._webserver_url = self._manager.webserver.url

        # Store the amount of time an error occurred
        self._error_count = 0

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

    def _respond_to_event(self, event_doc, response):
        curr_user_id = self._manager.user_profile["user_id"]
        response_data = {
            "user_id": curr_user_id,
            "content": ""
        }

        if response.text:
            response_content = json.loads(response.text)
            if "content" in response_content:
                response_data["content"] = response_content["content"]
            else:
                response_data["content"] = response_content

        try:
            # Only push the response if the user_id hasn't already sent a response
            self._manager.collection.update_one(
                {"_id": event_doc["_id"], "responses.user_id": {"$ne": curr_user_id}},
                {"$push": {"responses": response_data}}
            )
        except Exception as e:
            print(f"Error updating event: {e}")

    def _update_last_handled_event_timestamp(self):
        # Update the local app registry
        # To keep track and properly retrieve the next events after that
        self._manager.app_registry.set_item(
            "last_handled_event_timestamp",
            get_timestamp_str(self._last_handled_event_timestamp))

    def _process_event(self, event_doc):
        current_timestamp = datetime.now()

        if (event_doc["user_id"] == self._curr_user_id) or\
                (event_doc["target_users"] and self._curr_user_id not in event_doc["target_users"]) or \
                (event_doc["target_groups"] and self._manager.user_profile["role"] not in event_doc["target_groups"]) or \
                ("expire_at" in event_doc and current_timestamp > event_doc["expire_at"]):
            # User is the one who emitted the event, OR
            # User is not targeted by this event, OR
            # This event is expired, so we skip it
            self._last_handled_event_timestamp = event_doc["timestamp"]
            return

        route = event_doc["route"]
        if not route.startswith("/"):
            route = "/" + route

        url_with_route = self._webserver_url + route

        # Send the event to the webserver API
        funct = getattr(requests, event_doc["type"])
        if not event_doc["content"]:
            response_obj = funct(url_with_route)
        else:
            response_obj = funct(url_with_route, **event_doc["content"])

        if response_obj.status_code == 200 and "responses" in event_doc:
            # A response is expected
            self._respond_to_event(event_doc, response_obj)

        # Update the last handled timestamp
        self._last_handled_event_timestamp = event_doc["timestamp"]

    def run(self):
        # Reset the error count
        self._error_count = 0

        # Retrieve the new events that were added since the last connection
        db_cursor = self._manager.collection.find({
            "timestamp": {
                "$gt": self._last_handled_event_timestamp
            }
        }).sort("timestamp", 1)

        # Process these events
        for event_doc in db_cursor:
            if not self._manager.is_running:
                self._update_last_handled_event_timestamp()
                return
            self._process_event(event_doc)

        if db_cursor.retrieved > 0:
            self._update_last_handled_event_timestamp()

        # Watch for new event documents directly on the collection
        with self._manager.collection.watch([{"$match": {"operationType": "insert"}}]) as stream:
            while self._manager.is_running:
                try:
                    # Non-blocking method to get the next change
                    change = stream.try_next()
                    if change:
                        event_doc = change["fullDocument"]
                        self._process_event(event_doc)
                        self._update_last_handled_event_timestamp()
                except pymongo.errors.PyMongoError as e:
                    print(f"Error in change stream: {e}")
                    self._error_count += 1
                    if self._error_count > 4:
                        print("Stopping the Event Handling due to the errors.")
                        return

                sleep(0.2)


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

    def start(self):
        if self._worker_thread:
            raise RuntimeError("The Event Handler cannot be started multiple times.")
        if not self._webserver:
            raise RuntimeError("Webserver not set. Cannot start the event handler.")

        self._worker_thread = EventHandlerWorker(self)

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
                           expire_in_secs: Optional[int]):
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

    if expire_in_secs is not None and (not isinstance(expire_in_secs, (int, float)) or expire_in_secs <= 0):
        return False, "The event 'expire_in' can only be None or a strictly positive integer."

    return True, None


@require_events_handler
def send_event(event_route: str,
               event_type: str,
               content: Optional[dict] = None,
               target_users: Optional[list] = None,
               target_groups: Optional[list] = None,
               expire_in_secs: Optional[float] = None,
               expect_responses: bool = False):
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
        event_route, event_type, content, target_users, target_groups, expire_in_secs)

    if not is_valid:
        raise ValueError(invalid_msg)

    timestamp = datetime.now(timezone.utc)
    event = {
        "timestamp": timestamp,
        "user_id": _EVENT_HANDLER.user_profile["user_id"],
        "route": event_route,
        "type": event_type,
        "target_users": target_users,
        "target_groups": target_groups
    }

    if content is not None:
        event["content"] = content

    if expire_in_secs is not None:
        event["expire_at"] = timestamp + timedelta(seconds=expire_in_secs)

    if expect_responses:
        event["responses"] = []

    event_doc_id = _EVENT_HANDLER.collection.insert_one(event).inserted_id

    return event_doc_id


@require_events_handler
def get_event_doc(event_doc_id: str) -> Optional[dict]:
    return _EVENT_HANDLER.collection.find_one({"_id": event_doc_id})
