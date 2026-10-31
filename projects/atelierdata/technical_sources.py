"""Curated lawful links to automotive repair information, no scraping or redistribution.

Free-to-view is not a redistribution licence. No user vehicle data, VIN or
search text is sent to any site automatically. All entries are offline metadata.
Verified source list: 2026-10-31; providers may change coverage/access.
"""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse
import unicodedata

# This is an online-source directory, NOT a local vehicle-specification database.
# Access: gratis, cont_gratuit, mixt, cu_plata, aplicatie_gratuita, public_neoficial.
ALL="*"

@dataclass(frozen=True)
class Source:
    key: str
    title: str
    url: str
    makes: tuple[str, ...]
    categories: tuple[str, ...]
    access: str
    market: str
    notes: str
    provenance: str

SOURCES=(
    Source("charm","Operation CHARM","https://charm.li/",
        ("BMW","Mitsubishi","Nissan","Volkswagen","Audi","Mercedes-Benz","Ford",
         "Toyota","Honda","Renault","Peugeot","Fiat","Volvo","Hyundai","Kia",
         "Suzuki","Subaru","Mazda","Mini","Land Rover","Jaguar"),
        ("Proceduri","Scheme","Diagnosticare","Manual de atelier"),
        "gratis","SUA / acoperire variabilă",
        "Arhivă comunitară; majoritatea vehiculelor 1982–2013. Nu presupune că motoarele europene sunt identice cu cele SUA.",
        "https://charm.li/"),
    Source("autodoc","AUTODOC CLUB România","https://club.autodoc24.ro/manuals",
        ("Opel","Mitsubishi","BMW","Nissan","Skoda","Volkswagen","Audi","Mercedes-Benz",
         "Ford","Renault","Dacia","Toyota","Peugeot","Citroen","Fiat","Honda",
         "Seat","Suzuki","Hyundai","Kia","Volvo","Mazda","Chevrolet"),
        ("Proceduri","Întreținere","Tutoriale"),
        "cont_gratuit","Europa / România",
        "PDF și tutoriale ilustrate pentru înlocuire piese; nu echivalează cu scheme electrice sau date OEM complete.",
        "https://club.autodoc24.ro/manuals"),
    Source("autodata","Auto-Data.net","https://www.auto-data.net/ro/",
        ("Opel","Mitsubishi","BMW","Nissan","Skoda","Volkswagen","Audi",
         "Mercedes-Benz","Ford","Renault","Dacia","Toyota","Peugeot","Citroen",
         "Fiat","Honda","Seat","Hyundai","Kia","Volvo","Mazda","Suzuki"),
        ("Date tehnice",),"gratis","Global / general",
        "Specificații generale publicate pe website, nu cupluri și proceduri de atelier. Nu copia automat baza.",
        "https://www.auto-data.net/ro/"),
    Source("mmc_lancer","MMC Manuals — Mitsubishi Lancer X",
        "https://www.mmc-manuals.ru/Mitsubishi_Lancer_X%3A_Service_Manuals",
        ("Mitsubishi",),("Manual de atelier","Proceduri","Scheme","Motor"),
        "public_neoficial","Lancer X 2007–2015; diferă după piață",
        "Catalog public cu manual Lancer X și Engine Overhaul 4A91 1.5 L. Licența de republicare nu este stabilită.",
        "https://www.mmc-manuals.ru/Mitsubishi_Lancer_X%3A_Service_Manuals"),
    Source("bmw_aos","BMW Group AOS (oficial)","https://aos-q2.bmwgroup.com/",
        ("BMW","Mini"),("Proceduri","Scheme","Diagnosticare","Date tehnice"),
        "cu_plata","Europa / service independent",
        "Portal BMW pentru operatori independenți; conținut profesional și permisiuni pot necesita abonament. Nu colecta VIN.",
        "https://aos-q2.bmwgroup.com/"),
    Source("bmw_owners","BMW — manuale oficiale proprietar",
        "https://www.bmw.co.uk/en/topics/owners/bmw-owners-manual.html",
        ("BMW",),("Manual utilizare",),"gratis","UK / limbi și modele disponibile",
        "Manuale de utilizare, nu documentație tehnică completă de service; poate solicita date de identificare pe site.",
        "https://www.bmw.co.uk/en/topics/owners/bmw-owners-manual.html"),
    Source("skoda_owner","Škoda — manuale oficiale în română",
        "https://manual.skoda-auto.com/599/ro-RO",
        ("Skoda",),("Manual utilizare",),"gratis","Europa / România",
        "Selectare VIN sau model; informații de utilizare, nu neapărat reparații.",
        "https://manual.skoda-auto.com/599/ro-RO"),
    Source("skoda_erwin","Škoda erWin (oficial)","https://skoda.erwin-store.com/erwin/showInfoTour.do",
        ("Skoda",),("Manual de atelier","Proceduri","Scheme","Date tehnice"),
        "cu_plata","Europa / OEM",
        "Documentele complete necesită acces flat-rate. Modelul, motorul și VIN trebuie verificate în portal.",
        "https://skoda.erwin-store.com/erwin/showInfoTour.do"),
    Source("nissan_techinfo","Nissan TechInfo (oficial, SUA)","https://www.nissan-techinfo.com/help",
        ("Nissan","Infiniti"),("Manual utilizare","Manual de atelier","Scheme","Diagnosticare"),
        "mixt","SUA / Canada",
        "Manuale proprietar gratuite; manuale de service OEM cu abonament, pentru piața nord-americană.",
        "https://www.nissan-techinfo.com/help"),
    Source("nissan_eu","Nissan RMI Europa (referință ACEA)","https://eu.nissan.biz/",
        ("Nissan",),("Manual de atelier","Proceduri","Scheme"),
        "cu_plata","Europa / operatori independenți",
        "Portal RMI indicat de ACEA; disponibilitatea și condițiile se confirmă în portal.",
        "https://www.acea.auto/fact/rmi-service-information/"),
    Source("stellantis_servicebox","Stellantis Service Box (oficial)",
        "https://public.servicebox-parts.com/",
        ("Opel","Vauxhall","Peugeot","Citroen","DS"),
        ("Manual de atelier","Proceduri","Scheme","Date tehnice"),
        "cu_plata","Europa / OEM",
        "Portal de reparații și mentenanță. Acoperirea Opel legacy și abonamentele necesită verificare.",
        "https://www.acea.auto/fact/rmi-service-information/"),
    Source("renault_asos","Renault Group ASOS / New Dialogys",
        "https://asos.asdh.aws.renault.com/offers/documentation",
        ("Renault","Dacia"),("Manual de atelier","Proceduri","Scheme","Date tehnice"),
        "cu_plata","Europa / OEM",
        "Portal oficial cu acces pe perioade; manuale, scheme, buletine și cataloage când abonamentul este activ.",
        "https://asos.asdh.aws.renault.com/offers/documentation"),
    Source("toyota_owners","Toyota România — manualul proprietarului",
        "https://www.toyota.ro/support/owners-manuals",
        ("Toyota",),("Manual utilizare",),"gratis","România",
        "Manuale de utilizare online și descărcabile; nu reprezintă manuale de atelier.",
        "https://www.toyota.ro/support/owners-manuals"),
    Source("toyota_tech","Toyota TechDoc Europe (OEM)",
        "https://www.toyota-tech.eu/",
        ("Toyota","Lexus"),("Manual de atelier","Proceduri","Scheme","Date tehnice"),
        "mixt","Europa / OEM",
        "Înregistrare necesară; există informații gratuite și documentație cu plată.",
        "https://www.toyota.fr/support/documentation-technique"),
    Source("vw_erwin","Volkswagen erWin","https://volkswagen.erwin-store.com/erwin/showHome.do",
        ("Volkswagen",),("Manual de atelier","Proceduri","Scheme","Date tehnice"),
        "cu_plata","Europa / OEM",
        "Informații oficiale de reparații, cu abonament pentru documente.",
        "https://www.acea.auto/fact/rmi-service-information/"),
    Source("audi_erwin","Audi erWin","https://erwin.audi.com/",
        ("Audi",),("Manual de atelier","Proceduri","Scheme","Date tehnice"),
        "cu_plata","Europa / OEM",
        "Portal oficial Audi; condițiile, limba și accesul depind de abonament.",
        "https://www.acea.auto/fact/rmi-service-information/"),
    Source("carmin","Carmin — scheme electrice (Android)",
        "https://play.google.com/store/apps/details?id=com.min.car",
        ("Opel","Mitsubishi","BMW","Nissan","Skoda","Volkswagen","Audi","Mercedes-Benz",
         "Ford","Renault","Toyota","Honda"),
        ("Scheme",),"mixt","Android / acoperire pe model de confirmat",
        "Aplicație gratuit de instalat, dar cu reclame și achiziții. Lista mărcilor este orientativă: verifică modelul în aplicație.",
        "https://play.google.com/store/apps/details?id=com.min.car"),
    Source("androbd","AndrOBD — OBD2 open-source","https://f-droid.org/packages/com.fr3ts0n.ecu.gui.androbd/",
        (ALL,),("Diagnosticare","OBD"),"aplicatie_gratuita","ELM327 / OBD2 compatibil",
        "Aplicație Android open-source, citire coduri și date live. PID-urile și funcțiile diferă în funcție de ECU.",
        "https://f-droid.org/packages/com.fr3ts0n.ecu.gui.androbd/"),
    Source("nhtsa","NHTSA — rechemări și informații de siguranță",
        "https://www.nhtsa.gov/recalls",
        ("BMW","Mitsubishi","Nissan","Volkswagen","Audi","Mercedes-Benz","Ford",
         "Toyota","Honda","Hyundai","Kia","Volvo","Mazda","Suzuki"),
        ("Rechemări","Diagnosticare"),"gratis","SUA; VIN UE poate să nu aibă acoperire",
        "Verificare rechemări și comunicații producător pentru piața SUA; nu înlocuiește informațiile RAR/UE.",
        "https://www.nhtsa.gov/recalls"),
    Source("mcp_charm","MCP CHARM — integrare open-source",
        "https://github.com/Gonzih/mcp-charm",
        ("BMW","Mitsubishi","Nissan","Volkswagen","Audi","Mercedes-Benz",
         "Ford","Toyota","Honda"),("Integrări",),"gratis","Cod sursă / GitHub",
        "Conector terț pentru CHARM; MIT se aplică doar codului conectorului, nu automat conținutului manualelor.",
        "https://github.com/Gonzih/mcp-charm"),
    Source("opel_owners","Opel — manuale oficiale proprietar",
        "https://www.opel.lv/owners/manuals.html",
        ("Opel",),("Manual utilizare","Întreținere"),"gratis","Europa / letonă",
        "Manuale electronice pentru Opel Astra, Corsa, Insignia, Meriva etc.; limba letonă, nu manual de atelier.",
        "https://www.opel.lv/owners/manuals.html"),
    Source("mitsubishi_owners","Mitsubishi — manuale oficiale utilizare",
        "https://www.mitsubishi-motors.nl/handleidingen",
        ("Mitsubishi",),("Manual utilizare",),"gratis","Olanda / multe modele istorice",
        "Manuale pentru Lancer și alte modele, după an și piață. Verifică anul; nu substitui manualul de service pentru 4A91.",
        "https://www.mitsubishi-motors.nl/handleidingen"),
    Source("nissan_owners_uk","Nissan UK — manuale oficiale proprietar",
        "https://www.nissan.co.uk/owners/car-repair/car-owner-manual.html",
        ("Nissan",),("Manual utilizare",),"gratis","UK / Europa",
        "Căutare după model și an; VIN necesar doar pentru unele căutări. Nu reprezintă manuale de service OEM.",
        "https://www.nissan.co.uk/owners/car-repair/car-owner-manual.html"),
    Source("vw_owners_ie","Volkswagen — manual digital",
        "https://www.volkswagen.ie/en/owners-and-services/customer-information/digital-manual.html",
        ("Volkswagen",),("Manual utilizare",),"gratis","Europa / Irlanda",
        "Manual online pentru modele din august 2019 încolo conform site-ului, identificare prin VIN.",
        "https://www.volkswagen.ie/en/owners-and-services/customer-information/digital-manual.html"),
    Source("skoda_video","Škoda — tutoriale video oficiale",
        "https://www.skoda-auto.com/services/video-manuals",
        ("Skoda",),("Tutoriale","Manual utilizare"),"gratis","Europa / modele selectate",
        "Explică folosirea funcțiilor vehiculului; nu include procedurile complete de reparație.",
        "https://www.skoda-auto.com/services/video-manuals"),
    Source("euro_rmi","Comisia Europeană — acces RMI",
        "https://single-market-economy.ec.europa.eu/sectors/automotive-industry/technical-harmonisation/access-vehicle-repair-and-maintenance-information_en",
        (ALL,),("Integrări",),"gratis","Uniunea Europeană",
        "Informații despre accesul operatorilor independenți la documentație RMI; nu include manuale de atelier.",
        "https://single-market-economy.ec.europa.eu/sectors/automotive-industry/technical-harmonisation/access-vehicle-repair-and-maintenance-information_en"),
)
ACCESS={"gratis","cont_gratuit","mixt","cu_plata","aplicatie_gratuita","public_neoficial"}

