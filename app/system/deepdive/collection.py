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
"""Database access for LLM powered deep dives."""
from collections.abc import Iterable
from typing import cast, Literal, overload, TypedDict
from uuid import UUID

import sqlalchemy as sa
from quick_server import PreventDefaultResponse
from sqlalchemy.orm import Session

from app.system.db.base import (
    DeepDiveCollection,
    DeepDiveElement,
    DeepDiveProcess,
    DeepDivePrompt,
    DeepDiveSegment,
)
from app.system.db.db import DBConnector
from app.system.prep.snippify import snippify_text


DeepDiveProcessRow = TypedDict('DeepDiveProcessRow', {
    "verify": int,
    "categories": int,
})
"""Prompt ids for verification and category prompts."""


DeepDiveSegmentationInfo = TypedDict('DeepDiveSegmentationInfo', {
    "chunk_size": int,
    "chunk_padding": int,
    "categories": list[str],
})
"""Information on chunking and what categories to expect."""


DeepDivePromptInfo = TypedDict('DeepDivePromptInfo', {
    "name": str,
    "main_prompt": str,
    "post_prompt": str | None,
    "categories": list[str] | None,
})
"""System prompts and categories for a given prompt. If categories is None the
prompt is a verification prompt."""


CollectionObj = TypedDict('CollectionObj', {
    "id": int,
    "user": UUID,
    "name": str,
    "deep_dive_name": str,
    "is_public": bool,
})
"""A collection."""


CollectionOptions = TypedDict('CollectionOptions', {
    "is_public": bool,
})
"""Collection options."""


VerifyResult = TypedDict('VerifyResult', {
    "reason": str,
    "is_hit": bool,
})
"""Result of a verification prompt."""


DeepDiveResult = TypedDict('DeepDiveResult', {
    "reason": str,
    "values": dict[str, int],
})
"""Result of a category prompt."""


DocumentObj = TypedDict('DocumentObj', {
    "id": int,
    "main_id": str,
    "url": str | None,
    "title": str | None,
    "deep_dive": int,
    "segmentation": DeepDiveSegmentationInfo,
    "is_valid": bool | None,
    "verify_reason": str | None,
    "deep_dive_result": DeepDiveResult | None,
    "error": str | None,
    "tag": str | None,
    "tag_reason": str | None,
})
"""Full document information."""


SegmentObj = TypedDict('SegmentObj', {
    "id": int,
    "main_id": str,
    "page": int,
    "deep_dive": int,
    "verify_id": int,
    "categories_id": int,
    "content": str,
    "is_valid": bool | None,
    "verify_reason": str | None,
    "deep_dive_result": DeepDiveResult | None,
    "error": str | None,
})
"""Full segment information."""


SegmentStats = TypedDict('SegmentStats', {
    "deep_dive": int,
    "is_valid": bool | None,
    "has_result": bool,
    "has_error": bool,
    "count": int,
})
"""Statistics about current segments."""


def get_deep_dives(db: DBConnector) -> list[str]:
    """
    Returns a list of all available deep dives.

    Args:
        db (DBConnector): The database connector.

    Returns:
        list[str]: The names of the deep dives.
    """
    with db.get_session() as session:
        stmt = sa.select(DeepDiveProcess.name)
        return [row.name for row in session.execute(stmt)]


def get_process_id(session: Session, name: str) -> int:
    """
    Get the id of a deep dive process.

    Args:
        session (Session): The database session.
        name (str): The name of the deep dive.

    Raises:
        ValueError: If the deep dive doesn't exist.

    Returns:
        int: The deep dive process id.
    """
    stmt = sa.select(DeepDiveProcess.id)
    stmt = stmt.where(DeepDiveProcess.name == name)
    stmt = stmt.limit(1)
    process_id = session.execute(stmt).scalar()
    if process_id is None:
        raise ValueError(f"could not find deep dive for {name=}")
    return int(process_id)


def get_deep_dive_process(
        session: Session, process_id: int) -> DeepDiveProcessRow:
    """
    Retrieves the specification of a deep dive process.

    Args:
        session (Session): The database session.
        process_id (int): The deep dive process id.

    Raises:
        ValueError: If the deep dive process doesn't exist.

    Returns:
        DeepDiveProcessRow: The deep dive process specification.
    """
    stmt = sa.select(DeepDiveProcess.verify_id, DeepDiveProcess.categories_id)
    stmt = stmt.where(DeepDiveProcess.id == process_id)
    stmt = stmt.limit(1)
    for row in session.execute(stmt):
        return {
            "verify": int(row.verify_id),
            "categories": int(row.categories_id),
        }
    raise ValueError(f"{process_id=} not found")


