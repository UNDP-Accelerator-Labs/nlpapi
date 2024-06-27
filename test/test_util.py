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
from typing import Any

from app.misc.util import escape, retain_some, unescape


def test_retain_some() -> None:

    def test_rs(
            input_arr: list[int],
            count: int,
            output_arr: list[int],
            delete_arr: set[int],
            **kwargs: Any) -> None:
        res, to_delete = retain_some(
            input_arr, count, key=lambda v: v, **kwargs)
        assert res == output_arr
        assert set(to_delete) == delete_arr

    test_rs(
        [5, 3, 2, 1, 9, 3, 0, 6],
        4,
        [3, 3, 5, 6, 9],
        {0, 1, 2})
    test_rs(
        [5, 3, 2, 1, 9, 3, 0, 6],
        4,
        [3, 5, 6, 9],
        {0, 1, 2, 3},
        keep_last=False)
    test_rs(
        [5, 3, 2, 1, 9, 3, 0, 6],
        4,
        [6, 3, 2, 1, 0],
        {3, 5, 9},
        reverse=True)
    test_rs(
        [5, 3, 2, 1, 9, 3, 0, 6],
        4,
        [3, 2, 1, 0],
        {3, 5, 6, 9},
        reverse=True,
        keep_last=False)
    test_rs(
        [5, 3, 2, 1, 9, 3, 0, 6],
        5,
        [2, 3, 3, 5, 6, 9],
        {0, 1})
    test_rs(
        [5, 3, 2, 1, 9, 3, 0, 6],
        5,
        [3, 3, 5, 6, 9],
        {0, 1, 2},
        keep_last=False)
    test_rs(
        [5, 3, 2, 1, 9, 3, 0, 6],
        5,
        [6, 3, 3, 2, 1, 0],
        {5, 9},
        reverse=True)
    test_rs(
        [5, 3, 2, 1, 9, 3, 0, 6],
        5,
        [3, 3, 2, 1, 0],
        {5, 6, 9},
        reverse=True,
        keep_last=False)
    test_rs(
        [5, 3, 2, 1, 9, 3],
        5,
        [1, 2, 3, 3, 5, 9],
        set())
    test_rs(
        [5, 3, 2, 1, 9, 3],
        6,
        [1, 2, 3, 3, 5, 9],
        set(),
        keep_last=False)
    test_rs(
        [5, 3, 2],
        6,
        [2, 3, 5],
        set())
    test_rs(
        [5, 3, 2],
        6,
        [2, 3, 5],
        set(),
        keep_last=False)


def test_escape() -> None:

    def test(text: str, subs: dict[str, str]) -> None:
        rsubs = {
            repl: key
            for key, repl in subs.items()
        }
        assert text == unescape(escape(text, subs), rsubs)

    test("abc", {"\n": "n"})
    test("abc\0\n", {"\n": "n"})
    test("\\n\n", {"\n": "n"})
    test("\\n0\\0\0\n", {"\n": "n"})

    test("abc", {"\0": "0"})
    test("abc\0\n", {"\0": "0"})
    test("\\n\n", {"\0": "0"})
    test("\\n0\\0\0\n", {"\0": "0"})

    test("abc", {"\n": "n", "\0": "0"})
    test("abc\0\n", {"\n": "n", "\0": "0"})
    test("\\n\n", {"\n": "n", "\0": "0"})
    test("\\n0\\0\0\n", {"\n": "n", "\0": "0"})