def normalize(text: str) -> str:
    text=unicodedata.normalize("NFKD",str(text))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold().strip()

def validate_catalog(entries=SOURCES):
    keys=set()
    for item in entries:
        if item.key in keys: raise ValueError("duplicate source key")
        keys.add(item.key)
        if not item.title or not item.makes or not item.categories or not item.notes:
            raise ValueError("incomplete source entry")
        if item.access not in ACCESS:raise ValueError("unknown access type")
        for url in (item.url,item.provenance):
            parsed=urlparse(url)
            if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("unsafe URL")
            if parsed.hostname in ("localhost","127.0.0.1","0.0.0.0"):
                raise ValueError("local URL refused")
    return True

def search_sources(query="",make="",category="",access="",entries=SOURCES):
    """Pure local matching; an empty make means all. No network request."""
    q=normalize(query)
    m=normalize(make)
    c=normalize(category)
    return [
        x for x in entries
        if (not m or ALL in x.makes or any(normalize(label)==m for label in x.makes))
        and (not c or any(normalize(label)==c for label in x.categories))
        and (not access or x.access==access)
        and (not q or q in normalize(" ".join((x.title,x.notes,x.market,x.access,
                " ".join(x.makes)," ".join(x.categories)))))
    ]

def makes():
    return sorted({name for x in SOURCES for name in x.makes if name!=ALL},key=normalize)

def categories():
    return sorted({cat for x in SOURCES for cat in x.categories},key=normalize)

validate_catalog()
