from __future__ import annotations

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    from .liangyu import LiangYuDictionary, format_matches
except ImportError:
    from liangyu import LiangYuDictionary, format_matches


DEFAULT_CONFIG = {
    "enabled": True,
    "max_matches_per_message": 5,
    "min_unseparated_match_len": 3,
    "ignore_command_messages": True,
    "reply_title": "良语翻译",
    "item_format": "{abbr}：{text}",
    "stop_event_after_reply": True,
}

COMMAND_PREFIXES = ("/", "!", "！", "／")


def config_value(config: AstrBotConfig | None, key: str):
    if config is None:
        return DEFAULT_CONFIG[key]
    try:
        return config.get(key, DEFAULT_CONFIG[key])
    except AttributeError:
        return DEFAULT_CONFIG[key]


def int_config_value(config: AstrBotConfig | None, key: str) -> int:
    try:
        return int(config_value(config, key))
    except (TypeError, ValueError):
        return int(DEFAULT_CONFIG[key])


@register("astrbot_plugin_liangyu", "Codex", "翻译群消息中的良语缩写", "v0.1.0")
class LiangYuTranslatorPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config
        self.dictionary = LiangYuDictionary.from_json()

    async def initialize(self):
        logger.info("良语翻译插件已加载 %s 条词条。", len(self.dictionary.entries))

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def translate_group_message(self, event: AstrMessageEvent):
        """自动翻译群消息中出现的良语缩写。"""
        if not config_value(self.config, "enabled"):
            return

        message = (event.message_str or "").strip()
        if not message:
            return
        if config_value(self.config, "ignore_command_messages") and message.startswith(
            COMMAND_PREFIXES
        ):
            return

        matches = self.dictionary.find_matches(
            message,
            max_matches=max(1, int_config_value(self.config, "max_matches_per_message")),
            min_unseparated_match_len=max(
                1, int_config_value(self.config, "min_unseparated_match_len")
            ),
        )
        if not matches:
            return

        if config_value(self.config, "stop_event_after_reply"):
            event.stop_event()
        yield event.plain_result(
            format_matches(
                matches,
                title=str(config_value(self.config, "reply_title")),
                item_format=str(config_value(self.config, "item_format")),
            )
        )

    @filter.command("良语")
    async def query_liangyu(self, event: AstrMessageEvent):
        """查询一个良语缩写的完整文本。"""
        query = self._extract_command_argument(event.message_str)
        if not query:
            yield event.plain_result(
                f"已收录 {len(self.dictionary.entries)} 条良语。用法：/良语 下·蠢"
            )
            return

        entry = self.dictionary.lookup(query)
        if entry is not None:
            yield event.plain_result(f"{entry.abbr}：{entry.text}")
            return

        matches = self.dictionary.find_matches(query, max_matches=3)
        if matches:
            yield event.plain_result(format_matches(matches, title="可能是这些良语"))
            return

        yield event.plain_result("未找到这个良语缩写。")

    @staticmethod
    def _extract_command_argument(message: str) -> str:
        message = (message or "").strip()
        if not message:
            return ""
        parts = message.split(maxsplit=1)
        command = parts[0].lstrip("".join(COMMAND_PREFIXES))
        if command == "良语" and len(parts) == 2:
            return parts[1].strip()
        if command == "良语":
            return ""
        return message
