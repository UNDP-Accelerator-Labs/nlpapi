# NLP-API provides useful Natural Language Processing capabilities as API.
# Copyright (C) 2024 UNDP Accelerator Labs, Josua Krause
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from typing import TypedDict

from app.system.deepdive.collection import DeepDiveName, DocumentObj
from app.system.smind.api import QueueStat
from app.system.smind.vec import DBName, VecDBStat
from app.system.workqueues.queue import ProcessError, ProcessQueueStats


SourceResponse = TypedDict('SourceResponse', {
    "source": str,
})
SourceListResponse = TypedDict('SourceListResponse', {
    "sources": list[str],
})
UserResponse = TypedDict('UserResponse', {
    "uuid": str | None,
    "name": str | None,
})
VersionResponse = TypedDict('VersionResponse', {
    "app_name": str,
    "app_commit": str,
    "python": str,
    "deploy_date": str,
    "start_date": str,
    "has_vecdb": bool,
    "has_llm": bool,
    "vecdb_ready": bool,
    "vecdbs": list[DBName],
    "deepdives": list[DeepDiveName],
    "error": list[str] | None,
})
StatsResponse = TypedDict('StatsResponse', {
    "vecdbs": list[VecDBStat],
    "queues": list[QueueStat],
    "process_queue": ProcessQueueStats,
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
CollectionResponse = TypedDict('CollectionResponse', {
    "collection_id": int,
})
CollectionJSON = TypedDict('CollectionJSON', {
    "id": int,
    "user": str,
    "name": str,
    "deep_dive_key": str,
    "is_public": bool,
})
CollectionListResponse = TypedDict('CollectionListResponse', {
    "collections": list[CollectionJSON],
})
CollectionOptionsResponse = TypedDict('CollectionOptionsResponse', {
    "success": bool,
})
DocumentResponse = TypedDict('DocumentResponse', {
    "document_ids": list[int],
})
DocumentListResponse = TypedDict('DocumentListResponse', {
    "documents": list[DocumentObj],
    "is_readonly": bool,
})
FulltextResponse = TypedDict('FulltextResponse', {
    "content": str | None,
    "error": str | None,
})
RequeueResponse = TypedDict('RequeueResponse', {
    "done": bool,
})
AddQueue = TypedDict('AddQueue', {
    "enqueued": bool,
})
ErrorProcessQueue = TypedDict('ErrorProcessQueue', {
    "errors": list[ProcessError],
})
