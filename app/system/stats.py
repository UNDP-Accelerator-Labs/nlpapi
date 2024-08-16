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
"""Compute usage statistics of certain NLP APIs."""
from collections.abc import Callable


LengthCounter = Callable[[str], str]
"""Adds the length of the text to the length counter. Returns the text."""
LengthResult = Callable[[], int]
"""Returns the current total of the length counter."""


def create_length_counter() -> tuple[LengthCounter, LengthResult]:
    """
    Creates a length counter pair.

    Returns:
        tuple[LengthCounter, LengthResult]: The counter to count processing
            amount and a function to retrieve the result.
    """
    total = 0

    def length_counter(text: str) -> str:
        nonlocal total

        total += len(text)
        return text

    def length_result() -> int:
        return total

    return length_counter, length_result
