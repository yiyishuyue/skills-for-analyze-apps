#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.4 internal flat-scenario calculation helpers. Use run_verified.py as the entry point."""

import argparse
import ast
import itertools
import json
import math
import os
import sys
import urllib.parse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

TORNADO_DEFAULT = {"range_pct": 0.2, "steps": 7}


class SpecError(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg
        super().__init__("[%s] %s" % (code, msg))


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def smart_num(x, nd=None):
    x = float(x)
    if nd is not None:
        return ("%%.%df" % nd) % x
    a = abs(x)
    if a == 0:
        return "0"
    if a >= 1000:
        return "{:,.1f}".format(x)
    if a >= 1:
        return ("%.3f" % x).rstrip("0").rstrip(".")
    if a >= 0.001:
        return ("%.4f" % x).rstrip("0").rstrip(".")
    return "%.3g" % x


def clip(s, n):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------- 校验

META_STR = ["title", "decision_goal", "metric", "unit", "horizon"]


def validate(spec):
    """契约校验：一次收集全部错误再抛出（不挤牙膏式报错）。"""
    errs = []

    def bad(code, msg):
        errs.append("[%s] %s" % (code, msg))

    if not isinstance(spec, dict):
        raise SpecError("E002", "spec 顶层必须是 JSON 对象（实际 %s）"
                        % type(spec).__name__)

    meta = spec.get("meta")
    if not isinstance(meta, dict):
        bad("E002", "缺少 meta 对象（title / decision_goal / metric / unit / horizon）")
        meta = {}
    for k in META_STR:
        if not str(meta.get(k) or "").strip():
            bad("E002", "meta.%s 缺失或为空（必填）" % k)
    threshold = meta.get("threshold")
    if threshold is not None:
        try:
            float(threshold)
        except (TypeError, ValueError):
            bad("E008", "meta.threshold 必须是数值（实际 %r）" % threshold)
        if not str(meta.get("threshold_label") or "").strip():
            bad("E015", "meta.threshold_label 缺失：写了 threshold 就必须写打正线的业务含义")

    var_list = spec.get("variables")
    if not isinstance(var_list, list) or not var_list:
        bad("E002", "缺少 variables 数组（至少 1 个关键变量）")
        var_list = []
    seen_ids = set()
    for i, v in enumerate(var_list):
        vid = v.get("id") if isinstance(v, dict) else None
        if (not isinstance(vid, str) or not vid.strip()
                or not vid.replace("_", "a").isalnum()
                or vid[0].isdigit() or vid != vid.lower()):
            bad("E003", "variables[%d].id 非法：须小写字母/数字/下划线且不以数字开头（实际 %r）"
                % (i, vid))
            continue
        if vid in seen_ids:
            bad("E003", "variables 里 id 重复：%s" % vid)
        seen_ids.add(vid)
        if not str(v.get("label") or "").strip():
            bad("E002", "变量 %s 缺 label（报告中要用业务名称呈现）" % vid)
        kind = v.get("kind")
        if kind not in ("fixed", "range", "discrete"):
            bad("E002", "变量 %s 的 kind 必须是 fixed / range / discrete（实际 %r）"
                % (vid, kind))
            continue
        try:
            float(v.get("base"))
        except (TypeError, ValueError):
            bad("E008", "变量 %s 缺合法的 base（数值基准值）" % vid)
        if kind == "range":
            try:
                low, high = float(v["low"]), float(v["high"])
                if low > high:
                    bad("E008", "变量 %s 的 range 区间反了：low(%s) > high(%s)"
                        % (vid, low, high))
            except (TypeError, ValueError, KeyError):
                bad("E002", "变量 %s kind=range 但缺 low / high" % vid)
        elif kind == "discrete":
            dist = v.get("distribution")
            if not isinstance(dist, list) or len(dist) < 1:
                bad("E002", "变量 %s kind=discrete 但缺 distribution"
                    "（[[取值, 概率], ...]）" % vid)
            else:
                tot = 0.0
                for j, pair in enumerate(dist):
                    if (not isinstance(pair, (list, tuple)) or len(pair) != 2):
                        bad("E008", "变量 %s distribution[%d] 必须是 [取值, 概率] 二元组"
                            % (vid, j))
                        continue
                    try:
                        x, w = float(pair[0]), float(pair[1])
                    except (TypeError, ValueError):
                        bad("E008", "变量 %s distribution[%d] 含非数值" % (vid, j))
                        continue
                    if w < 0:
                        bad("E008", "变量 %s distribution[%d] 概率为负" % (vid, j))
                    tot += w
                if abs(tot - 1.0) > 1e-6:
                    bad("E004", "变量 %s 的 distribution 概率之和 = %s（须 = 1；"
                        "请检查分布是否完整，引擎不做静默归一）" % (vid, smart_num(tot, 6)))
        sc = v.get("source_class")
        if sc not in ("user_data", "user_assumption", "industry_ref", "pending"):
            bad("E002", "变量 %s 缺 source_class（user_data / user_assumption / "
                "industry_ref / pending 四选一，用于区分数字来源）" % vid)

    opts = spec.get("options")
    if not isinstance(opts, list) or len(opts) < 2:
        bad("E007", "至少需要 2 个可选方案（options < 2 时不存在决策，直接做就行）")
        opts = []
    opt_ids = set()
    for i, o in enumerate(opts):
        oid = o.get("id") if isinstance(o, dict) else None
        if (not isinstance(oid, str) or not oid.strip()
                or not oid.replace("_", "a").isalnum() or oid[0].isdigit()):
            bad("E003", "options[%d].id 非法：%r" % (i, oid))
            continue
        if oid in opt_ids:
            bad("E003", "options 里 id 重复：%s" % oid)
        opt_ids.add(oid)
        if not str(o.get("label") or "").strip():
            bad("E002", "方案 %s 缺 label" % oid)
        chances = o.get("chances")
        if chances is not None:
            if not isinstance(chances, list) or not chances:
                bad("E002", "方案 %s 的 chances 若声明则须为非空数组" % oid)
                continue
            tot = 0.0
            for j, ch in enumerate(chances):
                if not isinstance(ch, dict):
                    bad("E008", "方案 %s chances[%d] 不是对象" % (oid, j))
                    continue
                try:
                    p = float(ch.get("prob"))
                except (TypeError, ValueError):
                    bad("E008", "方案 %s chances[%d] 缺合法 prob（0~1）" % (oid, j))
                    continue
                if p < 0 or p > 1:
                    bad("E008", "方案 %s chances[%d].prob = %s 超出 0~1"
                        % (oid, j, smart_num(p, 6)))
                tot += p
                vals = ch.get("values") or {}
                if not isinstance(vals, dict):
                    bad("E008", "方案 %s chances[%d].values 必须是对象" % (oid, j))
                else:
                    for k2 in vals:
                        if k2 not in seen_ids:
                            bad("E013", "方案 %s chances[%d].values 引用了未定义变量 %s"
                                % (oid, j, k2))
            if abs(tot - 1.0) > 1e-6:
                bad("E004", "方案 %s 的 chances 概率之和 = %s（须 = 1；情境必须互斥且完备，"
                    "引擎不做静默归一）" % (oid, smart_num(tot, 6)))
        ovs = o.get("overrides") or {}
        if not isinstance(ovs, dict):
            bad("E008", "方案 %s overrides 必须是对象" % oid)
        else:
            for k2 in ovs:
                if k2 not in seen_ids:
                    bad("E014", "方案 %s overrides 引用了未定义变量 %s" % (oid, k2))

    formula = spec.get("formula")
    if not isinstance(formula, str) or not formula.strip():
        bad("E002", "缺少 formula（收益公式，如 \"price * renew * pay_rate\"）")
    else:
        try:
            tree = ast.parse(formula, mode="eval")
        except SyntaxError as e:
            bad("E006", "formula 语法错误：%s（只允许 + - * / ** ( ) 与变量名，"
                "函数仅支持 abs/min/max/round）" % e.msg)
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp,
                                         ast.Constant, ast.Name, ast.Load,
                                         ast.Compare, ast.BoolOp, ast.Call,
                                         ast.Add, ast.Sub, ast.Mult, ast.Div,
                                         ast.Pow, ast.USub, ast.UAdd,
                                         ast.FloorDiv, ast.Mod,
                                         ast.Gt, ast.GtE, ast.Lt, ast.LtE,
                                         ast.Eq, ast.NotEq)):
                    bad("E006", "formula 含不允许的语法 %s（安全白名单：算术、比较、"
                        "abs/min/max/round）" % type(node).__name__)
                    break
            names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            undef = sorted(n for n in names if n not in seen_ids
                           and n not in ("abs", "min", "max", "round"))
            if undef:
                bad("E005", "formula 引用了未定义变量：%s（variables 里没有它们）"
                    % ", ".join(undef))

    if not isinstance(spec.get("assumptions", []), list):
        bad("E008", "assumptions 必须是字符串数组")

    # 方案级公式覆盖（可选）：差异化比较时各方案可用自己的公式
    for i, o in enumerate(opts):
        of = (o.get("formula") if isinstance(o, dict) else None)
        if of is None:
            continue
        if not isinstance(of, str) or not of.strip():
            bad("E006", "options[%d].formula 若声明则须为非空字符串" % i)
            continue
        try:
            otree = ast.parse(of, mode="eval")
        except SyntaxError as e:
            bad("E006", "options[%d].formula 语法错误：%s" % (i, e.msg))
            continue
        for node in ast.walk(otree):
            if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp,
                                     ast.Constant, ast.Name, ast.Load,
                                     ast.Compare, ast.BoolOp, ast.Call,
                                     ast.Add, ast.Sub, ast.Mult, ast.Div,
                                     ast.Pow, ast.USub, ast.UAdd,
                                     ast.FloorDiv, ast.Mod,
                                     ast.Gt, ast.GtE, ast.Lt, ast.LtE,
                                     ast.Eq, ast.NotEq)):
                bad("E006", "options[%d].formula 含白名单外语法 %s" % (i, type(node).__name__))
                break
        onames = {n.id for n in ast.walk(otree) if isinstance(n, ast.Name)}
        oundef = sorted(n for n in onames if n not in seen_ids
                        and n not in ("abs", "min", "max", "round"))
        if oundef:
            bad("E005", "options[%d].formula 引用了未定义变量：%s" % (i, ", ".join(oundef)))

    s2 = spec.get("sens2")
    if s2 is not None:
        if not isinstance(s2, dict) or not s2.get("var_x") or not s2.get("var_y"):
            bad("E016", "sens2 须为 {\"var_x\": 变量id, \"var_y\": 变量id}")
        else:
            for k2 in ("var_x", "var_y"):
                if s2.get(k2) not in seen_ids:
                    bad("E016", "sens2.%s 引用了未定义变量 %s" % (k2, s2.get(k2)))
                elif s2.get(k2) == s2.get("var_y" if k2 == "var_x" else "var_x"):
                    bad("E016", "sens2 的 var_x 与 var_y 不能相同")

    if errs:
        raise SpecError("E_MULTI", "spec 契约校验未通过，共 %d 处：\n  - %s"
                        % (len(errs), "\n  - ".join(errs)))
    return spec


