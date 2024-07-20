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
import numpy as np


def dot_order_np(
        ref_embed: np.ndarray,  # 1 x dim
        cand_embeds: np.ndarray,  # n x dim
        ) -> list[int]:
    mat_embed = cand_embeds.T  # dim x n
    dots = np.matmul(ref_embed, mat_embed).ravel()
    return list(np.argsort(dots))[::-1]


def dot_order(
        embed: list[float],
        sembeds: list[tuple[tuple[int, str], list[float]]],
        hit_limit: int) -> dict[int, list[str]]:
    mat_ref = np.array([embed])  # 1 x len(embed)

    def dot_hit(group: list[tuple[str, list[float]]]) -> list[str]:
        cand_embeds = np.array([
            sembed
            for (_, sembed) in group
        ])  # len(group) x len(embed)
        ixs = dot_order_np(mat_ref, cand_embeds)
        return [group[ix][0] for ix in ixs[:hit_limit]]

    lookup: dict[int, list[tuple[str, list[float]]]] = {}
    for ((pos, txt), cur_embed) in sembeds:
        cur: list[tuple[str, list[float]]] | None = lookup.get(pos)
        if cur is None:
            cur = []
            lookup[pos] = cur
        cur.append((txt, cur_embed))
    return {
        pos: dot_hit(cur_group)
        for (pos, cur_group) in lookup.items()
    }