def get_deep_dive_prompt_info(
        session: Session,
        prompt_ids: set[int]) -> dict[int, DeepDivePromptInfo]:
    """
    Retrieves the prompt specifications for the given prompt ids.

    Args:
        session (Session): The database session.
        prompt_ids (set[int]): The prompt ids to retrieve.

    Returns:
        dict[int, DeepDivePromptInfo]: The mapping of prompt id to
            specification.
    """
    stmt = sa.select(
        DeepDivePrompt.id,
        DeepDivePrompt.name,
        DeepDivePrompt.main_prompt,
        DeepDivePrompt.post_prompt,
        DeepDivePrompt.categories)
    stmt = stmt.where(DeepDivePrompt.id.in_(list(prompt_ids)))
    res: dict[int, DeepDivePromptInfo] = {}
    for row in session.execute(stmt):
        res[int(row.id)] = {
            "name": row.name,
            "main_prompt": row.main_prompt,
            "post_prompt": row.post_prompt,
            "categories": f"{row.categories}".split(","),
        }
    return res


def add_collection(
        db: DBConnector,
        user: UUID,
        name: str,
        deep_dive: str) -> int:
    """
    Adds a new collection.

    Args:
        db (DBConnector): The database connector.
        user (UUID): The user uuid.
        name (str): The name of the collection.
        deep_dive (str): The deep dive process name.

    Raises:
        ValueError: If the collection could not be added.

    Returns:
        int: The collection id.
    """
    with db.get_session() as session:
        process_id = get_process_id(session, deep_dive)
        stmt = sa.insert(DeepDiveCollection).values(
            name=name,
            user=user,
            process=process_id)
        stmt = stmt.returning(DeepDiveCollection.id)
        row_id = session.execute(stmt).scalar()
        if row_id is None:
            raise ValueError(f"error adding collection {name}")
    return int(row_id)


def set_options(
        db: DBConnector,
        collection_id: int,
        options: CollectionOptions,
        user: UUID | None) -> None:
    """
    Sets the options for the given collection.

    Args:
        db (DBConnector): The database connector.
        collection_id (int): The collection id.
        options (CollectionOptions): The option values to set.
        user (UUID | None): The user uuid.
    """
    with db.get_session() as session:
        verify_user(session, collection_id, user, write=True)
        stmt = sa.update(DeepDiveCollection)
        stmt = stmt.where(DeepDiveCollection.id == collection_id)
        stmt = stmt.values(
            is_public=options["is_public"])
        session.execute(stmt)


def get_collections(db: DBConnector, user: UUID) -> Iterable[CollectionObj]:
    """
    Retrieves the collections visible to the given user.

    Args:
        db (DBConnector): The database connector.
        user (UUID): The user uuid.

    Yields:
        CollectionObj: The collection.
    """
    with db.get_session() as session:
        stmt = sa.select(
            DeepDiveCollection.id,
            DeepDiveCollection.user,
            DeepDiveCollection.name,
            DeepDiveCollection.is_public,
            DeepDiveProcess.name.label("ddname"))
        stmt = stmt.where(sa.and_(
            DeepDiveCollection.process == DeepDiveProcess.id,
            sa.or_(
                DeepDiveCollection.user == user,
                DeepDiveCollection.is_public)))
        stmt = stmt.order_by(DeepDiveCollection.id)
        for row in session.execute(stmt):
            yield {
                "id": int(row.id),
                "user": row.user,
                "name": row.name,
                "deep_dive_name": row.ddname,
                "is_public": row.is_public,
            }


