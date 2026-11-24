"""Verified entry point; Python standard library only."""
import argparse, ast, hashlib, json, math, sys
from pathlib import Path
import decision_engine as engine

def need(ok, why):
    if not ok: raise ValueError(why)

def num(x):
    need(type(x) in (int,float) and math.isfinite(x), "数值须有限且不能是布尔值")
    return float(x)

def finite(x):
    if isinstance(x,float): need(math.isfinite(x),"非有限数")
    elif isinstance(x,dict):
        for y in x.values(): finite(y)
    elif isinstance(x,list):
        for y in x: finite(y)

def check(spec):
    finite(spec); engine.validate(spec)
    p=spec.get("evidence_policy",{})
    need(p.get("inputs_confirmed") is True,"须核对输入与口径")
    need(type(spec["meta"].get("higher_is_better",True)) is bool,"排序方向须为布尔值")
    if spec["meta"].get("threshold") is not None: num(spec["meta"]["threshold"])
    sens=spec.get("sensitivity",{})
    enabled=sens.get("enabled",False)
    need(type(enabled) is bool,"enabled须为布尔值")
    steps=sens.get("steps",7)
    need(type(steps) is int and 2<=steps<=31,"steps须为2至31的整数")
    locked=set(); chance=False
    for o in spec["options"]:
        num(o.get("fixed_cost",0))
        need(spec["meta"].get("higher_is_better",True) or o.get("fixed_cost",0)==0,"最小化目标请把全部成本写入公式，fixed_cost须为0")
        need("chances" not in o or bool(o["chances"]),"chances不能为空")
        need(not o.get("children"),"不支持递归树")
        locked.update(o.get("overrides",{}))
        for ch in o.get("chances",[]):
            chance=True;num(ch["prob"])
            need(not ch.get("children"),"不支持递归树")
            locked.update(ch.get("values",{}))
        tree=ast.parse(o.get("formula",spec["formula"]),mode="eval")
        need(len(list(ast.walk(tree)))<=100,"公式过于复杂")
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                need(isinstance(node.func,ast.Name) and node.func.id in engine.SAFE_FUNCS,"函数不在白名单")
            if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Pow):
                need(isinstance(node.right,ast.Constant) and type(node.right.value) in (int,float) and abs(node.right.value)<=8,"幂指数须为绝对值不超过8的常数")
    stochastic=0;combos=1;scanned=[]
    for v in spec["variables"]:
        need(v["source_class"]!="pending","待确认参数不能产生正式推荐")
        base=num(v["base"]); values=[base]
        if v["kind"]=="range":
            need(p.get("uniform_ranges_confirmed") is True,"区间不自动等于均匀分布")
            n=v.get("steps",6);need(type(n) is int and 2<=n<=31,"区间steps须为2至31")
            values.extend([num(v["low"]),num(v["high"])])
            need(v["low"]<=base<=v["high"],"基准超出区间")
            stochastic+=1;combos*=n
        elif v["kind"]=="discrete":
            for x,w in v["distribution"]: values.append(num(x));num(w)
            stochastic+=1;combos*=len(v["distribution"])
        if enabled and v.get("scan"):
            lo,hi=num(v["scan"]["low"]),num(v["scan"]["high"])
            need(lo<hi and lo<=base<=hi,"扫描范围须递增且包含基准")
            need(v["id"] not in locked,"不得扫描被方案/情景锁定的变量")
            need(bool(v["scan"].get("source")),"扫描需依据")
            values.extend([lo,hi]);scanned.append(v["id"])
        for o in spec["options"]:
            if v["id"] in o.get("overrides",{}): values.append(num(o["overrides"][v["id"]]))
            for ch in o.get("chances",[]):
                if v["id"] in ch.get("values",{}): values.append(num(ch["values"][v["id"]]))
        if "domain" in v:
            need(isinstance(v["domain"],list) and len(v["domain"])==2,"domain须为[下界,上界]")
            lo,hi=map(num,v["domain"])
            need(lo<=hi and all(lo<=x<=hi for x in values),"超出业务有效范围")
    need(not enabled or scanned,"启用敏感性须给出scan")
    if spec.get("sens2"):
        need(enabled and all(spec["sens2"][k] in scanned for k in ("var_x","var_y")),"二维轴须有scan")
        need(spec["sens2"]["var_x"]!=spec["sens2"]["var_y"],"二维轴不能相同")
    if stochastic>1 and any(not o.get("chances") for o in spec["options"]):
        need(p.get("independence_confirmed") is True,"独立性未确认")
    need(combos*len(spec["options"])*(1+len(scanned)*steps*45+(steps*steps if len(scanned)>1 else 0))<=2000000,"联合展开过大")
    try: r=engine.solve(spec);finite(r)
    except Exception as e: raise ValueError("计算失败："+str(e)) from e
    r["engine_version"]="1.4.1"
    r["input_sha256"]=hashlib.sha256(json.dumps(spec,sort_keys=True,ensure_ascii=False,allow_nan=False).encode("utf-8")).hexdigest()
    r["evaluation_kind"]="expected_value" if stochastic or chance else "baseline"
    r["score_label"]="假设条件下的期望值" if stochastic or chance else "基准情景值"
    if any(x["kind"]=="range" for x in spec["variables"]):r["score_label"]="假设条件下的近似期望值"
    best=r["ranking"][0]["emv"]
    r["candidate_ids"]=[o["option_id"] for o in r["ranking"] if math.isclose(o["emv"],best,rel_tol=1e-9,abs_tol=1e-9)]
    r["recommendation_status"]="numerical_tie" if len(r["candidate_ids"])>1 else "highest_modeled_score"
    if len(r["candidate_ids"])>1:r["recommended"]=None
    r["limitations"]=["计算排名不是市场验证或风险效用判断。","emv保留为兼容字段，语义见score_label。","有限网格可能漏掉非单调反转；没有发现反转不代表全域稳健。"]
    if any(x["kind"]=="range" for x in spec["variables"]):r["limitations"].append("range按有限等距节点等权近似；非线性公式下不是连续均匀分布的精确积分，需检查节点数敏感性。")
    if r["sens2_grid"]:
        for row in r["sens2_grid"]["cells"]:
            for cell in row:
                cell["candidate_ids"]=[key for key,score in cell["scores"].items() if math.isclose(score,cell["emv"],rel_tol=1e-9,abs_tol=1e-9)]
                if len(cell["candidate_ids"])>1:cell["best_option_id"]=None
    return r

