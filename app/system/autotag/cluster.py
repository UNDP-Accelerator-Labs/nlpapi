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
"""The processing queue for the auto tagging and clustering."""
import collections
from typing import Literal, Protocol, TypedDict

import numpy as np
from redipy import Redis
from scattermind.system.torch_util import tensor_to_str
from sklearn.cluster import AgglomerativeClustering  # type: ignore
from sklearn.preprocessing import normalize  # type: ignore

from app.misc.math import dot_order_np
from app.misc.util import (
    CHUNK_PADDING,
    CHUNK_SIZE,
    get_time_str,
    json_compact_str,
    json_read_str,
    NL,
    only,
)
from app.system.autotag.autotag import (
    add_tag_members,
    clear_clusters,
    create_cluster,
    create_tag_group,
    get_incomplete,
    get_keywords,
    get_tag_group,
    get_tag_group_cluster_args,
    get_tags_for_main_id,
    is_ready,
    is_updating_tag_group,
    remove_tag_member,
    write_tag,
)
from app.system.autotag.platform import fill_in_everything, process_main_ids
from app.system.db.db import DBConnector
from app.system.prep.fulltext import AllDocsFn, FullTextFn, IsRemoveFn
from app.system.prep.snippify import snippify_text
from app.system.smind.api import get_text_results_immediate, GraphProfile
from app.system.workqueues.queue import ProcessEnqueue, register_process_queue


class TaggerProcessor(Protocol):  # pylint: disable=too-few-public-methods
    """Function to add a new tag group to the processing queue."""
    def __call__(
            self,
            *,
            name: str | None,
            bases: list[str],
            is_updating: bool,
            cluster_args: dict) -> None:
        """
        Adds a new tag group to the processing queue.

        Args:
            name (str | None): The name of the tag group. If None the current
                time is used instead.
            bases (list[str]): Which document bases to include. Valid bases are
                `solution`, `experiment`, `actionplan`, `blog`, and `rave_ce`.
            is_updating (bool): Whether the tag group should update the
                platforms' tagging tables in the end.
            cluster_args (dict): Arguments for the clustering algorithm.
        """


InitTaggerPayload = TypedDict('InitTaggerPayload', {
    "stage": Literal["init"],
    "name": str | None,
    "is_updating": bool,
    "cluster_args": dict,
    "bases": list[str],
})
"""Initial payload for creating the tag group."""
TagTaggerPayload = TypedDict('TagTaggerPayload', {
    "stage": Literal["tag"],
})
"""Indicates that there are some documents that need auto tagging."""
CluterTaggerPayload = TypedDict('CluterTaggerPayload', {
    "stage": Literal["cluster"],
    "tag_group": int,
})
"""Performs a clustering for the given tag group."""
UpdatePlatformPayload = TypedDict('UpdatePlatformPayload', {
    "stage": Literal["platform"],
    "tag_group": int,
})
"""Update the platforms' tagging tables with the clusters of the given tag
group."""
TaggerPayload = (
    InitTaggerPayload
    | TagTaggerPayload
    | CluterTaggerPayload
    | UpdatePlatformPayload)
"""Processing queue payload for auto-tagging and clustering tasks."""


BATCH_SIZE = 20
"""How many documents to auto-tag in one step."""
TOP_K = 10
"""How many raw keywords to generate per document."""