def verify_user(
        session: Session,
        collection_id: int,
        user: UUID | None,
        *,
        write: bool,
        allow_none: bool = False) -> bool:
    """
    Verifies that the given user is allowed to perform an operation.

    Args:
        session (Session): The database session.
        collection_id (int): The collection id.
        user (UUID | None): The user uuid.
        write (bool): Whether the operation requires write access to the
            collection.
        allow_none (bool, optional): Whether to allow an empty user uuid.
            Defaults to False.

    Raises:
        PreventDefaultResponse: If the user is not allowed to access the
            collection id.

    Returns:
        bool: True, if the user is *not* allowed to write to the collection.
    """
    if user is None:
        if not allow_none:
            raise PreventDefaultResponse(401, "invalid collection for user")
        return False
    stmt = sa.select(
        DeepDiveCollection.id,
        (DeepDiveCollection.user != user).label("is_readonly"))
    stmt = stmt.where(sa.and_(
        DeepDiveCollection.id == collection_id,
        sa.or_(
            DeepDiveCollection.user == user,
            sa.false() if write else DeepDiveCollection.is_public)))
    row = session.execute(stmt).one_or_none()
    if row is None or int(row.id) != collection_id:
        raise PreventDefaultResponse(401, "invalid collection for user")
    return bool(row.is_readonly)


def add_documents(
        db: DBConnector,
        collection_id: int,
        main_ids: list[str],
        user: UUID | None,
        *,
        allow_none: bool = False) -> list[int]:
    """
    Adds documents to a collection.

    Args:
        db (DBConnector): The database connector.
        collection_id (int): The collection id.
        main_ids (list[str]): The main ids to add.
        user (UUID | None): The user uuid.
        allow_none (bool, optional): Whether to allow an unspecified user.
            This is useful if a collection is created automatically and not via
            user action. Defaults to False.

    Returns:
        list[int]: The list of collection member ids of successfully added
            documents.
    """
    res: list[int] = []
    with db.get_session() as session:
        verify_user(
            session, collection_id, user, write=True, allow_none=allow_none)
        for main_id in main_ids:
            cstmt = db.upsert(DeepDiveElement).values(
                main_id=main_id,
                deep_dive_id=collection_id)
            cstmt = cstmt.on_conflict_do_nothing()
            cstmt = cstmt.returning(DeepDiveElement.id)
            eid = session.execute(cstmt).scalar()
            if eid is not None:
                res.append(int(eid))
    return res


@overload
def convert_deep_dive_result(
        ddr: dict[str, int | str],
        *,
        categories: list[str] | None) -> DeepDiveResult:
    ...


@overload
def convert_deep_dive_result(
        ddr: None, *, categories: list[str] | None) -> None:
    ...


def convert_deep_dive_result(
        ddr: dict[str, int | str] | None,
        *,
        categories: list[str] | None) -> DeepDiveResult | None:
    """
    Converts a deep dive result to the current unified format. Deep dive
    results can either have all fields in the object directly
    `{"reason": ..., "a": 1, "b": 5, ...}` or separate the scores out
    `{"reason": ..., "values": {"a": 1, "b": 5, ...}}`. The second variety
    is preferred as it avoids problems with a potential `reason` category and
    makes handling the object overall easier. The first variety is easier for
    an LLM to create.

    Args:
        ddr (dict[str, int  |  str] | None): The deep dive result.
        categories (list[str] | None): The expected categories. If None, no
            checks are performed.

    Raises:
        ValueError: If there is an error interpreting the result.

    Returns:
        DeepDiveResult | None: The standardized result or None if the result
            was None.
    """
    if ddr is None:
        return None
    if "values" not in ddr:
        if categories is not None:
            if "reason" in categories:
                raise ValueError(
                    "must use 'values' key when 'reason' is a category")
            return {
                "reason": cast(str, ddr["reason"]),
                "values": {
                    cat: int(ddr[cat])
                    for cat in categories
                },
            }
        return {
            "reason": cast(str, ddr["reason"]),
            "values": {
                key: int(value)
                for key, value in ddr.items()
                if key != "reason"
            },
        }
    res = cast(DeepDiveResult, ddr)
    if categories is not None:
        missing = set(categories).difference(res["values"].keys())
        if missing:
            raise ValueError(f"categories {missing} are missing in {ddr}")
    return res


