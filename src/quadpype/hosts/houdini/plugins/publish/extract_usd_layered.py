import os
import contextlib
import hou

import pyblish.api

from quadpype.client import (
    get_asset_by_name,
    get_subset_by_name,
    get_last_version_by_subset_id,
    get_representation_by_name,
)
from quadpype.pipeline import (
    get_representation_path,
    publish,
)
import quadpype.hosts.houdini.api.usd as hou_usdlib
from quadpype.hosts.houdini.api.lib import render_rop


@contextlib.contextmanager
def parm_values(overrides):
    """Override Parameter values during the context."""

    originals = []
    try:
        for parm, value in overrides:
            originals.append((parm, parm.eval()))
            parm.set(value)
        yield
    finally:
        for parm, value in originals:
            # Parameter might not exist anymore so first
            # check whether it's still valid
            if hou.parm(parm.path()):
                parm.set(value)


class ExtractUSDLayered(publish.Extractor):

    order = pyblish.api.ExtractorOrder
    label = "Extract Layered USD"
    hosts = ["houdini"]
    families = ["usdLayered", "usdShade"]

    # Force Output Processors so it will always save any file
    # into our unique staging directory with processed Avalon paths
    output_processors = ["avalon_uri_processor", "stagingdir_processor"]

    def process(self, instance):

        self.log.info("Extracting: %s" % instance)

        staging_dir = self.staging_dir(instance)
        fname = instance.data.get("usdFilename")

        # The individual rop nodes are collected as "publishDependencies"
        dependencies = instance.data["publishDependencies"]
        ropnodes = [dependency[0] for dependency in dependencies]
        assert all(
            node.type().name() in {"usd", "usd_rop"} for node in ropnodes
        )

        # Main ROP node, either a USD Rop or ROP network with
        # multiple USD ROPs
        node = hou.node(instance.data["instance_node"])

        # Collect any output dependencies that have not been processed yet
        # during extraction of other instances
        outputs = [fname]
        active_dependencies = [
            dep
            for dep in dependencies
            if dep.data.get("publish", True)
            and not dep.data.get("_isExtracted", False)
        ]
        for dependency in active_dependencies:
            outputs.append(dependency.data["usdFilename"])

        pattern = r"*[/\]{0} {0}"
        save_pattern = " ".join(pattern.format(fname) for fname in outputs)

        # Run a stack of context managers before we start the render to
        # temporarily adjust USD ROP settings for our publish output.
        rop_overrides = {
            # This sets staging directory on the processor to force our
            # output files to end up in the Staging Directory.
            "stagingdiroutputprocessor_stagingDir": staging_dir,
            # Force the Avalon URI Output Processor to refactor paths for
            # references, payloads and layers to published paths.
            "avalonurioutputprocessor_use_publish_paths": True,
            # Only write out specific USD files based on our outputs
            "savepattern": save_pattern,
        }
        overrides = list()
        with contextlib.ExitStack() as stack:

            for ropnode in ropnodes:
                manager = hou_usdlib.outputprocessors(
                    ropnode,
                    processors=self.output_processors,
                    disable_all_others=True,
                )
                stack.enter_context(manager)

                # Some of these must be added after we enter the output
                # processor context manager because those parameters only
                # exist when the Output Processor is added to the ROP node.
                for name, value in rop_overrides.items():
                    parm = ropnode.parm(name)
                    assert parm, "Parm not found: %s.%s" % (
                        ropnode.path(),
                        name,
                    )
                    overrides.append((parm, value))

            stack.enter_context(parm_values(overrides))

            # Render the single ROP node or the full ROP network
            render_rop(node)

        # Assert all output files in the Staging Directory
        for output_fname in outputs:
            path = os.path.join(staging_dir, output_fname)
            assert os.path.exists(path), "Output file must exist: %s" % path

        # Set up the dependency for publish if they have new content
        # compared to previous publishes
        project_name = instance.context.data["projectName"]
        for dependency in active_dependencies:
            dependency_fname = dependency.data["usdFilename"]

            filepath = os.path.join(staging_dir, dependency_fname)
            similar = self._compare_with_latest_publish(
                project_name, dependency, filepath
            )
            if similar:
                # Deactivate this dependency
                self.log.debug(
                    "Dependency matches previous publish version,"
                    " deactivating %s for publish" % dependency
                )
                dependency.data["publish"] = False
            else:
                self.log.debug("Extracted dependency: %s" % dependency)
                # This dependency should be published
                dependency.data["files"] = [dependency_fname]
                dependency.data["stagingDir"] = staging_dir
                dependency.data["_isExtracted"] = True

        # Store the created files on the instance
        if "files" not in instance.data:
            instance.data["files"] = []
        instance.data["files"].append(fname)

    def _compare_with_latest_publish(self, project_name, dependency, new_file):
        import filecmp

        _, ext = os.path.splitext(new_file)

        # Compare this dependency with the latest published version
        # to detect whether we should make this into a new publish
        # version. If not, skip it.
        asset = get_asset_by_name(
            project_name, dependency.data["asset"], fields=["_id"]
        )
        subset = get_subset_by_name(
            project_name,
            dependency.data["subset"],
            asset["_id"],
            fields=["_id"]
        )
        if not subset:
            # Subset doesn't exist yet. Definitely new file
            self.log.debug("No existing subset..")
            return False

        version = get_last_version_by_subset_id(
            project_name, subset["_id"], fields=["_id"]
        )
        if not version:
            self.log.debug("No existing version..")
            return False

        representation = get_representation_by_name(
            project_name, ext.lstrip("."), version["_id"]
        )
        if not representation:
            self.log.debug("No existing representation..")
            return False

        old_file = get_representation_path(representation)
        if not os.path.exists(old_file):
            return False

        return filecmp.cmp(old_file, new_file)
