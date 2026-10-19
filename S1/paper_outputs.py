"""Numerical tables1-5 and figure1-3 outputs from verified per-seed records.
This command recalculates summaries; it is NOT a fresh selection experiment.
"""
from __future__ import annotations
import argparse,json,math,shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import pandas as pd
from revision import stats
from reportlab.graphics.shapes import Drawing,String,Line,Circle
from reportlab.graphics import renderPDF
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
import pypdfium2 as pdfium

def write(out,name,data):
    (data if isinstance(data,pd.DataFrame) else pd.DataFrame(data)).to_csv(out/name,index=False,encoding="utf-8-sig")

def figure2(cells,out):
    """Regenerate the revised large-cell heatmap; rounding affects labels only."""
    width,height=486,350
    c=canvas.Canvas(str(out/"figure2.pdf"),pagesize=(width,height))
    def txt(x,y,t,size=9,anchor="center",color=(0,0,0)):
        c.setFont("Times-Roman",size);c.setFillColorRGB(*color)
        if anchor=="right":c.drawRightString(x,y,str(t))
        elif anchor=="left":c.drawString(x,y,str(t))
        else:c.drawCentredString(x,y,str(t))
    def rgb(v):
        z=min(abs(v)/15.1,1);base=(.18,.37,.65) if v<0 else (.69,.14,.18)
        return tuple(1-z*(1-q) for q in base)
    txt(width/2,338,"M versus B2 | mean paired test TC difference | n=100",10)
    txt(width/2,324,"Hatching: 95% CI includes zero. Color indicates the mean direction only.",8.5)
    for row,scenario in enumerate(["abrupt","gradual"]):
        for col,changed in enumerate([5,9,13]):
            x0=col*162+27;top=290-row*142;cw,ch=24,22
            txt(col*162+84,top+12,f"{scenario.title()} | {changed}/30 ({changed/30:.1%})",9)
            for r,k in enumerate([1,3,5]):
                yy=top-(r+1)*ch;txt(x0-5,yy+7,k,9,"right")
                for j,lam in enumerate([0,.25,.5,1,2]):
                    z=cells[(cells.scenario==scenario)&(cells.changed_skus==changed)&
                            (cells.budget_k==k)&(cells["lambda"]==lam)].iloc[0]
                    v=float(z.mean_difference);xx=x0+j*cw
                    c.setFillColorRGB(*rgb(v));c.setStrokeColorRGB(1,1,1);c.setLineWidth(.35)
                    c.rect(xx,yy,cw,ch,fill=1,stroke=1)
                    if z.ci95_low<=0<=z.ci95_high:
                        c.saveState();clip=c.beginPath();clip.rect(xx,yy,cw,ch);c.clipPath(clip,stroke=0,fill=0)
                        c.setStrokeColorRGB(.7,.7,.7);c.setLineWidth(.3)
                        for offset in range(-25,35,5):c.line(xx+offset,yy,xx+offset+ch,yy+ch)
                        c.restoreState()
                    txt(xx+cw/2,yy+7,"0.0" if abs(v)<.05 else f"{v:.1f}",10.5,
                        color=(1,1,1) if abs(v)>8 else (0,0,0))
            txt(col*162+7,top-39,"K",9)
            for j,lam in enumerate([0,.25,.5,1,2]):txt(x0+j*cw+cw/2,top-80,f"{lam:g}",9)
            txt(col*162+84,top-94,"Movement cost \u03bb",9)
    bx,bw,by=114,258,25
    for i in range(258):
        c.setFillColorRGB(*rgb(-15.1+30.2*i/257));c.rect(bx+i,by,1.1,8,fill=1,stroke=0)
    txt(bx,12,"\u221215.1 (M lower)",8.5)
    txt(bx+bw/2,12,"0",8.5);txt(bx+bw,12,"+15.1 (B2 lower)",8.5)
    c.showPage();c.save()
    doc=pdfium.PdfDocument(out/"figure2.pdf");page=doc[0];bitmap=page.render(scale=400/72)
    im=bitmap.to_pil();im.save(out/"figure2.png",dpi=(400,400));im.close();bitmap.close();page.close();doc.close()

