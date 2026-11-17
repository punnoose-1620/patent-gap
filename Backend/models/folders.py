import uuid
from env_controller import getFolderDatabaseName
from models.cases import (
    get_case_by_id, 
    delete_case, 
    update_case, 
    has_delete_permission as has_case_delete_permission)
from database import (
    connect_to_database, 
    getDataByKeyValue, 
    addDataById, 
    getDataById, 
    updateDataById, 
    deleteDataById)

__case_folders_key = 'folders'

def __add_folder_to_case(case_id: str, folder_id: str):
    """
    Add a folder to a case.
    """
    case_data = get_case_by_id(case_id)
    if not case_data:
        raise ValueError(f"Case {case_id} not found")
    folders = list(case_data.get(__case_folders_key) or [])
    if folder_id not in folders:
        folders.append(folder_id)
    update_flag = update_case(case_id, {__case_folders_key: folders})
    return update_flag

def __remove_folder_from_case(case_id: str, folder_id: str):
    """
    Remove a folder from a case.
    """
    case_data = get_case_by_id(case_id)
    if not case_data:
        raise ValueError(f"Case {case_id} not found")
    folders = list(case_data.get(__case_folders_key) or [])
    if folder_id in folders:
        folders.remove(folder_id)
    update_flag = update_case(case_id, {__case_folders_key: folders})
    if not update_flag.get('success', False):
        return False
    return True

#TODO: Add functions to add folder ID to user profile

#TODO: Add functions to remove folder ID from user profile

def has_delete_permission(user_id: str, folder_id: str):
    """
    Check if the user has delete permission for the folder.
    Only Creator and Owner can delete the folder.
    """
    folder_data = get_folder(folder_id)
    if not folder_data:
        return False
    created_by = folder_data.get('created_by')
    owner = folder_data.get('owner')
    return (user_id == created_by) or (user_id == owner)

def has_edit_permission(user_id: str, folder_id: str):
    """
    Check if the user has edit permission for the folder.
    Only Creator, Owner and Editors can edit the folder.
    """
    folder_data = get_folder(folder_id)
    if not folder_data:
        return False
    created_by = folder_data.get('created_by')
    owner = folder_data.get('owner')
    editors = folder_data.get('editors') or []
    return (user_id == created_by) or (user_id == owner) or (user_id in editors)

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
    cases_list = []
    if viewers:
        viewer_list.extend(viewers)
    if editors:
        editor_list.extend(editors)
    if cases:
        cases_list.extend(cases)
    # De-dupe editors, viewers and cases
    viewer_list = list(set(viewer_list))
    editor_list = list(set(editor_list))
    cases_list = list(set(cases_list))
    
    folder_data = {
        '_id': folder_id,
        'name': folder_name,
        'created_by': user_id,
        'owner': user_id,
        'viewers': viewer_list,
        'editors': editor_list,
        'cases': cases_list,
    }
    addDataById(connect_to_database(), getFolderDatabaseName(), folder_data)
    return folder_id

def rename_folder(folder_id: str, new_name: str, user_id: str):
    """
    Rename a folder.
    """
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("New folder name cannot be empty")
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    if not has_edit_permission(user_id, folder_id):
        raise ValueError("Permission denied to rename folder")
    old_name = folder_data.get('name')
    if old_name == new_name:
        return True
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'name': new_name}, folder_id)
    if not update_flag:
        raise ValueError(f"Failed to rename folder: {folder_id} to: {new_name}")
    return True

def add_case_to_folder(folder_id: str, case_id: str, user_id: str):
    """
    Add a case to a folder.
    """
    if not has_edit_permission(user_id, folder_id):
        raise ValueError("Permission denied to add case to folder")
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    cases = list(folder_data.get('cases') or [])
    if case_id not in cases:
        cases.append(case_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'cases': cases}, folder_id)
    if not update_flag:
        raise ValueError(f"Failed to add case {case_id} to folder: {folder_id}")
    add_folder_to_case_flag = __add_folder_to_case(case_id, folder_id)
    if not add_folder_to_case_flag:
        raise ValueError(f"Failed to add folder: {folder_id} to case: {case_id}")
    return True

def remove_case_from_folder(folder_id: str, case_id: str, user_id: str):
    """
    Remove a case from a folder.
    """
    if not has_edit_permission(user_id, folder_id):
        raise ValueError("Permission denied to remove case from folder")
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    cases = list(folder_data.get('cases') or [])
    if case_id in cases:
        cases.remove(case_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'cases': cases}, folder_id)
    if not update_flag:
        raise ValueError(f"Failed to remove case {case_id} from folder: {folder_id}")
    remove_folder_from_case_flag = __remove_folder_from_case(case_id, folder_id)
    if not remove_folder_from_case_flag:
        raise ValueError(f"Failed to remove folder: {folder_id} from case: {case_id}")
    return True

