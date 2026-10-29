from app.modules.users.controller.user_controller import oauth_router, user_router
from app.modules.users.job import register_token_refresh_job

# Module hooks into the shared scheduler on import (main.py only includes the routers).
register_token_refresh_job()

__all__ = ["user_router", "oauth_router"]
