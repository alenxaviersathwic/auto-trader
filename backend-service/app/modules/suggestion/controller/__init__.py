from app.modules.suggestion.controller.suggestion_controller import suggestion_router

# No server-side loop to resume after a restart: the Suggestion page drives iterations (one card at a
# time), so RUNNING card sessions simply continue the next time the page is open.

__all__ = ["suggestion_router"]
