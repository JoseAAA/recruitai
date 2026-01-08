"""
Cloud Sync API Routes
Handles OAuth flow and folder synchronization for OneDrive and Google Drive.
"""
import secrets
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.db.models import CloudConnectionDB, UserDB
from app.adapters.onedrive_adapter import onedrive_adapter
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cloud", tags=["cloud-sync"])

# Store OAuth states temporarily (in production, use Redis)
oauth_states: dict[str, dict] = {}


class CloudConnectionResponse(BaseModel):
    id: str
    provider: str
    folder_path: Optional[str]
    is_active: bool
    last_sync: Optional[datetime]
    created_at: datetime


class FolderItem(BaseModel):
    id: str
    name: str
    path: str


class FileItem(BaseModel):
    id: str
    name: str
    size: int
    modified: Optional[str]


class SyncRequest(BaseModel):
    folder_path: str


class SyncStatus(BaseModel):
    connection_id: str
    provider: str
    folder_path: str
    last_sync: Optional[datetime]
    files_synced: int = 0
    status: str  # "active", "syncing", "error"


# ==================== OneDrive OAuth ====================

@router.get("/onedrive/status")
async def get_onedrive_status():
    """Check if OneDrive is configured."""
    return {
        "configured": onedrive_adapter.is_configured,
        "redirect_uri": settings.ONEDRIVE_REDIRECT_URI,
    }


@router.get("/onedrive/auth")
async def start_onedrive_auth(
    user_id: str = Query(..., description="Current user ID for association")
):
    """
    Start OneDrive OAuth flow.
    Returns URL to redirect user to Microsoft login.
    """
    if not onedrive_adapter.is_configured:
        raise HTTPException(
            status_code=400,
            detail="OneDrive OAuth not configured. Set ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET."
        )
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    oauth_states[state] = {
        "user_id": user_id,
        "created_at": datetime.utcnow()
    }
    
    auth_url = onedrive_adapter.get_authorization_url(state)
    
    return {
        "auth_url": auth_url,
        "message": "Redirect user to auth_url for Microsoft login"
    }