def register_tagger(
        db: DBConnector,
        *,
        global_db: DBConnector,
        platforms: dict[str, DBConnector],
        process_queue_redis: Redis,
        articles_graph: GraphProfile,
        graph_tags: GraphProfile,
        get_all_docs: AllDocsFn,
        doc_is_remove: IsRemoveFn,
        get_full_text: FullTextFn) -> TaggerProcessor:
    """
    Registers the auto-tagging and clustering processing queue.

    Args:
        db (DBConnector): The nlpapi database connector.
        global_db (DBConnector): The login database connector.
        platforms (dict[str, DBConnector]): The platform database connectors.
        process_queue_redis (Redis): The processing queue redis.
        articles_graph (GraphProfile): Model to create document embeddings.
        graph_tags (GraphProfile): Model to create document keywords.
        get_all_docs (AllDocsFn): Retrieves all documents (as main ids) for
            the given base.
        doc_is_remove (IsRemoveFn): Whether a document (via main id) is not
            visible (anymore).
        get_full_text (FullTextFn): Retrieves the full text of a document
            (via main id).

    Returns:
        TaggerProcessor: Function to enqueue tag groups.
    """

    def tagger_payload_to_json(entry: TaggerPayload) -> dict[str, str]:
        if entry["stage"] == "init":
            return {
                "stage": "init",
                "name": "" if entry["name"] is None else entry["name"],
                "bases": ",".join(entry["bases"]),
                "is_updating": f"{int(entry['is_updating'])}",
                "cluster_args": json_compact_str(entry["cluster_args"]),
            }
        if entry["stage"] == "tag":
            return {
                "stage": "tag",
            }
        if entry["stage"] == "cluster":
            return {
                "stage": "cluster",
                "tag_group": f"{entry['tag_group']}",
            }
        if entry["stage"] == "platform":
            return {
                "stage": "platform",
                "tag_group": f"{entry['tag_group']}",
            }
        raise ValueError(f"invalid stage {entry['stage']}")

    def tagger_payload_from_json(payload: dict[str, str]) -> TaggerPayload:
        if payload["stage"] == "init":
            return {
                "stage": "init",
                "name": payload["name"] if payload["name"] else None,
                "bases": payload["bases"].split(","),
                "is_updating": bool(int(payload["is_updating"])),
                "cluster_args": json_read_str(payload["cluster_args"]),
            }
        if payload["stage"] == "tag":
            return {
                "stage": "tag",
            }
        if payload["stage"] == "cluster":
            return {
                "stage": "cluster",
                "tag_group": int(payload['tag_group']),
            }
        if payload["stage"] == "platform":
            return {
                "stage": "platform",
                "tag_group": int(payload['tag_group']),
            }
        raise ValueError(f"invalid stage {payload['stage']}")

    def tagger_compute(entry: TaggerPayload) -> str:
        if entry["stage"] == "init":
            return tagger_init(
                db,
                entry,
                process_queue_redis=process_queue_redis,
                get_all_docs=get_all_docs,
                doc_is_remove=doc_is_remove,
                process_enqueue=process_enqueue)
        if entry["stage"] == "tag":
            return tagger_tag(
                db,
                process_queue_redis=process_queue_redis,
                graph_tags=graph_tags,
                get_full_text=get_full_text,
                doc_is_remove=doc_is_remove,
                process_enqueue=process_enqueue)
        if entry["stage"] == "cluster":
            return tagger_cluster(
                db,
                entry["tag_group"],
                process_queue_redis=process_queue_redis,
                articles_graph=articles_graph,
                process_enqueue=process_enqueue)
        if entry["stage"] == "platform":
            return tagger_update_platform(
                db,
                global_db=global_db,
                platforms=platforms,
                tag_group=entry["tag_group"],
                get_all_docs=get_all_docs)
        raise ValueError(f"invalid stage {entry['stage']}")

    process_enqueue = register_process_queue(
        "tagger",
        tagger_payload_to_json,
        tagger_payload_from_json,
        tagger_compute)

    def tagger_processor(
            *,
            name: str | None,
            bases: list[str],
            is_updating: bool,
            cluster_args: dict) -> None:
        process_enqueue(
            process_queue_redis,
            {
                "stage": "init",
                "name": name,
                "bases": bases,
                "is_updating": is_updating,
                "cluster_args": cluster_args,
            })

    return tagger_processor


def tag_doc(
        main_id: str,
        *,
        graph_tags: GraphProfile,
        get_full_text: FullTextFn,
        top_k: int) -> tuple[set[str] | None, str | None]:
    """
    Creates auto-tags for the given document.

    Args:
        main_id (str): The document main id.
        graph_tags (GraphProfile): Model for extracting document keywords.
        get_full_text (FullTextFn): Retrieve the full text of a document via
            main id.
        top_k (int): How many keywords to generate per document.

    Returns:
        tuple[set[str] | None, str | None]: Set of keywords or error.
    """
    full_text, error_ft = get_full_text(main_id)
    if full_text is None:
        return None, error_ft
    smind = graph_tags.get_api()
    ns = graph_tags.get_ns()
    input_field = only(graph_tags.get_input_fields())
    texts = [
        snippet
        for (snippet, _) in snippify_text(
            full_text,
            chunk_size=CHUNK_SIZE,
            chunk_padding=CHUNK_PADDING)
    ]
    tasks = [
        smind.enqueue_task(
            ns,
            {
                input_field: text,
            })
        for text in texts
    ]
    success = True
    error_msg = ""
    kwords: collections.defaultdict[str, float] = \
        collections.defaultdict(lambda: 0.0)
    for tid, resp in smind.wait_for(tasks, timeout=300, auto_clear=True):
        if resp["error"] is not None:
            error = resp["error"]
            error_msg = (
                f"{error_msg}\n{error['code']} ({error['ctx']}): "
                f"{error['message']}\n{NL.join(error['traceback'])}")
            success = False
            continue
        result = resp["result"]
        if result is None:
            error_msg = f"{error_msg}\nmissing result for {tid}"
            success = False
            continue
        keywords = tensor_to_str(result["tags"]).split(",")
        if not keywords or (len(keywords) == 1 and not keywords[0]):
            continue
        scores = list(result["scores"].cpu().tolist())
        if len(keywords) != len(scores):
            error_msg = (
                f"{error_msg}\nkeywords and scores mismatch: "
                f"{keywords=} {scores=}")
            success = False
            continue
        for keyword, score in zip(keywords, scores):
            kwords[keyword] += score
    if not success:
        return None, error_msg
    top_kwords = sorted(
        kwords.items(),
        key=lambda wordscore: wordscore[1],
        reverse=True)[:top_k]
    return {kword for (kword, _) in top_kwords}, None


