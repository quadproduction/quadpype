import pyblish.api
import shutil
from pathlib import Path

class ExtractSource(pyblish.api.InstancePlugin):
    """Extract instances sources for traypublisher host to a stagingDir."""

    label = "Extract source"
    order = pyblish.api.ExtractorOrder - 0.5
    hosts = ["traypublisher"]

    def process(self, instance):
        dst_staging = Path(instance.data.get("stagingDir"))
        for repre in instance.data.get("representations"):
            repre_files = repre["files"]
            if isinstance(repre_files, str):
                repre_files = [repre_files]

            src_staging = Path(repre["stagingDir"])
            for file in repre_files:
                src_full_path = src_staging / file
                dst_full_path = dst_staging / file
                shutil.copy(src_full_path.resolve(strict=False),
                            dst_full_path.resolve(strict=False))

                self.log.info(f"{file} has been transferred from {src_staging} to {dst_staging}")

            repre["stagingDir"] = dst_staging
            self.log.info(f"stagingDir has been updated to {dst_staging}")
