
from qtpy import QtWidgets

from quadpype.lib.user import get_trackers_user_id, get_user_profile
from quadpype.settings import get_project_settings
from quadpype.widgets.message_window import Window


def filter_projects_by_assignee(projects):
    """Filter projects by assignee.
    """

    filtered_projects = []
    curr_user_profile = get_user_profile()
    curr_user_role = curr_user_profile["role"]
    curr_user_is_admin = curr_user_role == "administrator"

    trackers_id = get_trackers_user_id()
    if not trackers_id:
        parents = {
                widget.objectName(): widget
                for widget in QtWidgets.QApplication.topLevelWidgets()
            }
        Window(
            title="No trackers user ID",
            message="Trackers user ID not found. Please connect to your tracker "
            "account before using the launcher.",
            parent=parents.get("LauncherWindow"),
            level="info"
        )
        return

    for project_doc in projects:
        if curr_user_is_admin:
            filtered_projects.append(project_doc)
            continue

        project_name = project_doc.get("name")
        settings = get_project_settings(project_name)
        global_settings = settings.get("global", {})

        bypass_assignees = global_settings.get('launcher', {}).get("bypass_assignees", False)

        if bypass_assignees:
            filtered_projects.append(project_doc)
            continue

        project_team = project_doc.get("data", {}).get("team", [])
        user_is_in_project = any(
            value in project_team for value in trackers_id if value is not None
        )
        if user_is_in_project:
            filtered_projects.append(project_doc)

    return filtered_projects