def compile_formula(src):
    return compile(src, "<formula>", "eval")


SAFE_FUNCS = {"abs": abs, "min": min, "max": max, "round": round}


def eval_formula(code, vals):
    env = dict(SAFE_FUNCS)
    env.update({k: float(v) for k, v in vals.items()})
    return float(eval(code, {"__builtins__": {}}, env))


# ---------------------------------------------------------------- 变量展开

def var_points(v):
    """变量 → [(取值, 概率权重), ...]。range 按 N 等距点等权（均值恰为区间均值）。"""
    kind = v["kind"]
    base = float(v["base"])
    if kind == "fixed":
        return [(base, 1.0)]
    if kind == "range":
        low, high = float(v["low"]), float(v["high"])
        steps = max(2, int(v.get("steps", 6)))
        return [(low + (high - low) * i / (steps - 1), 1.0 / steps)
                for i in range(steps)]
    if kind == "discrete":
        return [(float(x), float(w)) for x, w in v["distribution"]]
    raise SpecError("E002", "未知变量 kind：%r" % kind)


def probe_values(v, sens):
    """Only explicitly sourced finite scan bounds are probed."""
    if v.get("scan"):
        low, high = v["scan"]["low"], v["scan"]["high"]
        n = int(sens.get("steps", 7))
        return [low + (high-low)*i/(n-1) for i in range(n)]
    return None


