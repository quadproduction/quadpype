import bpy

def split_hierarchy(hierarchy):
    """Split a str hierarchy to a list of individual name

    Args:
        hierarchy (str): a string template like "{parent}-{asset}<-{numbering}>/{asset}-model<-{variant}><-{numbering}>"
    Return:
        list: a list of separated template like ["{parent}-{asset}<-{numbering}>",
        "{asset}-model<-{variant}><-{numbering}>"]
    """

    return hierarchy.replace('\\', '/').split('/')


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
