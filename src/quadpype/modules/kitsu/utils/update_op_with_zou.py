"""Functions to update QuadPype data using Kitsu DB (a.k.a Zou)."""
import re
from copy import deepcopy
from typing import Dict, List, Tuple

from gazu.exception import RouteNotFoundException
from pymongo import DeleteOne, UpdateOne
import gazu

from quadpype.client import (
    get_project,
    get_assets,
    get_asset_by_id,
    get_asset_by_name,
    create_project,
    get_quadpype_collection,
)
from quadpype.pipeline import AvalonMongoDB
from quadpype.client import save_project_timestamp
from quadpype.modules.kitsu.utils.credentials import validate_credentials

from quadpype.lib import Logger

log = Logger.get_logger(__name__)

# Accepted namin pattern for OP
naming_pattern = re.compile("^[a-zA-Z0-9_.]*$")

KitsuStateToBool = {
    'Closed': False,
    'Open': True
}


def create_op_asset(gazu_entity: dict) -> dict:
    """Create QuadPype asset dict from gazu entity.

    :param gazu_entity:
    """
    return {
        "name": gazu_entity["name"],
        "type": "asset",
        "schema": "quadpype:asset-3.0",
        "data": {"zou": gazu_entity, "tasks": {}},
    }


def get_kitsu_project_name(project_id: str) -> str:
    """Get project name based on project id in kitsu.

    Args:
        project_id (str): UUID of project in Kitsu.

    Returns:
        str: Name of Kitsu project.
    """

    project = gazu.project.get_project(project_id)
    return project["name"]


def set_op_project(dbcon: AvalonMongoDB, project_id: str):
    """Set project context.

    Args:
        dbcon (AvalonMongoDB): Connection to DB
        project_id (str): Project zou ID
    """

    dbcon.Session["AVALON_PROJECT"] = get_kitsu_project_name(project_id)


