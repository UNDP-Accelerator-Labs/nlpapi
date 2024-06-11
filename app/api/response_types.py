from typing import TypedDict

from app.system.smind.api import QueueStat
from app.system.smind.vec import VecDBStat


SourceResponse = TypedDict('SourceResponse', {
    "source": str,
})
SourceListResponse = TypedDict('SourceListResponse', {
    "sources": list[str],
})
VersionResponse = TypedDict('VersionResponse', {
    "app_name": str,
    "app_commit": str,
    "python": str,
    "deploy_date": str,
    "start_date": str,
    "has_vecdb": bool,
    "has_llm": bool,
    "error": list[str] | None,
})
StatsResponse = TypedDict('StatsResponse', {
    "vecdbs": list[VecDBStat],
    "queues": list[QueueStat],
})
URLInspectResponse = TypedDict('URLInspectResponse', {
    "url": str,
    "iso3": str | None,
})
DateResponse = TypedDict('DateResponse', {
    "date": str | None,
})
Snippy = TypedDict('Snippy', {
    "text": str,
    "offset": int,
})
SnippyResponse = TypedDict('SnippyResponse', {
    "count": int,
    "snippets": list[Snippy],
})
BuildIndexResponse = TypedDict('BuildIndexResponse', {
    "new_index_count": int,
})