def figure3(summary,out):
    d=Drawing(864,310)
    def txt(x,y,t,size=10,anchor="middle"):
        d.add(String(x,y,str(t),fontName="Helvetica",fontSize=size,textAnchor=anchor))
    txt(432,291,"Five retail cases: paired M-minus-B2 test TC (bars: complete case range)",14)
    low=min(-10,math.floor(summary["min"].min()/10)*10)
    high=max(10,math.ceil(summary["max"].max()/10)*10)
    for ci,lam in enumerate([0,.25,.5,1,2]):
        x0=48+ci*164;top=250;bottom=70;w=125
        py=lambda v:bottom+(v-low)/(high-low)*(top-bottom)
        txt(x0+w/2,267,"lambda="+str(lam))
        for tick in range(low,high+1,10):
            yy=py(tick)
            d.add(Line(x0,yy,x0+w,yy,strokeColor=HexColor("#dddddd"),strokeWidth=.5))
            if ci==0:txt(x0-7,yy-3,tick,9,"end")
        points=[]
        for k in [1,3,5]:
            r=summary[(summary.budget_k==k)&(summary["lambda"]==lam)].iloc[0]
            xx=x0+12+(k-1)/4*(w-24);points.append((xx,py(r["mean"])))
            color=HexColor("#225ea8")
            d.add(Line(xx,py(r["min"]),xx,py(r["max"]),strokeColor=color))
            for v in [r["min"],r["max"]]:d.add(Line(xx-4,py(v),xx+4,py(v),strokeColor=color))
            d.add(Circle(xx,py(r["mean"]),2.4,fillColor=color,strokeColor=color))
            txt(xx,50,k,10)
        for a,b in zip(points,points[1:]):d.add(Line(*a,*b,strokeColor=HexColor("#225ea8")))
    txt(432,24,"Budget K; negative differences favor M. Bars are not confidence intervals.",11)
    pdf=out/"figure3.pdf";renderPDF.drawToFile(d,str(pdf))
    doc=pdfium.PdfDocument(pdf);page=doc[0];bitmap=page.render(scale=300/72)
    im=bitmap.to_pil();im.save(out/"figure3.png",dpi=(300,300));im.close();bitmap.close();page.close();doc.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary",type=Path,required=True)
    p.add_argument("--cohorts",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    b=pd.read_csv(a.primary/"sensitivity_budget_effects_100seeds.csv")
    b=b[b.metric.eq("TC")]
    rows=[]
    for scenario in ["abrupt","gradual"]:
        for count in [5,9,13]:
            rec={"scenario":scenario,"changed_skus":count}
            for lo,hi in [(1,3),(3,5)]:
                g=b[(b.scenario==scenario)&(b.changed_skus==count)&(b.lower_budget==lo)&(b.higher_budget==hi)]
                assert len(g)==5
                rec.update({f"K{hi}-K{lo}_CI_below_zero":int((g.ci95_high<0).sum()),
                            f"K{hi}-K{lo}_CI_above_zero":int((g.ci95_low>0).sum()),
                            f"K{hi}-K{lo}_CI_includes_zero":int(((g.ci95_low<=0)&(g.ci95_high>=0)).sum())})
            rows.append(rec)
    write(out,"table1_budget_interval_counts.csv",rows)
    c=pd.read_csv(a.cohorts/"cost_decomposition.csv")
    write(out,"table2_cost_components.csv",c[(c.strategy!="B0")|(c.K==1)])
    trace=pd.read_csv(ROOT/"results/decision_trace.csv")
    write(out,"table3_decision_trace.csv",trace)
    q=pd.read_csv(ROOT/"results/batch_detail.csv")
    assert len(q)==3600
    qr=[];reference=pd.read_csv(ROOT/"results/batch_contrasts.csv")
    for (scenario,capacity),g in q[q.strategy=="M"].groupby(["scenario","Q"]):
        w=g.pivot(index="seed",columns="K",values="total_cost")
        assert len(w)==100
        for lo,hi in [(1,3),(3,5)]:
            s=stats(w[hi]-w[lo])
            r=reference[(reference.scenario==scenario)&(reference.Q==capacity)&
                        (reference.kind=="budget")&(reference.contrast==f"K{hi}-K{lo}")].iloc[0]
            for key in ["mean","sd","ci_low","ci_high"]:assert abs(s[key]-r[key])<1e-10
            qr.append({"scenario":scenario,"Q":capacity,"contrast":f"K{hi}-K{lo}",**s})
    write(out,"table4_capacity_budget_contrasts.csv",qr)
    co=pd.read_csv(a.cohorts/"cohort_contrasts.csv")
    co=co[(co.metric=="total_cost")&(co["lambda"]==1)&co.scenario.isin(["abrupt","gradual"])&
          ((co.kind=="budget")|((co.contrast=="M-B2")&co.K.isin([1,5])))]
    assert len(co)==24
    write(out,"table5_seed_cohorts.csv",co)
    # Export regenerated figures1-2 with their complete plotted values.
    for index,stem in [(1,"figure_budget_response_100seeds")]:
        for ext in ["pdf","png"]:shutil.copy2(a.primary/"figures"/(stem+"."+ext),out/(f"figure{index}."+ext))
    f1=pd.read_csv(a.primary/"sensitivity_strategy_summary_100seeds.csv")
    write(out,"figure1_values.csv",f1[f1.strategy=="M"])
    f2=pd.read_csv(a.primary/"sensitivity_paired_comparisons_100seeds.csv")
    f2=f2[(f2.metric=="TC")&(f2.comparator=="B2")]
    assert len(f2)==90
    write(out,"figure2_values.csv",f2)
    old=pd.read_csv(ROOT/"figures/figure2_cells.csv")
    for r in old.itertuples():
        z=f2[(f2.scenario==r.scenario)&(f2.changed_skus==r.changed_skus)&
             (f2.budget_k==r.K)&(f2["lambda"]==r.lambda_cost)].iloc[0]
        assert abs(r.mean-z.mean_difference)<1e-10
        assert abs(r.ci_low-z.ci95_low)<1e-10 and abs(r.ci_high-z.ci95_high)<1e-10
        assert r.hatched==bool(z.ci95_low<=0<=z.ci95_high)
    figure2(f2,out)
    real=pd.read_csv(ROOT/"frozen/optional/reference/real_data_results.csv")
    assert len(real)==375
    rr=real[real.strategy.isin(["M","B2"])].pivot(index=["case_id","budget_k","lambda"],columns="strategy",values="total_cost")
    diff=(rr.M-rr.B2).rename("M_minus_B2_TC").reset_index()
    assert len(diff)==75
    write(out,"figure3_case_differences.csv",diff)
    summary=diff.groupby(["budget_k","lambda"]).M_minus_B2_TC.agg(["mean","min","max"]).reset_index()
    write(out,"figure3_values.csv",summary);figure3(summary,out)
    report={"status":"PASS","mode":"statistics from archived outcomes","table_count":5,"figure_count":3,
            "Q2_budget_contrasts_independently_recomputed":8,"Figure2_means_intervals_masks_checked":90,
            "retail_pairs_checked":75,"fresh_selection_experiments":0,
            "table3_source":"archived trace, selection frozen before posthoc test evaluation",
            "figures":"numerically reproduced; font/layout may differ from manuscript presentation copies"}
    (out/"PAPER_OUTPUTS_REPORT.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report),flush=True)
if __name__=="__main__":main()