def update_op_assets(
    dbcon: AvalonMongoDB,
    gazu_project: dict,
    project_doc: dict,
    entities_list: List[dict],
    asset_doc_ids: Dict[str, dict],
) -> List[Tuple[str, dict]]:
    """Update QuadPype assets.
    Set 'data' and 'parent' fields.

    Args:
        dbcon (AvalonMongoDB): Connection to DB
        gazu_project (dict): Dict of gazu,
        project_doc (dict): Dict of project,
        entities_list (List[dict]): List of zou entities to update
        asset_doc_ids (Dict[str, dict]): Dicts of [{zou_id: asset_doc}, ...]

    Returns:
        List[Tuple[str, dict]]: List of (doc_id, update_dict) tuples
    """
    assets_with_update = []
    if not project_doc:
        return assets_with_update

    project_name = project_doc["name"]

    for item in entities_list:
        # Check asset exists
        item_doc = asset_doc_ids.get(item["id"])
        if not item_doc:  # Create asset
            op_asset = create_op_asset(item)
            insert_result = dbcon.insert_one(op_asset)
            item_doc = get_asset_by_id(project_name, insert_result.inserted_id)

        # Update asset
        item_data = deepcopy(item_doc["data"])
        item_data.update(item.get("data") or {})
        item_data["zou"] = item

        # == Asset settings ==
        # Frame in, fallback to project's value or default value (1001)
        # TODO: get default from settings/project_anatomy/attributes.json
        try:
            frame_in = int(
                item_data.pop(
                    "frame_in", project_doc["data"].get("frameStart")
                )
            )
        except (TypeError, ValueError):
            frame_in = 1001
        item_data["frameStart"] = frame_in

        #List Shots in Sequence
        if item.get("type") == "Sequence":
            shots = gazu.shot.all_shots_for_sequence(item)
            item_data["shotsInSeq"] = [asset_doc_ids.get(i['id']).get("_id") for i in shots]

        item_data.pop("inputLinks", None)
        # Retrieve casting
        try:
            item_entity = gazu.entity.get_entity(item["id"])
            item_data["castedAssets"] = [asset_doc_ids.get(i) for i in item_entity.get("entities_out", [])]
        except RouteNotFoundException:
            print(f"Can not retrieve entity from {item['name']}")

        # Frames duration, fallback on 1
        try:
            # NOTE nb_frames is stored directly in item
            # because of zou's legacy design
            frames_duration = int(item.get("nb_frames", 1))
        except (TypeError, ValueError):
            frames_duration = None
        # Frame out, fallback on frame_in + duration or project's value or 1001
        frame_out = item_data.pop("frame_out", None)
        if not frame_out:
            if frames_duration:
                frame_out = frame_in + frames_duration - 1
            else:
                frame_out = project_doc["data"].get("frameEnd", frame_in)
        item_data["frameEnd"] = int(frame_out)
        # Fps, fallback to project's value or default value (25.0)
        try:
            fps = float(item_data.get("fps"))
        except (TypeError, ValueError):
            fps = float(
                gazu_project.get("fps", project_doc["data"].get("fps", 25))
            )
        item_data["fps"] = fps
        # Resolution, fall back to project default
        match_res = re.match(
            r"(\d+)x(\d+)",
            item_data.get("resolution", gazu_project.get("resolution")),
        )
        if match_res:
            item_data["resolutionWidth"] = int(match_res.group(1))
            item_data["resolutionHeight"] = int(match_res.group(2))
        else:
            item_data["resolutionWidth"] = int(
                project_doc["data"].get("resolutionWidth", 0)
            )
            item_data["resolutionHeight"] = int(
                project_doc["data"].get("resolutionHeight", 0)
            )
        # Properties that doesn't fully exist in Kitsu.
        # Guessing those property names below:
        # Pixel Aspect Ratio
        item_data["pixelAspect"] = float(
            item_data.get(
                "pixel_aspect", project_doc["data"].get("pixelAspect", 1.0)
            )
        )

        # Handle Start
        item_data["handleStart"] = int(
            item_data.get(
                "handle_start", project_doc["data"].get("handleStart", 0)
            )
        )
        # Handle End
        item_data["handleEnd"] = int(
            item_data.get("handle_end", project_doc["data"].get("handleEnd", 0))
        )
        # Clip In
        item_data["clipIn"] = int(
            item_data.get("clip_in", project_doc["data"].get("clipIn", 0))
        )
        # Clip Out
        item_data["clipOut"] = int(
            item_data.get("clip_out", project_doc["data"].get("clipOut", 0))
        )

        # Tasks
        tasks_list = []
        item_type = item["type"]
        if item_type == "Asset":
            tasks_list = gazu.task.all_tasks_for_asset(item)
        elif item_type == "Shot":
            tasks_list = gazu.task.all_tasks_for_shot(item)
        elif item_type == "Sequence":
            tasks_list = gazu.task.all_tasks_for_sequence(item)

        item_data["tasks"] = {
            t["task_type_name"]: {
                "type": t["task_type_name"],
                "zou": gazu.task.get_task(t["id"]),
            }
            for t in tasks_list
        }

        # Get zou parent id for correct hierarchy
        # Use parent substitutes if existing
        substitute_parent_item = (
            item_data["parent_substitutes"][0]
            if item_data.get("parent_substitutes")
            else None
        )
        if substitute_parent_item:
            parent_zou_id = substitute_parent_item["parent_id"]
        else:
            parent_zou_id = (
                # For Asset, put under asset type directory
                item.get("entity_type_id")
                if item_type == "Asset"
                else None
                # Else, fallback on usual hierarchy
                or item.get("parent_id")
                or item.get("episode_id")
                or item.get("source_id")
            )

        # Substitute item type for general classification (assets or shots)
        if item_type in ["Asset", "AssetType"]:
            entity_root_asset_name = "Assets"
        elif item_type in ["Episode", "Sequence", "Shot"]:
            entity_root_asset_name = "Shots"
        else:
            raise ValueError(f"Unknown entity type {item_type}")

        # Root parent folder if exist
        visual_parent_doc_id = None
        if parent_zou_id is not None:
            parent_zou_id_dict = asset_doc_ids.get(parent_zou_id)
            if parent_zou_id_dict is not None:
                visual_parent_doc_id = (
                    parent_zou_id_dict.get("_id")
                    if parent_zou_id_dict
                    else None
                )

        if visual_parent_doc_id is None:
            # Find root folder doc ("Assets" or "Shots")
            root_folder_doc = get_asset_by_name(
                project_name,
                asset_name=entity_root_asset_name,
                fields=["_id", "data.root_of"],
            )

            if root_folder_doc:
                visual_parent_doc_id = root_folder_doc["_id"]

        # Visual parent for hierarchy
        item_data["visualParent"] = visual_parent_doc_id

        # Add parents for hierarchy
        item_data["parents"] = []
        ancestor_id = parent_zou_id
        while ancestor_id is not None:
            parent_doc = asset_doc_ids.get(ancestor_id)
            if parent_doc is not None:
                item_data["parents"].insert(0, parent_doc["name"])

                # Get parent entity
                parent_entity = parent_doc["data"]["zou"]
                ancestor_id = parent_entity.get("parent_id")
            else:
                ancestor_id = None

        # Build QuadPype compatible name
        if item_type in ["Shot", "Sequence"] and parent_zou_id is not None:
            # Name with parents hierarchy "({episode}_){sequence}_{shot}"
            # to avoid duplicate name issue
            item_name = f"{item_data['parents'][-1]}_{item['name']}"

            # Update doc name
            asset_doc_ids[item["id"]]["name"] = item_name
        else:
            item_name = item["name"]

        # Set root folders parents
        item_data["parents"] = [entity_root_asset_name] + item_data["parents"]

        # Update 'data' different in zou DB
        updated_data = {
            k: v for k, v in item_data.items() if item_doc["data"].get(k) != v
        }
        if updated_data or not item_doc.get("parent"):
            assets_with_update.append(
                (
                    item_doc["_id"],
                    {
                        "$set": {
                            "name": item_name,
                            "data": item_data,
                            "parent": project_doc["_id"],
                        }
                    },
                )
            )
    return assets_with_update


