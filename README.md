# 产品人实用 Skill 库

面向产品人的可复用 Agent Skills，覆盖业务决策、用户反馈与竞品研究等工作场景。

## 技能目录

| Skill | 用途 | 状态 |
|---|---|---|
| [AI Decision Intelligence](skills/ai-decision-intelligence/SKILL.md) | 将业务问题转为决策树、期望利润、敏感性及盈亏平衡分析 | V1.1，可使用 |
| [X 投诉分析与竞品借鉴](skills/x-complaint-learnings/SKILL.md) | 提取用户原话、迁移路径、竞品对照与 P0–P3 动作 | 原版已收录 |

## 使用方式

将 `skills/ai-decision-intelligence/` 整个目录复制到所用 Agent 工具支持的技能目录中，然后描述需要分析的业务决策。技能会引导澄清信息、推导参数并生成决策报告。

本技能为完整指令文件，尚未附带独立计算和绘图脚本。完整执行需要 Agent 环境提供计算、联网检索和图表生成能力；数据不足时应明确说明假设与局限。

## 原项目：X-complaint-for-apps

原仓库定位：Skill for monitoring and analyzing complaints & public opinion of competing apps.

用于监测与分析竞品 App 的投诉和公众反馈。原版技能已收录于 `skills/x-complaint-learnings/`，包含 `SKILL.md` 和 `templates/report-outline.md`。

## X 投诉分析 Skill 使用方式

将 `skills/x-complaint-learnings/` 整个目录复制到 Agent 的技能目录，保留 `templates/` 子目录。指令保留 Grok Bot 原版内容，其中 X 取数工具、调用方式与 `/workspace/` 输出路径需要运行环境支持或映射到可用工具和目录。

原文件来自此前未合并的 [PR #1](https://github.com/yiyishuyue/X-complaint-for-apps/pull/1)，本次按技能库结构收录，未改写技能正文。

## 许可证

见 [LICENSE](LICENSE)。