def get_documents(
        db: DBConnector,
        collection_id: int,
        user: UUID | None,
        *,
        allow_none: bool = False) -> tuple[bool, list[DocumentObj]]:
    """
    Gets all documents for a collection.

    Args:
        db (DBConnector): The database connector.
        collection_id (int): The collection id.
        user (UUID | None): The user uuid.
        allow_none (bool, optional): Whether to allow an unset user uuid.
            Defaults to False.

    Returns:
        tuple[bool, list[DocumentObj]]: Boolean indicating whether the
            collection is readonly for the user and the list of documents.
    """
    with db.get_session() as session:
        is_readonly = verify_user(
            session, collection_id, user, write=False, allow_none=allow_none)
        stmt = sa.select(
            DeepDiveElement.id,
            DeepDiveElement.deep_dive_id,
            DeepDiveElement.url,
            DeepDiveElement.title,
            DeepDiveElement.main_id,
            DeepDiveElement.is_valid,
            DeepDiveElement.verify_reason,
            DeepDiveElement.deep_dive_result,
            DeepDiveElement.error,
            DeepDiveElement.tag,
            DeepDiveElement.tag_reason,
            DeepDiveProcess.chunk_size,
            DeepDiveProcess.chunk_padding,
            DeepDivePrompt.categories)
        stmt = stmt.where(sa.and_(
            DeepDiveElement.deep_dive_id == DeepDiveCollection.id,
            DeepDiveCollection.id == collection_id,
            DeepDiveProcess.id == DeepDiveCollection.process,
            DeepDivePrompt.id == DeepDiveProcess.categories_id))
        stmt = stmt.order_by(DeepDiveElement.id)

        def get_categories(categories_str: str | None) -> list[str]:
            assert categories_str is not None
            return categories_str.split(",")

        docs: list[DocumentObj] = [
            {
                "id": row.id,
                "main_id": row.main_id,
                "url": row.url,
                "title": row.title,
                "deep_dive": row.deep_dive_id,
                "segmentation": {
                    "chunk_size": row.chunk_size,
                    "chunk_padding": row.chunk_padding,
                    "categories": get_categories(row.categories),
                },
                "is_valid": row.is_valid,
                "verify_reason": row.verify_reason,
                "deep_dive_result": convert_deep_dive_result(
                    row.deep_dive_result, categories=None),
                "error": row.error,
                "tag": row.tag,
                "tag_reason": row.tag_reason,
            }
            for row in session.execute(stmt)
        ]
        return (is_readonly, docs)


def set_url_title(
        db: DBConnector,
        doc_id: int,
        url: str,
        title: str) -> None:
    """
    Sets the url and title of a document.

    Args:
        db (DBConnector): The database connector.
        doc_id (int): The document id.
        url (str): The url.
        title (str): The title.
    """
    with db.get_session() as session:
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(DeepDiveElement.id == doc_id)
        stmt = stmt.values(
            url=url,
            title=title)
        session.execute(stmt)


def set_tag(
        db: DBConnector,
        doc_id: int,
        tag: str | None,
        tag_reason: str) -> None:
    """
    Sets the tag (i.e., country) of a document.

    Args:
        db (DBConnector): The database connector.
        doc_id (int): The document id.
        tag (str | None): The tag or None.
        tag_reason (str): The reason.
    """
    with db.get_session() as session:
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(DeepDiveElement.id == doc_id)
        stmt = stmt.values(
            tag=tag,
            tag_reason=tag_reason)
        session.execute(stmt)


def set_verify(
        session: Session,
        doc_id: int,
        is_valid: bool,
        reason: str) -> None:
    """
    Sets the verification field of a document.

    Args:
        session (Session): The database session.
        doc_id (int): The document id.
        is_valid (bool): Whether the document is valid.
        reason (str): The reason.
    """
    stmt = sa.update(DeepDiveElement)
    stmt = stmt.where(DeepDiveElement.id == doc_id)
    stmt = stmt.values(
        verify_reason=reason,
        is_valid=is_valid)
    session.execute(stmt)


def set_deep_dive(
        session: Session,
        doc_id: int,
        deep_dive: DeepDiveResult) -> None:
    """
    Sets the category result of a document.

    Args:
        session (Session): The database session.
        doc_id (int): The document id.
        deep_dive (DeepDiveResult): The deep dive result.
    """
    stmt = sa.update(DeepDiveElement)
    stmt = stmt.where(DeepDiveElement.id == doc_id)
    stmt = stmt.values(deep_dive_result=deep_dive)
    session.execute(stmt)


