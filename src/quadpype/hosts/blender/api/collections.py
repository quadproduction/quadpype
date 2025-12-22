import bpy
from quadpype.pipeline import (
    split_hierarchy,
    get_task_hierarchy_templates,
    get_current_context,
    get_resolved_name
)


def create_collection(collection_name, link_to=None):
    """Create a collection based on a name and link it to a given
    Args:
        collection_name (str): the name of the new collection
        link_to (bpy.types.Collection or str): The collection to link the newly created one

    Returns:
        bpy.types.Collection: the newly created collection
    """

    collection = bpy.data.collections.get(collection_name)

    if not collection:
        collection = bpy.data.collections.new(collection_name)
        if isinstance(link_to, str):
            link_to = bpy.data.collections.get(link_to)
        if link_to and collection not in list(link_to.children):
            link_to.children.link(collection)

    return collection


def create_collections_from_hierarchy(hierarchies, parent_collection):
    """ Generate all the collection hierarchies based on a string like:
        'CH/CH-wizzardTest/wizzardTest-model'
        or a list of string like:
        ['CH/CH-wizzardTest/wizzardTest-model', 'CH/CH-wizzardTest/wizzardTest-rig']
        CH
        |-> CH-wizzardTest
        ||-> wizzardTest-model
        ||-> wizzardTest-rig

    Args:
        hierarchies (list or str): a list of str or a str of one or more hierarchy
        parent_collection: the collection to parent the top collection

    Return:
        bool: True if success
    """
    if isinstance(hierarchies, str):
        hierarchies = [hierarchies]

    for hierarchy in hierarchies:
        if isinstance(hierarchy, str):
            hierarchy = split_hierarchy(hierarchy)

        for level, collection_name in enumerate(hierarchy):
            if level == 0:
                parent = parent_collection
            else:
                parent = bpy.data.collections[hierarchy[level - 1]]

            create_collection(
                collection_name=collection_name,
                link_to=parent
            )

    return True


def get_corresponding_hierarchies_numbered(collections, collections_numbered):
    """Create a dict associating the original asset_collection name to its numbered version
    Args:
        collections (list): A list of resolved asset collection hierarchy
        collections_numbered (list): A list of resolved asset collection numbered hierarchy
    """
    result = {}
    for coll, coll_num in zip(collections, collections_numbered):
        coll_split = split_hierarchy(coll)
        coll_num_split = split_hierarchy(coll_num)

        for name, name_numbered in zip(coll_split, coll_num_split):
            result[name] = name_numbered

    return result


def get_top_collection(collection_name, default_parent_collection_name):
    parent_collection = bpy.data.collections.get(collection_name, None)
    if not parent_collection:
        parent_collection = bpy.data.collections.get(default_parent_collection_name, None)

    return parent_collection if parent_collection else bpy.context.scene.collection

def get_collections_numbered_hierarchy_and_correspondence(data_template, unique_number):
    collection_templates = get_task_hierarchy_templates(
        data_template,
        task=get_current_context()['task_name']
    )
    collections_are_created = None

    corresponding_collections_numbered = dict()
    collections_numbered_hierarchy = list()

    if collection_templates:
        collections_hierarchy = [
            get_resolved_name(
                data=data_template,
                template=template
            )
            for template in collection_templates
        ]
        collections_numbered_hierarchy = [
            get_resolved_name(
                data=data_template,
                template=template,
                numbering=unique_number
            )
            for template in collection_templates
        ]

        corresponding_collections_numbered = get_corresponding_hierarchies_numbered(
            collections_hierarchy,
            collections_numbered_hierarchy
        )

        collections_are_created = create_collections_from_hierarchy(
            hierarchies=collections_numbered_hierarchy,
            parent_collection=bpy.context.scene.collection
        )

    return collections_are_created, corresponding_collections_numbered, collections_numbered_hierarchy

def organize_objects_in_templated_collection(
        objects,
        collections_numbered_hierarchy,
        corresponding_collections_numbered,
        unique_number
):
    default_parent_collection_name = get_last_collection_from_first_template(
        collections_numbered_hierarchy
    )

    for blender_object in objects:

        if not blender_object.get('visible', True):
            continue

        collection = bpy.data.collections[default_parent_collection_name]

        object_hierarchies = blender_object.get('original_collection_parent', '')
        split_object_hierarchies = object_hierarchies.replace('\\', '/').split('/')

        for collection_number, hierarchy in enumerate(split_object_hierarchies):
            corresponding_collection_name = corresponding_collections_numbered.get(
                hierarchy,
                f"{hierarchy}-{unique_number}"
            )

            if collection_number == 0:
                collection = get_top_collection(
                    collection_name=corresponding_collection_name,
                    default_parent_collection_name=default_parent_collection_name
                )

            else:
                parent_collection_name = split_object_hierarchies[collection_number - 1]
                parent_collection_name_numbered = corresponding_collections_numbered.get(
                    parent_collection_name, f"{parent_collection_name}-{unique_number}")

                collection = create_collection(corresponding_collection_name, parent_collection_name_numbered)

        if blender_object in list(collection.objects):
            continue

        collection.objects.link(blender_object)

def get_last_collection_from_first_template(hierarchies):
    return split_hierarchy(hierarchies[0])[-1]