def chance_scale(chance_vals, base_val, probe):
    """情境显式值的扫描语义：基准非 0 等比缩放（整体水平同比例上/下移）；基准为 0 平移。"""
    if base_val:
        return chance_vals * probe / base_val
    return chance_vals + (probe - base_val)


# ---------------------------------------------------------------- 求解

def solve(spec):
    variables = spec["variables"]
    var_by_id = {v["id"]: v for v in variables}
    var_ids = [v["id"] for v in variables]
    meta = spec["meta"]
    higher = bool(meta.get("higher_is_better", True))
    threshold = meta.get("threshold")
    threshold = float(threshold) if threshold is not None else None
    code = compile_formula(spec["formula"])

    base_vals = {vid: float(var_by_id[vid]["base"]) for vid in var_ids}

    def option_emv(opt, swap=None):
        """swap: {var_id: probe_value}。返回该方案 EMV（已扣 fixed_cost）。"""
        ov = opt.get("overrides") or {}
        chances = opt.get("chances")
        fn = codes.get(opt["id"], code)
        if chances:
            emv = 0.0
            for ch in chances:
                vals = dict(base_vals)
                vals.update(ov)
                chv = ch.get("values") or {}
                vals.update(chv)
                if swap:
                    for vid, pv in swap.items():
                        if vid in chv:
                            vals[vid] = chance_scale(chv[vid],
                                                     base_vals.get(vid, 0.0), pv)
                        else:
                            vals[vid] = pv
                emv += float(ch["prob"]) * eval_formula(fn, vals)
        else:
            # 模式 B：变量联合分布期望（独立假设，区间按等距点近似）
            axes = []
            for v in variables:
                vid = v["id"]
                if swap and vid in swap:
                    axes.append([(swap[vid], 1.0)])
                elif vid in ov:
                    axes.append([(float(ov[vid]), 1.0)])
                else:
                    axes.append(var_points(v))
            acc, tw = 0.0, 0.0
            for combo in itertools.product(*axes):
                w = 1.0
                for _, wi in combo:
                    w *= wi
                vals = {vid: combo[i][0] for i, vid in enumerate(var_ids)}
                acc += w * eval_formula(fn, vals)
                tw += w
            emv = acc / tw if tw else 0.0
        return emv - float(opt.get("fixed_cost", 0.0))

    opts = spec["options"]
    codes = {"__global__": code}
    for o in opts:
        if o.get("formula"):
            codes[o["id"]] = compile_formula(o["formula"])
    ranking = []
    for o in opts:
        emv = option_emv(o)
        meets = None
        margin = None
        if threshold is not None:
            margin = (emv - threshold) if higher else (threshold - emv)
            meets = (emv >= threshold) if higher else (emv <= threshold)
        chances_out = []
        for ch in (o.get("chances") or []):
            vals = dict(base_vals)
            vals.update(o.get("overrides") or {})
            vals.update(ch.get("values") or {})
            chances_out.append({
                "id": ch.get("id"), "label": ch.get("label"),
                "prob": float(ch["prob"]),
                "payoff": eval_formula(codes.get(o["id"], code), vals),
            })
        ranking.append({
            "option_id": o["id"], "label": o["label"], "emv": emv,
            "margin": margin, "meets_threshold": meets,
            "chances": chances_out,
        })
    # ranking[0] 必须是最优方案：higher 时 EMV 最大在前，lower 时最小在前
    key = (lambda r: -r["emv"]) if higher else (lambda r: r["emv"])
    ranking.sort(key=key)
    best = ranking[0]

    # ---- 单因素敏感性（drivers）+ 翻转点 ----
    sens = spec.get("sensitivity") or {}
    drivers, switch_points, unscannable = [], [], []
    uncertainties = []
    emvs_by_var = {}
    for v in variables:
        vid = v["id"]
        probes = probe_values(v, sens) if sens.get("enabled", False) else None
        if probes is None:
            continue
        curve = {o["id"]: [option_emv(o, {vid: p}) for p in probes] for o in opts}
        emvs_by_var[vid] = {"probes": probes, "curve": curve}
        best_curve = curve[best["option_id"]]
        lo, hi = min(best_curve), max(best_curve)
        drivers.append({
            "var_id": vid, "label": var_by_id[vid]["label"],
            "probe_min": probes[0], "probe_max": probes[-1],
            "emv_low": lo, "emv_high": hi, "emv_base": best["emv"],
            "swing_abs": abs(hi - lo),
            "swing_pct": (abs(hi - lo) / abs(best["emv"])) if best["emv"] else None,
        })
        # 翻转点：相邻探测点间最优方案改变 → 二分逼近
        for i in range(len(probes) - 1):
            def argbest(x):
                scores = {o["id"]: option_emv(o, {vid: x}) for o in opts}
                if higher:
                    return max(scores, key=scores.get)
                return min(scores, key=scores.get)
            a, b = probes[i], probes[i + 1]
            if argbest(a) != argbest(b):
                lo_b, hi_b = a, b
                for _ in range(40):
                    mid = (lo_b + hi_b) / 2
                    if argbest(lo_b) == argbest(mid):
                        lo_b = mid
                    else:
                        hi_b = mid
                switch_points.append({
                    "var_id": vid, "label": var_by_id[vid]["label"],
                    "value": (lo_b + hi_b) / 2,
                    "on_side_1": argbest(a), "on_side_2": argbest(b),
                    "probe_low": a, "probe_high": b,
                })
    drivers = [d for d in drivers if d["swing_abs"] > 1e-10]
    drivers.sort(key=lambda d: -d["swing_abs"])
    for rank, d in enumerate(drivers, 1):
        d["rank"] = rank

    # ---- 双因素透视（sens2 显式指定，或默认摆幅最大的两个可扫变量）----
    # 被 overrides 钉死的变量不能当网格轴：网格的语义是「每格取最优方案」，
    # 而扫描会把各方案的 override 拉成同值、方案比较失效（价格档位比较应走 options）。
    sens2 = spec.get("sens2")
    grid = None
    ov_locked = set()
    for o in opts:
        ov_locked.update((o.get("overrides") or {}).keys())
    if sens2:
        for k in ("var_x", "var_y"):
            if sens2.get(k) in ov_locked:
                raise SpecError("E016", "sens2.%s（%s）被 options.overrides 钉死，"
                                "不能作为网格轴；定价档位比较请改用 options 表达"
                                % (k, sens2.get(k)))
    scan_ids = [d["var_id"] for d in drivers if d["var_id"] not in ov_locked]
    if sens2:
        vx, vy = sens2["var_x"], sens2["var_y"]
        sx = sens.get("steps", 6)
        px = probe_values(var_by_id[vx], {"steps": sx})
        py = probe_values(var_by_id[vy], {"steps": sx})
        if px and py:
            grid = {"var_x": vx, "var_y": vy, "x_values": px, "y_values": py,
                    "cells": []}
            for y in py:
                row = []
                for x in px:
                    scores = {o["id"]: option_emv(o, {vx: x, vy: y})
                              for o in opts}
                    bid = (max(scores, key=scores.get) if higher
                           else min(scores, key=scores.get))
                    row.append({"x": x, "y": y, "emv": scores[bid],
                                "best_option_id": bid, "scores": scores})
                grid["cells"].append(row)

    # ---- 假设与不确定性 ----
    assumptions = {"user_data": [], "user_assumption": [],
                   "industry_ref": [], "pending": []}
    for v in variables:
        line = "%s（%s）：%s" % (v["label"], v["id"],
                                v.get("source") or "未注明来源")
        assumptions.setdefault(v.get("source_class", "pending"), []).append(line)
    for a in spec.get("assumptions", []):
        assumptions["user_assumption"].append(str(a))
    for vid in unscannable:
        uncertainties.append("变量 %s 基准值为 0，无法做等比敏感性扫描；"
                             "如需扫描请改为 range 或 discrete 定义" % vid)
    if grid is None and sens2:
        uncertainties.append("sens2 指定的变量无法扫描，双因素透视表未生成")
    pending = [v["id"] for v in variables if v.get("source_class") == "pending"]
    if pending:
        uncertainties.append("以下变量来源为「待确认」，其结论随数据确认可能改变：%s"
                             % ", ".join(pending))
    if sum(v["kind"] != "fixed" for v in variables) > 1 and any(not o.get("chances") for o in opts):
        uncertainties.append("本模型按「变量分布独立」假设计算期望值；"
                             "若变量间强相关，请改用 chances 情境建模")
    if threshold is None:
        uncertainties.append("未设置 threshold（打正线），结论只有方案排序，"
                             "缺少「能不能做」的判断")

    return {
        "meta_summary": {
            "title": meta["title"], "decision_goal": meta["decision_goal"],
            "metric": meta["metric"], "unit": meta["unit"],
            "horizon": meta["horizon"],
            "threshold": threshold,
            "threshold_label": meta.get("threshold_label"),
            "higher_is_better": higher,
            "formula": spec["formula"],
        },
        "ranking": ranking,
        "recommended": {"option_id": best["option_id"], "label": best["label"],
                        "emv": best["emv"],
                        "margin": best["margin"],
                        "meets_threshold": best["meets_threshold"]},
        "drivers": drivers,
        "switch_points": switch_points,
        "sens2_grid": grid,
        "assumptions": assumptions,
        "uncertainties": uncertainties,
        "checks": {"prob_sums_ok": True, "formula_ok": True,
                   "options_count": len(opts), "variables_count": len(variables)},
    }