@router.get("/onedrive/callback")
async def onedrive_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth callback from Microsoft.
    Exchanges code for tokens and stores encrypted in DB.
    """
    if error:
        logger.error(f"OneDrive OAuth error: {error} - {error_description}")
        # Redirect to frontend with error
        return RedirectResponse(
            url=f"{settings.ONEDRIVE_REDIRECT_URI.replace('/api/cloud/onedrive/callback', '')}/data?error={error}"
        )
    
    # Verify state
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    
    state_data = oauth_states.pop(state)
    user_id = state_data["user_id"]
    
    try:
        # Exchange code for tokens
        tokens = await onedrive_adapter.exchange_code_for_tokens(code)
        
        # Get user info to verify connection
        user_info = await onedrive_adapter.get_user_info(tokens["access_token"])
        logger.info(f"OneDrive connected for user: {user_info.get('displayName')}")
        
        # Check if connection already exists
        result = await db.execute(
            select(CloudConnectionDB).where(
                CloudConnectionDB.user_id == UUID(user_id),
                CloudConnectionDB.provider == "onedrive"
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing connection
            existing.access_token_encrypted = onedrive_adapter.encryption.encrypt(tokens["access_token"])
            if tokens["refresh_token"]:
                existing.refresh_token_encrypted = onedrive_adapter.encryption.encrypt(tokens["refresh_token"])
            existing.expires_at = tokens["expires_at"]
            existing.is_active = True
        else:
            # Create new connection
            connection = CloudConnectionDB(
                user_id=UUID(user_id),
                provider="onedrive",
                access_token_encrypted=onedrive_adapter.encryption.encrypt(tokens["access_token"]),
                refresh_token_encrypted=onedrive_adapter.encryption.encrypt(tokens["refresh_token"]) if tokens["refresh_token"] else None,
                expires_at=tokens["expires_at"],
                is_active=True,
            )
            db.add(connection)
        
        await db.commit()
        
        # Redirect to frontend success page
        frontend_url = settings.ONEDRIVE_REDIRECT_URI.replace("/api/cloud/onedrive/callback", "")
        return RedirectResponse(url=f"{frontend_url}/data?connected=onedrive")
        
    except Exception as e:
        logger.error(f"OneDrive token exchange failed: {e}")
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")


@router.get("/onedrive/folders")
async def list_onedrive_folders(
    user_id: str = Query(...),
    path: str = Query("root"),
    db: AsyncSession = Depends(get_db)
):
    """List folders in OneDrive for folder selection."""
    # Get connection
    result = await db.execute(
        select(CloudConnectionDB).where(
            CloudConnectionDB.user_id == UUID(user_id),
            CloudConnectionDB.provider == "onedrive",
            CloudConnectionDB.is_active == True
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="OneDrive not connected")
    
    # Decrypt access token
    access_token = onedrive_adapter.encryption.decrypt(connection.access_token_encrypted)
    
    # Check if token expired and refresh if needed
    if connection.expires_at and connection.expires_at < datetime.utcnow():
        if connection.refresh_token_encrypted:
            refresh_token = onedrive_adapter.encryption.decrypt(connection.refresh_token_encrypted)
            new_tokens = await onedrive_adapter.refresh_access_token(refresh_token)
            connection.access_token_encrypted = onedrive_adapter.encryption.encrypt(new_tokens["access_token"])
            connection.expires_at = new_tokens["expires_at"]
            await db.commit()
            access_token = new_tokens["access_token"]
        else:
            raise HTTPException(status_code=401, detail="Token expired, reconnect required")
    
    try:
        folders = await onedrive_adapter.list_folders(access_token, path)
        return {
            "path": path,
            "folders": [
                FolderItem(
                    id=f["id"],
                    name=f["name"],
                    path=f"{path}/{f['name']}" if path != "root" else f["name"]
                )
                for f in folders
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list folders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list folders: {str(e)}")


@router.post("/onedrive/sync")
async def start_onedrive_sync(
    user_id: str = Query(...),
    request: SyncRequest = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Set folder path and trigger sync.
    Downloads new CVs from the folder and processes them.
    """
    # Get connection
    result = await db.execute(
        select(CloudConnectionDB).where(
            CloudConnectionDB.user_id == UUID(user_id),
            CloudConnectionDB.provider == "onedrive",
            CloudConnectionDB.is_active == True
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="OneDrive not connected")
    
    # Update folder path
    if request and request.folder_path:
        connection.folder_path = request.folder_path
    
    if not connection.folder_path:
        raise HTTPException(status_code=400, detail="No folder path configured")
    
    # Decrypt access token
    access_token = onedrive_adapter.encryption.decrypt(connection.access_token_encrypted)
    
    try:
        # List files in folder
        files = await onedrive_adapter.list_files(access_token, connection.folder_path)
        
        # TODO: For each file, download and process through CV extraction pipeline
        # This would be done async in production
        
        connection.last_sync = datetime.utcnow()
        await db.commit()
        
        return {
            "status": "completed",
            "folder_path": connection.folder_path,
            "files_found": len(files),
            "files": files[:10],  # Return first 10 for preview
            "last_sync": connection.last_sync.isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.delete("/onedrive/disconnect")
async def disconnect_onedrive(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Disconnect OneDrive and remove stored tokens."""
    result = await db.execute(
        select(CloudConnectionDB).where(
            CloudConnectionDB.user_id == UUID(user_id),
            CloudConnectionDB.provider == "onedrive"
        )
    )
    connection = result.scalar_one_or_none()
    
    if connection:
        await db.delete(connection)
        await db.commit()
    
    return {"status": "disconnected", "provider": "onedrive"}


# ==================== Connection Status ====================

@router.get("/connections")
async def list_connections(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """List all cloud connections for a user."""
    result = await db.execute(
        select(CloudConnectionDB).where(
            CloudConnectionDB.user_id == UUID(user_id)
        )
    )
    connections = result.scalars().all()
    
    return {
        "connections": [
            CloudConnectionResponse(
                id=str(c.id),
                provider=c.provider,
                folder_path=c.folder_path,
                is_active=c.is_active,
                last_sync=c.last_sync,
                created_at=c.created_at,
            )
            for c in connections
        ]
    }
