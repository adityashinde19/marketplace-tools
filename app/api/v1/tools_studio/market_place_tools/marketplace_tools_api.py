from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
import uuid
import os
import sys
import base64
import logging
from azure.storage.blob import BlobServiceClient
from app.services.tools_studio.market_place_tools.appsettings import AppSettings

# Configure logging
logger = logging.getLogger(__name__)

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.services.tools_studio.market_place_tools.deploy_tool import GitHubDeployWorkflowManager
from app.services.tools_studio.market_place_tools.stop_tool import GitHubStopWorkflowManager
from app.services.tools_studio.market_place_tools.update_tool import GitHubUpdateWorkflowManager
from app.services.tools_studio.market_place_tools.restart_tool import GitHubRestartWorkflowManager
from app.services.tools_studio.market_place_tools.delete_tool import GitHubDeleteWorkflowManager
from app.services.tools_studio.market_place_tools.database import update_container_app_restart_status, update_container_app_status_stop, delete_marketplace_tools_deployed, insert_marketplace_tools_deployed, get_deployment_id_by_app_name, get_user_tools_from_db, update_marketplace_tools_deployed,container_app_status_update
from app.services.tools_studio.market_place_tools.fetch_all_tool import fetch_all_marketplace_tools_with_images

router = APIRouter(
    tags=["marketplace_tools"],
    responses={404: {"description": "Not found"}},
    prefix="/agentbuilder/api/v1"
)

# Define request models
class StopRequest(BaseModel):
    app_name: str
    user_id: Optional[int] = None  # Making user_id optional

class RestartRequest(BaseModel):
    app_name: str
    user_id: Optional[int] = None  # Making user_id optional

class DeleteRequest(BaseModel):
    app_name: str
    user_id: Optional[int] = None  # Making user_id optional

class DeployToolRequest(BaseModel):
    user_id: int
    tool_id: str
    name: str
    description: str
    details: str
    sha: Optional[str] = None
    credentials: Dict[str, str] = Field(..., description="Key-value pairs for credentials")

class DeployToolResponse(BaseModel):
    deployment_id: str
    run_id: Optional[int]
    url: Optional[str]
    status: str
    error: Optional[str]




class updateRequest(BaseModel):
    deployment_id: str
    config_type: str = "environment"  # "environment" or "secrets"
    key_name: str
    key_value: str
    is_secret: bool = False
    unique_id: Optional[int] = None  # Optional tracking ID
    user_id: int  # User ID for database tracking


#user tools
class UserRequest(BaseModel):
    user_id: int

class UserToolsResponse(BaseModel):
    success: bool
    tools: List[Dict[str, Any]]
    message: str = ""






@router.get("/tools_studio/marketplace_tools/fetch_all_marketplace_tools", summary="Get all tools with images")
def get_all_tools():
    """
    Fetch all marketplace tools with their associated image (base64-encoded).
    """
    try:
        tools = fetch_all_marketplace_tools_with_images()
        return {"tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tools: {str(e)}")
    




#for deploying a tool container
@router.post("/tools_studio/marketplace_tools/deploy_tool_container")
async def deploy_tool(request: DeployToolRequest):
    # unique_id is generated here and passed to the workflow; clients do NOT need to send it
    deployment_id = (
        f"{request.tool_id[:4]}-{request.user_id}-{uuid.uuid4().hex[:4]}"
        .lower()
        .replace("_", "-")
        [:32]
    )
    unique_id = str(uuid.uuid4())[:8] # <-- Generate unique_id for workflow

    # Insert only initial fields
    data = {
        'user_id': request.user_id,
        'deployment_id': deployment_id,
        'name': request.name,
        'description': request.description,
        'details': request.details,
        'tool_id': request.tool_id,
        'sha': request.sha,
        'status': 'in progress'
    }
    insert_marketplace_tools_deployed(data)
    tool_dir = f"tools_studio/{request.tool_id}"
    token = os.environ.get("PERSONAL_GITHUB_TOKEN")
    try:
        workflow_manager = GitHubDeployWorkflowManager()
        
        # Get workflow details from environment
        repo = os.getenv("GITHUB_REPO", "adiityaaa19/custom-code")
        workflow_file = "admin-to-user-market-key2.yml"
        ref = os.getenv("GITHUB_REF", "main")
        
        # Trigger workflow and get run ID
        run_id_val = workflow_manager.trigger_github_workflow(
            deployment_id,
            tool_dir,
            request.credentials,
            unique_id
        )
        
        # Download and verify artifact
        artifact_json = workflow_manager.download_and_verify_artifact(
            run_id_val,
            deployment_id,
            unique_id
        )
        
        # Check status in artifact JSON
        if artifact_json.get("status") == "success":
            update_data = {
                'run_id': artifact_json.get("run_id"),
                'url': artifact_json.get("endpoint"),
                'status': 'running',
                'error': artifact_json.get("error")
            }
        else:
            update_data = {
                'run_id': artifact_json.get("run_id"),
                'url': artifact_json.get("endpoint"),
                'status': 'failure',
                'error': artifact_json.get("error") or "Deployment failed"
            }
        
        update_marketplace_tools_deployed(request.user_id, deployment_id, update_data)
        return DeployToolResponse(
            deployment_id=deployment_id,
            run_id=artifact_json.get("run_id"),
            url=artifact_json.get("endpoint"),
            status=update_data['status'],
            error=update_data['error']
        )
    except Exception as exc:
        update_marketplace_tools_deployed(request.user_id, deployment_id, {
            'run_id': None,
            'url': None,
            'status': 'failure',
            'error': str(exc)
        })
        raise HTTPException(status_code=500, detail=str(exc))