# ---------------------------------------------------------------- SVG 渲染

C_PURPLE, C_BLUE, C_WARN = "#a78bfa", "#38bdf8", "#f97316"
C_INK, C_MUTE, C_LINE, C_BG = "#1e293b", "#64748b", "#cbd5e1", "#f8fafc"


def _svg_head(w, h, title):
    return ("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"%d\" height=\"%d\" "
            "viewBox=\"0 0 %d %d\" font-family=\"PingFang SC, Microsoft YaHei, "
            "sans-serif\">\n<title>%s</title>\n<rect width=\"%d\" height=\"%d\" "
            "fill=\"white\"/>\n" % (w, h, w, h, esc(title), w, h))


def render_tree_svg(res):
    m = res["meta_summary"]
    ranking = res["ranking"]
    unit = m["unit"]
    n_ch = [len(r["chances"]) for r in ranking] or [1]
    block_hs = [72 + c * 54 + 18 for c in n_ch]
    H = 130 + sum(block_hs) + 60
    W = 1240
    out = [_svg_head(W, H, m["title"])]
    out.append("<text x=\"36\" y=\"40\" font-size=\"20\" font-weight=\"bold\" "
               "fill=\"%s\">决策树 · %s</text>" % (C_INK, esc(m["title"])))
    out.append("<text x=\"36\" y=\"64\" font-size=\"13\" fill=\"%s\">目标：%s ｜ "
               "指标：%s（%s，%s）</text>"
               % (C_MUTE, esc(m["decision_goal"]), esc(m["metric"]),
                  esc(unit), esc(m["horizon"])))
    rec_id = res["recommended"]["option_id"]
    thr = m.get("threshold")

    y = 100
    root_cy = y + sum(block_hs) / 2.0
    # root
    out.append("<rect x=\"36\" y=\"%.0f\" width=\"150\" height=\"64\" rx=\"8\" "
               "fill=\"%s\" stroke=\"%s\" stroke-width=\"2\"/>"
               % (root_cy - 32, "#ede9fe", C_PURPLE))
    out.append("<text x=\"111\" y=\"%.0f\" text-anchor=\"middle\" font-size=\"16\" "
               "font-weight=\"bold\" fill=\"%s\">决策</text>" % (root_cy - 6, C_INK))
    out.append("<text x=\"111\" y=\"%.0f\" text-anchor=\"middle\" font-size=\"11\" "
               "fill=\"%s\">选一个方案</text>" % (root_cy + 14, C_MUTE))

    scale_max = max((abs(r["emv"]) for r in ranking), default=1.0) or 1.0
    for r, bh in zip(ranking, block_hs):
        is_rec = r["option_id"] == rec_id
        oy = y + bh / 2.0
        # root -> option
        out.append("<line x1=\"186\" y1=\"%.0f\" x2=\"250\" y2=\"%.0f\" "
                   "stroke=\"%s\"/>" % (root_cy, oy, C_LINE))
        fill = "#f5f3ff" if is_rec else "white"
        stroke = C_PURPLE if is_rec else "#94a3b8"
        out.append("<rect x=\"250\" y=\"%.0f\" width=\"240\" height=\"64\" rx=\"8\" "
                   "fill=\"%s\" stroke=\"%s\" stroke-width=\"%d\"/>"
                   % (oy - 32, fill, stroke, 3 if is_rec else 1.5))
        tag = "★ 推荐" if is_rec else "方案"
        out.append("<text x=\"264\" y=\"%.0f\" font-size=\"11\" fill=\"%s\">%s</text>"
                   % (oy - 14, C_PURPLE if is_rec else C_MUTE, esc(tag)))
        out.append("<text x=\"264\" y=\"%.0f\" font-size=\"14\" font-weight=\"bold\" "
                   "fill=\"%s\">%s</text>" % (oy + 6, C_INK, esc(clip(r["label"], 16))))
        emv_txt = "%s %s" % (smart_num(r["emv"]), unit)
        meets_col = C_INK
        if r.get("meets_threshold") is False:
            meets_col = C_WARN
        elif r.get("meets_threshold"):
            meets_col = C_PURPLE
        out.append("<text x=\"264\" y=\"%.0f\" font-size=\"12\" fill=\"%s\">EMV = %s"
                   "</text>" % (oy + 24, meets_col, esc(emv_txt)))
        # option -> chances
        cy = y + 56
        for ch in (r["chances"] or [{"id": "-", "label": "变量分布加权期望",
                                     "prob": 1.0, "payoff": r["emv"]}]):
            cc = cy + 27
            out.append("<line x1=\"490\" y1=\"%.0f\" x2=\"560\" y2=\"%.0f\" "
                       "stroke=\"%s\"/>" % (oy, cc, C_LINE))
            out.append("<text x=\"525\" y=\"%.0f\" text-anchor=\"middle\" font-size=\"11\" "
                       "fill=\"%s\">p=%s</text>"
                       % (oy + (cc - oy) * 0.5 - 6, C_MUTE,
                          esc(smart_num(ch["prob"] * 100, 1) + "%")))
            out.append("<rect x=\"560\" y=\"%.0f\" width=\"330\" height=\"54\" "
                       "rx=\"7\" fill=\"%s\" stroke=\"%s\" stroke-width=\"1.2\"/>"
                       % (cc - 27, C_BG, "#94a3b8"))
            out.append("<text x=\"574\" y=\"%.0f\" font-size=\"12.5\" fill=\"%s\">%s"
                       "</text>" % (cc - 6, C_INK, esc(clip(ch.get("label") or ch.get("id") or "-", 18))))
            out.append("<text x=\"574\" y=\"%.0f\" font-size=\"11.5\" fill=\"%s\">%s%% ｜ "
                       "情境收益 %s %s</text>"
                       % (cc + 16, C_MUTE,
                          esc(smart_num(ch["prob"] * 100, 1)),
                          esc(smart_num(ch["payoff"])), esc(unit)))
            cy += 54
        # EMV 对比条
        bar_x, bar_w = 960, 220
        bw = max(6.0, abs(r["emv"]) / scale_max * bar_w)
        color = C_PURPLE if is_rec else C_BLUE
        if r.get("meets_threshold") is False:
            color = C_WARN
        out.append("<rect x=\"%d\" y=\"%.0f\" width=\"%.0f\" height=\"18\" rx=\"4\" "
                   "fill=\"%s\" opacity=\"0.85\"/>" % (bar_x, oy - 9, bw, color))
        out.append("<text x=\"%d\" y=\"%.0f\" font-size=\"11\" fill=\"%s\">%s</text>"
                   % (bar_x, oy - 14, C_MUTE, esc(clip(r["option_id"], 14))))
        y += bh
    # threshold 竖线
    if thr is not None and scale_max > 0:
        tx = 960 + abs(thr) / scale_max * 220
        if tx <= 960 + 220:
            ytop = 100
            ybot = y + 8
            out.append("<line x1=\"%.0f\" y1=\"%d\" x2=\"%.0f\" y2=\"%d\" "
                       "stroke=\"%s\" stroke-dasharray=\"5,4\"/>"
                       % (tx, ytop, tx, ybot, C_WARN))
            out.append("<text x=\"%.0f\" y=\"%d\" text-anchor=\"end\" font-size=\"11\" "
                       "fill=\"%s\">%s = %s</text>"
                       % (tx - 4, ytop - 6, C_WARN,
                          esc(m.get("threshold_label") or "阈值"), esc(smart_num(thr))))
    out.append("<text x=\"36\" y=\"%d\" font-size=\"11\" fill=\"%s\">情境收益 = 公式代入"
               "该情境变量值；EMV = Σ 概率×情境收益 − 方案固定成本（由 decision_engine.py"
               " 计算，概率和已校验 = 1）</text>" % (H - 18, C_MUTE))
    out.append("</svg>")
    return "".join(out)


