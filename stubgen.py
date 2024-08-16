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
"""Helper to create type stubs."""
import sys
from typing import IO


def process(fin: IO[str], fout: IO[str]) -> None:
    """
    Process a file.

    Args:
        fin (IO[str]): The input file handle.
        fout (IO[str]): The output file handle.
    """
    gap = 0
    max_len = 79
    prev_is_symbol = False
    add_indent = " " * 4
    buff = ""
    pretext_buff = ""

    def write_pretext(text: str) -> None:
        nonlocal pretext_buff

        pretext_buff = f"{pretext_buff}{text}"

    def write_line(text: str) -> None:
        nonlocal buff
        nonlocal gap
        nonlocal pretext_buff

        if not text.strip():
            if gap < 2:
                buff = f"{buff}{text}"
                gap += 1
            return
        if buff:
            fout.write(buff)
            buff = ""
        if pretext_buff:
            fout.write(pretext_buff)
            pretext_buff = ""
        fout.write(text)
        fout.flush()
        gap = 0

    start = True
    for line in fin:
        if not line.strip():
            write_line(line)
            continue

        if start and line.startswith("# pylint: disable"):
            continue
        start = False

        if line.lstrip().startswith("@"):
            write_pretext(line)
            continue

        is_indent = line.startswith(" ")
        is_def = line.lstrip().startswith("def ")
        is_class_def = is_def and not line.startswith("def ")
        is_class = line.startswith("class ")
        is_dddot = line.rstrip().endswith("...")
        is_need_gap = not (is_class or is_def) and not prev_is_symbol
        prev_is_symbol = not is_class and not is_def and not is_class_def
        if is_indent:
            cur_indent = line[:line.index(line.lstrip()[0])]
        else:
            cur_indent = ""
        if not is_indent:
            if is_class or is_def or is_need_gap:
                write_line("\n")
                write_line("\n")

        if is_class and is_dddot:
            class_def = line.rstrip().rstrip(". ")
            if len(class_def) > max_len:
                raise ValueError(f"class def longer than line! {class_def}")
            write_line(f"{class_def}\n{add_indent}...\n")
            continue

        outline = line.rstrip()
        if len(outline) <= max_len:
            write_line(line)
            continue

        if is_class_def and gap < 1:
            write_line("\n")

        def count_paren(text: str) -> int:
            count = 0
            for char in text:
                if char == "(":
                    count += 1
                elif char == ")":
                    count -= 1
                elif char == "[":
                    count += 2
                elif char == "]":
                    count -= 2
            return count

        first_paren = outline.find("(") + 1
        need_extra = 0 if cur_indent else 1
        paren_count = 0
        if first_paren > 0:
            paren_count += count_paren(outline[:first_paren])
            write_line(f"{outline[:first_paren]}\n")
            outline = f"{cur_indent}{add_indent}{outline[first_paren:]}"
        after_type = False
        while len(outline) > max_len or not outline.strip():
            end_ix = max_len - 2
            if outline.find("->", 0, end_ix) >= 0:
                after_type = True
            for bpoint in ("[(,: " if after_type else ",:[( "):
                ws_add = 0 if bpoint == " " else 1
                right_cutoff = (
                    outline.find(bpoint, 0, end_ix)
                    if bpoint in ["[("]
                    else outline.rfind(bpoint, 0, end_ix)) + ws_add
                if right_cutoff >= ws_add:
                    break
                if bpoint == " ":
                    raise ValueError(
                        "could not find any way to shorten line: "
                        f"{outline}")
            paren_count += count_paren(outline[:right_cutoff])
            if paren_count == 0:
                bslash = " \\"
            else:
                bslash = ""
            paren_extra = 0 if first_paren > 0 else need_extra
            if is_class:
                paren_extra += 1
            extra_indent = add_indent * (paren_count + paren_extra)
            write_line(f"{outline[:right_cutoff].rstrip()}{bslash}\n")
            outline = \
                f"{cur_indent}{extra_indent}{outline[right_cutoff:].lstrip()}"
        if outline.strip():
            write_line(f"{outline}\n")

        if is_class_def:
            write_line("\n")

    buff = buff.strip()
    if buff:
        fout.write(f"{buff}\n")
        fout.flush()


def run(fname_in: str, fname_out: str) -> None:
    """
    Process files.

    Args:
        fname_in (str): The input file.
        fname_out (str): The output file.
    """
    with open(fname_in, "r", encoding="utf-8") as fin:
        with open(fname_out, "a", encoding="utf-8") as fout:
            process(fin, fout)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise ValueError("must be called from stubgen.sh")
    run(sys.argv[1], sys.argv[2])
