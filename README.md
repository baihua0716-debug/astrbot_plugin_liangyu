# 良语翻译

AstrBot 插件，用于翻译群消息中出现的《边狱巴士公司》良秀式“良语”缩写。

## 功能

- 自动监听群消息并翻译命中的良语缩写。
- 支持 `吵·猪·折·脖` 这种带分隔符写法。
- 支持较长缩写的无分隔符写法，例如 `快说否头砸`。
- 对两字缩写采用保守匹配：消息完全等于 `全切` 时会命中，但普通句子里的 `全切` 默认不会自动触发，避免误报。
- 支持 `/良语 下·蠢` 手动查询。

## 配置

插件提供 `_conf_schema.json`，可在 AstrBot 插件配置中调整：

- `enabled`：是否启用群消息自动翻译。
- `max_matches_per_message`：单条消息最多回复多少个命中结果。
- `min_unseparated_match_len`：无分隔符缩写在句中命中的最小长度。
- `ignore_command_messages`：是否忽略命令消息。
- `reply_title`：自动回复标题。
- `item_format`：单条翻译格式，支持 `{abbr}` 和 `{text}`。
- `stop_event_after_reply`：回复后是否停止后续事件处理。

## 词库

当前词库位于 `data/liangyu_phrases.json`，来自项目目录中的 `良·语举例.xlsx`。

新增词条示例：

```json
{
  "abbr": "万·短·至·艺",
  "text": "将万物略缩的至上艺术"
}
```
