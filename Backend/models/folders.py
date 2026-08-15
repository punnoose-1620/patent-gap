import uuid
from env_controller import getFolderDatabaseName
from database import connect_to_database, getDataByKeyValue, addDataById, getDataById, updateDataById

def list_folders(user_id: str):
    """
    List all folders for a given user.
    """
    created_folders = getDataByKeyValue(connect_to_database(), getFolderDatabaseName(), 'created_by', user_id)
    viewer_folders = getDataByKeyValue(connect_to_database(), getFolderDatabaseName(), 'viewers', user_id)
    editor_folders = getDataByKeyValue(connect_to_database(), getFolderDatabaseName(), 'editors', user_id)

    returnValue = {
        'created_folders': created_folders,
        'viewer_folders': viewer_folders,
        'editor_folders': editor_folders,
    }
    return returnValue

def get_folder(folder_id: str):
    """
    Get a folder by id.
    """
    return getDataById(connect_to_database(), getFolderDatabaseName(), folder_id)

def create_folder(user_id: str, folder_name: str, viewers: list[str], editors: list[str], cases: list[str] = []):
    """
    Create a new folder for a given user.
    """
    folder_id = str(uuid.uuid4())
    folder_name = folder_name.strip()
    if not folder_name:
        raise ValueError("Folder name cannot be empty")
    viewer_list = []
    editor_list = []
    if viewers:
        viewer_list.extend(viewers)
    if editors:
        editor_list.extend(editors)
    folder_data = {
        '_id': folder_id,
        'name': folder_name,
        'created_by': user_id,
        'viewers': viewer_list,
        'editors': editor_list,
        'cases': cases,
    }
    addDataById(connect_to_database(), getFolderDatabaseName(), folder_data)
    return folder_id

def add_case_to_folder(folder_id: str, case_id: str):
    """
    Add a case to a folder.
    """
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    cases = list(folder_data.get('cases') or [])
    if case_id not in cases:
        cases.append(case_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'cases': cases}, folder_id)
    return update_flag

def remove_case_from_folder(folder_id: str, case_id: str):
    """
    Remove a case from a folder.
    """
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    cases = list(folder_data.get('cases') or [])
    if case_id in cases:
        cases.remove(case_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'cases': cases}, folder_id)
    return update_flag

def add_editor_to_folder(folder_id: str, editor_id: str):
    """
    Add an editor to a folder.
    """
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    editors = list(folder_data.get('editors') or [])
    if editor_id not in editors:
        editors.append(editor_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'editors': editors}, folder_id)
    return update_flag

def remove_editor_from_folder(folder_id: str, editor_id: str):
    """
    Remove an editor from a folder.
    """
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    editors = list(folder_data.get('editors') or [])
    if editor_id in editors:
        editors.remove(editor_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'editors': editors}, folder_id)
    return update_flag

def add_viewer_to_folder(folder_id: str, viewer_id: str):
    """
    Add a viewer to a folder.
    """
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    viewers = list(folder_data.get('viewers') or [])
    if viewer_id not in viewers:
        viewers.append(viewer_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'viewers': viewers}, folder_id)
    return update_flag

def remove_viewer_from_folder(folder_id: str, viewer_id: str):
    """
    Remove a viewer from a folder.
    """
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    viewers = list(folder_data.get('viewers') or [])
    if viewer_id in viewers:
        viewers.remove(viewer_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'viewers': viewers}, folder_id)
    return update_flag