def render_tornado_svg(res):
    m = res["meta_summary"]
    unit = m["unit"]
    drivers = res["drivers"]
    bars_end = 130 + len(drivers) * 56
    sw_pts = (res.get("switch_points") or [])[:4]
    # 画布高度按内容动态预留：条形区 + 基准标注 + 翻转点块 + 脚注
    H = bars_end + 92 + 20 * len(sw_pts)
    W = 1240
    out = [_svg_head(W, H, "敏感性分析 · %s" % m["title"])]
    out.append("<text x=\"36\" y=\"40\" font-size=\"20\" font-weight=\"bold\" "
               "fill=\"%s\">龙卷风图 · 对推荐方案「%s」的单因素敏感性</text>"
               % (C_INK, esc(clip(res["recommended"]["label"], 22))))
    out.append("<text x=\"36\" y=\"64\" font-size=\"13\" fill=\"%s\">条越长 = 该变量"
               "在指定区间内变化时，当前数值领先方案 EMV 变化越大；竖虚线 = 基准 EMV"
               "</text>" % (C_MUTE,))
    all_lo = min([d["emv_low"] for d in drivers] + [res["recommended"]["emv"]])
    all_hi = max([d["emv_high"] for d in drivers] + [res["recommended"]["emv"]])
    span = (all_hi - all_lo) or 1.0
    plot_x, plot_w = 300, 800
    base_x = plot_x + (res["recommended"]["emv"] - all_lo) / span * plot_w

    y = 130
    for d in drivers:
        cy = y + 22
        out.append("<text x=\"36\" y=\"%.0f\" font-size=\"13\" fill=\"%s\">%d. %s</text>"
                   % (cy + 2, C_INK, d["rank"], esc(clip(d["label"], 12))))
        sw = "摆幅 %s %s" % (smart_num(d["swing_abs"]), unit)
        if d.get("swing_pct") is not None:
            sw += "（%.0f%%）" % (d["swing_pct"] * 100)
        out.append("<text x=\"36\" y=\"%.0f\" font-size=\"11\" fill=\"%s\">%s</text>"
                   % (cy + 20, C_MUTE, esc(sw)))
        x1 = plot_x + (d["emv_low"] - all_lo) / span * plot_w
        x2 = plot_x + (d["emv_high"] - all_lo) / span * plot_w
        bx = plot_x + (d["emv_base"] - all_lo) / span * plot_w
        out.append("<rect x=\"%.0f\" y=\"%.0f\" width=\"%.0f\" height=\"20\" rx=\"3\" "
                   "fill=\"%s\"/>" % (x1, cy - 10, max(2.0, x2 - x1), C_BLUE))
        out.append("<rect x=\"%.0f\" y=\"%.0f\" width=\"%.0f\" height=\"20\" rx=\"3\" "
                   "fill=\"%s\"/>" % (bx, cy - 10, max(2.0, x2 - bx), C_PURPLE))
        out.append("<line x1=\"%.0f\" y1=\"%.0f\" x2=\"%.0f\" y2=\"%.0f\" "
                   "stroke=\"%s\" stroke-width=\"2\"/>"
                   % (bx, cy - 14, bx, cy + 14, C_INK))
        # 窄摆幅条两端标签会糊在一起：合并为一个区间标签居中显示
        if x2 - x1 < 80:
            out.append("<text x=\"%.0f\" y=\"%.0f\" text-anchor=\"middle\" "
                       "font-size=\"10.5\" fill=\"%s\">%s ~ %s</text>"
                       % ((x1 + x2) / 2, cy - 16, C_MUTE,
                          esc(smart_num(d["emv_low"])),
                          esc(smart_num(d["emv_high"]))))
        else:
            out.append("<text x=\"%.0f\" y=\"%.0f\" font-size=\"10.5\" fill=\"%s\">%s</text>"
                       % (x1, cy - 16, C_MUTE, esc(smart_num(d["emv_low"]))))
            out.append("<text x=\"%.0f\" y=\"%.0f\" font-size=\"10.5\" fill=\"%s\">%s</text>"
                       % (x2, cy - 16, C_MUTE, esc(smart_num(d["emv_high"]))))
        y += 56
    # 基准竖线
    ytop, ybot = 120, y
    out.append("<line x1=\"%.0f\" y1=\"%d\" x2=\"%.0f\" y2=\"%d\" stroke=\"%s\" "
               "stroke-dasharray=\"4,4\"/>" % (base_x, ytop, base_x, ybot, C_MUTE))
    out.append("<text x=\"%.0f\" y=\"%d\" font-size=\"11\" fill=\"%s\">基准 EMV %s</text>"
               % (base_x + 4, ybot + 16, C_MUTE,
                  esc(smart_num(res["recommended"]["emv"]) + " " + unit)))
    ly = bars_end + 46
    if sw_pts:
        out.append("<text x=\"36\" y=\"%d\" font-size=\"12.5\" fill=\"%s\">⚠ 结论翻转点："
                   "</text>" % (ly, C_WARN))
        ly += 22
        names = {r["option_id"]: r["label"] for r in res["ranking"]}
        for sp in sw_pts[:4]:
            out.append("<text x=\"36\" y=\"%d\" font-size=\"12\" fill=\"%s\">· %s = %s 时"
                       "推荐从「%s」变为「%s」</text>"
                       % (ly, C_INK, esc(sp["label"]), esc(smart_num(sp["value"], 3)),
                          esc(names.get(sp["on_side_1"], sp["on_side_1"])),
                          esc(names.get(sp["on_side_2"], sp["on_side_2"]))))
            ly += 20
    else:
        out.append("<text x=\"36\" y=\"%d\" font-size=\"12\" fill=\"%s\">扫描范围内未发现"
                   "推荐方案被反超的翻转点；有限网格不保证全域稳健</text>"
                   % (ly, C_INK))
    out.append("<text x=\"36\" y=\"%d\" font-size=\"11\" fill=\"%s\">紫 = 高于基准段，"
               "蓝 = 低于基准段；数字由 decision_engine.py 逐一重算 EMV 得到</text>"
               % (H - 14, C_MUTE))
    out.append("</svg>")
    return "".join(out)


