# -*- coding: utf-8 -*-
"""Tools used in **Igniter** GUI."""
import os
import sys
from typing import Union
from urllib.parse import urlparse
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

from .settings_utils import should_add_certificate_path_to_mongo_url


def is_running_locally():
    return "python" in os.path.basename(sys.executable).lower()


def validate_mongo_connection(cnx: str) -> (bool, str):
    """Check if provided mongodb URL is valid.

    Args:
        cnx (str): URL to validate.

    Returns:
        (bool, str): True if ok, False if not and reason in str.

    """
    parsed = urlparse(cnx)
    if parsed.scheme not in ["mongodb", "mongodb+srv"]:
        return False, "Not mongodb schema"

    kwargs = {
        "serverSelectionTimeoutMS": os.getenv("AVALON_TIMEOUT", 2000)
    }
    # Add certificate path if should be required
    if should_add_certificate_path_to_mongo_url(cnx):
        kwargs["tlsCAFile"] = certifi.where()

    try:
        client = MongoClient(cnx, **kwargs)
        client.server_info()
        with client.start_session():
            pass
        client.close()
    except ServerSelectionTimeoutError as e:
        return False, f"Cannot connect to server {cnx} - {e}"
    except ValueError:
        return False, f"Invalid port specified {parsed.port}"
    except (ConfigurationError, OperationFailure, InvalidURI) as exc:
        return False, str(exc)
    else:
        return True, "Connection is successful"


def validate_mongo_string(mongo: str) -> (bool, str):
    """Validate string if it is mongo url acceptable by **Igniter**..

    Args:
        mongo (str): String to validate.

    Returns:
        (bool, str):
            True if valid, False if not and in second part of tuple
            the reason why it failed.

    """
    if not mongo:
        return True, "empty string"
    return validate_mongo_connection(mongo)


def validate_path_string(path: str) -> (bool, str):
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


def get_quadpype_path_from_settings(settings: dict) -> Union[str, None]:
    """Get QuadPype path from global settings.

    Args:
        settings (dict): mongodb url.

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
