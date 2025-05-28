from quadpype.hosts.aftereffects.api import get_stub
from quadpype.pipeline import split_hierarchy
stub = get_stub()

def create_folder(folder_name, parent_to=None):
    """Create a folder based on a name and parent it to a given folder
    Args:
        folder_name (str): the name of the new folder
        parent_to (str): The folder to parent the newly created one

    Returns:
        AEItem: the newly created folder
    """
    all_folders = stub.get_items(comps=False, folders=True, footages=False)
    folder = find_folder(folder_name, all_folders)

    parent_folder = find_folder(parent_to, all_folders)
    if folder:
        return folder
    else:
        folder = stub.get_item(stub.add_item(folder_name, "FOLDER"))

    if folder and parent_folder:
        stub.parent_items(item_id=folder.id, parent_item_id=parent_folder.id)

    return folder

def find_folder(folder_name, all_folders=None):
    if not all_folders:
        all_folders = stub.get_items(comps=False, folders=True, footages=False)
    for folder in all_folders:
        if folder.name == folder_name:
            return folder
    return None

def create_folders_from_hierarchy(hierarchies):
    """ Generate all the folder hierarchies based on a string like:
        'CH/CH-wizzardTest/wizzardTest-model'
        or a list of string like:
        ['CH/CH-wizzardTest/wizzardTest-model', 'CH/CH-wizzardTest/wizzardTest-rig']
        CH
        |-> CH-wizzardTest
        ||-> wizzardTest-model
        ||-> wizzardTest-rig

    Args:
        hierarchies (list or str): a list of str or a str of one or more hierarchy

    Return:
        bool: True if success
    """

    if isinstance(hierarchies, str):
        hierarchies = [hierarchies]

    for hierarchy in hierarchies:
        if isinstance(hierarchy, str):
            hierarchy = split_hierarchy(hierarchy)

        for level, folder_name in enumerate(hierarchy):
            if level == 0:
                parent = None
            else:
                parent = hierarchy[level - 1]
            last_folder = create_folder(
                folder_name=folder_name,
                parent_to=parent
                )

    return True

def get_last_folder_from_first_template(hierarchies):
    all_folders = stub.get_items(comps=False, folders=True, footages=False)
    last_folder_name = split_hierarchy(hierarchies[0])[-1]
    last_folder = find_folder(last_folder_name, all_folders)

    return last_folder if last_folder else last_folder_name
