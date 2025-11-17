#!/usr/bin/env python3
"""
check_names.py

Checks the "names" section of a JSON-like file for:
 - JSON parse errors (often caused by missing commas)
 - Missing commas between array entries (line-based heuristic)
 - Duplicate letters used inside parentheses (e.g. "(D)ennis" -> "d")
 - Duplicate numbers used inside parentheses (e.g. "(1) Dennis")
 - Reports entries with no parenthesized token

Usage:
    python check_names.py path/to/file.json
or
    cat file.json | python check_names.py -

Exit codes:
  0 - OK (no problems found)
  1 - Problems found (duplicates, missing paren tokens, or comma heuristics)
  2 - Fatal (cannot locate "names" array or other unrecoverable error)
"""

from __future__ import annotations
import argparse
import json
import sys
import re
from collections import defaultdict
from typing import List, Tuple, Optional


def load_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def try_parse_json(text: str) -> Tuple[Optional[dict], Optional[str]]:
    try:
        obj = json.loads(text)
        return obj, None
    except json.JSONDecodeError as e:
        return None, str(e)


def find_bracket_block(text: str, key: str) -> Optional[Tuple[int, int, str]]:
    m = re.search(r'"' + re.escape(key) + r'"\s*:\s*\[', text)
    if not m:
        return None
    start = text.find('[', m.end() - 1)
    if start == -1:
        return None
    i = start
    depth = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    return start, end, text[start:end]
        i += 1
    return None


def extract_array_string_entries(block_text: str) -> List[Tuple[str, int, int, str]]:
    entries = []
    pattern = re.compile(r'"((?:\\.|[^"\\])*)"', re.DOTALL)
    for m in pattern.finditer(block_text):
        s = m.group(1)
        after_start = m.end()
        nl = block_text.find('\n', after_start)
        if nl == -1:
            nl = len(block_text)
        trailing = block_text[after_start:nl]
        entries.append((s, m.start(), m.end(), trailing))
    return entries


def check_missing_commas_in_block(block_text: str) -> List[Tuple[int, str]]:
    lines = block_text.splitlines()
    suspects = []
    entry_line_indices = []
    for idx, line in enumerate(lines):
        if '"' in line:
            # crude filter: ignore lines that look like object key lines (":")
            if re.search(r'"\s*:', line):
                continue
            # if the line contains a quoted string literal, consider it an entry line
            if re.search(r'"((?:\\.|[^"\\])*)"', line):
                entry_line_indices.append(idx)
    for i, idx in enumerate(entry_line_indices):
        if i == len(entry_line_indices) - 1:
            # last entry: should not have trailing comma
            line = lines[idx]
            last_quote = line.rfind('"')
            after = line[last_quote + 1:].strip()
            if after.startswith(','):
                suspects.append((idx + 1, line))
            continue
        line = lines[idx]
        last_quote = line.rfind('"')
        after = line[last_quote + 1:].strip()
        if not after.startswith(','):
            suspects.append((idx + 1, line))
    return suspects


def analyze_parsed_names(names: List[str]) -> Tuple[dict, dict, List[int]]:
    """
    Extract parenthesized tokens and classify them:
      - numeric tokens (all digits) -> number_map
      - letter tokens: extract the first alphabetical character (case-insensitive) -> letter_map
      - if no parenthesized token found -> no_paren list

    Returns (letter_map, number_map, no_paren_indices)
    where letter_map: key->list of indices, number_map: key->list of indices
    """
    letter_map = defaultdict(list)
    number_map = defaultdict(list)
    no_paren = []
    paren_pattern = re.compile(r'\(([^)]*)\)')
    for idx, entry in enumerate(names):
        if not isinstance(entry, str):
            no_paren.append(idx)
            continue
        m = paren_pattern.search(entry)
        if not m:
            no_paren.append(idx)
            continue
        token = m.group(1).strip()
        if token == "":
            no_paren.append(idx)
            continue
        # numeric tokens
        if token.isdigit():
            number_map[token].append(idx)
            continue
        # find first alphabetical character in token to use as the "initial"
        alpha_m = re.search(r'[A-Za-z]', token)
        if alpha_m:
            key = alpha_m.group(0).lower()
            letter_map[key].append(idx)
        else:
            # token is non-empty but has no alphas and is not pure digits -> store as "other"
            # treat as letter-like key using the whole token lowercased
            letter_map[token.lower()].append(idx)
    return letter_map, number_map, no_paren


def format_entries_for_report(names: List[str], indices: List[int]) -> List[str]:
    return [f"{i+1}: {names[i]!r}" for i in indices]


