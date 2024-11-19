from quadpype.client.mongo import validate_mongo_connection
from .registry import QuadPypeSecureRegistry


def change_quadpype_mongo_url(new_mongo_url):
    """Change mongo url in QuadPype registry.

    Change of QuadPype mongo URL require restart of running QuadPype processes or
    processes using pype.
    """

    validate_mongo_connection(new_mongo_url)
    key = "quadpypeMongo"
    registry = QuadPypeSecureRegistry("mongodb")
    existing_value = registry.get_item(key, None)
    if existing_value is not None:
        registry.delete_item(key)
    registry.set_item(key, new_mongo_url)
