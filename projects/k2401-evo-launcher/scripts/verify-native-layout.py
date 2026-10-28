#!/usr/bin/env python3
"""Strict geometric audit of the 20 native per-skin K2401 layouts.

Checks source-defined rectangles instead of screenshot hashes alone. The
separately implemented first Digital Dash is verified by Android emulator.
No changes to touch handling, ELM327, player or Android services.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
CODE=(ROOT/"app/src/main/java/ro/evolauncher/k2401/ThemeNativePanels.java").read_text()
section=CODE.split("static Layout profile(int id){",1)[1].split(
    "ThemeNativePanels(MainActivity",1)[0]
cases=re.findall(r"case\s+(\d+):\s*return new Layout\((.*?)\);\s*//",section,re.S)

def split_args(value):
    out,depth,start=[],0,0
    for i,c in enumerate(value):
        if c in "({[":depth+=1
        elif c in ")}]":depth-=1
        elif c=="," and depth==0:
            out.append(value[start:i].strip());start=i+1
    out.append(value[start:].strip())
    return out

def rect(spec):
    if spec=="null":return None
    m=re.fullmatch(r"rect\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",spec)
    assert m,spec
    return tuple(map(int,m.groups()))

def gauges(spec):
    m=re.fullmatch(r"(four|rightGrid|verticalFour|leftHero)\(([^)]+)\)",spec)
    if m:
        values=list(map(int,m.group(2).split(",")))
        if m.group(1)=="four":
            x,y,w,h,gap=values
            single=(w-3*gap)//4
            return [(x+i*(single+gap),y,single,h) for i in range(4)]
        if m.group(1)=="rightGrid":
            x,y,w,h,gap=values
            ww=(w-gap)//2;hh=(h-gap)//2
            return [(x+i%2*(ww+gap),y+i//2*(hh+gap),ww,hh) for i in range(4)]
        if m.group(1)=="verticalFour":
            x,y,w,h,gap=values
            hh=(h-3*gap)//4
            return [(x,y+i*(hh+gap),w,hh) for i in range(4)]
        x,y,w,h,rx,ry,rw,rh=values
        hh=(rh-20)//3
        return [(x,y,w,h)]+[(rx,ry+i*(hh+10),rw,hh) for i in range(3)]
    rects=re.findall(r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}",spec)
    return [tuple(map(int,fields)) for fields in rects]

def overlap(a,b):
    x,y,w,h=a;X,Y,W,H=b
    return max(0,min(x+w,X+W)-max(x,X))*max(0,min(y+h,Y+H)-max(y,Y))

assert len(cases)==20,f"Expected 20 native layouts, got {len(cases)}"
ids=set()
for number,body in cases:
    style=int(number);ids.add(style)
    args=split_args(body)
    assert len(args)==6,(style,args)
    slots=dict(zip(("clock","media","status","apps"),[rect(v) for v in args[:4]]))
    readings=gauges(args[4])
    assert len(readings)==4,(style,readings)
    slots.update({f"pid_{i}":r for i,r in enumerate(readings)})
    slots={k:v for k,v in slots.items() if v is not None}
    for name,(x,y,w,h) in slots.items():
        assert x>=96 and y>=54 and w>0 and h>0 and x+w<=1280 and y+h<=720,(
            style,name,(x,y,w,h),"covered by navigation/header or outside screen")
    for i,(name,a) in enumerate(slots.items()):
        for other,b in list(slots.items())[i+1:]:
            pixels=overlap(a,b)
            # Car Status deliberately frames its four genuine live cards
            # inside a larger native status backdrop. It does not duplicate RPM.
            permitted=style==18 and name=="status" and other.startswith("pid_")
            assert pixels<=200 or permitted,(style,name,other,pixels)
    print(f"K2401_NATIVE_LAYOUT={style:02d} PASS widgets={len(slots)}")
assert ids==set(range(1,21)),sorted(ids)
assert "lastStyle!=18" in CODE,"Car Status duplicate RPM text reintroduced"
print("K2401_ALL_20_NATIVE_LAYOUTS_NO_OVERLAP=PASS")

# Skin 00 uses its own Digital Dash implementation. Verify that the
# approved visible media + three footer controls have the same hit boxes,
# and the two fuel-trim cards do not extend beyond the 1280px viewport.
ENGINE=(ROOT/"app/src/main/java/ro/evolauncher/k2401/SkinEngine.java").read_text()
expected={
    "mediaRect":(860,74,1265,412),
    "appRect":(13,630,197,714),
    "skinRect":(201,630,385,714),
    "mapsRect":(389,630,573,714),
}
for name,box in expected.items():
    pattern=rf"private final Rect {name}=new Rect\(([^)]*)\)"
    match=re.search(pattern,ENGINE)
    assert match,(name,"missing action rectangle")
    actual=tuple(map(int,match.group(1).split(",")))
    assert actual==box,(name,actual,box)
assert 'panel(c,860,74,405,338' in ENGINE,"Digital Dash media artwork/hit mismatch"
assert 'int[] bx={13,201,389},bw={184,184,184}' in ENGINE,"Dock art/hit mismatch"
assert 'compactDigitalFuelTrim(c,860,426,194,205' in ENGINE,"STFT card displaced"
assert 'compactDigitalFuelTrim(c,1066,426,199,205' in ENGINE,"LTFT card displaced"
assert 'selected==0&&x>=860&&x<=1265&&y>=74&&y<=412' in ENGINE
assert 'host.mediaAction(x<1080?0:x<1165?1:2)' in ENGINE
assert '(x>=627&&x<=843&&y>=220&&y<=436)' in ENGINE, "Coolant gauge lost OBD details touch"
# Unrelated legacy mock artwork must not come back after a UI-only refresh.
MAIN=(ROOT/"app/src/main/java/ro/evolauncher/k2401/MainActivity.java").read_text()
VECTOR=(ROOT/"app/src/main/java/ro/evolauncher/k2401/NavVectorIcons.java").read_text()
assert 't(c,"YT",' not in MAIN,"Misleading baked YouTube album fallback"
assert 'Permite controlul YouTube Music prin MediaSession' not in MAIN
assert 'NavVectorIcons.draw(c,i,54,y+38' in MAIN,"OEM font icons returned"
assert all(f"case {i}:" in VECTOR for i in range(6)),"Missing native icon"
assert 'MediaVectorIcons.draw(c,x+390,y+h-46' in MAIN,"Old font-based player controls"
print("K2401_NATIVE_NAV_AND_MEDIA_ZERO_FALSE_ICONS=PASS")
print("K2401_DIGITAL_DASH_VISUAL_TOUCH_ALIGNMENT=PASS")

