import sys, copy
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import run_checked as checked
base={"meta":{"title":"校验","decision_goal":"比较基准收益","metric":"收益","unit":"元","horizon":"一期"},"variables":[{"id":"x","label":"数量","base":10,"kind":"fixed","source":"合成测试输入","source_class":"user_assumption"}],"options":[{"id":"a","label":"A"},{"id":"b","label":"B","fixed_cost":3}],"formula":"x * 2","evidence_policy":{"inputs_confirmed":True,"sensitivity_range_confirmed":True}}
passed=0
def rejected(d):
    global passed
    try: checked.check(d)
    except (ValueError,checked.engine.SpecError): passed+=1; return
    raise AssertionError("Expected failure")
d=copy.deepcopy(base);d["evidence_policy"]={};rejected(d)
d=copy.deepcopy(base);d["variables"][0]["source_class"]="pending";rejected(d)
d=copy.deepcopy(base);d["variables"][0].update(kind="range",low=5,high=15);rejected(d)
d=copy.deepcopy(base);d["variables"][0].update(kind="discrete",distribution=[[5,.5],[15,.5]]);d["variables"].append(dict(d["variables"][0],id="y"));rejected(d)
d=copy.deepcopy(base);d["formula"]="x/0";rejected(d)
checked.check(base)
r=checked.engine.solve(base)
assert r["ranking"][0]["emv"]==20
assert r["ranking"][1]["emv"]==17
passed+=1
print(str(passed)+"/6 evidence-gate and numeric checks passed; synthetic inputs only")
