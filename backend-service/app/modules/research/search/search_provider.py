from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class SearchProvider(Protocol):
    """
    Search provider interface for discovering fresh articles across the web.
    """

    async def search(
        self, query: str, limit: int = 10, time_range: str = "day"
    ) -> List[Dict[str, Any]]:
        """
        Executes query and returns list of results: [{url, title, snippet, publishedDate}]
        """
        ...
