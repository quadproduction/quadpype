# -*- coding: utf-8 -*-
"""Look loader."""
import json
from collections import defaultdict

from qtpy import QtWidgets

from quadpype.client import get_representation_by_name
from quadpype.pipeline import (
    get_current_project_name,
    get_representation_path,
)
import quadpype.hosts.maya.api.plugin
from quadpype.hosts.maya.api import lib
from quadpype.widgets.message_window import ScrollMessageBox

from quadpype.hosts.maya.api.lib import get_reference_node


class LookLoader(quadpype.hosts.maya.api.plugin.ReferenceLoader):
    """Specific loader for lookdev"""

    families = ["look"]
    representations = ["ma"]

    label = "Reference look"
    order = -10
    icon = "code-fork"
    color = "orange"

    def process_reference(self, context, name, namespace, options):
        from maya import cmds

        with lib.maintained_selection():
            file_url = self.prepare_root_value(
                file_url=self.filepath_from_context(context),
                project_name=context["project"]["name"]
            )
            nodes = cmds.file(file_url,
                              namespace=namespace,
                              reference=True,
                              returnNewNodes=True)

        self[:] = nodes

    def switch(self, container, representation):
        self.update(container, representation)

    def update(self, container, representation):
        """
            Called by Scene Inventory when look should be updated to current
            version.
            If any reference edits cannot be applied, eg. shader renamed and
            material not present, reference is unloaded and cleaned.
            All failed edits are highlighted to the user via message box.

        Args:
            container: object that has look to be updated
            representation: (dict): relationship data to get proper
                                       representation from DB and persisted
                                       data in .json
        Returns:
            None
        """
        from maya import cmds

        # Get reference node from container members
        members = lib.get_container_members(container)
        reference_node = get_reference_node(members, log=self.log)

        shader_nodes = cmds.ls(members, type='shadingEngine')
        orig_nodes = set(self._get_nodes_with_shader(shader_nodes))

        # Trigger the regular reference update on the ReferenceLoader
        super(LookLoader, self).update(container, representation)

        # get new applied shaders and nodes from new version
        shader_nodes = cmds.ls(members, type='shadingEngine')
        nodes = set(self._get_nodes_with_shader(shader_nodes))

        project_name = get_current_project_name()
        json_representation = get_representation_by_name(
            project_name, "json", representation["parent"]
        )

        # Load relationships
        shader_relation = get_representation_path(json_representation)
        with open(shader_relation, "r") as f:
            json_data = json.load(f)

        # update of reference could result in failed edits - material is not
        # present because of renaming etc. If so highlight failed edits to user
        failed_edits = cmds.referenceQuery(reference_node,
                                           editStrings=True,
                                           failedEdits=True,
                                           successfulEdits=False)
        if failed_edits:
            # clean references - removes failed reference edits
            cmds.file(cr=reference_node)  # cleanReference

            # reapply shading groups from json representation on orig nodes
            lib.apply_shaders(json_data, shader_nodes, orig_nodes)

            msg = ["During reference update some edits failed.",
                   "All successful edits were kept intact.\n",
                   "Failed and removed edits:"]
            msg.extend(failed_edits)

            msg = ScrollMessageBox(QtWidgets.QMessageBox.Warning,
                                   "Some reference edit failed",
                                   msg)
            msg.exec_()

        attributes = json_data.get("attributes", [])

        # region compute lookup
        nodes_by_id = defaultdict(list)
        for node in nodes:
            nodes_by_id[lib.get_id(node)].append(node)
        lib.apply_attributes(attributes, nodes_by_id)

    def _get_nodes_with_shader(self, shader_nodes):
        """
            Returns list of nodes belonging to specific shaders
        Args:
            shader_nodes: <list> of Shader groups
        Returns
            <list> node names
        """
        from maya import cmds

        for shader in shader_nodes:
            future = cmds.listHistory(shader, future=True)
            connections = cmds.listConnections(future,
                                               type='mesh')
            if connections:
                # Ensure unique entries only to optimize query and results
                connections = list(set(connections))
                return cmds.listRelatives(connections,
                                          shapes=True,
                                          fullPath=True) or []
        return []
