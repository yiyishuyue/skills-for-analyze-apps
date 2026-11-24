# V1.4 计算后端

Python标准库，无WorkBuddy账号、SDK或网络服务依赖。保留整个目录即可分发；运行环境需允许读取文件与执行Python。纯聊天环境可使用分析流程，不能声称执行了本程序。已实测本机标准库运行，未逐一验证所有Agent软件或操作系统。

主入口：python scripts/run_verified.py --spec 模型.json --outdir 新的空目录
run_checked.py是兼容入口；不要直接运行内部decision_engine.py。默认拒绝非空输出目录，以免旧图混入新结果。

输入的基础字段见 [workbuddy-spec-contract.md](workbuddy-spec-contract.md)，其中自动扫描与旧产物约定在V1.4中不适用，以下规则优先：
- evidence_policy.inputs_confirmed=true：明确核对输入与口径，不代表事实真伪已经独立审计。
- range不自动解释为概率；只有均匀近似有依据并被接受时才设置uniform_ranges_confirmed=true。多个随机变量直接求积需independence_confirmed=true；相关量用完整互斥联合情景表达。
- pending、非有限数、除零、非法概率及过大的展开会失败，不产生正式推荐。
- 敏感性默认关闭。启用须设置sensitivity.enabled=true，并为每个参与扫描的变量提供scan={low:下界,high:上界,source:范围依据}。范围要包含base；零基准也可用明确范围扫描。steps为2至31的整数。
- 变量可提供domain=[下界,上界]，例如概率用[0,1]；基础值、情景值、方案覆盖和扫描范围均检查。没有domain时程序无法判断业务有效域，Agent仍需核对。
- 被方案或情景锁定的变量不直接扫描，以免扫描抹掉方案差异。需要另建符合业务关系的情景；不静默缩放。
- 如需二维，sens2的两根轴须有scan；仅显式指定sens2时出二维图。有限扫描可能漏掉非单调反转，不宣称已找到所有翻转点。

输出：
- decision-result.json：确定性值或假设下期望值、候选、并列、适用限制和扫描结果。emv字段为兼容保留，按evaluation_kind与score_label解释。
- input-spec.json、decision-report.md、option-comparison.svg：始终生成。比较图不冒充递归概率树。
- 只有存在非零变化时输出龙卷风图；只在二维有效时输出热力图。
- 数值并列用candidate_ids列出并设置recommended=null。数值接近不等于统计等效，统计误差需另评估。
- 情景payoff是该方案公式的毛结果，fixed_cost在方案总分中只扣一次。

能力边界：平面方案/单层互斥情景、独立分布期望、有限范围扫描。不支持递归决策、EVSI自动求解、价格需求估计或风险效用学习；不能通过勾选确认字段补出缺失证据。复杂问题按主技能选择其他透明计算，或说明暂不能可靠量化。

来源：基于用户提供的WorkBuddy本地包改进。V1.4修复了方案公式情景明细不一致、默认扫描、零摆幅误列关键因素等；报告不再将确定性基准标成期望值。原始来源、分析推导、试验目标可以分别引用；不要求所有事实数字来自引擎。
验证：test/test_verified.py覆盖输入闸门、公式明细、成本、并列、确定性、概率及扫描。真实案例回放仅检验指定任务，不能证明通用建议质量。

补充：input_sha256核对的是规范化输入内容，不能证明来源真实性。range是有限节点等权近似，非连续分布精确积分；复杂非线性需检查近似误差。最小化目标要把所有成本写入formula，fixed_cost必须为0，避免误用减成本语义。