def tagger_init(
        db: DBConnector,
        entry: InitTaggerPayload,
        *,
        process_queue_redis: Redis,
        get_all_docs: AllDocsFn,
        doc_is_remove: IsRemoveFn,
        process_enqueue: ProcessEnqueue[TaggerPayload]) -> str:
    """
    Creates a new tag group and adds all documents to be processed.

    Args:
        db (DBConnector): The database connector.
        entry (InitTaggerPayload): The payload for creating the tag group.
        process_queue_redis (Redis): The processing queue redis.
        get_all_docs (AllDocsFn): Retrieves all documents for the given base.
        doc_is_remove (IsRemoveFn): Whether a document (via main id) has been
            removed.
        process_enqueue (ProcessEnqueue[TaggerPayload]): Enqueues the next
            step.

    Raises:
        ValueError: If any error happens.

    Returns:
        str: Status update.
    """
    errors: list[str] = []
    total = 0
    with db.get_session() as session:
        name = entry["name"]
        if name is None:
            name = f"tag {get_time_str()}"
        cur_tag_group = get_tag_group(session, entry["name"])
        if cur_tag_group is None:
            cur_tag_group = create_tag_group(
                session,
                entry["name"],
                is_updating=entry["is_updating"],
                cluster_args=entry["cluster_args"])
    for base in entry["bases"]:
        cur_main_ids: list[str] = []
        for cur_main_id in get_all_docs(base):
            is_remove, error_remove = doc_is_remove(cur_main_id)
            if error_remove is not None:
                errors.append(error_remove)
                continue
            if is_remove:
                continue
            cur_main_ids.append(cur_main_id)
        items_per = 100
        for ix in range(0, len(cur_main_ids), items_per):
            with db.get_session() as session:
                add_tag_members(
                    db,
                    session,
                    cur_tag_group,
                    cur_main_ids[ix:ix + items_per])
        total += len(cur_main_ids)
    process_enqueue(
        process_queue_redis,
        {
            "stage": "tag",
        })
    if errors:
        raise ValueError(
            f"errors while processing:\n{NL.join(errors)}")
    return f"created tag group {cur_tag_group} with {total} entries"


def tagger_tag(
        db: DBConnector,
        *,
        process_queue_redis: Redis,
        graph_tags: GraphProfile,
        get_full_text: FullTextFn,
        doc_is_remove: IsRemoveFn,
        process_enqueue: ProcessEnqueue[TaggerPayload]) -> str:
    """
    Computes the auto-tags for pending documents.

    Args:
        db (DBConnector): The database connector.
        process_queue_redis (Redis): The processing queue redis.
        graph_tags (GraphProfile): Model for extracting document keywords.
        get_full_text (FullTextFn): Gets the full text of a document
            (via main id).
        doc_is_remove (IsRemoveFn): Whether a document (via main id) has been
            removed.
        process_enqueue (ProcessEnqueue[TaggerPayload]): Enqueues the next
            step.

    Raises:
        ValueError: If any error happens.

    Returns:
        str: Status update.
    """
    batch_size = BATCH_SIZE
    errors: list[str] = []
    with db.get_session() as session:
        processing_count = 0
        tag_groups: set[int] = set()
        for elem in get_incomplete(session):
            main_id = elem["main_id"]
            is_remove, error_remove = doc_is_remove(main_id)
            if error_remove is not None:
                errors.append(error_remove)
                continue
            if is_remove:
                remove_tag_member(session, elem["tag_group"], elem["main_id"])
                continue
            tag_group = elem["tag_group"]
            keywords, error = tag_doc(
                main_id,
                graph_tags=graph_tags,
                get_full_text=get_full_text,
                top_k=TOP_K)
            if keywords is None:
                errors.append(
                    "error while processing "
                    f"{main_id} for {tag_group}:\n{error}")
            else:
                write_tag(
                    db,
                    session,
                    tag_group,
                    main_id,
                    list(keywords))
            tag_groups.add(tag_group)
            processing_count += 1
            if processing_count >= batch_size:
                break
        if processing_count > 0:
            process_enqueue(
                process_queue_redis,
                {
                    "stage": "tag",
                })
        for tag_group in tag_groups:
            if is_ready(session, tag_group):
                process_enqueue(
                    process_queue_redis,
                    {
                        "stage": "cluster",
                        "tag_group": tag_group,
                    })
        if errors:
            raise ValueError(
                f"errors while processing:\n{NL.join(errors)}")
    return f"finished {processing_count}"


