"""
Word-level diff utility for Writing Tools Response Window (Issues #284, #25, #206).

Uses Python's standard library `difflib.SequenceMatcher` (zero external dependencies)
with adjacent whitespace-separated edit merging so rephrased phrases render as one
clean removed block followed by one clean added block.
"""

from __future__ import annotations

import difflib
import html
import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"\r?\n|[ \t]+|[^\s\w]+|\w+", re.UNICODE)


@dataclass(frozen=True)
class DiffResult:
    html: str
    deletions: int
    insertions: int
    has_changes: bool


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text or "")


def _is_horizontal_space_only(tokens: list[str]) -> bool:
    return bool(tokens) and all(t.strip(" \t") == "" and "\n" not in t and "\r" not in t for t in tokens)


def _merge_adjacent_opcodes(
    opcodes: list[tuple[str, int, int, int, int]],
    orig_tokens: list[str],
    new_tokens: list[str],
) -> list[tuple[str, int, int, int, int]]:
    """
    Merge consecutive non-equal opcodes separated only by horizontal spaces so
    multi-word rewrites read cleanly as one removed phrase + one added phrase.
    """
    if not opcodes:
        return []

    merged: list[tuple[str, int, int, int, int]] = []
    i = 0
    n = len(opcodes)
    while i < n:
        tag, i1, i2, j1, j2 = opcodes[i]
        if tag == "equal":
            merged.append((tag, i1, i2, j1, j2))
            i += 1
            continue

        # Start accumulating a changed region
        cur_i1, cur_i2, cur_j1, cur_j2 = i1, i2, j1, j2
        i += 1
        while i < n:
            next_tag, ni1, ni2, nj1, nj2 = opcodes[i]
            if next_tag != "equal":
                cur_i2 = ni2
                cur_j2 = nj2
                i += 1
                continue
            # Peek ahead: if this equal span is only spaces and another edit follows, absorb it
            if (
                i + 1 < n
                and opcodes[i + 1][0] != "equal"
                and _is_horizontal_space_only(orig_tokens[ni1:ni2])
                and _is_horizontal_space_only(new_tokens[nj1:nj2])
            ):
                cur_i2 = opcodes[i + 1][2]
                cur_j2 = opcodes[i + 1][4]
                i += 2
                continue
            break

        if cur_i1 == cur_i2:
            merged_tag = "insert"
        elif cur_j1 == cur_j2:
            merged_tag = "delete"
        else:
            merged_tag = "replace"
        merged.append((merged_tag, cur_i1, cur_i2, cur_j1, cur_j2))

    return merged


def _format_plain_html(text: str) -> str:
    return html.escape(text).replace("\r\n", "\n").replace("\n", "<br>")


def build_word_diff(original: str, revised: str, color_mode: str = "light") -> DiffResult:
    """
    Build a theme-aware HTML word-level diff between `original` and `revised`.
    """
    orig_tokens = _tokenize(original)
    new_tokens = _tokenize(revised)

    matcher = difflib.SequenceMatcher(None, orig_tokens, new_tokens, autojunk=False)
    opcodes = _merge_adjacent_opcodes(matcher.get_opcodes(), orig_tokens, new_tokens)

    if color_mode == "dark":
        del_style = "background-color:#4c1d1d;color:#fca5a5;text-decoration:line-through;padding:1px 2px;border-radius:3px;"
        ins_style = "background-color:#14532d;color:#86efac;padding:1px 2px;border-radius:3px;"
        meta_color = "#aaaaaa"
    else:
        del_style = "background-color:#fee2e2;color:#b91c1c;text-decoration:line-through;padding:1px 2px;border-radius:3px;"
        ins_style = "background-color:#dcfce7;color:#166534;padding:1px 2px;border-radius:3px;"
        meta_color = "#555555"

    parts: list[str] = []
    deletions = 0
    insertions = 0

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            parts.append(_format_plain_html("".join(orig_tokens[i1:i2])))
        elif tag == "delete":
            removed = "".join(orig_tokens[i1:i2])
            deletions += sum(1 for t in orig_tokens[i1:i2] if t.strip())
            parts.append(f'<span style="{del_style}">{_format_plain_html(removed)}</span>')
        elif tag == "insert":
            added = "".join(new_tokens[j1:j2])
            insertions += sum(1 for t in new_tokens[j1:j2] if t.strip())
            parts.append(f'<span style="{ins_style}">{_format_plain_html(added)}</span>')
        elif tag == "replace":
            removed = "".join(orig_tokens[i1:i2])
            added = "".join(new_tokens[j1:j2])
            deletions += sum(1 for t in orig_tokens[i1:i2] if t.strip())
            insertions += sum(1 for t in new_tokens[j1:j2] if t.strip())
            parts.append(f'<span style="{del_style}">{_format_plain_html(removed)}</span>')
            parts.append(" ")
            parts.append(f'<span style="{ins_style}">{_format_plain_html(added)}</span>')

    has_changes = deletions > 0 or insertions > 0
    if not has_changes:
        summary = "No changes detected."
    else:
        summary = f"Word diff: -{deletions} removed, +{insertions} added"

    header_html = (
        f'<div style="font-size:12px;color:{meta_color};margin-bottom:8px;">'
        f"{html.escape(summary)}</div>"
    )
    body_html = f'<div style="white-space:normal;line-height:1.45;">{"".join(parts)}</div>'
    return DiffResult(
        html=header_html + body_html,
        deletions=deletions,
        insertions=insertions,
        has_changes=has_changes,
    )
