import os
import platform
from appdirs import user_data_dir
from typing import Union, Optional
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import certifi
from pymongo import MongoClient
from semver import VersionInfo

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

def _get_studio_global_settings_overrides_for_version(collection, version=None):
    return collection.find_one({"type": "global_settings_versioned", "version": version})

def check_version_order(version_order_key, all_versions_keys, collection, version, version_order_checked=False):
    if version_order_checked:
        return

    # Query document holding sorted list of version strings
    doc = collection.find_one({"type": version_order_key} or {})
    if not doc:
        doc = {"type":  version_order_key}

    if all_versions_keys not in doc:
        doc[all_versions_keys] = []

    # Skip if the current version is already available
    if version in doc[all_versions_keys]:
        return

    # Add the current version and existing versions, then sort them
    all_objected_versions = [VersionInfo.parse(version)]
    for version_str in doc[all_versions_keys]:
        all_objected_versions.append(VersionInfo.parse(version_str))

    doc[all_versions_keys] = [
        str(version) for version in sorted(all_objected_versions)
    ]

    # Update the document in the database
    collection.replace_one(
        {"type": version_order_key},
        doc,
        upsert=True
        )
    return True

def find_closest_global_settings(collection, settings_key, fallback_key, version):
    check_version_order("versions_order",
                         "all_versions",
                         collection,
                         version,
                         version_order_checked=False)

    doc_filters = {
        "type": {"$in": [settings_key, fallback_key]}
    }
    other_versions = collection.find(
        doc_filters,
        {
            "_id": True,
            "version": True,
            "type": True
        }
    )

    versioned_doc = collection.find_one({"type": "versions_order"}) or {}

    legacy_settings_doc = None
    versioned_settings_by_version = {}
    for doc in other_versions:
        if doc["type"] == fallback_key:
            legacy_settings_doc = doc
        elif doc["type"] == settings_key:
            if doc["version"] == version:
                return doc["_id"]
            versioned_settings_by_version[doc["version"]] = doc

    versions_in_doc = versioned_doc.get("all_versions") or []
    # Cases when only legacy settings can be used
    if (
            # There are not versioned documents yet
            not versioned_settings_by_version
            # Versioned document is not available at all
            # - this can happen only if old build of QuadPype was used
            or not versioned_doc
            # Current QuadPype version is not available
            # - something went really wrong when this happens
            or version not in versions_in_doc
    ):
        if not legacy_settings_doc:
            return None
        return legacy_settings_doc["_id"]


    # Separate versions to lower and higher and keep their order
    lower_versions = []
    higher_versions = []
    before = True
    for version_str in versions_in_doc:
        if version_str == version:
            before = False
        elif before:
            lower_versions.append(version_str)
        else:
            higher_versions.append(version_str)

    # Use legacy settings doc as source document
    src_doc_id = None
    if legacy_settings_doc:
        src_doc_id = legacy_settings_doc["_id"]

    # Find the highest version which has available settings
    if lower_versions:
        for version_str in reversed(lower_versions):
            doc = versioned_settings_by_version.get(version_str)
            if doc:
                src_doc_id = doc["_id"]
                break
    # Use versions with higher version only if there are no legacy
    #   settings and there are not any versions before
    if src_doc_id is None and higher_versions:
        for version_str in higher_versions:
            doc = versioned_settings_by_version.get(version_str)
            if doc:
                src_doc_id = doc["_id"]
                break

    if src_doc_id is None:
        return None
    return collection.find_one({"_id": src_doc_id})

def get_global_settings_overrides_doc(collection, version):
    document = _get_studio_global_settings_overrides_for_version(collection, version)
    if document is None:
        document = find_closest_global_settings(collection,
                                                "global_settings_versioned",
                                                "global_settings",
                                                str(version))

    version = None
    if document and document["type"] == "global_settings_versioned":
        version = document["version"]

    return document, version

def get_studio_global_settings_overrides(url: str, version=None):
    kwargs = {}
    if should_add_certificate_path_to_mongo_url(url):
        kwargs["tlsCAFile"] = certifi.where()
    client = MongoClient(url, **kwargs)
    quadpype_db = os.getenv("QUADPYPE_DATABASE_NAME") or "quadpype"
    collection = client[quadpype_db]["settings"]
    document, version = get_global_settings_overrides_doc(collection, version)

    if not document:
        document = collection.find_one({"type": "global_settings"})
    client.close()
    return document.get("data") if document else {}

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
