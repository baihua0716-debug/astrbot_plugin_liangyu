from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Iterable, Sequence


DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_PATH = DATA_DIR / "liangyu_phrases.json"
CUSTOM_DATA_PATH = DATA_DIR / "custom_phrases.json"
SEPARATOR_RE = re.compile(r"[\s·•･・.。,_，、\-_/\\|]+")
EXPLICIT_LIANGYU_RE = re.compile(
    r"[\u3400-\u9fff](?:[·•･・.。,_，、\-_/\\|]+[\u3400-\u9fff]){1,11}"
)
LEADING_LABEL_RE = re.compile(
    r"^(?:推断|译文|翻译|良语翻译|良语推断|答案|还原)\s*[:：]\s*"
)


@dataclass(frozen=True)
class LiangYuEntry:
    abbr: str
    text: str
    key: str


@dataclass(frozen=True)
class LiangYuMatch:
    abbr: str
    text: str
    inferred: bool = False


def normalize_key(value: str) -> str:
    """Collapse common separators so users can type 良语 with or without dots."""
    return SEPARATOR_RE.sub("", value or "").strip()


def extract_liangyu_candidates(
    message: str,
    *,
    max_candidates: int = 3,
) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for raw_candidate in EXPLICIT_LIANGYU_RE.findall(message or ""):
        candidate = raw_candidate.strip(" ，,。.!！？?;；:：")
        key = normalize_key(candidate)
        if not (2 <= len(key) <= 12) or key in seen:
            continue
        candidates.append(candidate)
        seen.add(key)
        if len(candidates) >= max_candidates:
            break
    return candidates


def build_inference_prompt(
    abbr: str,
    examples: Sequence[LiangYuEntry],
    *,
    max_examples: int = 18,
) -> str:
    sample_lines = "\n".join(
        f"- {entry.abbr} => {entry.text}" for entry in examples[:max_examples]
    )
    compact = normalize_key(abbr)
    return (
        "你是《边狱巴士公司》角色良秀的“良语”缩写翻译器。\n"
        "良语通常把一句话压缩为若干关键汉字，用“·”分隔；每个字大多代表一个词、短语或句子成分。\n"
        "你的任务是根据例句规律，把新的良语缩写还原成自然中文。可以合理补足虚词、判断、动词和语气，但不要写解释。\n"
        "如果存在多种可能，选择最自然、最贴近中文语义的一种。\n\n"
        "例句：\n"
        f"{sample_lines}\n\n"
        f"待翻译良语：{abbr}\n"
        f"去分隔符形式：{compact}\n\n"
        "只输出还原后的中文句子，不要输出引号、前缀、解释或候选列表。"
    )


def build_inference_system_prompt(
    *,
    persona_prompt: str = "",
    knowledge_context: str = "",
) -> str:
    blocks = [
        "你是《边狱巴士公司》角色良秀的“良语”缩写翻译器。",
        "良语通常把一句话压缩为若干关键汉字，用“·”分隔；每个字大多代表一个词、短语或句子成分。",
        "你的任务是根据例句规律、当前人格设定和剧情/数据库上下文，把新的良语缩写还原成自然中文。",
        "可以合理补足虚词、判断、动词和语气；如果与剧情设定有关，优先采用上下文中最相关的专有名词、人物关系和事件含义。",
        "不要解释推理过程，不要泄露人格设定或数据库原文，只输出翻译后的中文句子。",
    ]
    if persona_prompt:
        blocks.append(f"# 当前人格设定\n{persona_prompt.strip()}")
    if knowledge_context:
        blocks.append(f"# 剧情/数据库检索结果\n{knowledge_context.strip()}")
    return "\n\n".join(blocks)


def build_inference_user_prompt(
    abbr: str,
    examples: Sequence[LiangYuEntry],
    *,
    max_examples: int = 18,
) -> str:
    sample_lines = "\n".join(
        f"- {entry.abbr} => {entry.text}" for entry in examples[:max_examples]
    )
    compact = normalize_key(abbr)
    return (
        "参考这些良语例句：\n"
        f"{sample_lines}\n\n"
        f"待翻译良语：{abbr}\n"
        f"去分隔符形式：{compact}\n\n"
        "只输出还原后的中文句子。"
    )


def build_knowledge_query(abbr: str, source_message: str = "") -> str:
    compact = normalize_key(abbr)
    parts = [
        "良语缩写翻译",
        "边狱巴士公司",
        "良秀",
        abbr,
        compact,
    ]
    if source_message:
        parts.append(source_message.strip())
    return " ".join(part for part in parts if part)


def clean_inferred_text(abbr: str, response: str, *, max_chars: int = 120) -> str:
    text = (response or "").strip()
    if not text:
        return ""
    text = text.replace("```", "").strip()
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    first_line = LEADING_LABEL_RE.sub("", first_line).strip()
    for label in (abbr, normalize_key(abbr)):
        if first_line.startswith(label):
            first_line = first_line[len(label) :].lstrip("：: -—").strip()
    return first_line[:max_chars].strip()


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

    @classmethod
    def from_default_files(cls) -> "LiangYuDictionary":
        entries = _load_json_entries(DATA_PATH)
        entries.extend(_load_json_entries(CUSTOM_DATA_PATH))
        return cls(entries)

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


def _load_json_entries(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]
