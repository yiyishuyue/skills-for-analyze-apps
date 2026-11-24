# 产品人实用 Skill 库

面向产品人的可复用 Agent Skills，覆盖业务决策、用户反馈与竞品研究等工作场景。

## 技能目录

| Skill | 用途 | 状态 |
|---|---|---|
| [Decision Model Coach](skills/decision-model-coach/SKILL.md) | 按决策阶段选择需求验证、目标权衡、经济模型、决策树与敏感性分析 | V1.2，可使用 |
| [X 投诉分析与竞品借鉴](skills/x-complaint-learnings/SKILL.md) | 提取用户原话、迁移路径、竞品对照与 P0–P3 动作 | 原版已收录 |

## 使用方式

将 `skills/decision-model-coach/` 整个目录复制到所用 Agent 工具支持的技能目录中，然后描述需要分析的业务决策。技能会先识别决策阶段与信息缺口，再选择验证实验或定量方法，给出有条件的建议及改变建议的新证据。

请保留 `references/` 子目录，其中包含早期产品验证实验指引。技能未附带独立计算和绘图脚本；按任务需要使用 Agent 环境的计算、联网检索及图表能力。数据不足时可交付定性建议或验证方案，不强制生成利润、概率树或二维矩阵。

## 原项目：X-complaint-for-apps

原仓库定位：Skill for monitoring and analyzing complaints & public opinion of competing apps.

用于监测与分析竞品 App 的投诉和公众反馈。原版技能已收录于 `skills/x-complaint-learnings/`，包含 `SKILL.md` 和 `templates/report-outline.md`。

## X 投诉分析 Skill 使用方式

将 `skills/x-complaint-learnings/` 整个目录复制到 Agent 的技能目录，保留 `templates/` 子目录。指令保留 Grok Bot 原版内容，其中 X 取数工具、调用方式与 `/workspace/` 输出路径需要运行环境支持或映射到可用工具和目录。

原文件来自此前未合并的 [PR #1](https://github.com/yiyishuyue/X-complaint-for-apps/pull/1)，本次按技能库结构收录，未改写技能正文。

## 许可证

见 [LICENSE](LICENSE)。
