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
"""Utilities for tests."""
import collections
import os
import re
from xml.etree import ElementTree as ET

import pandas as pd
import pandas.testing as pd_test


XML_FILE_PATTERN = re.compile(r".*\.xml")
TEST_FILE_PATTERN = re.compile(r"^test_.*\.py$")
DEFAULT_TEST_DURATION = 10.0


def listdir(path: str) -> list[str]:
    """
    List the content of a folder. This function exists to avoid dependencies
    to other parts of the codebase.

    Args:
        path (str): The folder.

    Returns:
        list[str]: The files and folders inside the given folder.
    """
    return sorted(os.listdir(path))


def check_equal(a: pd.DataFrame, b: pd.DataFrame) -> None:
    """
    Check whether two dataframes are essentially the same.

    Args:
        a (pd.DataFrame): One dataframe.
        b (pd.DataFrame): The other dataframe.
    """
    pd_test.assert_frame_equal(a[sorted(a.columns)], b[sorted(b.columns)])


def find_tests(folder: str) -> collections.abc.Iterable[str]:
    """
    Find test files in the given folder.

    Args:
        folder (str): The folder.

    Yields:
        str: The full path to the test file.
    """
    for item in listdir(folder):
        if not os.path.isdir(item) and TEST_FILE_PATTERN.match(item):
            yield os.path.join(folder, item)


def merge_results(base_folder: str, out_filename: str) -> None:
    """
    Merges results found in the `parts` subdirectory of the base folder.
    Writes the merged test results to the out file.

    Args:
        base_folder (str): The base folder.
        out_filename (str): The out file.
    """
    xml_files = listdir(os.path.join(base_folder, "parts"))

    testsuites = ET.Element("testsuites")
    combined = ET.SubElement(testsuites, "testsuite")
    failures = 0
    skipped = 0
    tests = 0
    errors = 0
    time = 0.0
    for file_name in xml_files:
        if XML_FILE_PATTERN.match(file_name):
            tree = ET.parse(os.path.join(base_folder, "parts", file_name))
            test_suite = tree.getroot()[0]

            combined.attrib["name"] = test_suite.attrib["name"]
            combined.attrib["timestamp"] = test_suite.attrib["timestamp"]
            combined.attrib["hostname"] = test_suite.attrib["hostname"]
            failures += int(test_suite.attrib["failures"])
            skipped += int(test_suite.attrib["skipped"])
            tests += int(test_suite.attrib["tests"])
            errors += int(test_suite.attrib["errors"])
            for testcase in test_suite:
                time += float(testcase.attrib["time"])
                ET.SubElement(combined, testcase.tag, testcase.attrib)

    combined.attrib["failures"] = f"{failures}"
    combined.attrib["skipped"] = f"{skipped}"
    combined.attrib["tests"] = f"{tests}"
    combined.attrib["errors"] = f"{errors}"
    combined.attrib["time"] = f"{time}"

    new_tree = ET.ElementTree(testsuites)
    new_tree.write(
        os.path.join(base_folder, out_filename),
        xml_declaration=True,
        encoding="utf-8")


def split_tests(filepath: str, total_nodes: int, cur_node: int) -> None:
    """
    Splits tests equally among available worker nodes.

    Args:
        filepath (str): The path to previous test results for timing
            information.
        total_nodes (int): The total amount of worker nodes.
        cur_node (int): The identity of the current worker node.
    """
    _, fname = os.path.split(filepath)
    base = "test"
    if XML_FILE_PATTERN.match(fname):
        test_files = sorted(find_tests(base))
        try:
            tree = ET.parse(filepath)
            already: set[str] = set()
            test_time_map: dict[str, float] = collections.defaultdict(float)
            for testcases in tree.getroot()[0]:
                cur_key = \
                    f"testcases.attrib['file']#{testcases.attrib['name']}"
                if cur_key in already:
                    continue
                fname = os.path.normpath(testcases.attrib["file"])
                test_time_map[fname] += float(testcases.attrib["time"])
                already.add(cur_key)

            for file in test_files:
                fname = os.path.normpath(file)
                if fname not in test_time_map:
                    test_time_map[fname] = DEFAULT_TEST_DURATION

            time_keys: list[tuple[str, float]] = sorted(
                test_time_map.items(),
                key=lambda el: (el[1], el[0]),
                reverse=True)
        except FileNotFoundError:
            time_keys = [
                (os.path.normpath(file), DEFAULT_TEST_DURATION)
                for file in test_files
            ]

        def find_lowest_total_time(
                test_sets: list[tuple[list[str], float]]) -> int:
            minimum = None
            ret = -1
            for ix, val in enumerate(test_sets):
                if minimum is None or val[1] < minimum:
                    minimum = val[1]
                    ret = ix
            return ret

        test_sets: list[tuple[list[str], float]] = [
            ([], 0.0) for _ in range(total_nodes)]
        for key, timing in time_keys:
            ix = find_lowest_total_time(test_sets)
            lowest_list, lowest_time = test_sets[ix]
            test_sets[ix] = (lowest_list + [key], lowest_time + timing)
        print(f"{test_sets[cur_node][1]},{','.join(test_sets[cur_node][0])}")
    else:
        raise TypeError(f"File {fname} is not a valid xml file.")
