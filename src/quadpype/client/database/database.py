import os
import sys
import time
import logging
import pymongo
import certifi

from bson.json_util import (
    loads,
    dumps,
    CANONICAL_JSON_OPTIONS
)

if sys.version_info[0] == 2:
    from urlparse import urlparse, parse_qs
else:
    from urllib.parse import urlparse, parse_qs


class DatabaseEnvNotSet(Exception):
    pass


def documents_to_json(docs):
    """Convert documents to json string.

    Args:
        Union[list[dict[str, Any]], dict[str, Any]]: Document/s to convert to
            json string.

    Returns:
        str: Json string with database documents.
    """

    return dumps(docs, json_options=CANONICAL_JSON_OPTIONS)


def load_json_file(filepath):
    """Load database documents from a json file.

    Args:
        filepath (str): Path to a json file.

    Returns:
        Union[dict[str, Any], list[dict[str, Any]]]: Loaded content from a
            json file.
    """

    if not os.path.exists(filepath):
        raise ValueError("Path {} was not found".format(filepath))

    with open(filepath, "r") as stream:
        content = stream.read()
    return loads("".join(content))


def get_project_database_name():
    """Name of database name where projects are available.

    Returns:
        str: Name of database name where projects are.
    """

    return os.getenv("QUADPYPE_PROJECTS_DB_NAME") or "quadpype_projects"


def _decompose_uri(database_uri):
    """Decompose database URI to basic components.

    Used for creation of MongoHandler which expect database URI components as
    separated kwargs. Components are at the end not used as we're setting
    connection directly this is just a dumb components for MongoHandler
    validation pass.
    """

    # Use first url from passed url
    #   - this is because it is possible to pass multiple urls for multiple
    #       replica sets which would crash on urlparse otherwise
    #   - please don't use comma in username of password
    database_uri = database_uri.split(",")[0]
    components = {
        "scheme": None,
        "host": None,
        "port": None,
        "username": None,
        "password": None,
        "auth_db": None
    }

    result = urlparse(database_uri)
    if result.scheme is None:
        _uri = "mongodb://{}".format(database_uri)
        result = urlparse(_uri)

    components["scheme"] = result.scheme
    components["host"] = result.hostname
    try:
        components["port"] = result.port
    except ValueError:
        raise RuntimeError("invalid port specified")
    components["username"] = result.username
    components["password"] = result.password

    try:
        components["auth_db"] = parse_qs(result.query)['authSource'][0]
    except KeyError:
        # no auth db provided, database will use the one we are connecting to
        pass

    return components


def get_database_uri_components():
    database_uri = os.getenv("QUADPYPE_DB_URI")
    if database_uri is None:
        raise DatabaseEnvNotSet(
            "URI of Database is not set."
        )
    return _decompose_uri(database_uri)


