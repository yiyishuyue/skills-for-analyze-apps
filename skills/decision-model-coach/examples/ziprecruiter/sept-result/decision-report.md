# ZipRecruiter：公开数据回放 September

基准情景值 / 美元
候选：p249
状态：highest_modeled_score

- 月价249美元：42330.0
- 月价99美元：23760.0

敏感性：
未运行或无非零变化，不报告关键因素。

输入摘要校验值：3e76ff085a22966ebd76825c093862022dc0c7f2835999444544a17a21c33b78

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
