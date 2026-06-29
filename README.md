# 良语翻译

AstrBot 插件，用于翻译群消息中出现的《边狱巴士公司》良秀式“良语”缩写。

## 功能

- 自动监听群消息并翻译良语缩写。
- 支持 `吵·猪·折·脖` 这种带分隔符写法。
- 支持较长缩写的无分隔符写法，例如 `快说否头砸`。
- 对两字缩写采用保守匹配：消息完全等于 `全切` 时会命中，但普通句子里的 `全切` 默认不会自动触发，避免误报。
- 词库未命中时，会调用 AstrBot 当前 LLM，根据已知例句规律、当前人格设定和知识库/数据库内容推断未知良语。
- 支持 `/良语 下·蠢` 手动查询或推断。

## 配置

插件提供 `_conf_schema.json`，可在 AstrBot 插件配置中调整：

- `enabled`：是否启用群消息自动翻译。
- `max_matches_per_message`：单条消息最多回复多少个命中结果。
- `min_unseparated_match_len`：无分隔符缩写在句中命中的最小长度。
- `ignore_command_messages`：是否忽略命令消息。
- `reply_title`：自动回复标题。
- `item_format`：单条翻译格式，支持 `{abbr}` 和 `{text}`。
- `enable_llm_fallback`：词库未命中时是否调用 LLM 推断。
- `auto_infer_unknown_dotted`：群消息中出现未知带分隔符良语时是否自动推断。
- `use_persona_context`：推断时是否读取当前会话生效的人格设定。
- `use_knowledge_base`：推断时是否尝试检索 AstrBot 知识库/数据库。
- `max_llm_candidates_per_message`：单条消息最多自动推断多少个未知良语。
- `llm_prompt_examples`：构造推断提示词时使用多少条例句。
- `knowledge_context_max_chars`：注入模型的知识库检索结果最大字符数。
- `inferred_reply_title`：LLM 推断回复标题。
- `inferred_item_format`：LLM 推断结果格式。
- `stop_event_after_reply`：回复后是否停止后续事件处理。

## 词库

当前词库位于 `data/liangyu_phrases.json`，来自项目目录中的 `良·语举例.xlsx`。词库不再是唯一翻译来源，而是：

- 已知良语的快速准确翻译表。
- 未知良语 LLM 推断时的少样本风格参考。

插件启动时也会读取可选的 `data/custom_phrases.json`，可用于放置你自己的测试项或群内自造良语。

新增词条示例：

```json
{
  "abbr": "万·短·至·艺",
  "text": "将万物略缩的至上艺术"
}
```

## 推断未知良语

群消息中出现带分隔符的未知良语，例如：

```text
你·我·母
```

插件会把它识别为候选良语，并调用 AstrBot 当前配置的 LLM。推断时会尝试读取：

- 当前会话生效的人格设定。
- 当前会话或全局配置启用的 AstrBot 知识库检索结果。
- 内置良语例句规律。

如果剧情内容写在 AstrBot 人格或知识库里，模型会优先结合这些上下文推断，例如：

```text
你是我的母亲
```

没有分隔符的未知缩写更容易误判，默认不在群消息中自动触发；可以用手动命令：

```text
/良语 你我母
```
