"""Kitsu credentials functions."""

import os
from typing import Tuple, Optional
import gazu

from quadpype.lib import emit_event, QuadPypeSecureRegistry


def validate_credentials(
    login: str,
    password: str,
    kitsu_url: Optional[str] = None,
) -> bool:
    """Validate credentials by trying to connect to Kitsu host URL.

    Args:
        login (str): Kitsu user login
        password (str): Kitsu user password
        kitsu_url (str, optional): Kitsu host URL. Defaults to None.

    Returns:
        bool: Are credentials valid?
    """

    if kitsu_url is None:
        kitsu_url = os.getenv("KITSU_SERVER")
        if not kitsu_url:
            raise

    # Connect to server
    validate_host(kitsu_url)

    # Authenticate
    try:
        gazu.log_in(login, password)
    except gazu.exception.AuthFailedException:
        return False

    emit_event("kitsu.user.logged", data={"username": login}, source="kitsu")

    return True


def validate_host(kitsu_url: str) -> bool:
    """Validate credentials by trying to connect to Kitsu host URL.

    Args:
        kitsu_url (str, optional): Kitsu host URL.

    Returns:
        bool: Is host valid?
    """
    # Connect to server
    gazu.set_host(kitsu_url)

    # Test host
    if gazu.client.host_is_valid():
        return True
    else:
        raise gazu.exception.HostException(f"Host '{kitsu_url}' is invalid.")


def clear_credentials():
    """Clear credentials in Secure Registry."""
    (login, password) = load_credentials()
    if login is None and password is None:
        return

    # Get user registry
    user_registry = QuadPypeSecureRegistry("kitsu_user")

    # Set user settings
    if login is not None:
        user_registry.delete_item("login")
    if password is not None:
        user_registry.delete_item("password")


def save_credentials(login: str, password: str):
    """Save credentials in Secure Registry.

    Args:
        login (str): Kitsu user login
        password (str): Kitsu user password
    """
    # Get user registry
    user_registry = QuadPypeSecureRegistry("kitsu_user")

    # Set user settings
    user_registry.set_item("login", login)
    user_registry.set_item("password", password)


def load_credentials() -> Tuple[str, str]:
    """Load registered credentials.

    Returns:
        Tuple[str, str]: (Login, Password)
    """
    # Get user registry
    user_registry = QuadPypeSecureRegistry("kitsu_user")

    return (
        user_registry.get_item("login", None),
        user_registry.get_item("password", None)
    )


def set_credentials_envs(login: str, password: str):
    """Set environment variables with Kitsu login and password.

    Args:
        login (str): Kitsu user login
        password (str): Kitsu user password
    """
    os.environ["KITSU_LOGIN"] = login
    os.environ["KITSU_PWD"] = password