def write_project_to_op(project: dict) -> UpdateOne:
    """Write gazu project to QuadPype database.
    Create project if doesn't exist.

    Args:
        project (dict): Gazu project

    Returns:
        UpdateOne: Update instance for the project
    """
    project_name = project["name"]
    project_dict = get_project(project_name)
    if not project_dict:
        project_dict = create_project(project_name, project_name)

    # Project data and tasks
    project_data = project_dict["data"] or {}

    # Build project code and update Kitsu
    project_code = project.get("code")
    if not project_code:
        project_code = project["name"].replace(" ", "_").lower()
        project["code"] = project_code

        # Update Zou
        gazu.project.update_project(project)

    # Update data
    project_data.update(
        {
            "code": project_code,
            "fps": float(project["fps"]),
            "zou_id": project["id"],
            "active": KitsuStateToBool[project["project_status_name"]]
        }
    )

    match_res = re.match(r"(\d+)x(\d+)", project["resolution"])
    if match_res:
        project_data["resolutionWidth"] = int(match_res.group(1))
        project_data["resolutionHeight"] = int(match_res.group(2))
    else:
        log.warning(
            f"'{project['resolution']}' does not match the expected"
            " format for the resolution, for example: 1920x1080"
        )

    return UpdateOne(
        {"_id": project_dict["_id"]},
        {
            "$set": {
                "config.tasks": {
                    t["name"]: {"short_name": t.get("short_name", t["name"])}
                    for t in gazu.task.all_task_types_for_project(project)
                    or gazu.task.all_task_types()
                },
                "data": project_data,
            }
        },
    )


