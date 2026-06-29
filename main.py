from __future__ import annotations

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    from .liangyu import (
        LiangYuDictionary,
        LiangYuMatch,
        build_inference_system_prompt,
        build_inference_user_prompt,
        build_knowledge_query,
        clean_inferred_text,
        extract_liangyu_candidates,
        format_matches,
        format_understanding_context,
        is_explicit_translation_request,
        normalize_key,
    )
except ImportError:
    from liangyu import (
        LiangYuDictionary,
        LiangYuMatch,
        build_inference_system_prompt,
        build_inference_user_prompt,
        build_knowledge_query,
        clean_inferred_text,
        extract_liangyu_candidates,
        format_matches,
        format_understanding_context,
        is_explicit_translation_request,
        normalize_key,
    )


DEFAULT_CONFIG = {
    "enabled": True,
    "max_matches_per_message": 5,
    "min_unseparated_match_len": 3,
    "ignore_command_messages": True,
    "reply_title": "良语翻译",
    "inferred_reply_title": "良语推断",
    "item_format": "{abbr}：{text}",
    "inferred_item_format": "{abbr}：{text}",
    "enable_llm_fallback": True,
    "auto_reply_on_explicit_request": True,
    "silent_understand_normal_messages": True,
    "silent_infer_unknown": True,
    "use_persona_context": True,
    "use_knowledge_base": True,
    "max_llm_candidates_per_message": 2,
    "llm_prompt_examples": 18,
    "knowledge_context_max_chars": 2400,
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


@register("astrbot_plugin_liangyu", "Codex", "翻译群消息中的良语缩写", "v0.4.1")
class LiangYuTranslatorPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config
        self.dictionary = LiangYuDictionary.from_default_files()

    async def initialize(self):
        logger.info("良语翻译插件已加载 %s 条词条。", len(self.dictionary.entries))

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def translate_group_message(self, event: AstrMessageEvent):
        """理解群消息中出现的良语缩写，并在明确请求时翻译。"""
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

        candidates = extract_liangyu_candidates(
            message,
            max_candidates=max(
                1, int_config_value(self.config, "max_llm_candidates_per_message")
            ),
        )
        unknown_candidates = self._filter_unknown_candidates(candidates, matches)
        explicit_request = is_explicit_translation_request(message)

        if explicit_request and config_value(self.config, "auto_reply_on_explicit_request"):
            reply_matches = list(matches)
            if unknown_candidates and config_value(self.config, "enable_llm_fallback"):
                reply_matches.extend(
                    await self._infer_matches(event, unknown_candidates, message)
                )
            if not reply_matches:
                return
            if config_value(self.config, "stop_event_after_reply"):
                event.stop_event()
            yield event.plain_result(self._format_reply(reply_matches))
            return

        if not config_value(self.config, "silent_understand_normal_messages"):
            return
        if not self._will_request_llm(event):
            return

        context_matches = list(matches)
        unresolved_candidates: list[str] = []
        if (
            unknown_candidates
            and config_value(self.config, "enable_llm_fallback")
            and config_value(self.config, "silent_infer_unknown")
        ):
            context_matches.extend(
                await self._infer_matches(event, unknown_candidates, message)
            )
            resolved_keys = {normalize_key(match.abbr) for match in context_matches}
            unresolved_candidates = [
                candidate
                for candidate in unknown_candidates
                if normalize_key(candidate) not in resolved_keys
            ]
        else:
            unresolved_candidates = unknown_candidates

        if context_matches or unresolved_candidates:
            self._append_understanding_context(
                event,
                context_matches,
                unresolved_candidates,
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

        if not config_value(self.config, "enable_llm_fallback"):
            yield event.plain_result("未找到这个良语缩写。")
            return

        inferred = await self._infer_matches(event, [query], query)
        if inferred:
            yield event.plain_result(
                format_matches(
                    inferred,
                    title=str(config_value(self.config, "inferred_reply_title")),
                    item_format=str(config_value(self.config, "inferred_item_format")),
                )
            )
            return

        yield event.plain_result("未找到这个良语缩写，也暂时无法调用模型推断。")

    def _format_reply(self, matches: list[LiangYuMatch]) -> str:
        return format_matches(
            matches,
            title=str(
                config_value(
                    self.config,
                    "inferred_reply_title"
                    if any(match.inferred for match in matches)
                    else "reply_title",
                )
            ),
            item_format=str(
                config_value(
                    self.config,
                    "inferred_item_format"
                    if any(match.inferred for match in matches)
                    else "item_format",
                )
            ),
        )

    def _filter_unknown_candidates(
        self,
        candidates: list[str],
        matches: list[LiangYuMatch],
    ) -> list[str]:
        known_keys = {normalize_key(match.abbr) for match in matches}
        unknown: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = normalize_key(candidate)
            if not key or key in known_keys or key in seen:
                continue
            entry = self.dictionary.lookup(candidate)
            if entry:
                known_keys.add(entry.key)
                continue
            unknown.append(candidate)
            seen.add(key)
        return unknown

    @staticmethod
    def _will_request_llm(event: AstrMessageEvent) -> bool:
        if event.get_extra("provider_request") is not None:
            return True
        return bool(
            getattr(event, "is_at_or_wake_command", False)
            and not getattr(event, "call_llm", False)
        )

    @staticmethod
    def _append_understanding_context(
        event: AstrMessageEvent,
        matches: list[LiangYuMatch],
        unknown_candidates: list[str],
    ) -> None:
        addition = format_understanding_context(
            matches,
            unknown_candidates=unknown_candidates,
        )
        if not addition:
            return
        event.message_str = f"{event.message_str}\n\n{addition}"
        if getattr(event, "message_obj", None) is not None:
            event.message_obj.message_str = event.message_str

    async def _infer_matches(
        self,
        event: AstrMessageEvent,
        candidates: list[str],
        source_message: str = "",
    ) -> list[LiangYuMatch]:
        provider_id = await self._get_chat_provider_id(event)
        if not provider_id:
            logger.warning("良语推断失败：当前会话没有可用的 LLM 提供商。")
            return []

        matches: list[LiangYuMatch] = []
        persona_prompt = ""
        if config_value(self.config, "use_persona_context"):
            persona_prompt = await self._get_persona_prompt(event)

        for candidate in candidates:
            knowledge_context = ""
            if config_value(self.config, "use_knowledge_base"):
                knowledge_context = await self._retrieve_knowledge_context(
                    event,
                    candidate,
                    source_message,
                )

            system_prompt = build_inference_system_prompt(
                persona_prompt=persona_prompt,
                knowledge_context=knowledge_context,
            )
            prompt = build_inference_user_prompt(
                candidate,
                self.dictionary.entries,
                max_examples=max(1, int_config_value(self.config, "llm_prompt_examples")),
            )
            try:
                response = await self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=prompt,
                    system_prompt=system_prompt,
                )
            except Exception as exc:
                logger.warning("良语推断失败：%s", exc)
                continue

            text = clean_inferred_text(
                candidate,
                getattr(response, "completion_text", ""),
            )
            if text:
                matches.append(LiangYuMatch(abbr=candidate, text=text, inferred=True))
        return matches

    async def _get_persona_prompt(self, event: AstrMessageEvent) -> str:
        umo = getattr(event, "unified_msg_origin", None)
        if not umo:
            return ""

        conversation_persona_id = None
        try:
            conversation_manager = getattr(self.context, "conversation_manager", None)
            if conversation_manager:
                conversation_id = await conversation_manager.get_curr_conversation_id(umo)
                if conversation_id:
                    conversation = await conversation_manager.get_conversation(
                        umo, conversation_id
                    )
                    conversation_persona_id = getattr(
                        conversation, "persona_id", None
                    )
        except Exception as exc:
            logger.warning("无法读取当前会话人格 ID：%s", exc)

        provider_settings = {}
        try:
            cfg = self.context.get_config(umo=umo)
            provider_settings = cfg.get("provider_settings", {})
        except Exception as exc:
            logger.warning("无法读取当前会话 provider 设置：%s", exc)

        try:
            _, persona, _, _ = await self.context.persona_manager.resolve_selected_persona(
                umo=umo,
                conversation_persona_id=conversation_persona_id,
                platform_name=event.get_platform_name(),
                provider_settings=provider_settings,
            )
        except Exception as exc:
            logger.warning("无法解析当前人格：%s", exc)
            return ""

        if not persona:
            return ""
        try:
            return str(persona.get("prompt", "")).strip()
        except AttributeError:
            return ""

    async def _retrieve_knowledge_context(
        self,
        event: AstrMessageEvent,
        candidate: str,
        source_message: str,
    ) -> str:
        umo = getattr(event, "unified_msg_origin", None)
        if not umo:
            return ""

        try:
            from astrbot.core.tools.knowledge_base_tools import retrieve_knowledge_base
        except Exception as exc:
            logger.warning("无法加载 AstrBot 知识库检索工具：%s", exc)
            return ""

        query = build_knowledge_query(candidate, source_message)
        try:
            result = await retrieve_knowledge_base(
                query=query,
                umo=umo,
                context=self.context,
            )
        except Exception as exc:
            logger.warning("良语推断知识库检索失败：%s", exc)
            return ""

        if not result:
            return ""
        max_chars = max(200, int_config_value(self.config, "knowledge_context_max_chars"))
        return str(result).strip()[:max_chars]

    async def _get_chat_provider_id(self, event: AstrMessageEvent):
        umo = getattr(event, "unified_msg_origin", None)
        try:
            provider_id = await self.context.get_current_chat_provider_id(umo=umo)
            if provider_id:
                return provider_id
        except Exception as exc:
            logger.warning("无法获取当前会话 LLM Provider：%s", exc)

        try:
            providers = self.context.get_all_providers()
            if providers:
                return providers[0].meta().id
        except Exception as exc:
            logger.warning("无法获取可用 LLM Provider：%s", exc)
        return None

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