def set_error(db: DBConnector, doc_id: int, error: str) -> None:
    """
    Sets the error for a document.

    Args:
        db (DBConnector): The database connector.
        doc_id (int): The document id.
        error (str): The error.
    """
    with db.get_session() as session:
        set_doc_error(session, doc_id, error)


def set_doc_error(session: Session, doc_id: int, error: str) -> None:
    """
    Sets the error for a document in a database session.

    Args:
        session (Session): The database session.
        doc_id (int): The document id.
        error (str): The error.
    """
    stmt = sa.update(DeepDiveElement)
    stmt = stmt.where(DeepDiveElement.id == doc_id)
    stmt = stmt.values(error=error)
    session.execute(stmt)


def requeue(
        db: DBConnector,
        collection_id: int,
        user: UUID | None,
        main_ids: list[str],
        *,
        allow_none: bool = False) -> None:
    """
    Requeues documents for processing.

    Args:
        db (DBConnector): The database connector.
        collection_id (int): The collection id.
        user (UUID | None): The user uuid.
        main_ids (list[str]): The list of documents as main ids.
        allow_none (bool, optional): Whether the user uuid can be None.
            Defaults to False.
    """
    with db.get_session() as session:
        verify_user(
            session, collection_id, user, write=True, allow_none=allow_none)
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(sa.and_(
            DeepDiveElement.deep_dive_id == collection_id,
            DeepDiveElement.main_id.in_(main_ids)))
        stmt = stmt.values(
            url=None,
            title=None,
            is_valid=None,
            verify_reason=None,
            deep_dive_result=sa.null(),
            error=None)
        session.execute(stmt)
        remove_segments(session, collection_id, main_ids)


def requeue_error(
        db: DBConnector,
        collection_id: int,
        user: UUID | None,
        main_ids: list[str],
        *,
        allow_none: bool = False) -> None:
    """
    Requeues only the segments containing an error for reprocessing.

    Args:
        db (DBConnector): The database connector.
        collection_id (int): The collection id.
        user (UUID | None): The user uuid.
        main_ids (list[str]): The list of main ids.
        allow_none (bool, optional): Whether the user uuid can be None.
            Defaults to False.
    """
    with db.get_session() as session:
        verify_user(
            session, collection_id, user, write=True, allow_none=allow_none)
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(sa.and_(
            DeepDiveElement.deep_dive_id == collection_id,
            DeepDiveElement.main_id.in_(main_ids)))
        stmt = stmt.values(
            url=None,
            title=None,
            is_valid=None,
            verify_reason=None,
            deep_dive_result=sa.null(),
            error=None)
        session.execute(stmt)

        seg_stmt = sa.update(DeepDiveSegment)
        seg_stmt = seg_stmt.where(sa.and_(
            DeepDiveSegment.deep_dive_id == collection_id,
            DeepDiveSegment.main_id.in_(main_ids)))
        seg_stmt = seg_stmt.values(error=None)
        session.execute(seg_stmt)


def requeue_meta(
        db: DBConnector,
        collection_id: int,
        user: UUID | None,
        main_ids: list[str],
        *,
        allow_none: bool = False) -> None:
    """
    Requeue only the document meta data for reprocessing.

    Args:
        db (DBConnector): The database connector.
        collection_id (int): The collection id.
        user (UUID | None): The user uuid.
        main_ids (list[str]): The list of documents as main ids.
        allow_none (bool, optional): Whether the user uuid can be None.
            Defaults to False.
    """
    with db.get_session() as session:
        verify_user(
            session, collection_id, user, write=True, allow_none=allow_none)
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(sa.and_(
            DeepDiveElement.deep_dive_id == collection_id,
            DeepDiveElement.main_id.in_(main_ids)))
        stmt = stmt.values(url=None, title=None, tag=None, tag_reason=None)
        session.execute(stmt)


