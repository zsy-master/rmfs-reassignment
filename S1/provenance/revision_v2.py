"""Supplementary revision analyses; frozen primary files are read-only.

Run with Python 3.12 using the dependencies in frozen/requirements.txt.
No SciPy dependency is required: Student-t critical values use the exact
cosine-integral recurrence for integer degrees of freedom and bisection;
the pooled100 calculation retains the frozen historical critical constant.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,math,os,platform,statistics,sys,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent
FROZEN=ROOT/'frozen'
OUT=ROOT/'results'
sys.path.insert(0,str(FROZEN))
import pandas as pd
import numpy as np
from instances import build_instances_for_seed,load_config,derived_seed,fingerprint
from rmfs_core import (EPS,apply_swap,batch_orders,select_budgeted_batching_aware,
                       enumerate_cross_pod_swaps,select_association_greedy)
from reproduce import check_assets
BUDGETS=(1,3,5)
SEEDS=tuple(range(2026092401,2026092501))
SCENARIOS=('abrupt','gradual')
LAM=1.0
RAW_HASH='bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def csv(p,rows):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 (rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)).to_csv(p,index=False,encoding='utf-8-sig')
def t_cdf(t,df):
 if t<0:return 1-t_cdf(-t,df)
 theta=math.atan(t/math.sqrt(df));c=math.cos(theta);s=math.sin(theta);n=df-1
 start=0 if n%2==0 else 1
 integ=theta if start==0 else s
 for k in range(start+2,n+1,2):integ=s*c**(k-1)/k+(k-1)*integ/k
 return .5+math.exp(math.lgamma((df+1)/2)-math.lgamma(df/2))/math.sqrt(math.pi)*integ
def tcrit(df):
 # Preserve the historical 100-seed critical value exactly.
 if df==99:return 1.9842169515086827
 lo,hi=0.,16.
 for _ in range(80):
  mid=(lo+hi)/2
  if t_cdf(mid,df)<.975:lo=mid
  else:hi=mid
 return (lo+hi)/2
def stats(values):
 values=list(map(float,values));n=len(values)
 assert n>=2 and all(math.isfinite(v) for v in values)
 mean=statistics.mean(values);sd=statistics.stdev(values);half=tcrit(n-1)*sd/math.sqrt(n)
 return {'n':n,'df':n-1,'mean':mean,'sd':sd,'ci_low':mean-half,'ci_high':mean+half,
         'wins':sum(v < -EPS for v in values),'ties':sum(abs(v)<=EPS for v in values),
         'losses':sum(v>EPS for v in values)}
def preflight():
 assert abs(tcrit(99)-1.9842169515086827)<1e-11
 assert abs(tcrit(29)-2.045229642132703)<1e-11
 assert abs(tcrit(69)-1.9949454151072374)<1e-11
 protocol=json.loads((ROOT/'protocol.json').read_text(encoding='utf-8'))
 checked=0;omitted=0
 for rel,digest in protocol['frozen_source_manifest'].items():
  path=FROZEN/rel
  if rel.startswith(('.idea/','.venv/')) and not path.exists():omitted+=1;continue
  assert sha(path)==digest,rel
  checked+=1
 check_assets()
 return {'status':'PASS','python':sys.version,'platform':platform.platform(),
         'frozen_files_checked':checked,'optional_local_files_omitted':omitted,'tcrit':{n:tcrit(n-1) for n in [30,70,100]},
         'protocol_sha256':sha(ROOT/'protocol.json'),'supplement_source_sha256':sha(__file__)}
def main_detail():
 d=pd.read_csv(FROZEN/'reference/formal_detail_100seeds.csv',keep_default_na=False)
 assert len(d)==22500 and d.seed.nunique()==100
 assert not d.duplicated(['seed','scenario','budget_k','lambda','strategy']).any()
 assert np.allclose(d.total_cost,d.pv_test+d['lambda']*d.movement,rtol=0,atol=1e-10)
 assert (d.movement==2*d.n_swaps).all()
 return d
def aggregate():
 report=preflight();out=OUT;d=main_detail()
 lock=json.loads((FROZEN/'reference/ORIGINAL_SEED_LOCK.json').read_text(encoding='utf-8'))
 groups=[('original30',lock['old_seeds']),('added70',lock['added_seeds']),('pooled100',lock['all_seeds'])]
 contrasts=[];summaries=[]
 for cohort,seeds in groups:
  g=d[d.seed.isin(seeds)]
  assert g.seed.nunique()==len(seeds)
  for key,a in g.groupby(['scenario','budget_k','lambda','strategy'],sort=True):
   rec=dict(zip(['scenario','K','lambda','strategy'],key),cohort=cohort)
   for col,prefix in [('pv_test','pv'),('n_swaps','swaps'),('movement','movement'),('total_cost','tc')]:
    rec.update({prefix+'_'+k:v for k,v in stats(a[col]).items() if k not in ['wins','ties','losses']})
   rec['movement_charge_mean']=float((a['lambda']*a.movement).mean())
   summaries.append(rec)
  for (scenario,k,lam),a in g.groupby(['scenario','budget_k','lambda']):
   for metric in ['total_cost','pv_test']:
    w=a.pivot(index='seed',columns='strategy',values=metric).reindex(seeds)
    assert not w.isna().any().any()
    for comp in ['B0','B1','B2','B3']:
     contrasts.append({'cohort':cohort,'scenario':scenario,'K':k,'lambda':lam,'kind':'method',
      'contrast':'M-'+comp,'metric':metric,**stats(w.M-w[comp])})
  for (scenario,lam),a in g[g.strategy.eq('M')].groupby(['scenario','lambda']):
   for metric in ['total_cost','pv_test']:
    w=a.pivot(index='seed',columns='budget_k',values=metric).reindex(seeds)
    for low,high in [(1,3),(3,5)]:
     contrasts.append({'cohort':cohort,'scenario':scenario,'K':high,'lambda':lam,'kind':'budget',
      'contrast':f'K{high}-K{low}','metric':metric,**stats(w[high]-w[low])})
 c=pd.DataFrame(contrasts);s=pd.DataFrame(summaries)
 csv(out/'cohort_contrasts.csv',c);csv(out/'cohort_strategy_summary.csv',s)
 pooled=c[c.cohort.eq('pooled100')]
 old=pd.read_csv(FROZEN/'reference/paired_comparisons_100seeds.csv')
 budget=pd.read_csv(FROZEN/'reference/budget_effects_100seeds.csv')
 errors=[]
 for r in pooled.itertuples():
  metric='TC' if r.metric=='total_cost' else 'PV'
  if r.kind=='method':
   q=old[(old.scenario==r.scenario)&(old.budget_k==r.K)&(old['lambda']==c.loc[r.Index,'lambda'])&
         (old.comparator==r.contrast[2:])&(old.metric==metric)]
  else:
   low=int(r.contrast.split('-K')[1]);high=r.K
   q=budget[(budget.scenario==r.scenario)&(budget['lambda']==c.loc[r.Index,'lambda'])&
            (budget.lower_budget==low)&(budget.higher_budget==high)&(budget.metric==metric)]
  assert len(q)==1
  for v,ref in [(r.mean,'mean_difference'),(r.sd,'sd_difference'),(r.ci_low,'ci95_low'),(r.ci_high,'ci95_high')]:
   errors.append(abs(v-float(q.iloc[0][ref])))
 assert max(errors)<1e-9,max(errors)
 index_cols=['scenario','K','lambda','kind','contrast','metric']
 m=c.pivot(index=index_cols,columns='cohort',values='mean')
 weight_error=(m.pooled100-.3*m.original30-.7*m.added70).abs().max()
 assert weight_error<1e-10
 representative=s[(s.cohort=='pooled100')&s.scenario.isin(SCENARIOS)&(s['lambda']==LAM)&s.strategy.isin(['B0','B2','M'])].copy()
 representative['budget_increment']='';representative['budget_difference_mean']=np.nan
 representative['budget_ci_low']=np.nan;representative['budget_ci_high']=np.nan
 for idx,r in representative.iterrows():
  if r.strategy=='M' and r.K>1:
   z=pooled[(pooled.scenario==r.scenario)&(pooled['lambda']==LAM)&(pooled.K==r.K)&
     (pooled.kind=='budget')&(pooled.metric=='total_cost')].iloc[0]
   representative.loc[idx,['budget_increment','budget_difference_mean','budget_ci_low','budget_ci_high']]=[z.contrast,z['mean'],z.ci_low,z.ci_high]
 csv(out/'cost_decomposition.csv',representative)
 sel=c[(c['lambda']==LAM)&c.scenario.isin(SCENARIOS)&c.metric.eq('total_cost')&
       ((c.kind.eq('budget'))|((c.contrast.isin(['M-B0','M-B2']))&c.K.isin([1,5])))]
 csv(out/'representative_cohorts.csv',sel)
 report.update(status='PASS',pooled_numeric_checks=len(errors),max_difference=max(errors),
               weighted_mean_error=float(weight_error),cohort_contrasts=len(c),
               cohort_summary_rows=len(s),new_simulations=0)
 save(out/'aggregate_report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
def apply_pairs(layout,pairs):
 for pair in pairs:layout=apply_swap(layout,tuple(pair))
 return layout
def q_unit(seed):
 config=load_config(FROZEN/'protocol_config.json')
 insts=build_instances_for_seed(seed,config,.3)
 check=json.loads((FROZEN/f'reference/checkpoints/seed_{seed}_changed_9.json').read_text(encoding='utf-8'))
 rows=[];paths={}
 for scenario in SCENARIOS:
  inst=insts[scenario];ref=check['scenarios'][scenario]
  assert inst.instance_fingerprint==ref['instance_fingerprint']
  assert inst.initial_fingerprint==ref['initial_fingerprint']
  before=time.perf_counter()
  chosen=select_budgeted_batching_aware(inst.initial_layout,inst.decision_orders,2,5,LAM,len(inst.test_orders))
  search_seconds=time.perf_counter()-before
  pairs=[list(r.sku_pair) for r in chosen.swaps]
  paths[scenario]={'M_pairs':pairs,'M_decision_records':[vars(r) for r in chosen.swaps],
                   'seconds':search_seconds,'instance_fingerprint':inst.instance_fingerprint}
  # Only now, after selection is fixed, evaluate test orders on the frozen prefixes.
  cache={}
  for k in BUDGETS:
   strategies={'B0':[],'B2':ref['B2']['pairs'][:k],'M':pairs[:k]}
   for name,path in strategies.items():
    layout=apply_pairs(inst.initial_layout,path)
    if layout not in cache:cache[layout]=batch_orders(inst.test_orders,layout,2).pod_visits
    pv=cache[layout];m=2*len(path)
    rows.append(dict(seed=seed,scenario=scenario,Q=2,K=k,lambda_cost=LAM,strategy=name,
       pv_test=pv,n_swaps=len(path),movement=m,movement_charge=LAM*m,total_cost=pv+LAM*m,
       final_layout=json.dumps(layout,separators=(',',':')),swap_sequence=json.dumps(path,separators=(',',':')),
       initial_fingerprint=inst.initial_fingerprint,instance_fingerprint=inst.instance_fingerprint))
 return {'seed':seed,'Q':2,'lambda':LAM,'paths':paths,'rows':rows,'protocol_sha256':sha(ROOT/'protocol.json')}
def batch(workers=4,pilot=False):
 preflight()
 out=OUT/'batch_units';out.mkdir(parents=True,exist_ok=True)
 seeds=SEEDS[:1] if pilot else SEEDS
 pending=[];payloads=[]
 for seed in seeds:
  f=out/f'{seed}.json'
  if f.exists():
   p=json.loads(f.read_text(encoding='utf-8'))
   assert p['protocol_sha256']==sha(ROOT/'protocol.json') and p['seed']==seed
   assert p['Q']==2 and len(p['rows'])==18
   payloads.append(p)
  else:pending.append(seed)
 with ProcessPoolExecutor(max_workers=workers) as pool:
  futures={pool.submit(q_unit,s):s for s in pending}
  for fut in as_completed(futures):
   p=fut.result();save(out/f'{p["seed"]}.json',p);payloads.append(p)
   print(f'Q2 completed {len(payloads)}/{len(seeds)}; seed={p["seed"]}',flush=True)
 if pilot:
  save(OUT/'batch_pilot_report.json',{'status':'PASS','seed':seeds[0],
       'scenarios':SCENARIOS,'new_searches':2,'seconds':{s:payloads[0]['paths'][s]['seconds'] for s in SCENARIOS}})
  return
 q2=pd.DataFrame([r for p in sorted(payloads,key=lambda v:v['seed']) for r in p['rows']])
 assert len(q2)==1800 and not q2.duplicated(['seed','scenario','Q','K','strategy']).any()
 primary=main_detail()
 q4=primary[(primary['lambda']==LAM)&primary.scenario.isin(SCENARIOS)&primary.strategy.isin(['B0','B2','M'])].rename(columns={'budget_k':'K','lambda':'lambda_cost'}).copy()
 q4['Q']=4;q4['movement_charge']=q4.lambda_cost*q4.movement
 allrows=pd.concat([q2,q4[q2.columns]],ignore_index=True)
 assert len(allrows)==3600 and allrows.groupby(['seed','scenario']).instance_fingerprint.nunique().eq(1).all()
 assert np.allclose(allrows.total_cost,allrows.pv_test+allrows.movement_charge,atol=1e-12)
 assert (allrows.movement==2*allrows.n_swaps).all() and (allrows.n_swaps<=allrows.K).all()
 for (seed,scenario,q,strategy),g in allrows.groupby(['seed','scenario','Q','strategy']):
  previous=[]
  for r in g.sort_values('K').itertuples():
   seq=json.loads(r.swap_sequence);assert seq[:len(previous)]==previous
   previous=seq
 summaries=[];contrasts=[]
 for key,g in allrows.groupby(['scenario','Q','K','strategy']):
  rec=dict(zip(['scenario','Q','K','strategy'],key))
  rec.update({'pv_mean':g.pv_test.mean(),'swaps_mean':g.n_swaps.mean(),
              'movement_charge_mean':g.movement_charge.mean(),'tc_mean':g.total_cost.mean()})
  summaries.append(rec)
 for (scenario,q),g in allrows[allrows.strategy.eq('M')].groupby(['scenario','Q']):
  w=g.pivot(index='seed',columns='K',values='total_cost').reindex(SEEDS)
  for lo,hi in [(1,3),(3,5)]:contrasts.append(dict(scenario=scenario,Q=q,kind='budget',K=hi,contrast=f'K{hi}-K{lo}',**stats(w[hi]-w[lo])))
 for (scenario,q,k),g in allrows.groupby(['scenario','Q','K']):
  w=g.pivot(index='seed',columns='strategy',values='total_cost').reindex(SEEDS)
  for b in ['B0','B2']:contrasts.append(dict(scenario=scenario,Q=q,kind='method',K=k,contrast='M-'+b,**stats(w.M-w[b])))
 csv(OUT/'batch_detail.csv',allrows);csv(OUT/'batch_summary.csv',summaries)
 csv(OUT/'batch_contrasts.csv',contrasts)
 report=preflight();report.update(status='PASS',new_search_units=200,total_rows=3600,Q2_rows=1800,
    Q4_rows_reused=1800,seeds=100,main_protocol_unchanged=True,selection_interfaces_exclude_test=True)
 save(OUT/'batch_report.json',report);print(json.dumps(report),flush=True)
def trace():
 preflight();config=load_config(FROZEN/'protocol_config.json')
 seed=SEEDS[0];scenario='gradual';inst=build_instances_for_seed(seed,config,.3)[scenario]
 # Freeze entire selection before passing any test order to the evaluator.
 selection=select_budgeted_batching_aware(inst.initial_layout,inst.decision_orders,4,5,LAM,400)
 layouts=[inst.initial_layout];records=[]
 for rec in selection.swaps:
  layouts.append(apply_swap(layouts[-1],rec.sku_pair))
  records.append({'step':rec.step,'pair':json.dumps(rec.sku_pair),'decision_delta_pv':rec.value_before-rec.value_after,
      'predicted_gross_saving':rec.marginal_gain,'movement_charge':2*LAM,'predicted_net_saving':rec.score,'action':'accept'})
 if len(records)<5:
  layout=selection.layout;pv=batch_orders(inst.decision_orders,layout,4).pod_visits
  candidates=[]
  for pair in enumerate_cross_pod_swaps(layout):
   nxt=apply_swap(layout,pair);delta=pv-batch_orders(inst.decision_orders,nxt,4).pod_visits
   candidates.append((2*delta-2*LAM,pair,delta))
  best=sorted(candidates,key=lambda v:(-v[0],v[1]))[0];assert best[0]<=EPS
  records.append({'step':len(selection.swaps)+1,'pair':json.dumps(best[1]),'decision_delta_pv':best[2],
    'predicted_gross_saving':2*best[2],'movement_charge':2*LAM,'predicted_net_saving':best[0],'action':'stop_score'})
 else:records.append({'step':6,'pair':'','action':'stop_budget'})
 frozen_at=time.time()
 test_pv=[batch_orders(inst.test_orders,l,4).pod_visits for l in layouts]
 for i,rec in enumerate(records):
  if rec['action']=='accept':
   rec['realized_gross_saving']=test_pv[i]-test_pv[i+1]
   rec['realized_net_saving']=rec['realized_gross_saving']-2*LAM
   rec['test_pv_after']=test_pv[i+1]
  else:rec.update(realized_gross_saving=None,realized_net_saving=None,test_pv_after=test_pv[-1])
 main=main_detail();ref=main[(main.seed==seed)&(main.scenario==scenario)&(main.budget_k==5)&(main['lambda']==LAM)&(main.strategy=='M')].iloc[0]
 assert json.loads(ref.swap_sequence)==[list(r.sku_pair) for r in selection.swaps]
 assert ref.pv_test==test_pv[-1]
 csv(OUT/'decision_trace.csv',records)
 save(OUT/'trace_report.json',{'status':'PASS','seed':seed,'scenario':scenario,'Q':4,'lambda':LAM,'K':5,
  'initial_test_pv':test_pv[0],'final_test_pv':test_pv[-1],'actual_swaps':len(selection.swaps),
  'final_TC':test_pv[-1]+2*LAM*len(selection.swaps),'selection_frozen_before_test_evaluation':True,
  'accepted_prefixes_evaluated_posthoc':True,'rejected_candidates_test_evaluated':False,'frozen_at_epoch':frozen_at})
 print('TRACE PASS',records,flush=True)
def real_cases(raw):
 preflight();raw=Path(raw);assert sha(raw)==RAW_HASH
 spec=importlib.util.spec_from_file_location('rev_common',FROZEN/'optional/_common.py')
 common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
 legacy=common.load_legacy('run_real_data_validation');legacy.RAW_XLSX=raw
 print('Cleaning public workbook with frozen function',flush=True)
 baskets,cleaning=legacy.read_and_clean()
 cases,selection=legacy.make_cases(baskets)
 expected=pd.read_csv(FROZEN/'optional/reference/real_data_cases.csv')
 assert len(cases)==len(expected)==5
 rows=[];bounds=[];mapping=[];orders=[];used=set()
 for case in cases:
  cid=case['case_id'];assert case['fingerprint']==expected.loc[expected.case_id.eq(cid),'case_fingerprint'].iloc[0]
  begin=case['cursor_start'];cal=list(range(begin,begin+5000));selected=set(case['selected_codes'])
  eligible=[]
  for idx in range(begin+5000,len(baskets)):
   if len(selected.intersection(baskets[idx]['skus']))>=2:
    eligible.append(idx)
    if len(eligible)==1000:break
  windows={'calibration':cal,'initial':eligible[:400],'decision':eligible[400:600],'test':eligible[600:]}
  code_to_id={c:i for i,c in case['id_to_code'].items()}
  for window,indices in windows.items():
   assert indices
   for pos,idx in enumerate(indices,1):
    b=baskets[idx];assert b['invoice'] not in used;used.add(b['invoice'])
    rows.append(dict(case_id=cid,window=window,global_cleaned_basket_position=idx+1,
       position_in_window=pos,invoice=b['invoice'],timestamp=b['date'].isoformat()))
    if window!='calibration':
     ids=sorted(code_to_id[c] for c in b['skus'] if c in code_to_id)
     orders.append(dict(case_id=cid,window=window,order_id=pos,invoice=b['invoice'],skus=json.dumps(ids)))
   first,last=baskets[indices[0]],baskets[indices[-1]]
   bounds.append(dict(case_id=cid,window=window,n=len(indices),first_invoice=first['invoice'],last_invoice=last['invoice'],
      first_global_position=indices[0]+1,last_global_position=indices[-1]+1,
      start=first['date'].isoformat(),end=last['date'].isoformat()))
  for i,stock in case['id_to_code'].items():mapping.append(dict(case_id=cid,sku_id=i,StockCode=stock))
 csv(OUT/'case_invoice_membership.csv',rows)
 csv(OUT/'case_boundaries.csv',bounds)
 csv(OUT/'case_stockcodes.csv',mapping)
 csv(OUT/'case_projected_orders.csv',orders)
 csv(OUT/'case_dates.csv',expected)
 save(OUT/'case_report.json',{'status':'PASS','source_sha256':RAW_HASH,'cleaning':cleaning,
      'cases':5,'case_fingerprints_match':True,'membership_rows':len(rows),'projected_orders':len(orders),
      'invoice_nonoverlap':True,'CustomerID_exported':False,'source_reference':'https://doi.org/10.24432/C5CG6D'})
 print('CASES PASS',len(rows),len(orders),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['preflight','aggregate','batch','trace','cases'])
 parser.add_argument('--workers',type=int,default=4);parser.add_argument('--pilot',action='store_true');parser.add_argument('--raw',type=Path)
 parser.add_argument('--output',type=Path,help='Output directory; use a fresh folder for fresh Q2 searches')
 args=parser.parse_args()
 if args.output is not None:OUT=args.output.resolve()
 OUT.mkdir(parents=True,exist_ok=True)
 if args.command=='preflight':print(json.dumps(preflight(),ensure_ascii=False))
 elif args.command=='aggregate':aggregate()
 elif args.command=='batch':batch(args.workers,args.pilot)
 elif args.command=='trace':trace()
 elif args.command=='cases':
  if args.raw is None:parser.error('--raw is required for cases')
  real_cases(args.raw)
