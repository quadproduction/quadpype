import os


def get_ftrack_event_database_info():
    database_name = os.environ["QUADPYPE_DATABASE_NAME"]
    collection_name = "ftrack_events"
    return database_name, collection_name
