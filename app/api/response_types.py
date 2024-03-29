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
    "error": list[str] | None,
})
StatsResponse = TypedDict('StatsResponse', {
    "vecdbs": list[VecDBStat],
    "queues": list[QueueStat],
})
