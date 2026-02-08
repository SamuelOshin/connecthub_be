"""Audit Logging System"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.supabase import get_supabase_admin_client


class AuditLogger:
    """
    Audit logger for tracking user actions.
    Uses service role to bypass RLS for insertions.
    """
    
    # Actions that should be audited
    AUDITABLE_ACTIONS = {
        # Profile actions
        "GET /api/v1/profiles/me": "PROFILE_VIEW",
        "PATCH /api/v1/profiles/me": "PROFILE_UPDATE",
        
        # Photo actions
        "POST /api/v1/photos/upload-url": "PHOTO_UPLOAD",
        "DELETE /api/v1/photos/": "PHOTO_DELETE",
        
        # Discovery actions
        "POST /api/v1/discovery/swipe": "SWIPE",
        
        # Match actions
        "DELETE /api/v1/matches/": "UNMATCH",
        
        # Chat actions
        "POST /api/v1/chat/": "MESSAGE_SEND",
        
        # Privacy actions
        "GET /api/v1/privacy/export": "DATA_EXPORT",
        "POST /api/v1/privacy/delete-request": "DELETION_REQUEST",
        "DELETE /api/v1/privacy/cancel-deletion": "DELETION_CANCEL",
        
        # Safety actions
        "POST /api/v1/safety/block/": "USER_BLOCK",
        "DELETE /api/v1/safety/block/": "USER_UNBLOCK",
        "POST /api/v1/safety/report": "USER_REPORT",
    }
    
    def __init__(self):
        self.supabase = get_supabase_admin_client()
    
    def get_action_type(self, method: str, path: str) -> Optional[str]:
        """Determine the action type from method and path."""
        # Check exact matches first
        key = f"{method} {path}"
        if key in self.AUDITABLE_ACTIONS:
            return self.AUDITABLE_ACTIONS[key]
        
        # Check prefix matches for parameterized routes
        for route_prefix, action in self.AUDITABLE_ACTIONS.items():
            route_method, route_path = route_prefix.split(" ", 1)
            if method == route_method and path.startswith(route_path):
                return action
        
        return None
    
    async def log(
        self,
        user_id: Optional[UUID],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log an audit event."""
        try:
            self.supabase.table("audit_logs").insert({
                "user_id": str(user_id) if user_id else None,
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "details": details or {},
                "ip_address": ip_address,
                "user_agent": user_agent
            }).execute()
        except Exception as e:
            # Log error but don't fail the request
            print(f"Audit log error: {e}")


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically log auditable actions.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.audit_logger = AuditLogger()
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Get action type
        action_type = self.audit_logger.get_action_type(
            request.method, 
            request.url.path
        )
        
        # Call the actual endpoint
        response = await call_next(request)
        
        # Only log successful actions
        if action_type and 200 <= response.status_code < 300:
            # Extract user ID from request state (set by auth dependency)
            user_id = getattr(request.state, "user_id", None)
            
            # Get client info
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            # Log the action
            await self.audit_logger.log(
                user_id=user_id,
                action=action_type,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None  # Truncate long user agents
            )
        
        return response


# Singleton instance
_audit_logger: Optional[AuditLogger] = None

def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
