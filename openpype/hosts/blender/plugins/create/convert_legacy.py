# -*- coding: utf-8 -*-
"""Converter for legacy Houdini subsets."""
from quadpype.pipeline.create.creator_plugins import SubsetConvertorPlugin
from quadpype.hosts.blender.api.lib import imprint


class BlenderLegacyConvertor(SubsetConvertorPlugin):
    """Find and convert any legacy subsets in the scene.

    This Converter will find all legacy subsets in the scene and will
    transform them to the current system. Since the old subsets doesn't
    retain any information about their original creators, the only mapping
    we can do is based on their families.

    Its limitation is that you can have multiple creators creating subset
    of the same family and there is no way to handle it. This code should
    nevertheless cover all creators that came with QuadPype.

    """
    identifier = "io.quadpype.creators.blender.legacy"
    family_to_id = {
        "action": "io.quadpype.creators.blender.action",
        "camera": "io.quadpype.creators.blender.camera",
        "animation": "io.quadpype.creators.blender.animation",
        "blendScene": "io.quadpype.creators.blender.blendscene",
        "layout": "io.quadpype.creators.blender.layout",
        "model": "io.quadpype.creators.blender.model",
        "pointcache": "io.quadpype.creators.blender.pointcache",
        "render": "io.quadpype.creators.blender.render",
        "review": "io.quadpype.creators.blender.review",
        "rig": "io.quadpype.creators.blender.rig",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.legacy_subsets = {}

    def find_instances(self):
        """Find legacy subsets in the scene.

        Legacy subsets are the ones that doesn't have `creator_identifier`
        parameter on them.

        This is using cached entries done in
        :py:meth:`~BaseCreator.cache_subsets()`

        """
        self.legacy_subsets = self.collection_shared_data.get(
            "blender_cached_legacy_subsets")
        if not self.legacy_subsets:
            return
        self.add_convertor_item(
            "Found {} incompatible subset{}".format(
                len(self.legacy_subsets),
                "s" if len(self.legacy_subsets) > 1 else ""
            )
        )

    def convert(self):
        """Convert all legacy subsets to current.

        It is enough to add `creator_identifier` and `instance_node`.

        """
        if not self.legacy_subsets:
            return

        for family, instance_nodes in self.legacy_subsets.items():
            if family in self.family_to_id:
                for instance_node in instance_nodes:
                    creator_identifier = self.family_to_id[family]
                    self.log.info(
                        "Converting {} to {}".format(instance_node.name,
                                                     creator_identifier)
                    )
                    imprint(instance_node, data={
                        "creator_identifier": creator_identifier
                    })
