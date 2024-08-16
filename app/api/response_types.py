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
"""The types for the api endpoint results."""
from typing import TypedDict

from app.system.autotag.autotag import TagClusterEntry
from app.system.deepdive.collection import DocumentObj, SegmentStats
from app.system.smind.api import QueueStat
from app.system.smind.vec import DBName, VecDBStat
from app.system.workqueues.queue import ProcessError, ProcessQueueStats


UserResponse = TypedDict('UserResponse', {
    "uuid": str | None,
    "name": str | None,
})
"""Provides information about the currently logged in user: the uuid and
display name."""
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
    "deepdives": list[str],
    "error": list[str] | None,
})
"""Provides information about the currently running server."""
HeartbeatResponse = TypedDict('HeartbeatResponse', {
    "okay": bool,
})
"""Heartbeat response."""
StatsResponse = TypedDict('StatsResponse', {
    "vecdbs": list[VecDBStat],
    "queues": list[QueueStat],
    "process_queue": ProcessQueueStats,
})
"""Statistics about the current state of the app. """
URLInspectResponse = TypedDict('URLInspectResponse', {
    "url": str,
    "iso3": str | None,
})
"""Information about a url."""
DateResponse = TypedDict('DateResponse', {
    "date": str | None,
})
"""The date or `None` if no date could be found."""
Snippy = TypedDict('Snippy', {
    "text": str,
    "offset": int,
})
"""A snippet. It contains the text and the offset in the fulltext."""
SnippyResponse = TypedDict('SnippyResponse', {
    "count": int,
    "snippets": list[Snippy],
})
"""The number of snippets and the actual snippets in a list."""
BuildIndexResponse = TypedDict('BuildIndexResponse', {
    "new_index_count": int,
})
"""Indicates the number of newly created indices."""
CollectionResponse = TypedDict('CollectionResponse', {
    "collection_id": int,
})
"""The collection id."""
CollectionStats = TypedDict('CollectionStats', {
    "segments": list[SegmentStats],
})
"""Segment statistics. Provides information about the progress of each
snippet."""
CollectionJSON = TypedDict('CollectionJSON', {
    "id": int,
    "user": str,
    "name": str,
    "deep_dive_name": str,
    "is_public": bool,
})
"""Information about a collection."""
CollectionListResponse = TypedDict('CollectionListResponse', {
    "collections": list[CollectionJSON],
})
"""All collections visible to the current user."""
CollectionOptionsResponse = TypedDict('CollectionOptionsResponse', {
    "success": bool,
})
"""Whether the operation was successful."""
DocumentResponse = TypedDict('DocumentResponse', {
    "document_ids": list[int],
})
"""List of document ids."""
DocumentListResponse = TypedDict('DocumentListResponse', {
    "documents": list[DocumentObj],
    "is_readonly": bool,
})
"""All documents of a collection and information about whether the current
user is allowed to modify the collection."""
TagListResponse = TypedDict('TagListResponse', {
    "tags": dict[str, list[str]],
    "tag_group": int,
})
"""Tags (clusters) of a given set of main ids. The tag group is returned as
well."""
TagClustersResponse = TypedDict('TagClustersResponse', {
    "clusters": list[TagClusterEntry],
    "tag_group": int,
})
"""Clusters of a given tag group. The tag group is returned as well."""
TagDocsResponse = TypedDict('TagDocsResponse', {
    "main_ids": list[str],
    "tag_group": int,
    "cluster_id": int,
})
"""All documents (main ids) with the given tag (cluster). The tag group and
cluster id are returned as well."""
FulltextResponse = TypedDict('FulltextResponse', {
    "content": str | None,
    "error": str | None,
})
"""Either the fulltext of a document or the error."""
TitleResponse = TypedDict('TitleResponse', {
    "url": str | None,
    "title": str | None,
    "error": str | None,
})
"""Either the url and title of a document or the error."""
TitlesResponse = TypedDict('TitlesResponse', {
    "info": list[TitleResponse],
})
"""Info about multiple documents."""
RequeueResponse = TypedDict('RequeueResponse', {
    "done": bool,
})
"""Whether the queue operation was successful."""
AddQueue = TypedDict('AddQueue', {
    "enqueued": bool,
})
"""Whether the element is successfully added to the queue."""
ErrorProcessQueue = TypedDict('ErrorProcessQueue', {
    "errors": list[ProcessError],
})
"""Errors in the processing queue."""
