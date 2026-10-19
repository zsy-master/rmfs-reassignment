"""English entry point for the frozen RMFS reviewer package (CPython 3.12.14).
Run: python review.py --help
All numerical algorithms and original reference assets remain in frozen/.
"""
from __future__ import annotations
import argparse,hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def integrity():
    lock=json.loads((ROOT/"SHA256SUMS.json").read_text(encoding="utf-8"))
    for relative,expected in lock.items():
        path=(ROOT/relative).resolve()
        if ROOT not in path.parents or not path.is_file() or digest(path)!=expected:
            raise ValueError("Package hash mismatch or missing file: "+relative)
    return len(lock)

def compare_q2(output,seeds):
    """Compare fresh paths and outcomes; hardware timing is deliberately excluded."""
    comparisons={}
    for seed in seeds:
        original=json.loads((ROOT/f"results/batch_units/{seed}.json").read_text(encoding="utf-8"))
        current=json.loads((output/f"batch_units/{seed}.json").read_text(encoding="utf-8"))
        if current["rows"]!=original["rows"]:
            raise ValueError(f"Q2 outcomes differ for seed {seed}")
        for scenario in ("abrupt","gradual"):
            for key in ("M_pairs","M_decision_records","instance_fingerprint"):
                if current["paths"][scenario][key]!=original["paths"][scenario][key]:
                    raise ValueError(f"Q2 path mismatch: {seed}/{scenario}/{key}")
    comparisons["seed_paths_checked"]=len(seeds)
    if len(seeds)==100:
        import pandas as pd
        keys={
            "batch_detail.csv":["seed","scenario","Q","K","lambda_cost","strategy"],
            "batch_summary.csv":["scenario","Q","K","strategy"],
            "batch_contrasts.csv":["scenario","Q","kind","K","contrast"]}
        for name,key in keys.items():
            actual=pd.read_csv(output/name).sort_values(key).reset_index(drop=True)
            expected=pd.read_csv(ROOT/"results"/name).sort_values(key).reset_index(drop=True)
            pd.testing.assert_frame_equal(actual,expected,check_dtype=False,check_exact=False,rtol=1e-12,atol=1e-10)
            comparisons[name]=len(actual)
    return comparisons

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=["check","statistics","smoke","primary","q2","retail","runtime"])
    p.add_argument("--output",type=Path,help="New output folder OUTSIDE the S1 package")
    p.add_argument("--workers",type=int,default=min(4,os.cpu_count() or 1))
    p.add_argument("--raw",type=Path,help="Original UCI online_retail_II.xlsx (retail mode)")
    a=p.parse_args()
    if a.mode!="check" and a.output is None:p.error("--output is required")
    if a.mode=="retail" and a.raw is None:p.error("--raw is required for retail mode")
    if not 1<=a.workers<=(os.cpu_count() or 1):p.error("invalid worker count")
    n=integrity()
    env=os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"]="1"
    env["PYTHONIOENCODING"]="utf-8"
    if platform.python_version()!="3.12.14":
        print("NOTE: verified RNG environment is CPython 3.12.14; current="+platform.python_version(),flush=True)
    if a.mode=="check":
        subprocess.run([sys.executable,"-B",str(ROOT/"revision.py"),"preflight"],cwd=ROOT,env=env,check=True)
        print(json.dumps({"status":"PASS","mode":"check","package_files_checked":n,"searches_executed":0}))
        return
    out=a.output.resolve()
    if out==ROOT or ROOT in out.parents:p.error("output must be outside the package")
    out.mkdir(parents=True,exist_ok=False)
    report={"status":"RUNNING","mode":a.mode,"python":sys.version,"platform":platform.platform(),
            "workers":a.workers,"package_files_checked":n,"steps":[]}
    started=time.perf_counter()
    def save():
        (out/"REVIEW_REPORT.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    def call(script,*arguments,expected=None):
        cmd=[sys.executable,"-B",str(ROOT/script),*map(str,arguments)]
        print("\nRunning: "+script+" "+" ".join(map(str,arguments)),flush=True)
        subprocess.run(cmd,cwd=ROOT,env=env,check=True)
        if expected:
            r=json.loads((out/expected).read_text(encoding="utf-8"))
            if r.get("status")!="PASS":raise ValueError("Incomplete or failed report: "+expected)
        report["steps"].append({"script":script,"arguments":list(map(str,arguments)),"completed":True})
        save()
    save()
    try:
        call("revision.py","preflight")
        if a.mode=="statistics":
            call("frozen/reproduce.py","verify","--scope","all","--figures","--output",out/"primary",expected="primary/REPRODUCTION_REPORT.json")
            call("revision.py","aggregate","--output",out/"cohorts",expected="cohorts/aggregate_report.json")
            call("paper_outputs.py","--primary",out/"primary","--cohorts",out/"cohorts","--output",out/"paper",expected="paper/PAPER_OUTPUTS_REPORT.json")
        elif a.mode=="smoke":
            call("frozen/reproduce.py","fresh","--scope","one","--seed","2026092401","--workers",a.workers,
                 "--output",out/"primary",expected="primary/REPRODUCTION_REPORT.json")
            call("revision.py","batch","--pilot","--workers",a.workers,"--output",out/"q2",expected="q2/batch_pilot_report.json")
            call("revision.py","trace","--output",out/"trace",expected="trace/trace_report.json")
            report["Q2_reference_comparisons"]=compare_q2(out/"q2",[2026092401])
            report["fresh_Q2_first_seed_matches_archive"]=True
        elif a.mode=="primary":
            call("frozen/reproduce.py","fresh","--scope","all","--figures","--workers",a.workers,
                 "--output",out/"primary",expected="primary/REPRODUCTION_REPORT.json")
            call("revision.py","aggregate","--output",out/"cohorts",expected="cohorts/aggregate_report.json")
            call("paper_outputs.py","--primary",out/"primary","--cohorts",out/"cohorts","--output",out/"paper",expected="paper/PAPER_OUTPUTS_REPORT.json")
            report["Q2_in_paper_outputs"]="archived Q2 per-seed records; use q2 mode for fresh Q2 search"
        elif a.mode=="q2":
            call("revision.py","batch","--workers",a.workers,"--output",out/"q2",expected="q2/batch_report.json")
            report["Q2_reference_comparisons"]=compare_q2(out/"q2",list(range(2026092401,2026092501)))
        elif a.mode=="retail":
            raw=a.raw.resolve()
            call("revision.py","cases","--raw",raw,"--output",out/"metadata",expected="metadata/case_report.json")
            call("frozen/optional/real_data.py","--raw",raw,"--output",out/"cases",expected="cases/REPRODUCTION_REPORT.json")
        elif a.mode=="runtime":
            call("frozen/optional/benchmark.py","--scope","all","--output",out/"runtime",expected="runtime/BENCHMARK_REPORT.json")
        report.update(status="PASS",elapsed_seconds=time.perf_counter()-started)
        save();print(json.dumps(report,indent=2),flush=True)
    except BaseException as error:
        report.update(status="FAIL",error=repr(error),elapsed_seconds=time.perf_counter()-started)
        save();raise
if __name__=="__main__":main()