def get_documents_in_queue(db: DBConnector) -> Iterable[DocumentObj]:
    """
    Retrieve documents that need processing.

    Args:
        db (DBConnector): The database connector.

    Yields:
        DocumentObj: The document.
    """
    with db.get_session() as session:
        stmt = sa.select(
            DeepDiveElement.id,
            DeepDiveElement.deep_dive_id,
            DeepDiveElement.main_id,
            DeepDiveElement.url,
            DeepDiveElement.title,
            DeepDiveElement.is_valid,
            DeepDiveElement.verify_reason,
            DeepDiveElement.deep_dive_result,
            DeepDiveElement.error,
            DeepDiveElement.tag,
            DeepDiveElement.tag_reason,
            DeepDiveProcess.chunk_size,
            DeepDiveProcess.chunk_padding,
            DeepDivePrompt.categories)
        stmt = stmt.where(sa.and_(
            DeepDivePrompt.id == DeepDiveProcess.categories_id,
            DeepDiveProcess.id == DeepDiveCollection.process,
            DeepDiveElement.deep_dive_id == DeepDiveCollection.id,
            sa.or_(
                DeepDiveElement.url.is_(None),
                DeepDiveElement.title.is_(None),
                DeepDiveElement.is_valid.is_(None),
                DeepDiveElement.deep_dive_result.is_(None),
                DeepDiveElement.tag_reason.is_(None)),
            DeepDiveElement.error.is_(None)))
        stmt = stmt.order_by(
            DeepDiveElement.deep_dive_id, DeepDiveElement.main_id)

        def get_categories(categories_str: str) -> list[str]:
            assert categories_str is not None
            return categories_str.split(",")

        for row in session.execute(stmt):
            yield {
                "id": row.id,
                "main_id": row.main_id,
                "url": row.url,
                "title": row.title,
                "deep_dive": row.deep_dive_id,
                "segmentation": {
                    "chunk_size": row.chunk_size,
                    "chunk_padding": row.chunk_padding,
                    "categories": get_categories(row.categories),
                },
                "is_valid": row.is_valid,
                "verify_reason": row.verify_reason,
                "deep_dive_result": convert_deep_dive_result(
                    row.deep_dive_result, categories=None),
                "error": row.error,
                "tag": row.tag,
                "tag_reason": row.tag_reason,
            }


def add_segments(
        db: DBConnector,
        doc: DocumentObj,
        full_text: str) -> int:
    """
    Add segments for the given document.

    Args:
        db (DBConnector): The database connector.
        doc (DocumentObj): The document.
        full_text (str): The full text of the document.

    Returns:
        int: The number of pages for the document.
    """
    page = 0
    with db.get_session() as session:
        collection_id = doc["deep_dive"]
        main_id = doc["main_id"]
        segmentation_info = doc["segmentation"]
        remove_segments(session, collection_id, [main_id])
        for content, _ in snippify_text(
                full_text,
                chunk_size=segmentation_info["chunk_size"],
                chunk_padding=segmentation_info["chunk_padding"]):
            stmt = sa.insert(DeepDiveSegment).values(
                main_id=main_id,
                page=page,
                deep_dive_id=collection_id,
                content=content)
            session.execute(stmt)
            page += 1
    return page


def get_segments_in_queue(db: DBConnector) -> Iterable[SegmentObj]:
    """
    Retrieves all unprocessed segments.

    Args:
        db (DBConnector): The database connector.

    Yields:
        SegmentObj: The segment.
    """
    with db.get_session() as session:
        stmt = sa.select(
            DeepDiveSegment.id,
            DeepDiveSegment.main_id,
            DeepDiveSegment.page,
            DeepDiveSegment.deep_dive_id,
            DeepDiveSegment.content,
            DeepDiveSegment.is_valid,
            DeepDiveSegment.verify_reason,
            DeepDiveSegment.deep_dive_result,
            DeepDiveSegment.error,
            DeepDiveProcess.verify_id,
            DeepDiveProcess.categories_id)
        stmt = stmt.where(sa.and_(
            DeepDiveProcess.id == DeepDiveCollection.process,
            DeepDiveSegment.deep_dive_id == DeepDiveCollection.id,
            sa.or_(
                DeepDiveSegment.is_valid.is_(None),
                DeepDiveSegment.deep_dive_result.is_(None)),
            DeepDiveSegment.error.is_(None)))
        stmt = stmt.order_by(
            DeepDiveSegment.deep_dive_id,
            DeepDiveSegment.main_id,
            DeepDiveSegment.page)
        # stmt = stmt.order_by(
        #     DeepDiveSegment.main_id,
        #     DeepDiveSegment.deep_dive_id,
        #     DeepDiveSegment.page)
        stmt = stmt.limit(20)
        for row in session.execute(stmt):
            yield {
                "id": row.id,
                "main_id": row.main_id,
                "page": row.page,
                "deep_dive": row.deep_dive_id,
                "verify_id": row.verify_id,
                "categories_id": row.categories_id,
                "content": row.content,
                "is_valid": row.is_valid,
                "verify_reason": row.verify_reason,
                "deep_dive_result": convert_deep_dive_result(
                    row.deep_dive_result, categories=None),
                "error": row.error,
            }


