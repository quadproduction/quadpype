"""
Logging to console and to database. For database logging, you need to set either
`QUADPYPE_LOG_TO_SERVER` to True as en environment variable.
"""


import datetime
import getpass
import logging
import os
import platform
import socket
import sys
import time
import traceback
import threading
import copy

from quadpype.client.database import (
    DatabaseEnvNotSet,
    get_database_uri_components,
    QuadPypeDBConnection,
)
from . import Terminal

try:
    import log4mongo
    from log4mongo.handlers import MongoHandler
except ImportError:
    log4mongo = None
    MongoHandler = type("NOT_SET", (), {})

# Check for `unicode` in builtins
USE_UNICODE = hasattr(__builtins__, "unicode")


class LogStreamHandler(logging.StreamHandler):
    """ StreamHandler class designed to handle utf errors in python 2.x hosts.

    """

    def __init__(self, stream=None):
        super().__init__(stream)
        self.enabled = True

    def enable(self):
        """ Enable StreamHandler

            Used to silence output
        """
        self.enabled = True

    def disable(self):
        """ Disable StreamHandler

            Make StreamHandler output again
        """
        self.enabled = False

    def emit(self, record):
        if not self.enable:
            return
        try:
            msg = self.format(record)
            msg = Terminal.log(msg)
            stream = self.stream
            if stream is None:
                return
            fs = "%s\n"
            # if no unicode support...
            if not USE_UNICODE:
                stream.write(fs % msg)
            else:
                try:
                    if (isinstance(msg, unicode) and  # noqa: F821
                            getattr(stream, 'encoding', None)):
                        ufs = u'%s\n'
                        try:
                            stream.write(ufs % msg)
                        except UnicodeEncodeError:
                            stream.write((ufs % msg).encode(stream.encoding))
                    else:
                        if (getattr(stream, 'encoding', 'utf-8')):
                            ufs = u'%s\n'
                            stream.write(ufs % unicode(msg))  # noqa: F821
                        else:
                            stream.write(fs % msg)
                except UnicodeError:
                    stream.write(fs % msg.encode("UTF-8"))
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise

        except OSError:
            self.handleError(record)
        except ValueError:
            # this is raised when logging during interpreter shutdown
            # or it real edge cases where logging stream is already closed.
            # In particular, it happens a lot in 3DEqualizer.
            # TODO: remove this condition when the cause is found.
            pass

        except Exception:
            print(repr(record))
            self.handleError(record)


class LogFormatter(logging.Formatter):

    DFT = '%(levelname)s >>> { %(name)s }: [ %(message)s ]'
    default_formatter = logging.Formatter(DFT)

    def __init__(self, formats):
        super().__init__()
        self.formatters = {}
        for loglevel in formats:
            self.formatters[loglevel] = logging.Formatter(formats[loglevel])

    def format(self, record):
        formatter = self.formatters.get(record.levelno, self.default_formatter)

        _exc_info = record.exc_info
        record.exc_info = None

        out = formatter.format(record)
        record.exc_info = _exc_info

        if record.exc_info is not None:
            line_len = len(str(record.exc_info[1]))
            if line_len > 30:
                line_len = 30
            out = "{}\n{}\n{}\n{}\n{}".format(
                out,
                line_len * "=",
                str(record.exc_info[1]),
                line_len * "=",
                self.formatException(record.exc_info)
            )
        return out


class DatabaseFormatter(logging.Formatter):

    DEFAULT_PROPERTIES = logging.LogRecord(
        '', '', '', '', '', '', '', '').__dict__.keys()

    def format(self, record):
        """Formats LogRecord into python dictionary."""
        # Standard document
        document = {
            'timestamp': datetime.datetime.now(),
            'level': record.levelname,
            'thread': record.thread,
            'threadName': record.threadName,
            'message': record.getMessage(),
            'loggerName': record.name,
            'fileName': record.pathname,
            'module': record.module,
            'method': record.funcName,
            'lineNumber': record.lineno
        }
        document.update(Logger.get_process_data())

        # Standard document decorated with exception info
        if record.exc_info is not None:
            document['exception'] = {
                'message': str(record.exc_info[1]),
                'code': 0,
                'stackTrace': self.formatException(record.exc_info)
            }

        # Standard document decorated with extra contextual information
        if len(self.DEFAULT_PROPERTIES) != len(record.__dict__):
            contextual_extra = set(record.__dict__).difference(
                set(self.DEFAULT_PROPERTIES))
            if contextual_extra:
                for key in contextual_extra:
                    document[key] = record.__dict__[key]
        return document


