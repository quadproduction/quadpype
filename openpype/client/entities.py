from .server.entities import *


def get_asset_name_identifier(asset_doc):
    """Get asset name identifier by asset document.

    This function is added because of AYON implementation where name
        identifier is not just a name but full path.

    Asset document must have "name" key, and "data.parents" when in AYON mode.

    Args:
        asset_doc (dict[str, Any]): Asset document.
    """
    return asset_doc["name"]
