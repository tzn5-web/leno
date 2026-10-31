"""Suggest locally indexed PDF evidence for a selected vehicle-card field.

Text excerpts are offered for review only. No numerical value is inferred,
saved, or taken from a different vehicle automatically.
"""
from pdf_text_index import search_pdf_text
from vehicle_service_card import FIELD_DATA

ALIASES={
 "Cod motor":("engine code","engine no","engine number"),
 "Vâscozitate SAE":("engine oil","viscosity","SAE"),
 "Normă ACEA / API / OEM":("ACEA","API","engine oil"),
 "Capacitate cu filtru":("oil capacity","with filter","oil filter"),
 "Tip / omologare antigel":("coolant","antifreeze","cooling liquid"),
 "Capacitate circuit":("coolant capacity","cooling system"),
 "Concentrație / amestec":("mixing ratio","coolant mixture"),
 "Anvelope față":("tyre size","tire size","tyre"),
 "Anvelope spate":("tyre size","tire size","tyre"),
 "Presiune față normal":("tyre pressure","inflation pressure"),
 "Presiune spate normal":("tyre pressure","inflation pressure"),
 "Presiune față încărcat":("tyre pressure","full load"),
 "Presiune spate încărcat":("tyre pressure","full load"),
 "Tip lichid de frână":("brake fluid","DOT"),
 "Cuplu șuruburi roți":("wheel nut","wheel bolt","wheel torque"),
 "Tip bujii":("spark plug","ignition"),
 "Tip agent frigorific":("refrigerant","air conditioning"),
}

def search_evidence(store,vehicle_id,field_index,limit=40):
    if isinstance(field_index,bool) or not isinstance(field_index,int):
        raise ValueError("Parametru invalid")
    if field_index<0 or field_index>=len(FIELD_DATA):
        raise ValueError("Parametru necunoscut")
    field=FIELD_DATA[field_index]
    terms=(field[1],)+ALIASES.get(field[1],())
    dedup={}
    for term in terms:
        for hit in search_pdf_text(store,vehicle_id,term,limit=limit):
            key=(hit["attachment_id"],hit["page_number"])
            if key not in dedup:
                dedup[key]={**hit,"matched_term":term,"status":"fragment de verificat manual"}
            if len(dedup)>=limit:break
        if len(dedup)>=limit:break
    return list(dedup.values())
