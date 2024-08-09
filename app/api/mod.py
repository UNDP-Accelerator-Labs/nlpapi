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
"""Modules can be used through a unified api endpoint to compute multiple
metrics for a given input string."""
import uuid
from collections.abc import Mapping
from typing import Any


class Module:
    """
    A module defines a metric for input strings. It can be accessed via the
    `/api/extract` endpoint when it is registered in `server.py`.
    """
    @staticmethod
    def name() -> str:
        """
        The name of the module.

        Returns:
            str: The name of the module. This is a parameter to the
                `/api/extract` endpoint.
        """
        raise NotImplementedError()

    def execute(
            self,
            input_str: str,
            user: uuid.UUID,
            args: dict[str, Any]) -> Mapping[str, Any]:
        """
        Executes the module and returns a dictionary with its results.

        Args:
            input_str (str): The input string.
            user (uuid.UUID): The user that initiated the request.
            args (dict[str, Any]): Arguments to the module.

        Returns:
            Mapping[str, Any]: The results.
        """
        raise NotImplementedError()