def sync_all_projects(
    login: str,
    password: str,
    ignore_projects: set = None,
    include_projects: set = None,
    sync_quick_active_projects: bool = False,
):
    """Update all QuadPype projects in DB with Zou data.

    Args:
        login (str): Kitsu user login
        password (str): Kitsu user password
        ignore_projects (list): List of project names to ignore (not sync)
        include_projects (list): List of project names to sync (only sync them)
    Raises:
        gazu.exception.AuthFailedException: Wrong user login and/or password
    """

    # Authenticate
    if not validate_credentials(login, password):
        raise gazu.exception.AuthFailedException(
            f"Kitsu authentication failed for login: '{login}'..."
        )

    # Iterate projects
    dbcon = AvalonMongoDB()
    dbcon.install()
    all_projects = gazu.project.all_projects()

    project_to_sync = []
    all_kitsu_projects = {p["name"]: p for p in all_projects}

    if not include_projects:
        include_projects = set(all_kitsu_projects.keys())
    else:
        include_projects = set(include_projects)

    if ignore_projects:
        include_projects -= set(ignore_projects)

    for proj_name in include_projects:
        if proj_name in all_kitsu_projects:
            project_to_sync.append(all_kitsu_projects[proj_name])
        else:
            log.info(
                f"`{proj_name}` project does not exist in Kitsu."
                f" Please make sure the project is spelled correctly."
            )

    # Iterate over MongoDB projects and if it's not present in Kitsu project, deactivate it on MongoDB
    for project in dbcon.projects():
        project_name = project['name']
        if project_name in all_kitsu_projects:
            # Project exists on Kitsu, skip
            continue

        update_project_state_in_db(dbcon, project, active=False)

        # Remove from active projects collection
        if sync_quick_active_projects and project_exists_in_actives(project_name):
            remove_project_from_actives(project_name)
            log.info(f"Removed '{project_name}' from active projects collection.")

    for project in project_to_sync:
        sync_project_from_kitsu(dbcon, project, sync_quick_active_projects)


def update_project_state_in_db(dbcon: AvalonMongoDB, project: dict, active: bool):
    bulk_writes = []
    project['data']['active'] = active
    dbcon.Session["AVALON_PROJECT"] = project["name"]
    bulk_writes.append(
            UpdateOne(
            {"_id": project["_id"]},
            {
                "$set": {
                    "data": project['data']
                }
            }
        )
    )
    dbcon.bulk_write(bulk_writes)


def remove_project_from_actives(project_name: str) -> bool:
    """Remove project from active projects in database.

    Args:
        project_name (str): Name of the project to remove from active projects
    """
    collection = get_quadpype_collection("active_projects")
    if not collection:
        log.info("Can not find active projects collection from quadpype database.")
        return

    result = collection.delete_many({"name": project_name})
    if not result.deleted_count:
        log.info(f"No active project entry found for '{project_name}'")
        return False

    return True


def add_project_to_actives(project_name: str) -> bool:
    """Add project to active projects in database.

    Args:
        project_name (str): Name of the project to add to active projects
    """
    collection = get_quadpype_collection("active_projects")
    if not collection:
        log.info("Can not find active projects collection from quadpype database.")
        return

    project_dict = get_project(project_name)
    if not project_dict:
        log.info(f"Can not retrieve project '{project_name}' from quadpype projects database.")
        return False

    result = collection.insert_one(
        {
            "id": project_dict["_id"],
            "name": project_name,
            "data": {
                "code": project_dict["data"]["code"],
                "library_project": project_dict["data"]["library_project"],
                "active": True
            }

        }
    )
    if not result.inserted_id:
        log.info(f"Failed to add '{project_name}' to active projects")
        return False

    return True


def project_exists_in_actives(project_name: str) -> bool:
    """
    Check if a project exists in the QuadPype database.

    Args:
        project_name (str): Name of the project to check.

    Returns:
        bool: True if the project exists, False otherwise.
    """
    collection = get_quadpype_collection("active_projects")
    if not collection:
        log.info("Can not find active projects collection from quadpype database.")
        return

    project = collection.find_one({"name": project_name})
    return project is not None