def get_segments(
        session: Session,
        collection_id: int,
        main_id: str) -> Iterable[SegmentObj]:
    """
    Gets all segments of the given document.

    Args:
        session (Session): The database session.
        collection_id (int): The collection id.
        main_id (str): The document main id.

    Yields:
        SegmentObj: The segment.
    """
    stmt = sa.select(
        DeepDiveSegment.id,
        DeepDiveSegment.main_id,
        DeepDiveSegment.page,
        DeepDiveSegment.deep_dive_id,
        DeepDiveSegment.content,
        DeepDiveSegment.is_valid,
        DeepDiveSegment.verify_reason,
        DeepDiveSegment.deep_dive_result,
        DeepDiveSegment.error,
        DeepDiveProcess.verify_id,
        DeepDiveProcess.categories_id)
    stmt = stmt.where(sa.and_(
        DeepDiveProcess.id == DeepDiveCollection.process,
        DeepDiveSegment.deep_dive_id == DeepDiveCollection.id,
        DeepDiveSegment.deep_dive_id == collection_id,
        DeepDiveSegment.main_id == main_id))
    stmt = stmt.order_by(DeepDiveSegment.page)
    for row in session.execute(stmt):
        yield {
            "id": row.id,
            "main_id": row.main_id,
            "page": row.page,
            "deep_dive": row.deep_dive_id,
            "verify_id": row.verify_id,
            "categories_id": row.categories_id,
            "content": row.content,
            "is_valid": row.is_valid,
            "verify_reason": row.verify_reason,
            "deep_dive_result": convert_deep_dive_result(
                row.deep_dive_result, categories=None),
            "error": row.error,
        }


def set_verify_segment(
        db: DBConnector,
        seg_id: int,
        is_valid: bool,
        reason: str) -> None:
    """
    Sets the verification result of a segment.

    Args:
        db (DBConnector): The database connector.
        seg_id (int): The segment id.
        is_valid (bool): Whether the segment is valid.
        reason (str): The reason.
    """
    with db.get_session() as session:
        stmt = sa.update(DeepDiveSegment)
        stmt = stmt.where(DeepDiveSegment.id == seg_id)
        stmt = stmt.values(
            verify_reason=reason,
            is_valid=is_valid)
        session.execute(stmt)


def set_deep_dive_segment(
        db: DBConnector,
        seg_id: int,
        deep_dive: DeepDiveResult) -> None:
    """
    Sets the category result of a segment.

    Args:
        db (DBConnector): The database connector.
        seg_id (int): The segment id.
        deep_dive (DeepDiveResult): The result.
    """
    with db.get_session() as session:
        stmt = sa.update(DeepDiveSegment)
        stmt = stmt.where(DeepDiveSegment.id == seg_id)
        stmt = stmt.values(deep_dive_result=deep_dive)
        session.execute(stmt)


def set_error_segment(db: DBConnector, seg_id: int, error: str) -> None:
    """
    Set the error for a segment.

    Args:
        db (DBConnector): The database connector.
        seg_id (int): The segment id.
        error (str): The error.
    """
    with db.get_session() as session:
        stmt = sa.update(DeepDiveSegment)
        stmt = stmt.where(DeepDiveSegment.id == seg_id)
        stmt = stmt.values(error=error)
        session.execute(stmt)


def remove_segments(
        session: Session, collection_id: int, main_ids: list[str]) -> None:
    """
    Remove all segments for the given documents in the given collection.

    Args:
        session (Session): The database session.
        collection_id (int): The collection id.
        main_ids (list[str]): The documents as main ids.
    """
    stmt = sa.delete(DeepDiveSegment).where(sa.and_(
        DeepDiveSegment.main_id.in_(main_ids),
        DeepDiveSegment.deep_dive_id == collection_id))
    session.execute(stmt)