def report_from_parsed(names: List[str]) -> int:
    """
    Analyze parsed names list and print reports. Returns non-zero if issues found.
    """
    letter_map, number_map, no_paren = analyze_parsed_names(names)
    dup_letters = {k: v for k, v in letter_map.items() if len(v) > 1}
    dup_numbers = {k: v for k, v in number_map.items() if len(v) > 1}

    problems_found = 0

    print(f"Found {len(names)} entries in 'names' array.\n")

    if dup_letters:
        problems_found += 1
        print("Duplicate letter tokens (case-insensitive) detected:")
        for k, idxs in sorted(dup_letters.items()):
            print(f"  '{k}' used {len(idxs)} time(s):")
            for t in format_entries_for_report(names, idxs):
                print(f"    {t}")
        print()
    else:
        print("No duplicate letter tokens detected.\n")

    if dup_numbers:
        problems_found += 1
        print("Duplicate numeric tokens detected:")
        for k, idxs in sorted(dup_numbers.items(), key=lambda kv: kv[0]):
            print(f"  '{k}' used {len(idxs)} time(s):")
            for t in format_entries_for_report(names, idxs):
                print(f"    {t}")
        print()
    else:
        print("No duplicate numeric tokens detected.\n")

    if no_paren:
        problems_found += 1
        print("Entries with no parenthesized token (these may be missing initials/markers):")
        for i in no_paren:
            print(f"  {i+1}: {names[i]!r}")
        print()
    else:
        print("All entries contain a parenthesized token.\n")

    return 1 if problems_found else 0


def main():
    parser = argparse.ArgumentParser(description="Check the 'names' section for commas and duplicate initials/numbers.")
    parser.add_argument("file", help="JSON file to check, or - to read stdin")
    args = parser.parse_args()

    text = load_text(args.file)
    parsed, err = try_parse_json(text)
    if parsed is None:
        print("JSON parse error:")
        print(err)
        print("\nAttempting heuristic analysis on the raw text...\n")

        block = find_bracket_block(text, "names")
        if not block:
            print("Couldn't locate a 'names' array in the file. Make sure the key is spelled exactly \"names\".")
            sys.exit(2)
        start, end, block_text = block
        print(f"'names' array located at text indices {start}:{end}. Inspecting block lines for missing/extra commas...\n")

        suspects = check_missing_commas_in_block(block_text)
        if suspects:
            print("Suspect lines (line numbers are relative to the 'names' block):")
            for ln, line in suspects:
                print(f"  line {ln}: {line.rstrip()!s}")
            print("\nNotes:")
            print(" - Lines that contain a string entry but do not end with a comma (except the last entry) are flagged.")
            print(" - The last entry in the array should NOT have a trailing comma; if it does, it's flagged.")
            print()
        else:
            print("No obvious missing/extra-commas found by the line heuristic.\n")

        raw_entries = extract_array_string_entries(block_text)
        names_list = [e[0] for e in raw_entries]
        if not names_list:
            print("No string entries were found inside the names block (heuristic).")
            sys.exit(2)
        print(f"Found {len(names_list)} string entries inside the 'names' block (heuristic). Checking duplicates...\n")
        status = report_from_parsed(names_list)
        if status:
            print("Problems found by heuristic analysis. Fix the flagged entries and re-run.")
            sys.exit(1)
        else:
            print("No duplicate letters/numbers detected by heuristic analysis.")
            sys.exit(0)

    # JSON parsed successfully
    if "names" not in parsed:
        print("The JSON parsed successfully but does not contain a top-level 'names' key.")
        sys.exit(2)

    names = parsed["names"]
    if not isinstance(names, list):
        print("The 'names' key exists but is not an array.")
        sys.exit(2)

    status = report_from_parsed(names)

    # Also run the line-based comma/style heuristic on the raw block (useful for trailing commas)
    block = find_bracket_block(text, "names")
    if block:
        _, _, block_text = block
        suspects = check_missing_commas_in_block(block_text)
        if suspects:
            print("Line-based comma/style issues found in the 'names' block (line numbers relative to block):")
            for ln, line in suspects:
                print(f"  line {ln}: {line.rstrip()!s}")
            print("Note: When JSON parsed successfully, these are usually style issues (like an unexpected trailing comma).")
            status = 1 if status == 0 else status
        else:
            print("No line-based comma/style issues detected in the raw 'names' block.")

    if status:
        print("\nDone — problems were detected.")
        sys.exit(1)
    else:
        print("\nDone — no problems detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
