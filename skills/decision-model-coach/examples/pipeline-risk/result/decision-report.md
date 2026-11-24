# 真实工程案例：管道铺设施工风险应对

假设条件下的期望值 / 百万美元
候选：survey
状态：highest_modeled_score

- 开展详细勘测：15.001999999999999
  情景：失败并产生延期/超支；概率=0.158；公式毛结果=31.0（固定成本另扣）
  情景：未发生所列失败损失；概率=0.842；公式毛结果=12.0（固定成本另扣）
- 采用更优技术：20.696
  情景：失败并产生延期/超支；概率=0.158；公式毛结果=115.0（固定成本另扣）
  情景：未发生所列失败损失；概率=0.842；公式毛结果=3.0（固定成本另扣）
- 聘请专家项目团队：28.023000000000003
  情景：失败并产生延期/超支；概率=0.317；公式毛结果=41.0（固定成本另扣）
  情景：未发生所列失败损失；概率=0.683；公式毛结果=22.0（固定成本另扣）
- 不增加应对措施：35.504
  情景：失败并产生延期/超支；概率=0.317；公式毛结果=112.0（固定成本另扣）
  情景：未发生所列失败损失；概率=0.683；公式毛结果=0.0（固定成本另扣）
- 采取全部应对措施：56.849999999999994
  情景：失败并产生延期/超支；概率=0.05；公式毛结果=73.0（固定成本另扣）
  情景：未发生所列失败损失；概率=0.95；公式毛结果=56.0（固定成本另扣）

敏感性：
每延期一月的机会损失；摆幅=2.369999999999999
探测到的推荐边界：每延期一月的机会损失 ≈ 3.8962025316455993；technology / survey（有限扫描近似）

输入摘要校验值：c36b41029bf369cee62e478ac67b570292983fcdb8afe64c2cad5c065d9fe6e6

数据与假设：
user_assumption：来源为真实项目的公开事前评估模型，概率与损失来自专家估计，并非本项目实测频率。
user_assumption：每个方案对应失败/未失败两个互斥情景；同一失败分支内的延期与超支共同发生，不把它们当独立随机变量。
user_assumption：应对费用两个分支都承担；失败时再加延期机会损失与超支；不含共同且不影响排序的项目本金。
user_assumption：monthly_value扫描0至7.5是新增压力测试：零损失边界至论文基准；不是论文估计的置信区间或概率分布。
user_assumption：论文结果有舍入，按原始概率和严重程度重算；不为凑论文舍入数值而修改输入。
user_assumption：按风险中性的期望成本比较，假定备选方案均可执行；未提供现金预算等硬约束，不构成工程或投资执行批准。
industry_ref：应对费用（response_cost）：Dey (2001), Table VI: https://www.researchgate.net/publication/40499031_Decision_support_system_for_risk_management_a_case_study
industry_ref：失败时延期月数（delay）：Dey (2001), Table VI: https://www.researchgate.net/publication/40499031_Decision_support_system_for_risk_management_a_case_study
industry_ref：失败时直接超支（overrun）：Dey (2001), Table VI: https://www.researchgate.net/publication/40499031_Decision_support_system_for_risk_management_a_case_study
industry_ref：每延期一月的机会损失（monthly_value）：Dey (2001), Table VI: https://www.researchgate.net/publication/40499031_Decision_support_system_for_risk_management_a_case_study

限制：
未设置 threshold（打正线），结论只有方案排序，缺少「能不能做」的判断
计算排名不是市场验证或风险效用判断。
emv保留为兼容字段，语义见score_label。
有限网格可能漏掉非单调反转；没有发现反转不代表全域稳健。
