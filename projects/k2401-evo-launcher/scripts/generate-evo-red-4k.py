#!/usr/bin/env python3
"""Deterministic 3840x2160 EVO RED scenic layer. No baked telemetry or UI.
All numbers, clock, music, gauges and app shortcuts are native Android Canvas.
This is original procedural artwork, not an upscaled screenshot.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import math, random
random.seed(2401117)
W,H,S=3840,2160,3
dest=Path(__file__).resolve().parents[1]/"app/src/main/assets/skins/approved/evo-red-scene-3840x2160.webp"
dest.parent.mkdir(parents=True,exist_ok=True)
im=Image.new("RGB",(W,H))
px=im.load()
for y in range(H):
    t=y/H
    for x in range(W):
        dx=abs(x-W/2)/(W/2)
        glow=max(0,1-abs(y-980)/950)*max(0,1-dx*.9)
        px[x,y]=(int(4+9*glow+7*t),int(5+11*glow+7*t),int(9+18*glow+8*t))
d=ImageDraw.Draw(im,"RGB")
def P(points):return [(round(x*S),round(y*S)) for x,y in points]
def line(points,fill,width=1):d.line(P(points),fill=fill,width=max(1,round(width*S)),joint="curve")
def poly(points,fill):d.polygon(P(points),fill=fill)
# Distant alpine skyline; all scenic detail stays behind the four live gauges.
poly([(0,330),(75,264),(128,294),(225,218),(320,315),(390,255),(470,321),(550,252),(650,326),(735,246),(850,310),(955,225),(1045,301),(1150,241),(1280,326),(1280,440),(0,440)],(15,21,31))
poly([(0,380),(80,311),(185,350),(300,283),(430,367),(545,310),(640,360),(742,290),(870,359),(1000,299),(1130,351),(1280,292),(1280,465),(0,465)],(8,13,22))
# Distant buildings and tiny city light reflections.
for i in range(180):
    x=random.randint(365,915);h=random.randint(7,60)
    y=375+random.randint(-17,25)
    d.rectangle((x*S,(y-h)*S,(x+random.randint(1,6))*S,y*S),fill=(11,16,25))
    if random.random()<.35:
        d.ellipse((x*S,y*S,(x+1)*S,(y+1)*S),fill=(150,25,42))
# Perspective road with metallic guardrails and red light trails.
poly([(520,400),(760,400),(1260,720),(20,720)],(8,11,18))
for side in [-1,1]:
    x0=640+side*160;x1=640+side*630
    line([(x0,400),(x1,720)],(55,63,75),2.4)
    line([(x0+side*6,401),(x1+side*16,720)],(156,21,39),2.8)
    for j in range(13):
        y=409+j*j*2.2
        if y>710:break
        frac=(y-400)/320
        x=640+side*(165+frac*420)
        line([(x,y),(x+side*(7+frac*38),y+1)],(115+int(frac*100),23,38),1+frac*2)
# Road perspective guides and highlights.
line([(640,398),(640,720)],(24,30,39),2)
for j in range(12):
    y=425+j*24
    x=640+random.randint(-270,270)
    line([(x,y),(x+random.randint(-18,18),y+random.randint(4,18))],(53,15,24),1)
# Dark Lancer Evolution-inspired rear silhouette, central, no fake license data.
poly([(510,316),(531,282),(554,270),(576,242),(608,229),(672,229),(707,243),(730,269),(750,283),(770,318),(773,387),(752,409),(528,409),(507,388)],(4,6,10))
poly([(555,281),(577,248),(603,237),(674,237),(704,250),(727,281)],(23,29,38))
poly([(564,280),(585,252),(610,243),(667,243),(694,254),(716,280)],(8,14,24))
line([(517,315),(762,315)],(91,103,117),2)
poly([(508,320),(539,320),(560,335),(562,348),(510,345)],(126,5,21))
poly([(770,320),(741,320),(720,335),(718,348),(768,345)],(126,5,21))
for side in [-1,1]:
    x=640+side*106
    line([(x,328),(x+side*23,328)],(245,28,52),5)
    line([(x,335),(x+side*19,335)],(255,71,77),2)
poly([(517,351),(761,351),(757,385),(735,399),(545,399),(522,384)],(7,8,12))
line([(548,372),(731,372)],(70,76,83),2)
line([(548,394),(731,394)],(148,22,38),2)
poly([(540,405),(566,405),(570,412),(542,412)],(20,22,26))
poly([(712,405),(738,405),(736,412),(708,412)],(20,22,26))
# Rear wing and exhaust highlights.
line([(526,280),(751,280)],(22,26,34),6)
line([(545,279),(555,302)],(35,40,48),3)
line([(735,279),(725,302)],(35,40,48),3)
for x in (552,728):
    d.ellipse(((x-9)*S,391*S,(x+9)*S,411*S),fill=(2,3,5))
    d.ellipse(((x-6)*S,394*S,(x+6)*S,407*S),outline=(86,90,99),width=3)
# Reflections, with no literal symbols or readings.
for j in range(95):
    y=random.randint(414,716)
    spread=(y-400)/320
    x=640+random.choice([-1,1])*random.randint(20,int(60+470*spread))
    width=random.randint(2,int(5+38*spread))
    line([(x,y),(x+width,y)],(random.randint(35,110),random.randint(5,18),random.randint(10,26)),random.choice([1,2]))
# Fine carbon diagonal background outside the central scenic zone.
for y in range(108,565,10):
    for x in list(range(0,380,14))+list(range(900,1280,14)):
        line([(x,y),(x+5,y+3)],(16,18,23),.5)
im.save(dest,format="WEBP",quality=94,method=6)
print("K2401_EVO_RED_4K_SCENE=PASS",dest,im.size)
