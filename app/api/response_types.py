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

from app.system.deepdive.collection import DocumentObj
from app.system.smind.api import QueueStat
from app.system.smind.vec import VecDBStat


SourceResponse = TypedDict('SourceResponse', {
    "source": str,
})
SourceListResponse = TypedDict('SourceListResponse', {
    "sources": list[str],
})
UserResponse = TypedDict('UserResponse', {
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
CollectionResponse = TypedDict('CollectionResponse', {
    "collection_id": int,
})
CollectionJSON = TypedDict('CollectionJSON', {
    "id": int,
    "name": str,
})
CollectionListResponse = TypedDict('CollectionListResponse', {
    "collections": list[CollectionJSON],
})
DocumentResponse = TypedDict('DocumentResponse', {
    "document_ids": list[int],
})
DocumentListResponse = TypedDict('DocumentListResponse', {
    "documents": list[DocumentObj],
})