def report(r):
    s=["# "+r["meta_summary"]["title"],"",r["score_label"]+" / "+r["meta_summary"]["unit"],
       "候选："+", ".join(r["candidate_ids"]),"状态："+r["recommendation_status"],""]
    for o in r["ranking"]:
        s.append("- "+o["label"].replace("\n"," ")+"："+str(o["emv"]))
        if o["meets_threshold"] is not None:s.append("  达到指定目标线："+str(o["meets_threshold"]))
        for ch in o["chances"]:s.append("  情景："+str(ch["label"])+"；概率="+str(ch["prob"])+"；公式毛结果="+str(ch["payoff"])+"（固定成本另扣）")
    s+=["","敏感性："]+([d["label"]+"；摆幅="+str(d["swing_abs"]) for d in r["drivers"]] or ["未运行或无非零变化，不报告关键因素。"])
    for sp in r["switch_points"]:
        s.append("探测到的推荐边界："+sp["label"]+" ≈ "+str(sp["value"])+"；"+sp["on_side_1"]+" / "+sp["on_side_2"]+"（有限扫描近似）")
    s+=["","输入摘要校验值："+r["input_sha256"],"", "数据与假设："]
    for kind,lines in r["assumptions"].items():s.extend(kind+"："+line for line in lines)
    s+=["","限制："]+r["uncertainties"]+r["limitations"]
    return "\n".join(s)+"\n"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--spec",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    try:
        spec=json.loads(Path(a.spec).read_text(encoding="utf-8-sig"));r=check(spec)
        dest=Path(a.outdir);need(not dest.exists() or not any(dest.iterdir()),"输出目录非空，请选新目录")
        dest.mkdir(parents=True,exist_ok=True)
        (dest/"input-spec.json").write_text(json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        (dest/"decision-result.json").write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        (dest/"decision-report.md").write_text(report(r),encoding="utf-8")
        text=[r["score_label"]]+[o["label"]+" : "+str(o["emv"]) for o in r["ranking"]]
        svg='<svg xmlns="http://www.w3.org/2000/svg" width="900" height="'+str(60+45*len(text))+'"><rect width="100%" height="100%" fill="#faf8fc"/>'
        svg+="".join('<text x="20" y="'+str(35+45*i)+'" font-size="16">'+engine.esc(t)+'</text>' for i,t in enumerate(text))+"</svg>"
        (dest/"option-comparison.svg").write_text(svg,encoding="utf-8")
        if r["recommended"] and r["drivers"]:(dest/"sensitivity-tornado.svg").write_text(engine.render_tornado_svg(r).replace("EMV",engine.esc(r["score_label"])),encoding="utf-8")
        if r["sens2_grid"]:(dest/"sensitivity-heatmap.svg").write_text(engine.render_heatmap_svg(r).replace("EMV",engine.esc(r["score_label"])),encoding="utf-8")
        print("OK "+r["score_label"]+" 候选="+",".join(r["candidate_ids"]));return 0
    except Exception as e:print("[MODEL_GATE] "+str(e),file=sys.stderr);return 1
if __name__=="__main__":sys.exit(main())
