from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Iterable, Sequence


DATA_PATH = Path(__file__).resolve().parent / "data" / "liangyu_phrases.json"
SEPARATOR_RE = re.compile(r"[\s·•･・.。,_，、\-_/\\|]+")


@dataclass(frozen=True)
class LiangYuEntry:
    abbr: str
    text: str
    key: str


@dataclass(frozen=True)
class LiangYuMatch:
    abbr: str
    text: str


def normalize_key(value: str) -> str:
    """Collapse common separators so users can type 良语 with or without dots."""
    return SEPARATOR_RE.sub("", value or "").strip()


class LiangYuDictionary:
    def __init__(self, entries: Iterable[dict[str, str]]):
        parsed: list[LiangYuEntry] = []
        for item in entries:
            abbr = str(item.get("abbr", "")).strip()
            text = str(item.get("text", "")).strip()
            key = normalize_key(abbr)
            if abbr and text and key:
                parsed.append(LiangYuEntry(abbr=abbr, text=text, key=key))

        self.entries: tuple[LiangYuEntry, ...] = tuple(parsed)
        self._by_key = {entry.key: entry for entry in self.entries}
        self._by_abbr = {entry.abbr: entry for entry in self.entries}

    @classmethod
    def from_json(cls, path: str | Path = DATA_PATH) -> "LiangYuDictionary":
        with Path(path).open("r", encoding="utf-8") as fp:
            return cls(json.load(fp))

    def lookup(self, query: str) -> LiangYuEntry | None:
        query = (query or "").strip()
        if not query:
            return None
        return self._by_abbr.get(query) or self._by_key.get(normalize_key(query))

    def find_matches(
        self,
        message: str,
        *,
        max_matches: int = 5,
        min_unseparated_match_len: int = 3,
    ) -> list[LiangYuMatch]:
        message = message or ""
        compact_message = normalize_key(message)
        matches: list[LiangYuMatch] = []
        seen: set[str] = set()

        for entry in self.entries:
            if entry.key in seen:
                continue

            raw_hit = entry.abbr in message
            compact_exact = compact_message == entry.key
            compact_hit = (
                len(entry.key) >= min_unseparated_match_len
                and entry.key in compact_message
            )

            if raw_hit or compact_exact or compact_hit:
                matches.append(LiangYuMatch(abbr=entry.abbr, text=entry.text))
                seen.add(entry.key)
                if len(matches) >= max_matches:
                    break

        return matches


def format_matches(
    matches: Sequence[LiangYuMatch],
    *,
    title: str = "良语翻译",
    item_format: str = "{abbr}：{text}",
) -> str:
    lines = [title]
    for match in matches:
        try:
            lines.append(item_format.format(abbr=match.abbr, text=match.text))
        except (KeyError, IndexError, ValueError):
            lines.append(f"{match.abbr}：{match.text}")
    return "\n".join(lines)
