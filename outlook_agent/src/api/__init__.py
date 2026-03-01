from agents.outlook_agent.src.api.routes_oauth import router as oauth_router
from agents.outlook_agent.src.api.routes_email import router as email_router
from agents.outlook_agent.src.api.routes_folders import router as folders_router

__all__ = ["oauth_router", "email_router", "folders_router"]
