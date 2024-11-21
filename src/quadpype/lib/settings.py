import os
import platform
from appdirs import user_data_dir
from typing import Union, Optional
from urllib.parse import urlparse, parse_qs
from pathlib import Path

import certifi
from pymongo import MongoClient


# TODO: Avoid code duplication with same function in mongo client
def should_add_certificate_path_to_mongo_url(mongo_url):
    """Check if should add ca certificate to mongo url.

    Since 30.9.2021 cloud mongo requires newer certificates that are not
    available on most of the workstations. This adds path to certifi certificate
    which is valid for it. To add the certificate path url must have scheme
    'mongodb+srv' or has 'ssl=true' or 'tls=true' in url query.
    """
    parsed = urlparse(mongo_url)
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


def get_quadpype_global_settings(url: str) -> dict:
    """Load global settings from Mongo database.

    We are loading data from database `quadpype` and collection `settings`.
    There we expect document type `global_settings`.

    Args:
        url (str): MongoDB url.

    Returns:
        dict: With settings data. Empty dictionary is returned if not found.
    """
    kwargs = {}
    if should_add_certificate_path_to_mongo_url(url):
        kwargs["tlsCAFile"] = certifi.where()

    try:
        # Create mongo connection
        client = MongoClient(url, **kwargs)
        # Access settings collection
        quadpype_db = os.getenv("QUADPYPE_DATABASE_NAME") or "quadpype"
        col = client[quadpype_db]["settings"]
        # Query global settings
        global_settings = col.find_one({"type": "global_settings"}) or {}
        # Close Mongo connection
        client.close()

    except Exception:
        # TODO log traceback or message
        return {}

    return global_settings.get("data") or {}


def get_expected_studio_version_str(staging=False, global_settings=None):
    """Expected QuadPype version that should be used at the moment.

    If version is not defined in settings the latest found version is
    used.

    Using precached global settings is needed for usage inside QuadPype.

    Args:
        staging (bool): Staging version or production version.
        global_settings (dict): Optional precached global settings.

    Returns:
        PackageVersion: Version that should be used.
    """
    mongo_url = os.getenv("QUADPYPE_MONGO")
    if global_settings is None:
        global_settings = get_quadpype_global_settings(mongo_url)
    key = "staging_version" if staging else "production_version"

    return global_settings.get(key, "")


def get_local_quadpype_path(settings: Optional[dict] = None) -> Union[Path, None]:
    """Get QuadPype local path from global settings.

    Used to download and unzip QuadPype versions.
    Args:
        settings (dict): settings from DB.

    Returns:
        path to QuadPype or None if not found
    """
    if settings is None:
        settings = get_quadpype_global_settings(os.environ["QUADPYPE_MONGO"])

    path = (
        settings
        .get("local_quadpype_path", {})
        .get(platform.system().lower())
    )
    if path:
        return Path(path)
    return Path(user_data_dir("quadpype", "quad"))