def add_editor_to_folder(folder_id: str, editor_id: str, user_id: str):
    """
    Add an editor to a folder.
    """
    if not has_edit_permission(user_id, folder_id):
        raise ValueError("Permission denied to add editor to folder")
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    editors = list(folder_data.get('editors') or [])
    if editor_id not in editors:
        editors.append(editor_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'editors': editors}, folder_id)
    return update_flag

def remove_editor_from_folder(folder_id: str, editor_id: str, user_id: str):
    """
    Remove an editor from a folder.
    """
    if not has_edit_permission(user_id, folder_id):
        raise ValueError("Permission denied to remove editor from folder")
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    editors = list(folder_data.get('editors') or [])
    if editor_id in editors:
        editors.remove(editor_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'editors': editors}, folder_id)
    return update_flag

def add_viewer_to_folder(folder_id: str, viewer_id: str, user_id: str):
    """
    Add a viewer to a folder.
    """
    if not has_edit_permission(user_id, folder_id):
        raise ValueError("Permission denied to add viewer to folder")
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    viewers = list(folder_data.get('viewers') or [])
    if viewer_id not in viewers:
        viewers.append(viewer_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'viewers': viewers}, folder_id)
    return update_flag

def remove_viewer_from_folder(folder_id: str, viewer_id: str, user_id: str):
    """
    Remove a viewer from a folder.
    """
    if not has_edit_permission(user_id, folder_id):
        raise ValueError("Permission denied to remove viewer from folder")
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    viewers = list(folder_data.get('viewers') or [])
    if viewer_id in viewers:
        viewers.remove(viewer_id)
    update_flag = updateDataById(connect_to_database(), getFolderDatabaseName(), {'viewers': viewers}, folder_id)
    return update_flag

def __delete_case(case_id: str, user_id: str):
    """
    Delete a case.
    """
    if not has_case_delete_permission(user_id, case_id):
        raise ValueError(f"Permission denied for user: {user_id} to delete case: {case_id}")
    delete_case_flag = delete_case(case_id)
    if not delete_case_flag.get('success', False):
        raise ValueError(f"Failed to delete case: {case_id}")
    return True

def __delete_all_cases(cases: list[str], user_id: str, folder_id: str):
    """
    Delete all cases.
    """
    deleted_case_ids = []
    deletion_errors = []
    for case_id in cases:
        try:
            __delete_case(case_id, user_id)
            deleted_case_ids.append(case_id)
        except ValueError as e:
            try:
                remove_folder_from_case_flag = __remove_folder_from_case(case_id, folder_id)
                if not remove_folder_from_case_flag:
                    deletion_errors.append(f"Failed to remove folder: {folder_id} from case: {case_id}")
            except ValueError as e_sub:
                deletion_errors.append(str(e_sub))
            deletion_errors.append(str(e))
    return deleted_case_ids, deletion_errors

def delete_folder(user_id: str, folder_id: str, delete_all_cases: bool = False, delete_case_ids: list[str] = []):
    """
    Delete a folder.
    """
    if not has_delete_permission(user_id, folder_id):
        raise ValueError("Permission denied to delete folder")
    case_remove_errors = []
    deleted_case_ids = []
    folder_data = get_folder(folder_id)
    if not folder_data:
        raise ValueError("Folder not found")
    delete_flag = deleteDataById(connect_to_database(), getFolderDatabaseName(), folder_id)
    if not delete_flag:
        raise ValueError("Failed to delete folder")
    cases = list(folder_data.get('cases') or [])
    if delete_all_cases:
        print(f"Deleting all cases which are part of folder: {folder_id}")
        deleted_list, deletion_errors = __delete_all_cases(cases, user_id, folder_id)
        deleted_case_ids.extend(deleted_list)
        case_remove_errors.extend(deletion_errors)
    else:
        for case_id in delete_case_ids:
            if case_id in cases:
                try:
                    __delete_case(case_id, user_id)
                    deleted_case_ids.append(case_id)
                    cases.remove(case_id)
                except ValueError as e:
                    case_remove_errors.append(str(e))
            else:
                case_remove_errors.append(f"Case: {case_id} not part of folder: {folder_id}")
        for case_id in cases:
            remove_folder_from_case_flag = __remove_folder_from_case(case_id, folder_id)
            if not remove_folder_from_case_flag:
                case_remove_errors.append(f"Failed to remove folder: {folder_id} from case: {case_id}")

    return case_remove_errors, deleted_case_ids