def render_heatmap_svg(res):
    grid = res.get("sens2_grid")
    if not grid:
        return None
    m = res["meta_summary"]
    unit = m["unit"]
    xs, ys = grid["x_values"], grid["y_values"]
    emvs = [c["emv"] for row in grid["cells"] for c in row]
    lo, hi = min(emvs), max(emvs)
    span = (hi - lo) or 1.0
    cw, chh, ox, oy = 150, 64, 190, 130
    W = ox + cw * len(xs) + 40
    H = oy + chh * len(ys) + 90
    out = [_svg_head(W, H, "双因素敏感性 · %s" % m["title"])]
    out.append("<text x=\"36\" y=\"40\" font-size=\"20\" font-weight=\"bold\" fill=\"%s\">"
               "双因素透视表 · 每格取该变量组合下的最优方案 EMV</text>" % (C_INK,))
    out.append("<text x=\"36\" y=\"64\" font-size=\"13\" fill=\"%s\">行 = %s，列 = %s；"
               "颜色越深指标值越高；橙框 = 未达指定目标线</text>"
               % (C_MUTE, esc(_vlabel(res, grid["var_y"])),
                  esc(_vlabel(res, grid["var_x"]))))
    thr = m.get("threshold")
    for j, yv in enumerate(ys):
        yy = oy + j * chh
        out.append("<text x=\"%d\" y=\"%.0f\" text-anchor=\"end\" font-size=\"12\" "
                   "fill=\"%s\">%s</text>" % (ox - 12, yy + chh / 2 + 4, C_INK,
                                              esc(smart_num(yv, 3))))
        for i, xv in enumerate(xs):
            c = grid["cells"][j][i]
            t = (c["emv"] - lo) / span
            fill = _mix("#ede9fe", "#7c3aed", t)
            xx = ox + i * cw
            warn = thr is not None and (
                (c["emv"] < thr) if m.get("higher_is_better", True)
                else (c["emv"] > thr))
            out.append("<rect x=\"%.0f\" y=\"%.0f\" width=\"%d\" height=\"%d\" "
                       "fill=\"%s\" stroke=\"%s\" stroke-width=\"%d\"/>"
                       % (xx, yy, cw - 6, chh - 6, fill,
                          C_WARN if warn else "white", 3 if warn else 1))
            tc = "white" if t > 0.55 else C_INK
            out.append("<text x=\"%.0f\" y=\"%.0f\" font-size=\"12.5\" font-weight=\"bold\" "
                       "fill=\"%s\">%s</text>" % (xx + 12, yy + 26, tc,
                                                  esc(smart_num(c["emv"]))))
            out.append("<text x=\"%.0f\" y=\"%.0f\" font-size=\"11\" fill=\"%s\">%s</text>"
                       % (xx + 12, yy + 46, tc if t > 0.55 else C_MUTE,
                          esc("并列："+" / ".join(c["candidate_ids"]) if c.get("best_option_id") is None else _vlabel_opt(res, c["best_option_id"]))))
    for i, xv in enumerate(xs):
        out.append("<text x=\"%.0f\" y=\"%d\" font-size=\"12\" fill=\"%s\">%s</text>"
                   % (ox + i * cw + 12, oy - 12, C_INK, esc(smart_num(xv, 3))))
    out.append("<text x=\"36\" y=\"%d\" font-size=\"11\" fill=\"%s\">其余变量保持原模型定义；"
               "每格自动取 EMV 最优的方案（由 decision_engine.py 逐一重算）</text>"
               % (H - 20, C_MUTE))
    out.append("</svg>")
    return "".join(out)