def combine_segments(
        db: DBConnector,
        doc: DocumentObj,
        categories: list[str],
        ) -> Literal["empty", "incomplete", "done"]:
    """
    Combines the segments of a document and writes the final results. If
    successful, the segments get removed from the database.

    Args:
        db (DBConnector): The database connector.
        doc (DocumentObj): The document.
        categories (list[str]): The expected categories.

    Returns:
        str: `empty` if no segments existed, `incomplete` if not all results
            were available, and `done` if the segments were combined
            successfully. The database only updates on `done`.
    """
    with db.get_session() as session:
        collection_id = doc["deep_dive"]
        main_id = doc["main_id"]
        doc_id = doc["id"]
        is_error = False
        is_hit = False
        is_incomplete = False
        no_segments = True
        error_msg = "ERROR:"
        verify_msg = ""
        results: DeepDiveResult = {
            "reason": "",
            "values": {
                cat: 0
                for cat in categories
            },
        }
        for segment in get_segments(session, collection_id, main_id):
            no_segments = False
            page = segment["page"]
            error = segment["error"]
            is_valid = segment["is_valid"]
            verify_reason = segment["verify_reason"]
            deep_dive_result = segment["deep_dive_result"]
            if error is not None:
                is_error = True
                error_msg = f"{error_msg}\n[{page=}]:\n{error}\n"
                continue
            if is_valid is None or verify_reason is None:
                is_incomplete = True
                break
            if not is_valid:
                verify_msg = (
                    f"{verify_msg}\n\n[{page=} miss]:\n{verify_reason}"
                    ).lstrip()
                continue
            is_hit = True
            verify_msg = (
                f"{verify_msg}\n\n[{page=} hit]:\n{verify_reason}").lstrip()
            if deep_dive_result is None:
                is_incomplete = True
                break
            p_reason = results["reason"]
            results["reason"] = (
                f"{p_reason}\n\n[{page=}]:\n{verify_reason}".lstrip())
            for key, prev in results["values"].items():
                prev_val: int = int(prev)
                incoming_val: int = int(deep_dive_result["values"][key])
                next_val = max(prev_val, incoming_val)
                results["values"][key] = next_val
        if no_segments:
            return "empty"
        if is_incomplete:
            # NOTE: we cannot proceed!
            return "incomplete"
        if is_error:
            error_msg = f"{error_msg}\nVERIFY:\n{verify_msg}\n"
            error_msg = f"{error_msg}\nRESULT:\n{results['reason']}"
            set_doc_error(session, doc_id, error_msg)
        else:
            set_verify(session, doc_id, is_hit, verify_msg)
            if not is_hit:
                results = {
                    "reason": (
                        "Document did not pass filter! "
                        "No interpretation performed!"),
                    "values": {
                        cat: 0
                        for cat in categories
                    },
                }
            set_deep_dive(session, doc_id, results)
        if not is_error:
            remove_segments(session, collection_id, [main_id])
        return "done"


def segment_stats(db: DBConnector) -> Iterable[SegmentStats]:
    """
    Compute statistics about the current segments in the queue.

    Args:
        db (DBConnector): The database connector.

    Yields:
        SegmentStats: Segment statistics.
    """
    with db.get_session() as session:
        stmt = sa.select(
            DeepDiveSegment.deep_dive_id,
            DeepDiveSegment.is_valid,
            DeepDiveSegment.deep_dive_result.is_not(None).label("result"),
            DeepDiveSegment.error.is_not(None).label("error"),
            sa.func.count().label("total"))  # pylint: disable=not-callable
        stmt = stmt.group_by(
            DeepDiveSegment.deep_dive_id,
            DeepDiveSegment.is_valid,
            DeepDiveSegment.deep_dive_result.is_not(None),
            DeepDiveSegment.error.is_not(None))
        for row in session.execute(stmt):
            yield {
                "deep_dive": row.deep_dive_id,
                "is_valid": row.is_valid,
                "has_result": row.result,
                "has_error": row.error,
                "count": row.total,
            }


def create_deep_dive_tables(db: DBConnector) -> None:
    """
    Creates all deep dive tables.

    Args:
        db (DBConnector): The database connector.
    """
    db.create_tables([
        DeepDivePrompt,
        DeepDiveProcess,
        DeepDiveCollection,
        DeepDiveElement,
        DeepDiveSegment,
    ])
