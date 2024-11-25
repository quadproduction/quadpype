import threading
import asyncio
from pathlib import Path
from datetime import date

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from quadpype import get_all_registered_web_api_routers
from quadpype.version import __version__
from quadpype.resources import get_app_favicon_filepath, get_app_icon_filepath
from quadpype.lib import Logger

app_meta = {
    "title": "QuadPype FastAPI Web Server",
    "description": "Webserver used to communicate with the hosts and to handle RestAPI routes",
    "license_info": {
        "name": "Apache License 2.0",
        "url": "http://www.apache.org/licenses/",
    }
}

WEB_API = FastAPI(
    docs_url=None,
    redoc_url="/docs",
    **app_meta,
)

templates = Jinja2Templates(directory=Path(__file__).parent.joinpath("templates"))

@WEB_API.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(get_app_favicon_filepath())

@WEB_API.get('/logo.png', include_in_schema=False)
async def webserver_logo():
    return FileResponse(get_app_icon_filepath(variation_name="default"))


@WEB_API.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "version": __version__,
            "current_year": date.today().strftime("%Y")
        }
    )

# Register all defined routers
for router in get_all_registered_web_api_routers():
    WEB_API.include_router(router)


class WebServerManager:
    """Manager that cares about the web server thread."""

    ALL_METHODS = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]

    def __init__(self, host, port):
        self._log = None

        self.port = port
        self.host = host

        self.client = None
        self.handlers = {}
        self.on_stop_callbacks = []

        self.app = WEB_API

        origin_regex = fr"^https?://{host}"
        self.app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=origin_regex,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # add route with multiple methods for single "external app"

        self.webserver_thread = WebServerThread(self)

    @property
    def log(self):
        if self._log is None:
            self._log = Logger.get_logger(self.__class__.__name__)
        return self._log

    @property
    def url(self):
        return "http://{}:{}".format(self.host, self.port)

    def add_route(self, methods, path, handler):
        if methods == "*":
            methods = self.ALL_METHODS
        if not isinstance(methods, list):
            methods = [methods]

        self.app.add_api_route(path, handler, methods=methods)

    def add_static(self, path, directory, name=None):
        if isinstance(directory, (str, Path)):
            directory = StaticFiles(directory=directory)
        if not isinstance(directory, StaticFiles):
            raise TypeError("add_static: directory need to be of type StaticFiles")
        if not name:
            name = path

        self.app.mount(path, directory, name)

    def start_server(self):
        if self.webserver_thread and not self.webserver_thread.is_alive():
            self.webserver_thread.start()

    def stop_server(self):
        if not self.is_running:
            return
        try:
            self.log.debug("Stopping Web server")
            self.webserver_thread.is_running = False
            self.webserver_thread.stop()
        except Exception:  # noqa
            self.log.warning(
                "Error has happened during Killing Web server",
                exc_info=True
            )

    @property
    def is_running(self):
        if not self.webserver_thread:
            return False
        return self.webserver_thread.is_running

    def thread_stopped(self):
        for callback in self.on_stop_callbacks:
            callback()


class WebServerThread(threading.Thread):
    """ Listener for requests in thread."""

    def __init__(self, manager):
        self._log = None

        super().__init__()

        self.is_running = False
        self.manager = manager
        self.loop = None
        self.server = None

    @property
    def log(self):
        if self._log is None:
            self._log = Logger.get_logger(self.__class__.__name__)
        return self._log

    @property
    def port(self):
        return self.manager.port

    @property
    def host(self):
        return self.manager.host

    def run(self):
        try:
            self.log.info("Starting WebServer server")
            # create new loop for the thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            config = uvicorn.Config(WEB_API, host=self.host, port=int(self.port), log_level="info", loop=self.loop)
            self.server = uvicorn.Server(config)
            self.log.debug(
                "Running Web server on http://{}:{}".format(self.host, self.port)
            )
            self.is_running = True
            self.loop.run_until_complete(self.server.serve())
        except Exception:  # noqa
            self.log.warning(
                "Web Server service has failed", exc_info=True
            )
        finally:
            self.loop.close()  # optional

        self.is_running = False
        self.server.should_exit = True
        if self.loop.is_running():
            self.loop.close()
        self.manager.thread_stopped()
        self.log.info("Web server stopped")

    def stop(self):
        """Shuts server down"""
        self.server.should_exit = True