@router.post("/tools_studio/marketplace_tools/update_tool_container")
async def stop_container_app(request: updateRequest):
    """
    Update a container app deployment.
    
    Args:
        request: StopRequest object containing:
            - app_name: Name of the container app to update
            - user_id: Optional user ID (for database tracking)
    
    Returns:
        JSON response with status and any error messages
    """
    try:
        # Validate request
        if not request.deployment_id:
            raise HTTPException(status_code=400, detail="deployment_id is required")
            
        # Initialize GitHub workflow manager
        workflow_manager = GitHubUpdateWorkflowManager()
        
        # Generate unique ID for tracking
        unique_id = str(uuid.uuid4())[:6]
        
        # Trigger the workflow
        workflow_manager.trigger_update_workflow(request.deployment_id, unique_id, request.config_type, request.key_name, request.key_value, request.is_secret)
        
        # Wait for workflow completion and get results
        run_id = workflow_manager.get_workflow_run_by_artifact(unique_id)
        if not run_id:
            raise HTTPException(status_code=500, detail="Failed to get workflow run ID")
            
        result = workflow_manager.download_and_verify_artifact(run_id, request.deployment_id, unique_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to get workflow result")
        
        # Update database if user_id is provided and workflow was successful
        if request.user_id and result.get("status") == "success":
            try:
                success = container_app_status_update(
                    user_id=str(request.user_id),
                    deployment_id=request.deployment_id,
                    status="running",
                    run_id=run_id
                )
                if not success:
                    # Log warning but don't fail the request
                    print(f"Warning: Failed to update database status for app {request.deployment_id}")
            except Exception as db_error:
                # Log the error but don't fail the request
                print(f"Database update error: {str(db_error)}")
            
        return {"status": "success", "result": result}
        
    except HTTPException:
        # Re-raise HTTP exceptions as is
        raise
    except Exception as e:
        # Log the full error for debugging
        print(f"Error in stop_container_app: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to stop container: {str(e)}"
        )




#for stopping a tool container
@router.post("/tools_studio/marketplace_tools/stop_tool_container")
async def stop_container_app(request: StopRequest):
    """
    Stop a container app deployment.
    
    Args:
        request: StopRequest object containing:
            - app_name: Name of the container app to stop
            - user_id: Optional user ID (for database tracking)
    
    Returns:
        JSON response with status and any error messages
    """
    try:
        # Validate request
        if not request.app_name:
            raise HTTPException(status_code=400, detail="app_name is required")
            
        # Initialize GitHub workflow manager
        workflow_manager = GitHubStopWorkflowManager()
        
        # Generate unique ID for tracking
        unique_id = str(uuid.uuid4())[:6]
        
        # Trigger the workflow
        workflow_manager.trigger_stop_workflow(request.app_name, unique_id)
        
        # Wait for workflow completion and get results
        run_id = workflow_manager.get_workflow_run_by_artifact(unique_id)
        if not run_id:
            raise HTTPException(status_code=500, detail="Failed to get workflow run ID")
            
        result = workflow_manager.download_and_verify_artifact(run_id, request.app_name, unique_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to get workflow result")
        
        # Update database if user_id is provided and workflow was successful
        if request.user_id and result.get("status") == "success":
            try:
                success = update_container_app_status_stop(
                    user_id=str(request.user_id),
                    container_app_name=request.app_name,
                    status="paused",
                    run_id=run_id
                )
                if not success:
                    # Log warning but don't fail the request
                    print(f"Warning: Failed to update database status for app {request.app_name}")
            except Exception as db_error:
                # Log the error but don't fail the request
                print(f"Database update error: {str(db_error)}")
            
        return {"status": "success", "result": result}
        
    except HTTPException:
        # Re-raise HTTP exceptions as is
        raise
    except Exception as e:
        # Log the full error for debugging
        print(f"Error in stop_container_app: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to stop container: {str(e)}"
        )

#for restarting a tool container
@router.post("/tools_studio/marketplace_tools/restart_tool_container")
async def restart_container_app(request: RestartRequest):
    """
    Restart a container app deployment.
    
    Args:
        request: RestartRequest object containing:
            - app_name: Name of the container app to restart
            - user_id: Optional user ID (for database tracking)
    
    Returns:
        JSON response with status and any error messages
    """
    try:
        # Validate request
        if not request.app_name:
            raise HTTPException(status_code=400, detail="app_name is required")
            
        # Initialize GitHub workflow manager
        workflow_manager = GitHubRestartWorkflowManager()
        
        # Generate unique ID for tracking
        unique_id = str(uuid.uuid4())[:6]
        
        # Trigger the workflow
        workflow_manager.trigger_restart_workflow(request.app_name, unique_id)
        
        # Wait for workflow completion and get results
        run_id = workflow_manager.get_workflow_run_by_artifact(unique_id)
        if not run_id:
            raise HTTPException(status_code=500, detail="Failed to get workflow run ID")
            
        result = workflow_manager.download_and_verify_artifact(run_id, request.app_name, unique_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to get workflow result")
        
        # Update database if user_id is provided
        if request.user_id:
            try:
                status = "running" if result.get("status") == "success" else "error"
                success = update_container_app_restart_status(
                    user_id=str(request.user_id),
                    container_app_name=request.app_name,
                    status=status,
                    run_id=run_id,
                    error=result.get("error")
                )
                if not success:
                    print(f"Warning: Failed to update database status for app {request.app_name}")
            except Exception as db_error:
                print(f"Database update error: {str(db_error)}")
            
        return {"status": "success", "result": result}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in restart_container_app: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to restart container: {str(e)}"
        )


@router.post("/tools_studio/marketplace_tools/delete_tool_container")
async def delete_container_app(request: DeleteRequest):
    """
    Delete a container app deployment.
    
    Args:
        request: DeleteRequest object containing:
            - app_name: Name of the container app to delete
            - user_id: Optional user ID (for database tracking)
    
    Returns:
        JSON response with status and any error messages
    """
    try:
        # Initialize GitHub workflow manager
        workflow_manager = GitHubDeleteWorkflowManager()
        
        # Generate unique ID for tracking
        unique_id = str(uuid.uuid4())[:6]
        
        # Trigger the workflow
        workflow_manager.trigger_delete_workflow(request.app_name, unique_id)
        
        # Wait for workflow completion and get results
        run_id = workflow_manager.get_workflow_run_by_artifact(unique_id)
        result = workflow_manager.download_and_verify_artifact(run_id, request.app_name, unique_id)
        
        # Delete from database if user_id is provided and operation was successful
        if request.user_id and result.get("status") == "success":
            deleted_rows = delete_marketplace_tools_deployed(
                request.user_id,
                request.app_name
            )
            if deleted_rows == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"No deployment found for user {request.user_id} and app {request.app_name}"
                )
            
        return {"status": "success", "result": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




#user tools

@router.post("/tools_studio/marketplace_tools/my_tools", response_model=UserToolsResponse)
async def get_user_tools(request: UserRequest = Body(...)):
    """
    Fetch all tools deployed by a specific user using POST method.
    
    Request Body:
        - user_id: int - The ID of the user whose tools to fetch
        
    Returns:
        JSON response with list of tools (including base64-encoded images) and status
    """
    try:
        user_id = request.user_id
        tools = get_user_tools_from_db(user_id)
        
        # Add base64-encoded images to each tool
        if tools:
            try:
                # Get Azure Blob Storage configuration
                AZURE_CONNECTION_STRING = AppSettings().AZURE_BLOB_CONNECTION_STRING
                TOOLS_CONTAINER_NAME = AppSettings().AZURE_TOOLS_CONTAINER_NAME
                
                if not AZURE_CONNECTION_STRING:
                    logger.warning("Azure Storage connection string not set in environment variables.")
                else:
                    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
                    container_client = blob_service_client.get_container_client(TOOLS_CONTAINER_NAME)
                    
                    for tool in tools:
                        tool_id = tool.get('tool_id')
                        image_base64 = None
                        
                        # Try fetching the image with different extensions
                        for ext in ["", ".png", ".jpg", ".jpeg", ".webp"]:
                            try:
                                blob_client = container_client.get_blob_client(tool_id + ext)
                                image_bytes = blob_client.download_blob().readall()
                                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                                break
                            except Exception:
                                continue
                        
                        tool['image_base64'] = image_base64
            except Exception as e:
                logger.error(f"Error fetching images from blob storage: {str(e)}")
                # Continue without images if there's an error
        
        return {
            "success": True,
            "tools": tools,
            "message": f"Successfully retrieved {len(tools)} tools for user {user_id}"
        }
        
    except Exception as e:
        logger.error(f"Error in get_user_tools: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching tools: {str(e)}"
        )




    



