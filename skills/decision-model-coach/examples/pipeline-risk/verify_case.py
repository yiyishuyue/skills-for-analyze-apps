"""Replay a published real-project model; not a prospective or blind test."""
import argparse,copy,json,sys,math
from pathlib import Path
from fractions import Fraction as F
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import run_verified as runner

def verify():
    here=Path(__file__).resolve().parent
    raw=json.loads((here/'source-data.json').read_text(encoding='utf-8'))
    spec=json.loads((here/'decision-spec.json').read_text(encoding='utf-8'))
    result=runner.check(spec)
    def scores(r):return {x['option_id']:x['emv'] for x in r['ranking']}
    got=scores(result); checks=[]
    def ok(condition,name):
        if not condition:raise AssertionError(name)
        checks.append({'name':name,'passed':True})
    def frac(x):return F(str(x))
    # Independent closed-form evaluation, without importing solver internals.
    for a in raw['alternatives']:
        expected=frac(a['response_cost'])+frac(a['failure_probability'])*(frac(a['delay'])*frac(raw['monthly_delay_value'])+frac(a['overrun']))
        ok(math.isclose(got[a['id']],float(expected),abs_tol=1e-9),a['id']+': matches independent exact-fraction calculation')
    ok(result['recommended']['option_id']=='survey','baseline chooses detailed survey')
    ok([x['option_id'] for x in result['ranking']]==['survey','technology','experts','nothing','all'],'all-five-alternative ranking')
    survey=next(x for x in result['ranking'] if x['option_id']=='survey')
    ok([x['payoff'] for x in survey['chances']]==[31,12],'response cost included exactly once in each scenario')
    # Survey vs technology: 12+.158*(2r+4) = 3+.158*(12r+22).
    boundary=(F(9)/F('0.158')-18)/10
    switches=[x for x in result['switch_points'] if {x['on_side_1'],x['on_side_2']}=={'survey','technology'}]
    ok(len(switches)==1 and abs(switches[0]['value']-float(boundary))<1e-7,'native sensitivity boundary matches independent algebra')
    for r,choice in [(0,'technology'),(3,'technology'),(5,'survey'),(7.5,'survey')]:
        d=copy.deepcopy(spec);d['sensitivity']={'enabled':False};d['variables'][-1]['base']=r
        ok(runner.check(d)['recommended']['option_id']==choice,'monthly delay value '+str(r)+': '+choice)
    # Probability stress: change both complementary branches, never one alone.
    q_boundary=(F('20.696')-12)/19
    prob_scan=[]
    for i in range(101):
        q=i/100;d=copy.deepcopy(spec);d['sensitivity']={'enabled':False}
        option=next(o for o in d['options'] if o['id']=='survey')
        option['chances'][0]['prob']=q;option['chances'][1]['prob']=1-q
        res=runner.check(d);prob_scan.append({'q':q,'candidate_ids':res['candidate_ids'],'survey_cost':scores(res)['survey']})
    ok(all(x['candidate_ids']==(['survey'] if x['q']<float(q_boundary) else ['technology']) for x in prob_scan),'101 complementary-probability scenarios match analytic choice')
    d=copy.deepcopy(spec);d['sensitivity']={'enabled':False};d['options'][1]['chances'][0]['prob']=float(q_boundary);d['options'][1]['chances'][1]['prob']=1-float(q_boundary)
    ok(set(runner.check(d)['candidate_ids'])=={'survey','technology'},'probability boundary reports numerical tie')
    # Explicit hypothetical constraint, not an observed project budget.
    d=copy.deepcopy(spec);d['options']=[o for o,a in zip(d['options'],raw['alternatives']) if a['response_cost']<=10]
    ok(runner.check(d)['recommended']['option_id']=='technology','upstream hypothetical upfront-cost cap=10 changes feasible choice')
    for name,mutate in [
        ('malformed probability sum',lambda d:d['options'][1]['chances'][0].update(prob=.9)),
        ('negative probability',lambda d:d['options'][1]['chances'][0].update(prob=-.1)),
        ('year/month unit injection violates declared domain',lambda d:d['variables'][-1].update(base=90)),
        ('pending evidence',lambda d:d['variables'][-1].update(source_class='pending'))]:
        d=copy.deepcopy(spec);mutate(d)
        try:runner.check(d)
        except (ValueError,runner.engine.SpecError):ok(True,'rejected '+name)
        else:raise AssertionError('did not reject '+name)
    # A plausible-looking bad formula cannot be generically rejected: the oracle catches it.
    d=copy.deepcopy(spec);d['formula']='response_cost + delay * monthly_value * 12 + overrun'
    wrong=runner.check(d)
    ok(abs(scores(wrong)['survey']-got['survey'])>1,'independent oracle detects annual/monthly formula mistake; generic gate alone does not')
    return raw,spec,result,{'case':'Dey 2001 pipeline laying','checks':checks,'passed':len(checks),'monthly_value_boundary':float(boundary),'survey_failure_probability_boundary':float(q_boundary),'probability_scan':prob_scan,'scope':'Published-model replay and model perturbations; not blind validation or actual future outcome evidence'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--outdir');args=ap.parse_args()
    raw,spec,r,audit=verify()
    if args.outdir:
        p=Path(args.outdir)
        if p.exists() and any(p.iterdir()):raise ValueError('Use a new empty output directory')
        p.mkdir(parents=True,exist_ok=True)
        for name,obj in [('source-data.json',raw),('input-spec.json',spec),('decision-result.json',r),('verification.json',audit)]:
            (p/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        (p/'decision-report.md').write_text(runner.report(r),encoding='utf-8')
        (p/'sensitivity-tornado.svg').write_text(runner.engine.render_tornado_svg(r).replace('EMV',r['score_label']),encoding='utf-8')
    print(json.dumps({'checks_passed':audit['passed'],'scores':{x['option_id']:round(x['emv'],6) for x in r['ranking']},'monthly_value_boundary':audit['monthly_value_boundary'],'probability_boundary':audit['survey_failure_probability_boundary']},ensure_ascii=False))
if __name__=='__main__':main()
