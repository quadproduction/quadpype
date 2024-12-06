import os
import re
import pyblish.api

from quadpype.hosts.photoshop import api as photoshop


class CollectExtensionVersion(pyblish.api.ContextPlugin):
    """ Pulls and compares version of installed extension.

        It is recommended to use same extension as in provided QuadPype code.

        Please use Anastasiy's Extension Manager or ZXPInstaller to update
        extension in case of an error.
    """
    # This technically should be a validator, but other collectors might be
    # impacted with usage of obsolete extension, so collector that runs first
    # was chosen
    order = pyblish.api.CollectorOrder - 0.5
    label = "Collect extension version"
    hosts = ["photoshop"]

    optional = True
    active = True

    def process(self, context):
        bundle_id = photoshop.stub().get_extension_bundle_id()
        installed_version = photoshop.stub().get_extension_version()
        if not bundle_id:
            raise ValueError("Thanks to use Quadpype by selecting Windows > Extensions (Legacy) > QuadPype ")


        if not installed_version:
            raise ValueError("Unknown version, probably old extension")

        manifest_url = os.path.join(os.path.dirname(photoshop.__file__),
                                    "extension", "CSXS", "manifest.xml")

        if not os.path.exists(manifest_url):
            self.log.debug("Unable to locate extension manifest, not checking")
            return

        expected_version = None
        expected_id = None
        with open(manifest_url) as fp:
            content = fp.read()
            id_found = re.findall(r'(ExtensionBundleId=\")([a-zA-Z\.]+)(\")',content)
            if id_found:
                expected_id = id_found[0][1]

            found = re.findall(r'(ExtensionBundleVersion=")([0-9\.]+)(")',content)
            if found:
                expected_version = found[0][1]

        if expected_id != bundle_id:
            msg = "Expected id '{}' found '{}'\n".format(expected_id, bundle_id)
            msg += "Thanks to use Quadpype by selecting Windows > Extensions (Legacy) > QuadPype  "
            raise ValueError(msg)

        if expected_version != installed_version:
            msg = "Expected version '{}' found '{}'\n".format(
                expected_version, installed_version)
            msg += "Please update your installed extension, it might not work "
            msg += "properly."

            raise ValueError(msg)