def should_add_certificate_path_to_database_uri(database_uri):
    """Check if should add ca certificate to database URI.

    Since 30.9.2021 cloud mongo requires newer certificates that are not
    available on most of workstation. This adds path to certifi certificate
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


def validate_database_connection(database_uri):
    """Check if the provided database URI is valid.

    Args:
        database_uri (str): URL to validate.

    Raises:
        ValueError: When the port in database uri is not valid.
        pymongo.errors.InvalidURI: If the passed database URI is invalid.
        pymongo.errors.ServerSelectionTimeoutError: If connection timeout
            passed so probably couldn't connect to the database.

    """

    client = QuadPypeDBConnection.create_connection(
        database_uri, retry_attempts=1
    )
    client.close()


class QuadPypeDBConnection:
    """Singleton Database connection.

    Keeps database connections by URI.
    """

    database_clients = {}
    log = logging.getLogger("QuadPypeDBConnection")

    @staticmethod
    def get_default_database_uri():
        return os.environ["QUADPYPE_DB_URI"]

    @classmethod
    def get_database_client(cls, database_uri=None):
        if database_uri is None:
            database_uri = cls.get_default_database_uri()

        connection = cls.database_clients.get(database_uri)
        if connection:
            # Naive validation of existing connection
            try:
                connection.server_info()
                with connection.start_session():
                    pass
            except Exception:
                connection = None

        if not connection:
            cls.log.debug("Creating database connection to {}".format(database_uri))
            connection = cls.create_connection(database_uri)
            cls.database_clients[database_uri] = connection

        return connection

    @classmethod
    def create_connection(cls, database_uri, timeout=None, retry_attempts=None):
        parsed = urlparse(database_uri)
        # Force validation of scheme
        if parsed.scheme not in ["mongodb", "mongodb+srv"]:
            raise pymongo.errors.InvalidURI((
                "Invalid URI scheme:"
                " URI must begin with 'mongodb://' or 'mongodb+srv://'"
            ))

        if timeout is None:
            timeout = int(os.getenv("QUADPYPE_DB_TIMEOUT") or 1000)

        kwargs = {
            "serverSelectionTimeoutMS": timeout
        }
        if should_add_certificate_path_to_database_uri(database_uri):
            kwargs["tlsCAFile"] = certifi.where()

        database_client = pymongo.MongoClient(database_uri, **kwargs)

        if retry_attempts is None:
            retry_attempts = 3

        elif not retry_attempts:
            retry_attempts = 1

        last_exc = None
        valid = False
        t1 = time.time()
        for attempt in range(1, retry_attempts + 1):
            try:
                database_client.server_info()
                with database_client.start_session():
                    pass
                valid = True
                break

            except Exception as exc:
                last_exc = exc
                if attempt < retry_attempts:
                    cls.log.warning(
                        "Attempt {} failed. Retrying... ".format(attempt)
                    )
                    time.sleep(1)

        if not valid:
            raise last_exc

        cls.log.info("Connected to {}, delay {:.3f}s".format(
            database_uri, time.time() - t1
        ))
        return database_client


# ------ Helper Database functions ------
# Functions can be helpful with custom tools to backup/restore database state.
# Not meant as API functionality that should be used in production codebase!
def get_collection_documents(database_name, collection_name, as_json=False):
    """Query all documents from a collection.

    Args:
        database_name (str): Name of database where to look for collection.
        collection_name (str): Name of collection where to look for collection.
        as_json (Optional[bool]): Output should be a json string.
            Default: 'False'

    Returns:
        Union[list[dict[str, Any]], str]: Queried documents.
    """

    client = QuadPypeDBConnection.get_database_client()
    output = list(client[database_name][collection_name].find({}))
    if as_json:
        output = documents_to_json(output)
    return output


def store_collection(filepath, database_name, collection_name):
    """Store collection documents to a json file.

    Args:
        filepath (str): Path to a json file where documents will be stored.
        database_name (str): Name of database where to look for collection.
        collection_name (str): Name of collection to store.
    """

    # Make sure directory for output file exists
    dirpath = os.path.dirname(filepath)
    if not os.path.isdir(dirpath):
        os.makedirs(dirpath)

    content = get_collection_documents(database_name, collection_name, True)
    with open(filepath, "w") as stream:
        stream.write(content)


def replace_collection_documents(docs, database_name, collection_name):
    """Replace all documents in a collection with passed documents.

    Warnings:
        All existing documents in collection will be removed if there are any.

    Args:
        docs (list[dict[str, Any]]): New documents.
        database_name (str): Name of database where to look for collection.
        collection_name (str): Name of collection where new documents are
            uploaded.
    """

    client = QuadPypeDBConnection.get_database_client()
    database = client[database_name]
    if collection_name in database.list_collection_names():
        database.drop_collection(collection_name)
    col = database[collection_name]
    col.insert_many(docs)


def restore_collection(filepath, database_name, collection_name):
    """Restore/replace collection from a json filepath.

    Warnings:
        All existing documents in collection will be removed if there are any.

    Args:
        filepath (str): Path to a json with documents.
        database_name (str): Name of database where to look for collection.
        collection_name (str): Name of collection where new documents are
            uploaded.
    """

    docs = load_json_file(filepath)
    replace_collection_documents(docs, database_name, collection_name)


def get_project_database(database_name=None):
    """Database object where project collections are.

    Args:
        database_name (Optional[str]): Custom name of database.

    Returns:
        pymongo.database.Database: Collection related to passed project.
    """

    if not database_name:
        database_name = get_project_database_name()
    return QuadPypeDBConnection.get_database_client()[database_name]


def get_project_connection(project_name, database_name=None):
    """Direct access to database collection.

    We're trying to avoid using direct access to the database. This should be used
    only for Create, Update and Remove operations until there are implemented
    api calls for that.

    Args:
        project_name (str): Project name for which collection should be
            returned.
        database_name (Optional[str]): Custom name of database.

    Returns:
        pymongo.collection.Collection: Collection related to passed project.
    """

    if not project_name:
        raise ValueError("Invalid project name {}".format(str(project_name)))
    return get_project_database(database_name)[project_name]


def get_project_documents(project_name, database_name=None):
    """Query all documents from project collection.

    Args:
        project_name (str): Name of project.
        database_name (Optional[str]): Name of database where to look for
            project.

    Returns:
        list[dict[str, Any]]: Documents in project collection.
    """

    if not database_name:
        database_name = get_project_database_name()
    return get_collection_documents(database_name, project_name)


def store_project_documents(project_name, filepath, database_name=None):
    """Store project documents to a file as json string.

    Args:
        project_name (str): Name of project to store.
        filepath (str): Path to a json file where output will be stored.
        database_name (Optional[str]): Name of database where to look for
            project.
    """

    if not database_name:
        database_name = get_project_database_name()

    store_collection(filepath, database_name, project_name)


def replace_project_documents(project_name, docs, database_name=None):
    """Replace documents in the database with passed documents.

    Warnings:
        Existing project collection is removed if exists in the database collection.

    Args:
        project_name (str): Name of project.
        docs (list[dict[str, Any]]): Documents to restore.
        database_name (Optional[str]): Name of database where project
            collection will be created.
    """

    if not database_name:
        database_name = get_project_database_name()
    replace_collection_documents(docs, database_name, project_name)


def restore_project_documents(project_name, filepath, database_name=None):
    """Restore documents in the database with passed documents.

    Warnings:
        Existing project collection is removed if exists in the database collection.

    Args:
        project_name (str): Name of project.
        filepath (str): File to json file with project documents.
        database_name (Optional[str]): Name of database where project
            collection will be created.
    """

    if not database_name:
        database_name = get_project_database_name()
    restore_collection(filepath, database_name, project_name)
