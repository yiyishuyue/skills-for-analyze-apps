> 历史字段说明：来自WorkBuddy原包。V1.4行为以 [verified-engine.md](verified-engine.md) 为准，特别是概率、扫描、输出及直接执行入口；下文不是当前全部能力承诺。

# decision-spec 输入契约（与 scripts/decision_engine.py 逐字对齐）

> 本文件是 spec JSON 的唯一权威定义。模板骨架见 `@templates/decision-spec.template.json`。
> 引擎对 spec 做确定性校验，任何违反契约的输入都会受控报错（退出码 1，中文提示），**不做静默修正**。

## 顶层字段

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `meta` | 是 | object | 决策元信息，见下表 |
| `variables` | 是 | array | 关键变量清单（至少 1 个），见下表 |
| `options` | 是 | array | 可选方案（**至少 2 个**；只有 1 个方案时不存在决策） |
| `formula` | 是 | string | 收益公式，Python 表达式，只能用变量 id 与 `abs/min/max/round` |
| `assumptions` | 否 | array[string] | 显式假设清单，逐条进入报告 |
| `sensitivity` | 否 | object | `{"range_pct": 0.2, "steps": 7}`（fixed 变量扫描半径与采样数） |
| `sens2` | 否 | object | `{"var_x": id, "var_y": id}` 指定双因素透视的两个变量；缺省时引擎自动选摆幅最大的两个可扫变量。**被任一方案 `overrides` 钉死的变量不能作网格轴**（定价档位比较请改用 options 表达，否则 E016） |

## meta 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | 是 | 决策问题标题 |
| `decision_goal` | 是 | 决策目标（一句话：要判断什么） |
| `metric` | 是 | 目标指标名（如 期望ARPU / 利润 / LTV） |
| `unit` | 是 | 计量单位（如 美元 / 万元） |
| `horizon` | 是 | 时间范围（如 半年 / 12个月）——口径必须先定死 |
| `threshold` | 否 | 打正线/约束阈值（数值）；写了它结论才有「能不能做」的判断 |
| `threshold_label` | threshold 存在时必填 | 打正线的业务含义（如 投放CPI上限） |
| `higher_is_better` | 否 | 默认 true；指标越小越好（如成本）时设 false |

## variables 字段（每个变量）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 小写字母/数字/下划线，不以数字开头，不重复；formula 通过 id 引用 |
| `label` | 是 | 业务名称（报告与图表用它呈现） |
| `base` | 是 | 基准值（数值） |
| `kind` | 是 | `fixed`（固定值）/ `range`（连续区间）/ `discrete`（离散分布） |
| `low` / `high` | kind=range 时必填 | 区间两端，low ≤ high |
| `steps` | 否 | range 的采样点数（默认 6；等距点等权，均值恰为区间均值） |
| `distribution` | kind=discrete 时必填 | `[[取值, 概率], ...]`，**概率之和必须 = 1**（容差 1e-6，超出即报 E004，不静默归一） |
| `source` | 是 | 来源说明：哪个数据窗口 / 哪份参考 / 为什么是这个区间 |
| `source_class` | 是 | 四选一：`user_data`（用户提供的数据）/ `user_assumption`（用户确认的假设）/ `industry_ref`（有出处的行业参考）/ `pending`（待确认——会进报告不确定性清单） |
| `notes` | 否 | 备注（分布形状、可优化性等） |

## options 字段（每个方案）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 同变量 id 命名规则，不重复 |
| `label` | 是 | 方案名称 |
| `fixed_cost` | 否 | 方案固定成本/投入，从 EMV 中扣减（默认 0） |
| `overrides` | 否 | `{变量id: 数值}`：该方案对变量基准值的覆盖（如不同定价档位） |
| `chances` | 否 | **情境式决策树**（模式 A）时提供：`[{"id","label","prob","values":{变量id:数值}}]`；prob ∈ 0~1 且**所有情境概率之和必须 = 1**（情境必须互斥且完备） |

## 两种求解模式（引擎自动判断）

- **模式 A（情境式）**：方案声明了 `chances` → EMV = Σ prob × formula(该情境变量值) − fixed_cost。适合「成功/失败」「乐观/悲观」等互斥情境。
- **模式 B（分布期望式）**：方案未声明 `chances` → EMV = 变量联合分布的期望（各变量独立假设；range 按等距点等权近似）− fixed_cost。适合「参数按分布波动」的测算（如定价 × 续费系数 × 付费率）。
- 同一包内两种模式可混用（不同方案各选各的），但语义要在 assumptions 里写明。

## 优先级与扫描语义

1. 变量取值优先级：`chances.values` > `options.overrides` > `variables.base`。
2. 单因素敏感性扫描：探测点覆盖 base（fixed 按 ±range_pct 生成，range 取区间，discrete 取全部取值）。
   - 情境里被显式钉死的值按「整体水平同比例缩放」处理（基准非 0 等比、基准为 0 平移）；
   - 被 `overrides` 覆盖的变量在扫描时同样被探测值临时覆盖（语义：该变量整体水平移动）。
3. `base = 0` 的 fixed 变量无法等比扫描：跳过并写入 `uncertainties`，不报错、不伪造。

## 引擎错误码（受控失败，退出码 1）

| 码 | 含义 |
|---|---|
| E001 | spec 不是合法 JSON |
| E002 | 必填字段缺失/为空/类型错 |
| E003 | id 非法或重复 |
| E004 | 概率之和 ≠ 1（变量分布或方案情境） |
| E005 | formula 引用了未定义变量 |
| E006 | formula 语法错误或含白名单外语法 |
| E007 | options 少于 2 个 |
| E008 | 数值非法（负概率、区间颠倒、类型错等） |
| E009 | 输出目录已有结果且未加 `--force` |
| E010 | spec 文件不存在或不可读 |
| E013/E014/E016 | chances.values / overrides / sens2 引用未定义变量 |
| E015 | 写了 threshold 但缺 threshold_label |
| E_MULTI | 以上多条一次性汇总报出（引擎一次报全，不挤牙膏） |

## 产出物

| 文件 | 内容 |
|---|---|
| `decision-result.json` | 结构化结论：ranking / recommended / drivers / switch_points / sens2_grid / assumptions / uncertainties。**报告里所有数字的唯一来源** |
| `decision-tree.svg` | 决策树图（分支 + 情境 + EMV 回溯 + 推荐高亮 + 打正线） |
| `sensitivity-tornado.svg` | 龙卷风图（按摆幅排序 + 翻转点标注） |
| `sensitivity-heatmap.svg` | 双因素透视热力表（有两个可扫变量时） |
| `sensitivity-table.md` | 同口径的 markdown 透视表 |