class Logger:
    DFT = "%(levelname)s >>> { %(name)s }: [ %(message)s ] "
    DBG = "  - { %(name)s }: [ %(message)s ] "
    INF = ">>> [ %(message)s ] "
    WRN = "*** WRN: >>> { %(name)s }: [ %(message)s ] "
    ERR = "!!! ERR: %(asctime)s >>> { %(name)s }: [ %(message)s ] "
    CRI = "!!! CRI: %(asctime)s >>> { %(name)s }: [ %(message)s ] "

    FORMAT_FILE = {
        logging.INFO: INF,
        logging.DEBUG: DBG,
        logging.WARNING: WRN,
        logging.ERROR: ERR,
        logging.CRITICAL: CRI,
    }

    # Is static class initialized
    bootstraped = False
    initialized = False
    _init_lock = threading.Lock()

    # Defines if database logging should be used
    use_database_logging = None
    database_process_id = None

    # Database name in Mongo
    log_database_name = os.getenv("QUADPYPE_DATABASE_NAME")
    # Collection name under database in Mongo
    log_collection_name = "logs"

    # Logging level - QUADPYPE_LOG_LEVEL
    log_level = None

    # Data same for all record documents
    process_data = None
    # Cached process name or ability to set different process name
    _process_name = None

    @classmethod
    def get_logger(cls, name=None):
        if not cls.initialized:
            cls.initialize()

        logger = logging.getLogger(name or "__main__")

        logger.setLevel(cls.log_level)

        add_database_handler = cls.use_database_logging
        add_console_handler = True

        for handler in logger.handlers:
            if isinstance(handler, MongoHandler):
                add_database_handler = False
            elif isinstance(handler, LogStreamHandler):
                add_console_handler = False

        if add_console_handler:
            logger.addHandler(cls._get_console_handler())

        if add_database_handler:
            try:
                handler = cls._get_database_handler()
                if handler:
                    logger.addHandler(handler)

            except DatabaseEnvNotSet:
                # Skip if database environments are not set yet
                cls.use_database_logging = False

            except Exception:
                lines = traceback.format_exception(*sys.exc_info())
                for line in lines:
                    if line.endswith("\n"):
                        line = line[:-1]
                    Terminal.echo(line)
                cls.use_database_logging = False

        # Do not propagate logs to root logger
        logger.propagate = False
        return logger

    @classmethod
    def _get_database_handler(cls):
        cls.bootstrap_database_log()

        if not cls.use_database_logging:
            return

        components = get_database_uri_components()
        kwargs = {
            "host": components["host"],
            "database_name": cls.log_database_name,
            "collection": cls.log_collection_name,
            "username": components["username"],
            "password": components["password"],
            "capped": True,
            "formatter": DatabaseFormatter()
        }
        if components["port"] is not None:
            kwargs["port"] = int(components["port"])
        if components["auth_db"]:
            kwargs["authentication_db"] = components["auth_db"]

        return MongoHandler(**kwargs)

    @classmethod
    def _get_console_handler(cls):
        formatter = LogFormatter(cls.FORMAT_FILE)
        console_handler = LogStreamHandler()

        console_handler.set_name("LogStreamHandler")
        console_handler.setFormatter(formatter)
        return console_handler

    @classmethod
    def initialize(cls):
        # TODO update already created loggers on re-initialization
        if not cls._init_lock.locked():
            with cls._init_lock:
                cls._initialize()
        else:
            # If lock is locked wait until is finished
            while cls._init_lock.locked():
                time.sleep(0.1)

    @classmethod
    def _initialize(cls):
        # Change initialization state to prevent runtime changes
        # if is executed during runtime
        cls.initialized = False

        # Define if should logging to database be used
        use_database_logging = (
            log4mongo is not None
            and os.getenv("QUADPYPE_LOG_TO_SERVER") == "1"
        )

        # Set database id for process (ONLY ONCE)
        if use_database_logging and cls.database_process_id is None:
            try:
                from bson.objectid import ObjectId
            except Exception:
                use_database_logging = False

            # Check if database id was passed with environments and pop it
            # - This is for subprocesses that are part of another process
            #   like Ftrack event server has 3 other subprocesses that should
            #   use same database id
            if use_database_logging:
                database_id = os.environ.pop("QUADPYPE_PROCESS_DB_ID", None)
                if not database_id:
                    # Create new object id
                    database_id = ObjectId()
                else:
                    # Convert string to ObjectId object
                    database_id = ObjectId(database_id)
                cls.database_process_id = database_id

        # Store result to class definition
        cls.use_database_logging = use_database_logging

        # Define what is logging level
        log_level = os.getenv("QUADPYPE_LOG_LEVEL")
        if not log_level:
            # Check QUADPYPE_DEBUG for backwards compatibility
            op_debug = os.getenv("QUADPYPE_DEBUG")
            if op_debug and int(op_debug) > 0:
                log_level = logging.DEBUG
            else:
                log_level = logging.INFO
        cls.log_level = int(log_level)

        logging.basicConfig(level=cls.log_level)

        if not os.getenv("QUADPYPE_DB_URI"):
            cls.use_database_logging = False

        # Mark as initialized
        cls.initialized = True

    @classmethod
    def get_process_data(cls):
        """Data about current process which should be same for all records.

        Process data are used for each record sent to database.
        """
        if cls.process_data is not None:
            return copy.deepcopy(cls.process_data)

        if not cls.initialized:
            cls.initialize()

        host_name = socket.gethostname()
        try:
            host_ip = socket.gethostbyname(host_name)
        except socket.gaierror:
            host_ip = "127.0.0.1"

        process_name = cls.get_process_name()

        cls.process_data = {
            "process_id": cls.database_process_id,
            "workstation_name": host_name,
            "host_ip": host_ip,
            "username": getpass.getuser(),
            "system_name": platform.system(),
            "process_name": process_name
        }
        return copy.deepcopy(cls.process_data)

    @classmethod
    def set_process_name(cls, process_name):
        """Set process name for database logs."""
        # Just change the attribute
        cls._process_name = process_name
        # Update process data if are already set
        if cls.process_data is not None:
            cls.process_data["process_name"] = process_name

    @classmethod
    def get_process_name(cls):
        """Process name that is like "label" of a process.

        QuadPype's logging can be used from QuadPype itself of from hosts.
        Even in QuadPype process it's good to know if logs are from tray or
        from other cli commands. This should help to identify that information.
        """
        if cls._process_name is not None:
            return cls._process_name

        # Get process name
        process_name = os.getenv("QUADPYPE_HOST_DISPLAY_NAME")
        if not process_name:
            try:
                import psutil
                process = psutil.Process(os.getpid())
                process_name = process.name()

            except ImportError:
                pass

        if not process_name:
            process_name = os.path.basename(sys.executable)

        cls._process_name = process_name
        return cls._process_name

    @classmethod
    def bootstrap_database_log(cls):
        """Prepare database logging."""
        if cls.bootstraped:
            return

        if not cls.initialized:
            cls.initialize()

        if not cls.use_database_logging:
            return

        if not cls.log_database_name:
            raise ValueError("Database name for logs is not set")

        client = log4mongo.handlers._connection
        if not client:
            client = cls.get_log_database_connection()
            # Set the client inside log4mongo handlers to not create another
            # database connection.
            log4mongo.handlers._connection = client

        logdb = client[cls.log_database_name]

        collist = logdb.list_collection_names()
        if cls.log_collection_name not in collist:
            logdb.create_collection(
                cls.log_collection_name,
                capped=True,
                max=5000,
                size=1073741824
            )
        cls.bootstraped = True

    @classmethod
    def get_log_database_connection(cls):
        """Database connection that allows to get to log collection.

        This is implemented to prevent multiple connections to database from same
        process.
        """
        if not cls.initialized:
            cls.initialize()

        return QuadPypeDBConnection.get_database_client()