def tagger_cluster(
        db: DBConnector,
        tag_group: int,
        *,
        process_queue_redis: Redis,
        articles_graph: GraphProfile,
        process_enqueue: ProcessEnqueue[TaggerPayload]) -> str:
    """
    Computes the clusters for a given tag group.

    Args:
        db (DBConnector): The database connector.
        tag_group (int): The tag group.
        process_queue_redis (Redis): The processing queue redis.
        articles_graph (GraphProfile): Model for document embeddings.
        process_enqueue (ProcessEnqueue[TaggerPayload]): Enqueues the next
            step.

    Returns:
        str: Status update.
    """

    def get_embeds() -> tuple[list[str], np.ndarray, dict]:
        with db.get_session() as session:
            keywords = sorted(get_keywords(session, tag_group))
            cluster_args = get_tag_group_cluster_args(session, tag_group)
        all_embeds = get_text_results_immediate(
            keywords,
            graph_profile=articles_graph,
            output_sample=[1.0])
        final_kw: list[str] = []
        embeds: list[list[float]] = []
        for keyword, embed in zip(keywords, all_embeds):
            if embed is None:
                continue
            final_kw.append(keyword)
            embeds.append(embed)
        final_embeds = normalize(embeds)
        return final_kw, final_embeds, cluster_args

    def do_cluster(embeds: np.ndarray, cluster_args: dict) -> list[list[int]]:
        kwargs = {
            "n_clusters": None,
            "distance_threshold": 0.75,
            "metric": "cosine",
            "linkage": "average",
            **cluster_args,
        }
        cmodel = AgglomerativeClustering(**kwargs)
        cmodel.fit(embeds)
        labels = cmodel.labels_
        ckwords: collections.defaultdict[str, list[int]] = \
            collections.defaultdict(list)
        for kw_ix, cluster_id in enumerate(labels):
            ckwords[cluster_id].append(kw_ix)
        return list(ckwords.values())

    def centroid(all_embeds: np.ndarray, cluster: list[int]) -> int:
        cembeds = all_embeds[cluster, :]  # len(cluster) x dim
        cvec = normalize(cembeds.sum(axis=0).reshape((1, -1)))  # 1 x dim
        ixs = dot_order_np(cvec, cembeds)
        return cluster[ixs[0]]

    kws, kwembeds, cluster_args = get_embeds()
    clusters = do_cluster(kwembeds, cluster_args)
    representatives: list[int] = [
        centroid(kwembeds, cluster)
        for cluster in clusters
    ]
    with db.get_session() as session:
        clear_clusters(session, tag_group)
        for cluster_ixs, representative_ix in zip(clusters, representatives):
            representative = kws[representative_ix]
            kw_cluster = {
                kws[cix]
                for cix in cluster_ixs
            }
            create_cluster(
                db,
                session,
                tag_group,
                representative,
                kw_cluster)
        is_updating = is_updating_tag_group(session, tag_group)

    if is_updating:
        process_enqueue(
            process_queue_redis,
            {
                "stage": "platform",
                "tag_group": tag_group,
            })
    return f"created {len(clusters)} clusters for {tag_group=}"


def tagger_update_platform(
        db: DBConnector,
        *,
        global_db: DBConnector,
        platforms: dict[str, DBConnector],
        tag_group: int,
        get_all_docs: AllDocsFn) -> str:
    """
    Updates the platforms' tagging tables with the clustering results of the
    given tag group.

    Args:
        db (DBConnector): The nlpapi database connector.
        global_db (DBConnector): The login database connector.
        platforms (dict[str, DBConnector]): The platform database connectors.
        tag_group (int): The tag group.
        get_all_docs (AllDocsFn): Retrieves all documents of a given base.

    Returns:
        str: Status update.
    """
    all_platforms: set[str] = set(platforms.keys())
    all_main_ids: list[str] = []
    for base in all_platforms:
        all_main_ids.extend(get_all_docs(base))

    with db.get_session() as session:
        def get_main_id_keywords(main_id: str) -> set[str]:
            return get_tags_for_main_id(session, tag_group, main_id)

        all_tags, kwords = process_main_ids(
            all_main_ids,
            platforms=all_platforms,
            get_keywords=get_main_id_keywords)

    fill_in_everything(global_db, platforms, all_tags=all_tags, kwords=kwords)
    return (
        f"updated all platforms ({all_platforms}) with tag group {tag_group}: "
        f"main_ids={len(all_main_ids)} all_tags={len(all_tags)}")