def sync_project_from_kitsu(dbcon: AvalonMongoDB, project: dict, sync_quick_active_projects: bool = False):
    """Update QuadPype project in DB with Zou data.

    `root_of` is meant to sort entities by type for a better readability in
    the data tree. It puts all shot like (Shot and Episode and Sequence) and
    asset entities under two different root folders or hierarchy, defined in
    settings.

    Args:
        dbcon (AvalonMongoDB): MongoDB connection
        project (dict): Project dict got using gazu.
    """
    bulk_writes = []

    # Get project from zou
    if not project:
        project = gazu.project.get_project_by_name(project["name"])

    # Get all statuses for projects from Kitsu
    all_status = gazu.project.all_project_status()
    for status in all_status:
        if project["project_status_id"] == status["id"]:
            project["project_status_name"] = status["name"]
            break

    # Get the project from QuadPype DB
    project_name = project["name"]
    project_dict = get_project(project_name)
    project_active_state_kitsu = KitsuStateToBool[project["project_status_name"]]

    # Early exit condition if the project is deactivated (closed) on Kitsu
    if not project_active_state_kitsu:

        # Remove from active projects collection
        if sync_quick_active_projects and project_exists_in_actives(project_name):
            remove_project_from_actives(project_name)
            log.info(f"Removed '{project_name}' from active projects collection.")

        if not project_dict:
            # The project doesn't exist on QuadPype DB, skip
            return

        # Deactivate the project on the QuadPype DB (if not already), then return
        op_active_state = project_dict.get('data', {}).get('active', False)
        if op_active_state != project_active_state_kitsu:
            log.info(f"Deactivate {project['name']} on QuadPype DB...")
            update_project_state_in_db(
                dbcon,
                project_dict,
                active=project_active_state_kitsu
            )
        return

    log.info(f"Synchronizing {project['name']}...")

    # Get all assets from zou
    all_assets = gazu.asset.all_assets_for_project(project)
    all_asset_types = gazu.asset.all_asset_types_for_project(project)
    all_episodes = gazu.shot.all_episodes_for_project(project)
    all_seqs = gazu.shot.all_sequences_for_project(project)
    all_shots = gazu.shot.all_shots_for_project(project)
    all_entities = [
        item
        for item in all_assets
        + all_asset_types
        + all_episodes
        + all_seqs
        + all_shots
        if naming_pattern.match(item["name"])
    ]

    if not project_dict:
        log.info("Project created: {}".format(project_name))

    bulk_writes.append(write_project_to_op(project))

    if not project_dict:
        # Try to find the newly created project document on QuadPype DB
        project_dict = get_project(project_name)

    dbcon.Session["AVALON_PROJECT"] = project_name

    # Query all assets of the local project
    zou_ids_and_asset_docs = {
        asset_doc["data"]["zou"]["id"]: asset_doc
        for asset_doc in get_assets(project_name)
        if asset_doc["data"].get("zou", {}).get("id")
    }
    zou_ids_and_asset_docs[project["id"]] = project_dict

    # Create entities root folders
    to_insert = [
        {
            "name": r,
            "type": "asset",
            "schema": "quadpype:asset-3.0",
            "data": {
                "root_of": r,
                "tasks": {},
                "visualParent": None,
                "parents": [],
            },
        }
        for r in ["Assets", "Shots"]
        if not get_asset_by_name(
            project_name, r, fields=["_id", "data.root_of"]
        )
    ]

    # Create
    to_insert.extend(
        [
            create_op_asset(item)
            for item in all_entities
            if item["id"] not in zou_ids_and_asset_docs.keys()
        ]
    )
    if to_insert:
        # Insert doc in DB
        dbcon.insert_many(to_insert)

        # Update existing docs
        zou_ids_and_asset_docs.update(
            {
                asset_doc["data"]["zou"]["id"]: asset_doc
                for asset_doc in get_assets(project_name)
                if asset_doc["data"].get("zou")
            }
        )

    # Update
    bulk_writes.extend(
        [
            UpdateOne({"_id": _id}, update)
            for (_id, update) in update_op_assets(
                dbcon,
                project,
                project_dict,
                all_entities,
                zou_ids_and_asset_docs,
            )
        ]
    )

    # Delete
    diff_assets = set(zou_ids_and_asset_docs.keys()) - {
        e["id"] for e in all_entities + [project]
    }
    if diff_assets:
        bulk_writes.extend(
            [
                DeleteOne(zou_ids_and_asset_docs[asset_id])
                for asset_id in diff_assets
            ]
        )

    # Write into DB
    if bulk_writes:
        dbcon.bulk_write(bulk_writes)
        save_project_timestamp(project['name'])

    # Add to active projects collection if not already present
    if sync_quick_active_projects and not project_exists_in_actives(project_name):
        add_project_to_actives(project_name)
        log.info(f"Added '{project_name}' to active projects collection.")
