# -*- coding: utf-8 -*-
"""Package storing all functions related to user data."""
import os
import getpass

from .user_settings import QuadPypeSettingsRegistry
from quadpype.settings import GENERAL_SETTINGS_KEY, get_user_settings


def _create_user_id(registry=None):
    """Create a user identifier."""
    from coolname import generate_slug

    if registry is None:
        registry = QuadPypeSettingsRegistry()

    new_id = generate_slug(3)

    print("Created user id \"{}\"".format(new_id))

    registry.set_item("user_id", new_id)

    return new_id


def get_user_id():
    """Get user identifier.

    Identifier is created if it does not exists yet.
    """

    registry = QuadPypeSettingsRegistry()
    try:
        return registry.get_item("user_id")
    except ValueError:
        return _create_user_id(registry=registry)


def get_local_site_id():
    """Get the local site identifier."""

    # Check if the value is set on the env variable
    # This is used for background syncing
    if os.getenv("QUADPYPE_LOCAL_ID"):
        return os.environ["QUADPYPE_LOCAL_ID"]

    # Else using the user ID
    return get_user_id()


def get_quadpype_username():
    """QuadPype username used for templates and publishing.

    May be different from machine's username.

    Always returns "QUADPYPE_USERNAME" environment if is set then tries local
    settings and last option is to use `getpass.getuser()` which returns
    machine username.
    """

    username = os.getenv("QUADPYPE_USERNAME")
    if not username:
        user_settings = get_user_settings()
        username = (
            user_settings
            .get(GENERAL_SETTINGS_KEY, {})
            .get("username")
        )
        if not username:
            username = getpass.getuser()
    return username
