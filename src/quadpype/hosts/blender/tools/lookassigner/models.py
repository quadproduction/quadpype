from collections import defaultdict

from qtpy import QtCore
import qtawesome

from quadpype.tools.utils import models
from quadpype.style import get_default_entity_icon_color


class AssetModel(models.TreeModel):

    Columns = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._icon_color = get_default_entity_icon_color()

    def add_items(self, items):
        """
        Add items to model with needed data
        Args:
            items(list): collection of item data

        Returns:
            None
        """

        self.beginResetModel()

        sorter = lambda x: x["name"]
        for item in sorted(items, key=sorter):
            asset_item = models.Item()
            asset_item.update(item)
            asset_item["icon"] = "folder"

            for asset_data in item["assets_data"]:
                namespace = asset_data['namespace']
                family = asset_data['family']
                collection_name = asset_data['collection_name']

                child = models.Item()
                child.update(item)
                child.update({
                    "name": f"{namespace}-{family}",
                    "namespace": namespace,
                    "collection_name": collection_name,
                    "looks": item["looks"],
                    "icon": "folder-o"
                })
                asset_item.add_child(child)

            self.add_child(asset_item)

        self.endResetModel()

    def data(self, index, role):

        if not index.isValid():
            return

        if role == models.TreeModel.ItemRole:
            node = index.internalPointer()
            return node

        # Add icon
        if role == QtCore.Qt.DecorationRole:
            if index.column() == 0:
                node = index.internalPointer()
                icon = node.get("icon")
                if icon:
                    return qtawesome.icon(
                        "fa.{0}".format(icon),
                        color=self._icon_color
                    )

        return super(AssetModel, self).data(index, role)


class LookModel(models.TreeModel):
    """Model displaying a list of looks and matches for assets"""

    Columns = ["label", "match"]

    def add_items(self, items):
        """Add items to model with needed data

        An item exists of:
            {
                "subset": 'name of subset',
                "asset": asset_document
            }

        Args:
            items(list): collection of item data

        Returns:
            None
        """

        self.beginResetModel()
        browsed_looks = list()
        for asset_item in items:

            for look in asset_item['looks']:
                if look in browsed_looks:
                    continue
                browsed_looks.append(look)

                item_node = models.Item()
                item_node["label"] = look.get('variant', '## UNDEFINED ##')
                item_node["repr_id"] = str(look.get('_id', ''))
                item_node["subset"] = "subset"
                item_node["match"] = len(items)

                self.add_child(item_node)

        self.endResetModel()
