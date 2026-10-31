"""Sourced, Autodata-style vehicle overview on top of existing technical_specs.

No fabricated specification; engine code from vehicle profile is explicitly
marked as user-entered and not independently verified.
"""
from __future__ import annotations
from technical_specs import add_spec,update_spec,remove_spec,list_specs

FIELD_DATA = [
    ["Identificare","Cod motor","Identificare","Cod motor",""],
    ["Identificare","Cilindree","Identificare","Cilindree","cm³"],
    ["Identificare","Putere","Identificare","Putere","kW"],
    ["Identificare","Normă de poluare","Identificare","Normă de poluare",""],
    ["Identificare","Distribuție (curea / lanț)","Identificare","Distribuție",""],
    ["Ulei motor","Vâscozitate SAE","Ulei motor","Vâscozitate SAE",""],
    ["Ulei motor","Normă ACEA / API / OEM","Ulei motor","Normă ACEA API OEM",""],
    ["Ulei motor","Capacitate cu filtru","Ulei motor","Cantitate cu filtru","L"],
    ["Ulei motor","Capacitate fără filtru","Ulei motor","Cantitate fără filtru","L"],
    ["Ulei motor","Referință filtru ulei","Ulei motor","Filtru ulei",""],
    ["Ulei motor","Interval schimb","Ulei motor","Interval schimb","km / luni"],
    ["Antigel","Tip / omologare antigel","Răcire","Tip antigel",""],
    ["Antigel","Concentrație / amestec","Răcire","Concentrație","%"],
    ["Antigel","Capacitate circuit","Răcire","Capacitate circuit","L"],
    ["Antigel","Interval schimb","Răcire","Interval schimb","km / ani"],
    ["Antigel","Termostat — deschidere","Răcire","Termostat","°C"],
    ["Anvelope și roți","Anvelope față","Anvelope","Dimensiune față",""],
    ["Anvelope și roți","Anvelope spate","Anvelope","Dimensiune spate",""],
    ["Anvelope și roți","Presiune față normal","Anvelope","Presiune față normal","bar"],
    ["Anvelope și roți","Presiune spate normal","Anvelope","Presiune spate normal","bar"],
    ["Anvelope și roți","Presiune față încărcat","Anvelope","Presiune față încărcat","bar"],
    ["Anvelope și roți","Presiune spate încărcat","Anvelope","Presiune spate încărcat","bar"],
    ["Anvelope și roți","Jante / PCD / ET","Anvelope","Jante / PCD / ET",""],
    ["Anvelope și roți","Cuplu șuruburi roți","Anvelope","Cuplu șuruburi roți","Nm"],
    ["Transmisie","Cod cutie de viteze","Transmisie","Cod cutie",""],
    ["Transmisie","Normă ulei cutie","Transmisie","Ulei cutie",""],
    ["Transmisie","Capacitate ulei cutie","Transmisie","Capacitate ulei cutie","L"],
    ["Frâne","Tip lichid de frână","Frâne","Lichid de frână",""],
    ["Frâne","Discuri față / uzură","Frâne","Discuri față","mm"],
    ["Frâne","Discuri / tamburi spate","Frâne","Frâne spate","mm"],
    ["Aprindere","Tip bujii","Aprindere","Tip bujii",""],
    ["Aprindere","Distanță electrozi","Aprindere","Distanță electrozi","mm"],
    ["Climatizare","Tip agent frigorific","Climatizare","Agent frigorific",""],
    ["Climatizare","Cantitate agent frigorific","Climatizare","Cantitate agent frigorific","g"],
    ["Alimentare","Combustibil","Alimentare","Combustibil",""],
    ["Alimentare","Capacitate rezervor","Alimentare","Capacitate rezervor","L"],
]
SECTIONS=tuple(dict.fromkeys(item[0] for item in FIELD_DATA))
PAIRS={(row[2],row[3]):i for i,row in enumerate(FIELD_DATA)}

def card(store,vehicle_id):
    if isinstance(vehicle_id,bool) or not isinstance(vehicle_id,int):
        raise ValueError("Invalid vehicle")
    vehicle=store.db.execute("SELECT * FROM vehicles WHERE id=?",(vehicle_id,)).fetchone()
    if vehicle is None:raise ValueError("Vehicul inexistent")
    values={i:[] for i in range(len(FIELD_DATA))}
    for row in list_specs(store,vehicle_id):
        i=PAIRS.get((row["system"],row["parameter"]))
        if i is not None:
            values[i].append({"id":row["id"],"value":row["value"],
                "unit":row["unit"],"conditions":row["conditions"],"source":row["source"]})
    if not values[0] and vehicle["engine"]:
        values[0]=[{"id":None,"value":vehicle["engine"],"unit":"",
            "conditions":"Introdus la crearea vehiculului; neverificat în documentație",
            "source":"Fișa vehiculului — informație declarată"}]
    return {"vehicle":dict(vehicle),"fields":FIELD_DATA,"values":values,
            "sourced_count":sum(bool(any(item["id"] is not None for item in rows))
                                for rows in values.values()),
            "total_count":len(FIELD_DATA)}

def _validated_field(index,value,source):
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(FIELD_DATA):
        raise ValueError("Câmp necunoscut")
    if not isinstance(value,str) or not value.strip():
        raise ValueError("Valoarea trebuie verificată în documentul sursă")
    if not isinstance(source,str) or not source.strip():
        raise ValueError("Sursa este obligatorie")
    return FIELD_DATA[index]

def add_value(store,vehicle_id,index,value,source,unit="",conditions=""):
    card(store,vehicle_id)
    section=_validated_field(index,value,source)
    return add_spec(store,vehicle_id,section[2],section[3],value.strip(),
                    unit.strip(),conditions.strip(),source.strip())

def edit_value(store,vehicle_id,spec_id,index,value,source,unit="",conditions=""):
    card(store,vehicle_id)
    section=_validated_field(index,value,source)
    row=store.db.execute("SELECT vehicle_id FROM technical_specs WHERE id=?",
                         (spec_id,)).fetchone()
    if row is None or row["vehicle_id"]!=vehicle_id:raise ValueError("Specificație din alt vehicul")
    update_spec(store,spec_id,section[2],section[3],value.strip(),unit.strip(),
                conditions.strip(),source.strip())
    return spec_id

def delete_value(store,vehicle_id,spec_id):
    card(store,vehicle_id)
    row=store.db.execute("SELECT vehicle_id FROM technical_specs WHERE id=?",
                         (spec_id,)).fetchone()
    if row is None or row["vehicle_id"]!=vehicle_id:raise ValueError("Specificație din alt vehicul")
    remove_spec(store,spec_id)
