# 产品人实用 Skill 库

面向产品人的可复用 Agent Skills，覆盖业务决策、用户反馈与竞品研究等工作场景。

## 技能目录

| Skill | 用途 | 状态 |
|---|---|---|
| [AI Decision Intelligence](skills/ai-decision-intelligence/SKILL.md) | 将业务问题转为决策树、期望利润、敏感性及盈亏平衡分析 | V1.1，可使用 |

## 使用方式

将 `skills/ai-decision-intelligence/` 整个目录复制到所用 Agent 工具支持的技能目录中，然后描述需要分析的业务决策。技能会引导澄清信息、推导参数并生成决策报告。

本技能为完整指令文件，尚未附带独立计算和绘图脚本。完整执行需要 Agent 环境提供计算、联网检索和图表生成能力；数据不足时应明确说明假设与局限。

## 原项目：X-complaint-for-apps

原仓库定位：Skill for monitoring and analyzing complaints & public opinion of competing apps.

用于监测与分析竞品 App 的投诉和公众反馈。目前仓库尚未包含该技能的实现文件，后续可作为独立技能加入。

## 许可证

见 [LICENSE](LICENSE)。
