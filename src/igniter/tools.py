# -*- coding: utf-8 -*-
"""Tools used in **Igniter** GUI."""
import os
from typing import Union
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import platform

import certifi
from pymongo import MongoClient
from pymongo.errors import (
    ServerSelectionTimeoutError,
    InvalidURI,
    ConfigurationError,
    OperationFailure
)


class QuadPypeVersionNotFound(Exception):
    """QuadPype version was not found in remote and local repository."""
    pass


class QuadPypeVersionIncompatible(Exception):
    """QuadPype version is not compatible with the installed one (build)."""
    pass


def should_add_certificate_path_to_database_uri(database_uri):
    """Check if should add ca certificate to database uri.

    Since 30.9.2021 cloud mongo requires newer certificates that are not
    available on most of workstation. This adds path to certificate
    which is valid for it. To add the certificate path url must have scheme
    'mongodb+srv' or has 'ssl=true' or 'tls=true' in url query.
    """
    parsed = urlparse(database_uri)
    query = parse_qs(parsed.query)
    lowered_query_keys = set(key.lower() for key in query.keys())
    add_certificate = False
    # Check if url 'ssl' or 'tls' are set to 'true'
    for key in ("ssl", "tls"):
        if key in query and "true" in query[key]:
            add_certificate = True
            break

    # Check if url contains 'mongodb+srv'
    if not add_certificate and parsed.scheme == "mongodb+srv":
        add_certificate = True

    # Check if url does already contain certificate path
    if add_certificate and "tlscafile" in lowered_query_keys:
        add_certificate = False
    return add_certificate


def validate_database_connection(database_uri: str) -> tuple[bool, str]:
    """Check if provided database URI is valid.

    Args:
        database_uri (str): URL to validate.

    Returns:
        (bool, str): True if ok, False if not and reason in str.

    """
    parsed = urlparse(database_uri)
    if parsed.scheme not in ["mongodb", "mongodb+srv"]:
        return False, "Not mongodb schema"

    kwargs = {
        "serverSelectionTimeoutMS": os.getenv("QUADPYPE_DB_TIMEOUT", 2000)
    }
    # Add certificate path if should be required
    if should_add_certificate_path_to_database_uri(database_uri):
        kwargs["tlsCAFile"] = certifi.where()

    try:
        client = MongoClient(database_uri, **kwargs)
        client.server_info()
        with client.start_session():
            pass
        client.close()
    except ServerSelectionTimeoutError as e:
        return False, f"Cannot connect to server {database_uri} - {e}"
    except ValueError:
        return False, f"Invalid port specified {parsed.port}"
    except (ConfigurationError, OperationFailure, InvalidURI) as exc:
        return False, str(exc)
    else:
        return True, "Connection is successful"


def validate_database_uri(database_uri: str) -> tuple[bool, str]:
    """Validate string if it is database uri acceptable by **Igniter**..

    Args:
        database_uri (str): String to validate.

    Returns:
        (bool, str):
            True if valid, False if not and in second part of tuple
            the reason why it failed.

    """
    if not database_uri:
        return True, "empty string"
    return validate_database_connection(database_uri)


def validate_path_string(path: str) -> tuple[bool, str]:
    """Validate string if it is path to QuadPype repository.

    Args:
        path (str): Path to validate.


    Returns:
        (bool, str):
            True if valid, False if not and in second part of tuple
            the reason why it failed.

    """
    if not path:
        return False, "empty string"

    if not Path(path).exists():
        return False, "path doesn't exists"

    if not Path(path).is_dir():
        return False, "path is not directory"

    return True, "valid path"


def get_quadpype_global_settings(database_uri: str) -> dict:
    """Load global settings from database URI.

    We are loading data from database `quadpype` and collection `settings`.
    There we expect document type `global_settings`.

    Args:
        database_uri (str): Database URI.

    Returns:
        dict: With settings data. Empty dictionary is returned if not found.
    """
    kwargs = {}
    if should_add_certificate_path_to_database_uri(database_uri):
        kwargs["tlsCAFile"] = certifi.where()

    try:
        # Create database connection
        client = MongoClient(database_uri, **kwargs)
        # Access settings collection
        quadpype_db = os.getenv("QUADPYPE_DATABASE_NAME") or "quadpype"
        col = client[quadpype_db]["settings"]
        # Query global settings
        global_settings = col.find_one({"type": "global_settings"}) or {}
        # Close database connection
        client.close()

    except Exception:
        # TODO log traceback or message
        return {}

    return global_settings.get("data") or {}


def get_quadpype_path_from_settings(settings: dict) -> Union[str, None]:
    """Get QuadPype path from global settings.

    Args:
        settings (dict): settings from DB.

    Returns:
        path to QuadPype or None if not found
    """
    paths = (
        settings
        .get("quadpype_path", {})
        .get(platform.system().lower())
    ) or []
    # For cases when `quadpype_path` is a single path
    if paths and isinstance(paths, str):
        paths = [paths]

    return next((path for path in paths if os.path.exists(path)), None)


def get_local_quadpype_path_from_settings(settings: dict) -> Union[Path, None]:
    """Get QuadPype local path from global settings.

    Used to download and unzip QuadPype versions.
    Args:
        settings (dict): settings from DB.

    Returns:
        path to QuadPype or None if not found
    """
    path = (
        settings
        .get("local_quadpype_path", {})
        .get(platform.system().lower())
    )
    if path:
        return Path(path)
    return None


def get_expected_studio_version_str(
    staging=False, global_settings=None
) -> str:
    """Version that should be currently used in studio.

    Args:
        staging (bool): Get current version for staging.
        global_settings (dict): Optional precached global settings.

    Returns:
        str: QuadPype version which should be used. Empty string means latest.
    """
    database_uri = os.getenv("QUADPYPE_DB_URI")
    if global_settings is None:
        global_settings = get_quadpype_global_settings(database_uri)
    key = "staging_version" if staging else "production_version"
    return global_settings.get(key) or ""


def load_stylesheet() -> str:
    """Load the CSS stylesheet.

    Returns:
        str: content of the stylesheet

    """
    stylesheet_path = Path(__file__).parent.resolve().joinpath(
        "resources", "style", "stylesheet.css")

    return stylesheet_path.read_text()


def get_app_icon_path(variation_name=None) -> str:
    """Path to the app icon png file.

    Returns:
        str: path of the png icon file

    """
    if not variation_name:
        variation_name = "default"

    icon_path = Path(__file__).parent.resolve().joinpath(
        "resources", "icons", "quadpype_icon_{}.png".format(variation_name))

    return str(icon_path)


def get_fonts_dir_path() -> str:
    """Path to the igniter fonts directory.

    Returns:
        str: path to the directory containing the font files

    """
    return str(Path(__file__).parent.resolve().joinpath("resources", "fonts"))
