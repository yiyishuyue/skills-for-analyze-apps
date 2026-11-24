# ZipRecruiter：公开数据回放 November

基准情景值 / 美元
候选：p249
状态：highest_modeled_score

- 月价249美元：37790.0
- 月价99美元：22570.0

敏感性：
未运行或无非零变化，不报告关键因素。

输入摘要校验值：9df5233056cf86beff7a6e5e208ae878a7e79688e28ef8e63642187576246a17

数据与假设：
user_assumption：统一比较的潜在客户数（exposures）：归一化基数，不是实际样本数
user_assumption：来源：https://ungated-research.s3.amazonaws.com/pdf/1777-JPE-2023-1-Personalized_Pricing_and_Consumer_Welfare.pdf
user_assumption：仅使用公开汇总数据作回放，收入非利润；不重新估计显著性或累计续费收入。
user_assumption：1000是归一化基数；价格和转化固定为观测值，不假定它们独立随机变化。
user_assumption：回顾已知结果的两方案比较，非独立盲测；不求全局最优价。

限制：
未设置 threshold（打正线），结论只有方案排序，缺少「能不能做」的判断
计算排名不是市场验证或风险效用判断。
emv保留为兼容字段，语义见score_label。
有限网格可能漏掉非单调反转；没有发现反转不代表全域稳健。
