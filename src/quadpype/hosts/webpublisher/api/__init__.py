import os
import logging

import pyblish.api

from quadpype.host import HostBase
from quadpype.hosts.webpublisher import WEBPUBLISHER_ROOT_DIR

log = logging.getLogger("quadpype.hosts.webpublisher")


class WebpublisherHost(HostBase):
    name = "webpublisher"

    def install(self):
        print("Installing QuadPype config...")
        pyblish.api.register_host(self.name)

        publish_plugin_dir = os.path.join(
            WEBPUBLISHER_ROOT_DIR, "plugins", "publish"
        )
        pyblish.api.register_plugin_path(publish_plugin_dir)
        self.log.info(publish_plugin_dir)