def _vlabel(res, vid):
    for d in res["drivers"]:
        if d["var_id"] == vid:
            return d["label"]
    return vid


def _vlabel_opt(res, oid):
    for r in res["ranking"]:
        if r["option_id"] == oid:
            return clip(r["label"], 14)
    return oid


def _mix(c1, c2, t):
    def hx(c):
        return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
    a, b = hx(c1), hx(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def render_table_md(res):
    m = res["meta_summary"]
    unit = m["unit"]
    lines = ["# 敏感性分析表 · %s" % m["title"], ""]
    rec = res["recommended"]
    lines.append("- 推荐方案：**%s**（EMV = %s %s）"
                 % (rec["label"], smart_num(rec["emv"]), unit))
    if m.get("threshold") is not None:
        lines.append("- 打正线：%s = %s ｜ 安全边际：%s %s（%s）"
                     % (m.get("threshold_label") or "阈值",
                        smart_num(m["threshold"]), smart_num(rec["margin"] or 0),
                        unit,
                        "达标" if rec["meets_threshold"] else "未达标"))
    lines.append("")
    lines.append("## 单因素敏感性（按摆幅排序 = 关键影响因素排序）")
    lines.append("")
    lines.append("| # | 变量 | 扫描区间 | 推荐方案 EMV 范围（%s） | 摆幅 | 摆幅占比 |"
                 % unit)
    lines.append("|---|---|---|---|---|---|")
    for d in res["drivers"]:
        pct = "—" if d.get("swing_pct") is None else "%.0f%%" % (d["swing_pct"] * 100)
        lines.append("| %d | %s | %s ~ %s | %s ~ %s | %s | %s |"
                     % (d["rank"], d["label"], smart_num(d["probe_min"], 3),
                        smart_num(d["probe_max"], 3), smart_num(d["emv_low"]),
                        smart_num(d["emv_high"]), smart_num(d["swing_abs"]), pct))
    if res["switch_points"]:
        lines.append("")
        lines.append("## 结论翻转点")
        lines.append("")
        names = {r["option_id"]: r["label"] for r in res["ranking"]}
        for sp in res["switch_points"]:
            lines.append("- 当 **%s = %s** 时，推荐从「%s」变为「%s」"
                         % (sp["label"], smart_num(sp["value"], 3),
                            names.get(sp["on_side_1"], sp["on_side_1"]),
                            names.get(sp["on_side_2"], sp["on_side_2"])))
    grid = res.get("sens2_grid")
    if grid:
        lines.append("")
        lines.append("## 双因素透视表（行 = %s，列 = %s；格值 = 该组合下最优方案 EMV）"
                     % (_vlabel(res, grid["var_y"]), _vlabel(res, grid["var_x"])))
        lines.append("")
        head = "| %s \\ %s | %s |" % (
            _vlabel(res, grid["var_y"]), _vlabel(res, grid["var_x"]),
            " | ".join(smart_num(x, 3) for x in grid["x_values"]))
        lines.append(head)
        lines.append("|---|" + "---|" * (len(grid["x_values"]) + 1))
        for j, yv in enumerate(grid["y_values"]):
            cells = []
            for c in grid["cells"][j]:
                cells.append("%s（%s）" % (smart_num(c["emv"]),
                                          _vlabel_opt(res, c["best_option_id"])))
            lines.append("| %s | %s |" % (smart_num(yv, 3), " | ".join(cells)))
    lines.append("")
    lines.append("> 敏感性分析的价值不在把格子填满，而在你调某一个假设时，"
                 "能马上看到结论会往哪边翻。上表全部数值由 decision_engine.py 重算，"
                 "未经引擎的数字不得写入结论。")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main

OUT_FILES = ("decision-result.json", "decision-tree.svg",
             "sensitivity-tornado.svg", "sensitivity-table.md")


def main(argv=None):
    ap = argparse.ArgumentParser(description="决策模型引擎")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.spec):
        print("[E010] spec 文件不存在：%s" % args.spec, file=sys.stderr)
        return 1
    try:
        with open(args.spec, "r", encoding="utf-8") as f:
            raw = f.read()
        spec = json.loads(raw)
    except ValueError as e:
        print("[E001] spec 不是合法 JSON：%s" % e, file=sys.stderr)
        return 1
    except (IOError, OSError) as e:
        print("[E010] spec 读取失败：%s" % e, file=sys.stderr)
        return 1

    os.makedirs(args.outdir, exist_ok=True)
    existing = [f for f in OUT_FILES
                if os.path.exists(os.path.join(args.outdir, f))]
    if existing and not args.force:
        print("[E009] 输出目录已存在结果文件（%s）；确认覆盖请加 --force，"
              "或换一个 --outdir" % ", ".join(existing), file=sys.stderr)
        return 1

    try:
        validate(spec)
        res = solve(spec)
    except SpecError as e:
        print(str(e), file=sys.stderr)
        return 1

    def w(name, content):
        p = os.path.join(args.outdir, name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

    w("decision-result.json", json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    w("decision-tree.svg", render_tree_svg(res) + "\n")
    w("sensitivity-tornado.svg", render_tornado_svg(res) + "\n")
    w("sensitivity-table.md", render_table_md(res))
    hm = render_heatmap_svg(res)
    if hm:
        w("sensitivity-heatmap.svg", hm + "\n")

    rec = res["recommended"]
    print("OK 推荐方案：%s（EMV = %s %s）" % (rec["label"],
                                             smart_num(rec["emv"]),
                                             res["meta_summary"]["unit"]))
    if rec.get("meets_threshold") is not None:
        print("   打正判断：%s（安全边际 %s %s）"
              % ("达标" if rec["meets_threshold"] else "未达标",
                 smart_num(rec["margin"] or 0), res["meta_summary"]["unit"]))
    drv_txt = " > ".join(d["label"] for d in res["drivers"][:5]) or "—"
    print("   关键影响因素（按摆幅）：%s" % drv_txt)
    print("   输出目录：%s" % os.path.abspath(args.outdir))
    return 0


if __name__ == "__main__":
    print("请使用 scripts/run_verified.py 执行带输入检查的分析。", file=sys.stderr)
    sys.exit(2)
