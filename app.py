import os
import json
import uuid
import httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

from config import settings

# Create app
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up templates
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)

# Mount static files
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

# In-memory session storage (replace with Redis in production)
sessions: Dict[str, Dict[str, Any]] = {}

class MCPRequest(BaseModel):
    action: str
    params: Optional[dict] = {}

class UserSession(BaseModel):
    session_id: str
    created_at: datetime
    last_activity: datetime
    user_data: Optional[dict] = {}
    auth_token: Optional[str] = None

# Helper functions
def get_or_create_session(session_id: str = None) -> UserSession:
    """Get or create a user session"""
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "session_id": session_id,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "user_data": {},
            "auth_token": None
        }
    
    # Update last activity
    sessions[session_id]["last_activity"] = datetime.utcnow()
    return UserSession(**sessions[session_id])

async def call_mcp_server(action: str, params: dict, token: str = None) -> dict:
    """Make a request to the Zomato MCP server"""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                settings.MCP_SERVER_URL,
                json={"action": action, "params": params},
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 401:
                return {"error": "Authentication required", "requires_auth": True}
                
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {str(e)}", "status_code": e.response.status_code}
        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    return templates.TemplateResponse("index.html", {"request": request, "title": settings.APP_NAME})

@app.get("/auth/login")
async def login():
    """Start OAuth flow"""
    auth_url = (
        f"{settings.MCP_SERVER_URL}/auth/authorize"
        f"?response_type=code"
        f"&client_id={settings.MCP_CLIENT_ID}"
        f"&redirect_uri={settings.MCP_REDIRECT_URI}"
        f"&state={str(uuid.uuid4())}"
    )
    return {"auth_url": auth_url}

@app.get("/auth/callback")
async def auth_callback(code: str, state: str):
    """OAuth callback endpoint"""
    try:
        # Exchange code for token
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.MCP_CLIENT_ID,
            "client_secret": settings.MCP_CLIENT_SECRET,
            "redirect_uri": settings.MCP_REDIRECT_URI
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.MCP_SERVER_URL}/auth/token",
                json=token_data
            )
            response.raise_for_status()
            token_response = response.json()
            
            # Store the token in the session
            session = get_or_create_session(state)
            sessions[state]["auth_token"] = token_response.get("access_token")
            
            return {"status": "success", "session_id": state}
            
    except Exception as e:
        return {"status": "error", "message": f"Authentication failed: {str(e)}"}

@app.post("/api/mcp")
async def mcp_endpoint(request: MCPRequest, session_id: str):
    """Proxy endpoint for MCP server requests"""
    if session_id not in sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    session = sessions[session_id]
    token = session.get("auth_token")
    
    if not token and request.action != "authenticate":
        return {"error": "Authentication required", "requires_auth": True}
    
    # Forward the request to MCP server
    result = await call_mcp_server(request.action, request.params, token)
    
    # Update session activity
    sessions[session_id]["last_activity"] = datetime.utcnow()
    
    return {"result": result, "session_id": session_id}

# Clean up old sessions
async def cleanup_sessions():
    """Remove sessions older than 24 hours"""
    now = datetime.utcnow()
    expired_sessions = [
        session_id for session_id, session in sessions.items()
        if now - session["created_at"] > timedelta(hours=24)
    ]
    for session_id in expired_sessions:
        sessions.pop(session_id, None)

# Startup and shutdown events
@app.on_event("startup")
async def startup():
    """Initialize application services"""
    # Ensure directories exist
    settings.TEMPLATES_DIR.mkdir(exist_ok=True)
    settings.STATIC_DIR.mkdir(exist_ok=True)
    
    # Clean up old sessions
    await cleanup_sessions()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD
    )
