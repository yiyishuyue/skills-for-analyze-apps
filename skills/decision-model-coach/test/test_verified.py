import sys,copy,unittest,json,tempfile,subprocess,os
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import run_verified as v
def base():
    return {"meta":{"title":"合成回归","decision_goal":"比较方案","metric":"收益","unit":"元","horizon":"一期"},"variables":[{"id":"x","label":"数量","base":6,"kind":"fixed","source":"合成输入","source_class":"user_assumption"}],"options":[{"id":"a","label":"A"},{"id":"b","label":"B","formula":"5"}],"formula":"x","evidence_policy":{"inputs_confirmed":True}}
class Verified(unittest.TestCase):
    def reject(self,fn):
        d=base();fn(d)
        with self.assertRaises(Exception):v.check(d)
    def test_baseline_no_noise(self):
        r=v.check(base());self.assertEqual(r["evaluation_kind"],"baseline");self.assertEqual(r["drivers"],[]);self.assertIsNone(r["sens2_grid"]);self.assertFalse(any("独立" in s for s in r["uncertainties"]))
    def test_no_confirmation(self):self.reject(lambda d:d.update(evidence_policy={}))
    def test_pending(self):self.reject(lambda d:d["variables"][0].update(source_class="pending"))
    def test_nan(self):self.reject(lambda d:d["variables"][0].update(base=float("nan")))
    def test_bool_number(self):self.reject(lambda d:d["variables"][0].update(base=True))
    def test_division_zero(self):self.reject(lambda d:d.update(formula="x/0"))
    def test_function_whitelist(self):self.reject(lambda d:d.update(formula="x()"))
    def test_exponent_limit(self):self.reject(lambda d:d.update(formula="x ** 999999"))
    def test_bad_probability(self):
        self.reject(lambda d:d["options"][0].update(chances=[{"id":"s","label":"事件","prob":.8,"values":{"x":2}}]))
    def test_range_not_probability(self):self.reject(lambda d:d["variables"][0].update(kind="range",low=2,high=10))
    def test_two_randoms_not_independent(self):
        def change(d):
            d["variables"][0].update(kind="discrete",distribution=[[2,.5],[10,.5]])
            d["variables"].append(dict(d["variables"][0],id="y"))
        self.reject(change)
    def test_discrete_expectation(self):
        d=base();d["variables"][0].update(kind="discrete",distribution=[[2,.25],[10,.75]])
        r=v.check(d);self.assertEqual(r["evaluation_kind"],"expected_value");self.assertEqual(r["ranking"][0]["emv"],8)
    def test_uniform_explicit(self):
        d=base();d["variables"][0].update(kind="range",low=2,high=10,steps=2);d["evidence_policy"]["uniform_ranges_confirmed"]=True
        self.assertEqual(v.check(d)["ranking"][0]["emv"],6)
    def test_tie(self):
        d=base();d["options"][1]["formula"]="6";r=v.check(d)
        self.assertIsNone(r["recommended"]);self.assertEqual(len(r["candidate_ids"]),2)
    def test_minimize(self):
        d=base();d["meta"]["higher_is_better"]=False
        self.assertEqual(v.check(d)["recommended"]["option_id"],"b")
    def test_overridden_formula_payoffs(self):
        d=base();d["options"][0].update(formula="x*3",fixed_cost=1,chances=[{"id":"s","label":"S","prob":.5,"values":{"x":1}},{"id":"t","label":"T","prob":.5,"values":{"x":3}}])
        a=next(r for r in v.check(d)["ranking"] if r["option_id"]=="a")
        self.assertEqual(a["emv"],5);self.assertEqual([c["payoff"] for c in a["chances"]],[3,9])
    def test_scan_requires_range(self):self.reject(lambda d:d.update(sensitivity={"enabled":True}))
    def test_scan_domain(self):
        def change(d):
            d["sensitivity"]={"enabled":True};d["variables"][0].update(domain=[0,10],scan={"low":0,"high":12,"source":"合成范围"})
        self.reject(change)
    def test_locked_variable(self):
        def change(d):
            d["sensitivity"]={"enabled":True};d["variables"][0]["scan"]={"low":2,"high":10,"source":"测试"};d["options"][0]["overrides"]={"x":7}
        self.reject(change)
    def test_valid_scan(self):
        d=base();d["sensitivity"]={"enabled":True,"steps":7};d["variables"][0]["scan"]={"low":2,"high":8,"source":"合成范围"}
        r=v.check(d);self.assertTrue(r["drivers"]);self.assertTrue(r["switch_points"]);self.assertAlmostEqual(r["switch_points"][0]["value"],5,places=6)
    def test_deterministic(self):self.assertEqual(v.check(base()),v.check(base()))
    def test_cost_minimization_uses_complete_formula(self):
        d=base();d["meta"]["higher_is_better"]=False;d["options"][0]["formula"]="x+3"
        self.assertEqual(v.check(d)["ranking"][1]["emv"],9)
    def test_minimize_no_implicit_cost_subtraction(self):
        self.reject(lambda d:(d["meta"].update(higher_is_better=False),d["options"][0].update(fixed_cost=3)))
    def test_domain_checks_scenario(self):
        self.reject(lambda d:(d["variables"][0].update(domain=[0,10]),d["options"][0].update(chances=[{"id":"s","label":"S","prob":1,"values":{"x":11}}])))
    def test_correlated_joint_states(self):
        d=base();d["variables"].append(dict(d["variables"][0],id="y"));d["formula"]="x*y"
        d["options"][0]["chances"]=[{"id":"s","label":"同低","prob":.5,"values":{"x":2,"y":2}},{"id":"t","label":"同高","prob":.5,"values":{"x":10,"y":10}}]
        self.assertEqual(v.check(d)["ranking"][0]["emv"],52)
    def test_independent_product(self):
        d=base();d["variables"][0].update(kind="discrete",distribution=[[2,.5],[10,.5]])
        d["variables"].append(dict(d["variables"][0],id="y"));d["formula"]="x*y";d["evidence_policy"]["independence_confirmed"]=True
        self.assertEqual(v.check(d)["ranking"][0]["emv"],36)
    def test_zero_swing_can_still_have_switch(self):
        d=base();d["options"][1]["formula"]="7";d["sensitivity"]={"enabled":True};d["variables"][0]["scan"]={"low":2,"high":10,"source":"合成范围"}
        r=v.check(d);self.assertEqual(r["drivers"],[]);self.assertTrue(r["switch_points"]);self.assertIn("推荐边界",v.report(r))
    def test_no_automatic_two_axis(self):
        d=base();d["variables"].append(dict(d["variables"][0],id="y"));d["formula"]="x+y";d["sensitivity"]={"enabled":True}
        for x in d["variables"]:x["scan"]={"low":2,"high":10,"source":"合成范围"}
        self.assertIsNone(v.check(d)["sens2_grid"])
    def test_two_axis_tie(self):
        d=base();d["variables"].append(dict(d["variables"][0],id="y"));d["formula"]="x+y";d["options"][1]["formula"]="x+y";d["sensitivity"]={"enabled":True,"steps":2};d["sens2"]={"var_x":"x","var_y":"y"}
        for x in d["variables"]:x["scan"]={"low":2,"high":10,"source":"合成范围"}
        r=v.check(d);self.assertTrue(all(c["best_option_id"] is None for row in r["sens2_grid"]["cells"] for c in row));self.assertIn("并列",v.engine.render_heatmap_svg(r))
    def test_threshold_does_not_mean_feasibility(self):
        d=base();d["meta"].update(threshold=10,threshold_label="目标值")
        r=v.check(d);self.assertFalse(r["ranking"][0]["meets_threshold"]);self.assertIn("False",v.report(r))
    def test_provenance_hash_changes(self):
        d=base();before=v.check(d)["input_sha256"];d["variables"][0]["source"]="另一份合成来源"
        self.assertNotEqual(before,v.check(d)["input_sha256"])
    def test_cli_artifacts_and_refuse_overwrite(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);d=base();d["options"][0]["label"]="<A & B>"
            spec=root/"spec.json";spec.write_text(json.dumps(d),encoding="utf-8");out=root/"out"
            cmd=[sys.executable,"-S",str(Path(v.__file__)),"--spec",str(spec),"--outdir",str(out)]
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONIOENCODING="utf-8")
            first=subprocess.run(cmd,capture_output=True,env=env)
            self.assertEqual(first.returncode,0,first.stderr.decode("utf-8"));ET.parse(out/"option-comparison.svg")
            self.assertEqual(json.loads((out/"input-spec.json").read_text(encoding="utf-8")),d)
            self.assertFalse((out/"sensitivity-tornado.svg").exists());self.assertFalse((out/"sensitivity-heatmap.svg").exists())
            self.assertEqual(subprocess.run(cmd,capture_output=True,env=env).returncode,1)
    def test_cli_invalid_produces_no_result(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);d=base();d["formula"]="x/0";spec=root/"spec.json";spec.write_text(json.dumps(d),encoding="utf-8");out=root/"out"
            r=subprocess.run([sys.executable,"-S",str(Path(v.__file__)),"--spec",str(spec),"--outdir",str(out)],capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1"))
            self.assertEqual(r.returncode,1);self.assertFalse(out.exists())
if __name__=="__main__":unittest.main()
