from copy import deepcopy
import re
import warnings

from quadpype.lib import filter_profiles, StringTemplate
from . import get_workfile_build_template

from quadpype.pipeline.context_tools import get_current_project_asset, get_current_context


DEFAULT_VARIANT_NAME = "Main"


def format_data(original_data, filter_variant=True, app=""):
    """Format incoming data for template resolving"""
    data = deepcopy(original_data)

    if original_data.get("context"):
        data = deepcopy(original_data["context"])

    parent = get_parent_data(data)
    if not parent:
        warnings.warn(f"Can not retrieve parent short from {data.get('parent', None)}", UserWarning)
    data["parent"] = parent
    data["app"] = app

    update_parent_data_with_entity_prefix(data)

    if is_current_asset_shot():
        data['sequence'], data['shot'] = extract_sequence_and_shot()
    if filter_variant:
        _remove_default_variant(data)
    return data


def get_resolved_name(data, template, **additional_data):
    """Resolve template_collections_naming with entered data.
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
        template (str): template to solve
    Returns:
        str: Resolved template
    """
    template_obj = StringTemplate(template)

    if additional_data:
        data = dict(data, **additional_data)
    return template_obj.format_strict(data).normalized()


def get_parent_data(data):
    parent = data.get('parent', None)
    if not parent:
        hierarchy = data.get('hierarchy')
        if not hierarchy:
            return

        return hierarchy.split('/')[-1]
    return parent


def _remove_default_variant(data):
    if data.get("variant") == DEFAULT_VARIANT_NAME or data.get("variant") == "":
        data.pop("variant")


def _get_parent_by_data(data):
    """
    Retrieve the parent asset name depending on given data
    This can be given by an instance or an app, and they are not sorted the same way

    Return:
        str, bool: The parent name (str) and a bool to specify if this is from anatomy or project (bool)
    """
    parent_name = None
    is_from_anatomy = False

    if data.get("parent"):
        parent_name = data["parent"]
    elif data.get("anatomyData"):
        is_from_anatomy = True
        parent_name = data["anatomyData"]["parent"]

    return parent_name, is_from_anatomy


def _get_entity_prefix(data):
    """Retrieve the asset_type (entity_type) short name for proper blender naming
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
    Return:
        str: A string corresponding to the short name for entered entity type
        bool: bool to specify if this is from anatomy or project (bool)
    """

    profiles = get_workfile_build_template("entity_type_name_matcher")
    parent, is_anatomy = _get_parent_by_data(data)

    profile_key = {"entity_types": parent}
    profile = filter_profiles(profiles, profile_key)
    if not profile:
        return None, is_anatomy

    return profile.get("entity_prefix"), is_anatomy


def update_parent_data_with_entity_prefix(data):
    """
    Will update the input data dict to change the value of the ["parent"] key
    to become the corresponding prefix
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
    """
    parent_prefix, is_anatomy = _get_entity_prefix(data)

    if not parent_prefix:
        return None

    if is_anatomy:
        data["anatomyData"]["parent"] = parent_prefix
    else:
        data["parent"] = parent_prefix


def split_hierarchy(hierarchy):
    """Split a str hierarchy to a list of individual name

    Args:
        hierarchy (str): a string template like "{parent}-{asset}<-{numbering}>/{asset}-model<-{variant}><-{numbering}>"
    Return:
        list: a list of separated template like ["{parent}-{asset}<-{numbering}>",
        "{asset}-model<-{variant}><-{numbering}>"]
    """

    return hierarchy.replace('\\', '/').split('/')


def is_current_asset_shot():
    asset_data = get_current_project_asset()["data"]
    return asset_data['parents'][0].lower() == "shots"


def extract_sequence_and_shot():
    asset_name = get_current_context()['asset_name']
    is_valid_pattern = re.match('^SQ[a-zA-Z0-9_.]+_[a-zA-Z.]+[a-zA-Z0-9_.]*$', asset_name)
    if not is_valid_pattern:
        raise RuntimeError(f"Can not extract sequence and shot from asset_name {asset_name}")

    return asset_name.split('_', 1)
