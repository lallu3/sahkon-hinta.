#!/usr/bin/env python3
"""
Sähkön hinta -infonäyttö.

Hakee tuntihinnat api.spot-hinta.fi -palvelusta, lisää kiinteät kustannukset
ja kirjoittaa staattisen HTML-sivun (index.html).

Sivulla ei ole JavaScriptiä eikä nykyaikaista CSS:ää, jotta se renderöityy
myös vanhoissa selaimissa (Safari 12 / iOS 12).
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# ASETUKSET — näitä voit muuttaa itse
# ---------------------------------------------------------------------------

# Kiinteä lisä sentteinä kilowattitunnilta.
# Tällä hetkellä: myyjän marginaali 0,49 snt/kWh.
#
# Huom. rajapinnan PriceWithTax sisältää jo pörssihinnan arvonlisäveron
# (25,5 %), joten sitä ei lisätä uudelleen. Tähän lukuun sen sijaan pitää
# sisällyttää vero itse, jos sopimuksesi marginaali on ilmoitettu
# verottomana (0,49 x 1,255 = 0,61).
#
# Jos lisäät myöhemmin siirtomaksun ja sähköveron, laske ne yhteen tähän.
KIINTEA_LISA_SNT = 0.49

# Sivun alareunassa näkyvä selite.
# Arvolla None selite muodostuu automaattisesti yllä olevasta luvusta,
# jolloin ne eivät voi mennä keskenään ristiin. Voit myös kirjoittaa oman
# tekstin lainausmerkkeihin, esim.
#   LISAN_SELITE = "Sis. marginaali, siirto ja sähkövero"
LISAN_SELITE = None

# Värien raja-arvot kokonaishinnalle (snt/kWh).
# Alle HALPA_RAJA = vihreä, väliltä = keltainen, yli KALLIS_RAJA = punainen.
HALPA_RAJA = 9.0
KALLIS_RAJA = 9.0

# Kaavioon piirrettävä kiinteä vertailuviiva (snt/kWh, kokonaishinta).
# Viiva näkyy molempien päivien kohdalla. Aseta None, jos et halua viivaa.
VERTAILUVIIVA_SNT = 9.0

# Mitä ison luvun oikealla puolella näytetään:
#   "seuraavat"  — tulevien tuntien hinnat (oletus)
#   "aariarvot"  — päivän halvin ja kallein tunti
YLAOSAN_TIEDOT = "seuraavat"

# Montako tulevaa tuntia näytetään, kun YLAOSAN_TIEDOT = "seuraavat".
SEURAAVIA_TUNTEJA = 2

# Tekstien kokojen yleiskerroin. Kasvata, jos teksti on liian pientä
# DAKboard-lohkossa; pienennä, jos se ei mahdu.
SKAALA = 1.0

# Ulkoasu. Vaihtoehdot:
#   "tumma"       — tumma tausta (oletus)
#   "vaalea"      — vaalea tausta
#   "lapinakyva"  — ei omaa taustaa, DAKboardin taustakuva näkyy läpi
TEEMA = "lapinakyva"

AIKAVYOHYKE = "Europe/Helsinki"

# priceResolution=60 antaa tuntihinnat varttihintojen sijaan.
API_URL = "https://api.spot-hinta.fi/TodayAndDayForward?priceResolution=60"

TEEMAT = {
    "tumma": {
        "tausta": "#12161c", "viiva": "#2a333f",
        "teksti": "#e8ecef", "vaimea": "#7c8794",
        "halpa": "#4fa96b", "keski": "#c9a227", "kallis": "#c4553d",
        "nyt": "#e8ecef", "varjo": "none",
        "korostus": "rgba(255,255,255,0.10)", "merkkiteksti": "#12161c",
    },
    "vaalea": {
        "tausta": "#f4f5f7", "viiva": "#d3d8de",
        "teksti": "#1c2128", "vaimea": "#69727d",
        "halpa": "#3d8a55", "keski": "#9e7c18", "kallis": "#b04630",
        "nyt": "#1c2128", "varjo": "none",
        "korostus": "rgba(0,0,0,0.07)", "merkkiteksti": "#f4f5f7",
    },
    "lapinakyva": {
        "tausta": "transparent", "viiva": "rgba(255,255,255,0.28)",
        "teksti": "#ffffff", "vaimea": "rgba(255,255,255,0.78)",
        "halpa": "#5cc17b", "keski": "#e0b52e", "kallis": "#e06a4f",
        "nyt": "#ffffff",
        "varjo": "0 1px 3px rgba(0,0,0,0.85), 0 0 12px rgba(0,0,0,0.6)",
        "korostus": "rgba(255,255,255,0.20)", "merkkiteksti": "#12161c",
    },
}

VARIT = TEEMAT[TEEMA]

VIIKONPAIVAT = ["ma", "ti", "ke", "to", "pe", "la", "su"]


def px(arvo):
    return "%.1fpx" % (arvo * SKAALA)


def hae_data():
    """Hakee hinnat rajapinnasta. SPOT_MOCK-muuttujalla voi lukea paikallisen
    tiedoston testausta varten."""
    mock = os.environ.get("SPOT_MOCK")
    if mock:
        with open(mock, "r", encoding="utf-8") as f:
            return json.load(f)

    pyynto = urllib.request.Request(
        API_URL, headers={"User-Agent": "sahko-infonaytto/1.0"}
    )
    with urllib.request.urlopen(pyynto, timeout=30) as vastaus:
        return json.loads(vastaus.read().decode("utf-8"))


def kasittele(raaka, tz):
    """Muuntaa rajapinnan vastauksen listaksi tunteja kokonaishintoineen."""
    tunnit = []
    for rivi in raaka:
        aika = datetime.fromisoformat(rivi["DateTime"]).astimezone(tz)
        spot_snt = float(rivi["PriceWithTax"]) * 100.0
        tunnit.append({
            "aika": aika,
            "paiva": aika.date(),
            "tunti": aika.hour,
            "hinta": spot_snt + KIINTEA_LISA_SNT,
        })
    tunnit.sort(key=lambda t: t["aika"])
    return tunnit


def vari(hinta):
    if hinta < HALPA_RAJA:
        return VARIT["halpa"]
    if hinta < KALLIS_RAJA:
        return VARIT["keski"]
    return VARIT["kallis"]


def muotoile(hinta):
    return ("%.2f" % hinta).replace(".", ",")


def paivan_nimi(d, tanaan, huomenna):
    if d == tanaan:
        return "Tänään"
    if d == huomenna:
        return "Huomenna"
    return "%s %d.%d." % (VIIKONPAIVAT[d.weekday()], d.day, d.month)


def rakenna_html(tunnit, nyt):
    tanaan = nyt.date()
    huomenna = tanaan + timedelta(days=1)

    nykyinen = None
    for t in tunnit:
        if t["paiva"] == tanaan and t["tunti"] == nyt.hour:
            nykyinen = t
            break

    tanaan_tunnit = [t for t in tunnit if t["paiva"] == tanaan]
    if tanaan_tunnit:
        halvin = min(tanaan_tunnit, key=lambda t: t["hinta"])
        kallein = max(tanaan_tunnit, key=lambda t: t["hinta"])
        keskiarvo = sum(t["hinta"] for t in tanaan_tunnit) / len(tanaan_tunnit)
    else:
        halvin = kallein = None
        keskiarvo = 0.0

    hinnat = [t["hinta"] for t in tunnit] or [0.0]
    yla = max(max(hinnat), 0.0)
    ala = min(min(hinnat), 0.0)
    vali = (yla - ala) or 1.0
    ylaosuus = (yla / vali) * 100.0
    alaosuus = 100.0 - ylaosuus

    # Vertailuviivan paikka mitataan koko pylväsalueen korkeudesta, johon
    # kuuluu myös mahdollinen negatiivinen vyöhyke nollaviivan alapuolella.
    # Viivaa ei piirretä, jos raja jää kaavion ulkopuolelle.
    viiva_ylhaalta = None
    if VERTAILUVIIVA_SNT is not None and yla > 0 and 0 < VERTAILUVIIVA_SNT <= yla:
        viiva_ylhaalta = (1.0 - VERTAILUVIIVA_SNT / yla) * ylaosuus

    paivat = []
    for t in tunnit:
        if not paivat or paivat[-1]["paiva"] != t["paiva"]:
            paivat.append({"paiva": t["paiva"], "tunnit": []})
        paivat[-1]["tunnit"].append(t)

    o = [SIVUN_ALKU % {
        "tausta": VARIT["tausta"],
        "viiva": VARIT["viiva"],
        "teksti": VARIT["teksti"],
        "vaimea": VARIT["vaimea"],
        "nyt": VARIT["nyt"],
        "varjo": VARIT["varjo"],
        "korostus": VARIT["korostus"],
        "merkkiteksti": VARIT["merkkiteksti"],
        "f_merkki": px(10),
        "ylaosuus": "%.3f" % ylaosuus,
        "alaosuus": "%.3f" % alaosuus,
        "f_iso": px(76), "f_yksikko": px(17), "f_eyebrow": px(11),
        "f_vertailu": px(13), "f_keski": px(26), "f_kello": px(12),
        "f_tunti": px(10), "f_alaosa": px(10), "f_paiva": px(11),
        "p_body": px(18), "p_sivu": px(20), "m_aari": px(32),
    }]

    o.append('<div class="ylaosa"><div>')
    o.append('<div class="eyebrow">Hinta nyt</div>')
    if nykyinen:
        suunta = ("alle päivän keskiarvon" if nykyinen["hinta"] < keskiarvo
                  else "yli päivän keskiarvon")
        o.append('<div class="iso" style="color:%s">%s'
                 '<span class="yksikko">snt/kWh</span></div>'
                 % (vari(nykyinen["hinta"]), muotoile(nykyinen["hinta"])))
        o.append('<div class="vertailu">%s</div>' % suunta)
    else:
        o.append('<div class="iso" style="color:%s">–'
                 '<span class="yksikko">snt/kWh</span></div>' % VARIT["vaimea"])
        o.append('<div class="vertailu">tuntihintaa ei saatavilla</div>')
    o.append("</div>")

    if YLAOSAN_TIEDOT == "seuraavat" and nykyinen is not None:
        i = tunnit.index(nykyinen)
        seuraavat = tunnit[i + 1:i + 1 + SEURAAVIA_TUNTEJA]
        if seuraavat:
            o.append('<div class="aariarvot">')
            for t in seuraavat:
                ero = t["hinta"] - nykyinen["hinta"]
                etumerkki = "+" if ero >= 0 else "\u2212"
                o.append('<div class="aari"><div class="eyebrow">Klo %02d</div>'
                         '<div class="keski-luku" style="color:%s">%s</div>'
                         '<div class="kello">%s%s</div></div>'
                         % (t["tunti"], vari(t["hinta"]), muotoile(t["hinta"]),
                            etumerkki, muotoile(abs(ero))))
            o.append("</div>")
    elif YLAOSAN_TIEDOT == "aariarvot" and halvin and kallein:
        o.append('<div class="aariarvot">')
        for otsikko, t, v in (("Halvin tänään", halvin, VARIT["halpa"]),
                              ("Kallein tänään", kallein, VARIT["kallis"])):
            o.append('<div class="aari"><div class="eyebrow">%s</div>'
                     '<div class="keski-luku" style="color:%s">%s</div>'
                     '<div class="kello">klo %02d</div></div>'
                     % (otsikko, v, muotoile(t["hinta"]), t["tunti"]))
        o.append("</div>")
    o.append("</div>")

    o.append('<div class="kaavio">')
    for i, p in enumerate(paivat):
        n = len(p["tunnit"])
        o.append('<div class="%s" style="-webkit-flex:%d;flex:%d">'
                 % ("paiva" if i == 0 else "paiva raja", n, n))
        o.append('<div class="paivaotsikko">%s</div>'
                 % paivan_nimi(p["paiva"], tanaan, huomenna))
        o.append('<div class="pylvaat">')
        if viiva_ylhaalta is not None:
            o.append('<div class="vertailuviiva" style="top:%.3f%%">'
                     '<span class="viivamerkki">%s</span></div>'
                     % (viiva_ylhaalta, muotoile(VERTAILUVIIVA_SNT)))
        for t in p["tunnit"]:
            on_nyt = (t is nykyinen)
            o.append('<div class="sarake%s">' % (" sarake-nyt" if on_nyt else ""))
            korkeus = (max(t["hinta"], 0.0) / yla * 100.0) if yla > 0 else 0.0
            if on_nyt:
                # Yhdysviiva merkistä pylvään yläreunaan. Pylvään yläreuna on
                # (100 - korkeus) % ylävyöhykkeen korkeudesta, ja ylävyöhyke
                # kattaa ylaosuus % koko sarakkeesta.
                yhdys = (100.0 - korkeus) * ylaosuus / 100.0
                o.append('<div class="nyt-yhdys" style="height:%.3f%%"></div>'
                         % yhdys)
                o.append('<div class="nyt-merkki">NYT</div>')
            o.append('<div class="ylaruutu">')
            if korkeus > 0:
                o.append('<div class="pylvas" style="height:%.3f%%;background:%s">'
                         '</div>' % (korkeus, vari(t["hinta"])))
            o.append("</div>")
            if ala < 0:
                alak = abs(min(t["hinta"], 0.0)) / abs(ala) * 100.0
                o.append('<div class="alaruutu">')
                if alak > 0:
                    o.append('<div class="pylvas" style="height:%.3f%%;'
                             'background:%s"></div>' % (alak, VARIT["halpa"]))
                o.append("</div>")
            o.append("</div>")
        o.append("</div>")

        o.append('<div class="asteikko">')
        for t in p["tunnit"]:
            merkki = "%02d" % t["tunti"] if t["tunti"] % 3 == 0 else "&nbsp;"
            o.append('<div class="tuntimerkki%s">%s</div>'
                     % (" tunti-nyt" if t is nykyinen else "", merkki))
        o.append("</div></div>")
    o.append("</div>")

    selite = LISAN_SELITE
    if selite is None:
        selite = ("Pörssihinta sis. ALV 25,5 %% + kiinteä lisä %s snt/kWh"
                  % muotoile(KIINTEA_LISA_SNT))
    o.append('<div class="alaosa"><span>%s</span>'
             '<span>Päivitetty %d.%d. klo %02d:%02d</span></div>'
             % (selite, nyt.day, nyt.month, nyt.hour, nyt.minute))
    o.append(SIVUN_LOPPU)
    return "".join(o)


SIVUN_ALKU = """<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="900">
<title>Sähkön hinta</title>
<style>
html, body {
  margin: 0; padding: 0; height: 100%%;
  background: %(tausta)s; color: %(teksti)s;
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
body {
  display: -webkit-flex; display: flex;
  -webkit-flex-direction: column; flex-direction: column;
  padding: %(p_body)s %(p_sivu)s;
  -webkit-box-sizing: border-box; box-sizing: border-box;
  text-shadow: %(varjo)s;
}
.ylaosa {
  display: -webkit-flex; display: flex;
  -webkit-align-items: flex-end; align-items: flex-end;
  -webkit-justify-content: space-between; justify-content: space-between;
  margin-bottom: %(p_body)s;
}
.eyebrow {
  font-size: %(f_eyebrow)s; font-weight: 600; letter-spacing: 0.14em;
  text-transform: uppercase; color: %(vaimea)s; margin-bottom: 4px;
}
.iso {
  font-size: %(f_iso)s; font-weight: 300; line-height: 0.9;
  letter-spacing: -0.03em; font-feature-settings: "tnum";
  white-space: nowrap;
}
.yksikko {
  font-size: %(f_yksikko)s; font-weight: 400; letter-spacing: 0;
  color: %(vaimea)s; margin-left: 8px;
}
.vertailu { font-size: %(f_vertailu)s; color: %(vaimea)s; margin-top: 8px; }
.aariarvot { display: -webkit-flex; display: flex; text-align: right; }
.aari { margin-left: %(m_aari)s; }
.keski-luku {
  font-size: %(f_keski)s; line-height: 1.1; font-feature-settings: "tnum";
  white-space: nowrap;
}
.kello { font-size: %(f_kello)s; color: %(vaimea)s; margin-top: 2px; }
.kaavio {
  -webkit-flex: 1; flex: 1;
  display: -webkit-flex; display: flex; min-height: 0;
}
.paiva {
  display: -webkit-flex; display: flex;
  -webkit-flex-direction: column; flex-direction: column;
  min-width: 0; padding: 0 6px;
}
.paiva.raja { border-left: 1px solid %(viiva)s; }
.paivaotsikko {
  font-size: %(f_paiva)s; font-weight: 600; letter-spacing: 0.14em;
  text-transform: uppercase; color: %(vaimea)s; margin-bottom: 8px;
}
.pylvaat {
  -webkit-flex: 1; flex: 1;
  display: -webkit-flex; display: flex;
  -webkit-align-items: stretch; align-items: stretch;
  position: relative; min-height: 0;
}
.vertailuviiva {
  position: absolute; left: 0; right: 0; height: 0;
  border-top: 1px dashed %(viiva)s;
}
.viivamerkki {
  position: absolute; right: 2px; bottom: 2px;
  font-size: %(f_tunti)s; color: %(vaimea)s;
  font-feature-settings: "tnum"; white-space: nowrap;
}
.sarake {
  -webkit-flex: 1; flex: 1;
  display: -webkit-flex; display: flex;
  -webkit-flex-direction: column; flex-direction: column;
  padding: 0 1px; min-width: 0;
}
.ylaruutu {
  height: %(ylaosuus)s%%;
  display: -webkit-flex; display: flex;
  -webkit-align-items: flex-end; align-items: flex-end;
}
.alaruutu {
  height: %(alaosuus)s%%;
  display: -webkit-flex; display: flex;
  -webkit-align-items: flex-start; align-items: flex-start;
}
.pylvas { width: 100%%; min-height: 2px; }
.sarake-nyt {
  background: %(korostus)s;
  position: relative;
}
.sarake-nyt .pylvas {
  -webkit-box-shadow: inset 0 3px 0 0 %(nyt)s;
  box-shadow: inset 0 3px 0 0 %(nyt)s;
}
.nyt-yhdys {
  position: absolute; top: 0; left: 50%%;
  -webkit-transform: translateX(-50%%);
  transform: translateX(-50%%);
  width: 0; border-left: 1px dashed %(nyt)s;
  z-index: 1;
}
.nyt-merkki {
  position: absolute; top: 0; left: 50%%;
  -webkit-transform: translateX(-50%%);
  transform: translateX(-50%%);
  background: %(nyt)s; color: %(merkkiteksti)s;
  font-size: %(f_merkki)s; font-weight: 700; letter-spacing: 0.1em;
  line-height: 1; padding: 3px 5px 2px 6px;
  border-radius: 2px; text-shadow: none;
  white-space: nowrap; z-index: 2;
}
.asteikko {
  display: -webkit-flex; display: flex; margin-top: 6px;
  border-top: 1px solid %(viiva)s; padding-top: 5px;
}
.tuntimerkki {
  -webkit-flex: 1; flex: 1; text-align: center;
  font-size: %(f_tunti)s; color: %(vaimea)s;
  font-feature-settings: "tnum"; min-width: 0; overflow: hidden;
}
.tuntimerkki.tunti-nyt { color: %(nyt)s; font-weight: 700; }
.alaosa {
  display: -webkit-flex; display: flex;
  -webkit-justify-content: space-between; justify-content: space-between;
  margin-top: 12px; font-size: %(f_alaosa)s; color: %(vaimea)s;
}
</style>
</head>
<body>
"""

SIVUN_LOPPU = """</body>
</html>
"""


def main():
    tz = ZoneInfo(AIKAVYOHYKE)
    nyt = datetime.now(tz)
    try:
        raaka = hae_data()
    except Exception as virhe:
        print("Hintojen haku epäonnistui: %s" % virhe, file=sys.stderr)
        return 1

    tunnit = kasittele(raaka, tz)
    if not tunnit:
        print("Rajapinta ei palauttanut hintoja.", file=sys.stderr)
        return 1

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(rakenna_html(tunnit, nyt))
    print("Kirjoitettu index.html, %d tuntia." % len(tunnit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
