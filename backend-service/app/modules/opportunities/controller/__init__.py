from app.modules.opportunities.controller.opportunity_controller import opportunity_router

# No server-side loop to resume after a restart: the Opportunities page drives iterations (one card at a
# time), so RUNNING card sessions simply continue the next time the page is open.

__all__ = ["opportunity_router"]

