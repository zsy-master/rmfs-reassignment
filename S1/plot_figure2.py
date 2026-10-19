from pathlib import Path
import json,math,hashlib
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import Color
import pypdfium2 as pdfium
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'figures';OUT.mkdir(exist_ok=True)
F=ROOT/'frozen'/'reference'/'sensitivity_paired_comparisons_100seeds.csv'
d=pd.read_csv(F);d=d[(d.metric=='TC')&(d.comparator=='B2')].copy()
assert len(d)==90
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/times.ttf'),help='Times-compatible TrueType font')
args=parser.parse_args()
pdfmetrics.registerFont(TTFont('PaperTimes',str(args.font)))
W,H=486,350
p=OUT/'figure2.pdf';c=canvas.Canvas(str(p),pagesize=(W,H))
def txt(x,y,t,size=9,anchor='center',color=(0,0,0)):
 c.setFont('PaperTimes',size);c.setFillColorRGB(*color)
 if anchor=='center':c.drawCentredString(x,y,str(t))
 elif anchor=='right':c.drawRightString(x,y,str(t))
 else:c.drawString(x,y,str(t))
def rgb(v):
 z=min(abs(v)/15.1,1);base=(.18,.37,.65) if v<0 else (.69,.14,.18)
 return tuple(1-z*(1-q) for q in base)
txt(W/2,338,'M versus B2 | mean paired test TC difference | n=100',10)
txt(W/2,324,'Hatching: 95% CI includes zero. Color indicates the mean direction only.',8.5)
plotted=[]
for i,scenario in enumerate(['abrupt','gradual']):
 for j,changed in enumerate([5,9,13]):
  x0=j*162+27;top=290-i*142;cw,ch=24,22
  txt(j*162+84,top+12,f'{scenario.title()} | {changed}/30 ({changed/30:.1%})',9)
  for r,k in enumerate([1,3,5]):
   yy=top-(r+1)*ch;txt(x0-5,yy+7,k,9,'right')
   for col,lam in enumerate([0,.25,.5,1,2]):
    a=d[(d.scenario==scenario)&(d.changed_skus==changed)&(d.budget_k==k)&(d['lambda']==lam)]
    assert len(a)==1;a=a.iloc[0];v=float(a.mean_difference);lo=float(a.ci95_low);hi=float(a.ci95_high);hat=lo<=0<=hi
    xx=x0+col*cw;c.setFillColor(Color(*rgb(v)));c.setStrokeColorRGB(1,1,1);c.setLineWidth(.35);c.rect(xx,yy,cw,ch,fill=1,stroke=1)
    if hat:
     c.saveState();clip=c.beginPath();clip.rect(xx,yy,cw,ch);c.clipPath(clip,stroke=0,fill=0)
     c.setStrokeColorRGB(.70,.70,.70);c.setLineWidth(.30)
     for off in range(-25,35,5):c.line(xx+off,yy,xx+off+ch,yy+ch)
     c.restoreState()
    txt(xx+cw/2,yy+7,('0.0' if abs(v)<.05 else f'{v:.1f}'),10.5,color=(1,1,1) if abs(v)>8 else (0,0,0))
    plotted.append(dict(scenario=scenario,changed_skus=changed,K=k,lambda_cost=lam,mean=v,ci_low=lo,ci_high=hi,hatched=hat))
  txt(j*162+7,top-39,'K',9)
  for col,lam in enumerate([0,.25,.5,1,2]):txt(x0+col*cw+cw/2,top-80,f'{lam:g}',9)
  txt(j*162+84,top-94,'Movement cost λ',9)
bx,bw,by=114,258,25
for k in range(258):
 v=-15.1+30.2*k/257;c.setFillColor(Color(*rgb(v)));c.rect(bx+k,by,1.1,8,fill=1,stroke=0)
txt(bx,12,'−15.1 (M lower)',8.5,'center');txt(bx+bw/2,12,'0',8.5);txt(bx+bw,12,'+15.1 (B2 lower)',8.5)
c.showPage();c.save()
pdf=pdfium.PdfDocument(p);pdf[0].render(scale=400/72).to_pil().save(OUT/'figure2.png',dpi=(400,400));pdf.close()
pd.DataFrame(plotted).to_csv(OUT/'figure2_cells.csv',index=False)
audit={'status':'PASS','cells':90,'means_and_CI_from_frozen_csv':True,'cell_font_pt':10.5,'axis_font_pt':9,
 'caption_note_font_pt':8.5,'printed_width_inches':W/72,'source_sha256':hashlib.sha256(F.read_bytes()).hexdigest()}
(OUT/'figure2_report.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(audit)
