import pyodbc
from typing import Any, Optional, Union,List, Dict


CONN_STR = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=tcp:agents-builder-database-server.database.windows.net;DATABASE=AgentsBuilder;UID=aressadmin;PWD=Aress123$'

def get_connection():
    return pyodbc.connect(CONN_STR)

def create_deployment_record(user_id: int, deployment_id: str, description: str, details: str, tool_id: str, sha: Optional[str] = None):
    """
    Build the initial deployment data dict and insert into DB with status 'in progress'.
    """
    data = {
        'user_id': user_id,
        'deployment_id': deployment_id,
        'description': description,
        'details': details,
        'tool_id': tool_id,
        'name': name,
        'sha': sha,
        'run_id': None,
        'url': None,
        'status': 'in progress',
        'error': None
    }
    return insert_marketplace_tools_deployed(data)

def insert_marketplace_tools_deployed(data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO marketplace_tools_deployed
        (user_id, deployment_id, description, details, tool_id, name, sha, run_id, url, status, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['user_id'], data['deployment_id'], data.get('description'), data.get('details'),
        data.get('tool_id'), data.get('name'), data.get('sha'), data.get('run_id'), data.get('url'),
        data.get('status'), data.get('error')
    ))
    conn.commit()
    cursor.close()
    conn.close()
    return cursor.rowcount

def update_marketplace_tools_deployed(user_id: int, deployment_id: str, status_or_dict: Union[str, dict], run_id: Any = None, url: str = None, error: str = None):
    """
    Update deployment record. Accepts either:
    - user_id, deployment_id, status, run_id, url, error
    - user_id, deployment_id, update_dict (with keys: status, run_id, url, error)
    """
    # If a dict is passed as the third argument, extract fields
    if isinstance(status_or_dict, dict):
        update_dict = status_or_dict
        status = update_dict.get('status')
        run_id = update_dict.get('run_id')
        url = update_dict.get('url')
        error = update_dict.get('error')
    else:
        status = status_or_dict
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE marketplace_tools_deployed
        SET status=?, run_id=?, url=?, error=?
        WHERE user_id=? AND deployment_id=?
    ''', (
        status,
        run_id,
        url,
        error,
        user_id,
        deployment_id
    ))
    conn.commit()
    cursor.close()
    conn.close()
    return cursor.rowcount

def get_deployment_id_by_app_name(user_id: int, app_name: str) -> Optional[str]:
    """
    Get the deployment_id for a given user and app_name.
    
    Args:
        user_id: User ID
        app_name: Name of the app
        
    Returns:
        deployment_id if found, None otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT deployment_id 
        FROM marketplace_tools_deployed 
        WHERE user_id=? AND tool_id LIKE ?
    ''', (user_id, f"%{app_name}%"))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None

def delete_marketplace_tools_deployed(user_id: int, deployment_id: str) -> int:
    """
    Delete a deployment record from the database.
    
    Args:
        user_id: User ID associated with the deployment
        deployment_id: ID of the deployment to delete
        
    Returns:
        Number of rows deleted (0 or 1)
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM marketplace_tools_deployed
        WHERE user_id=? AND deployment_id=?
    ''', (user_id, deployment_id))
    conn.commit()
    cursor.close()
    conn.close()
    return cursor.rowcount




def fetch_all_marketplace_tools() -> List[Dict[str, Any]]:
    """
    Fetch all marketplace tools.
    Example:
        tools = fetch_all_marketplace_tools()
        # Returns: List of dicts, each dict is a tool row
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM marketplace_tools WHERE soft_delete = 0')
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]




def get_user_tools_from_db(user_id: int) -> List[Dict[str, Any]]:
    """
    Fetch all tools for a specific user from the database.
    
    Args:
        user_id: The ID of the user whose tools to fetch
        
    Returns:
        List of dictionaries, each representing a tool
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM marketplace_tools_deployed WHERE user_id = ? AND soft_delete = 0"
        cursor.execute(query, (user_id,))
        
        # Get column names
        columns = [column[0] for column in cursor.description]
        
        # Convert rows to list of dictionaries
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
        
    except Exception as e:
        raise Exception(f"Database error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()




































































#iwreeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee





def update_container_app_status_stop(user_id: str, container_app_name: str, status: str, run_id: str = None):
    """
    Update the status and deployment_id of a container app in the database.
    
    Args:
        user_id: The ID of the user who owns the deployment
        container_app_name: Name of the container app (will update deployment_id)
        status: New status to set
        run_id: Optional run ID from the workflow
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Build the update query
        query = """
            UPDATE marketplace_tools_deployed
            SET status = ?, 
                run_id = COALESCE(?, run_id),
                deployment_id = ?
            WHERE user_id = ? 
            AND deployment_id = ?
        """
        
        params = (status, run_id, container_app_name, user_id, container_app_name)
        
        cursor.execute(query, params)
        conn.commit()
        
        return cursor.rowcount > 0
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Database error in update_container_app_status: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()





def container_app_status_update(user_id: str, deployment_id: str, status: str, run_id: str = None):
    """
    Update the status and deployment_id of a container app in the database.
    
    Args:
        user_id: The ID of the user who owns the deployment
        container_app_name: Name of the container app (will update deployment_id)
        status: New status to set
        run_id: Optional run ID from the workflow
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Build the update query
        query = """
            UPDATE marketplace_tools_deployed
            SET status = ?, 
                run_id = COALESCE(?, run_id),
                deployment_id = ?
            WHERE user_id = ? 
            AND deployment_id = ?
        """
        
        params = (status, run_id, deployment_id, user_id, deployment_id)
        
        cursor.execute(query, params)
        conn.commit()
        
        return cursor.rowcount > 0
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Database error in update_container_app_status: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()















































def update_container_app_restart_status(user_id: str, container_app_name: str, status: str, run_id: str = None, error: str = None):
    """
    Update the status and run_id of a container app in the database after restart.
    
    Args:
        user_id: The ID of the user who owns the deployment
        container_app_name: Name of the container app (used as deployment_id)
        status: New status to set ('running' on success, 'error' on failure)
        run_id: The run ID from the workflow
        error: Error message if any
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Build the update query
        query = """
            UPDATE marketplace_tools_deployed
            SET status = ?,
                run_id = COALESCE(?, run_id),
                error = ?
            WHERE user_id = ? 
            AND deployment_id = ?
        """
        
        params = (status, run_id, error, user_id, container_app_name)
        
        cursor.execute(query, params)
        conn.commit()
        
        return cursor.rowcount > 0
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Database error in update_container_app_restart_status: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()






