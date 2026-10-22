#!/usr/bin/env python3
"""Unterhaltsrechner (Testphase). Deterministische Berechnung von Kindes- und
Ehegattenunterhalt nach Düsseldorfer Tabelle und OLG-Leitlinie, Monat für Monat.

Aufruf:
  python3 unterhalt.py eingabe.json [--format md|json] [--leitlinien]

Eigene Ergänzung von digitalmann, nicht von Klotzkette. Ergebnisse immer nachprüfen.
"""
import argparse
import copy
import json
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
D = Decimal
C = D("0.01")
VERSION = "0.4.0"


def dec(x):
    return D(str(x or 0))


def cent(x):
    return dec(x).quantize(C, ROUND_HALF_UP)


class Fehler(Exception):
    pass


# --------------------------------------------------------------- Daten

def lade_daten():
    dt = json.load(open(DATA / "dt.json", encoding="utf-8"))["jahre"]
    ll = json.load(open(DATA / "leitlinien.json", encoding="utf-8"))["leitlinien"]
    return dt, {x["id"]: x for x in ll}


def leitlinie_aufloesen(lls, lid):
    if not lid:
        raise Fehler("Leitlinie fehlt. Vor der Berechnung den OLG-Bezirk abfragen und 'leitlinie' setzen "
                     "(Liste: --leitlinien).")
    if lid not in lls:
        raise Fehler(f"Unbekannte Leitlinie '{lid}'. Gültig: {', '.join(sorted(lls))}")
    ll = lls[lid]
    if ll.get("verweis"):
        basis = dict(lls[ll["verweis"]])
        basis.update({k: ll[k] for k in ("id", "name", "olg", "bundeslaender", "quelle", "quelle_art")})
        basis["verweis"] = ll["verweis"]
        return basis
    return ll


BLOECKE = ("berufsbedingt", "fahrtkosten", "bonus", "selbstbehalt", "rundung")


def _olg_schluessel(x):
    return x.lower().replace("ü", "ue").replace("ö", "oe").replace("ä", "ae").replace("ß", "ss").replace(" ", "")


def leitlinie_fuer(lls, lid, jahr, olg=None):
    """Leitlinienparameter für ein Kalenderjahr. Hauptstand ist 2026; für 2024 und 2025 werden die in
    'historie' hinterlegten Abweichungen der damaligen Fassung angewandt. 'je_olg': in diesem Jahr galten
    getrennte Leitlinien je OLG, dann ist die Eingabe 'olg' erforderlich."""
    ll = copy.deepcopy(leitlinie_aufloesen(lls, lid))
    ll["fassung"] = str(jahr)
    if jahr >= 2026:
        ll["fassung"] = "2026"
        return ll
    h = lls[lid].get("historie", {}).get(str(jahr))
    if h is None:
        ll["fassung_hinweis"] = f"Für {jahr} ist keine Fassung der Leitlinie hinterlegt; Parameter Stand 2026. Damalige Fassung prüfen."
        return ll
    h = dict(h)
    je = h.pop("je_olg", None)

    def anwenden(x):
        for k, v in x.items():
            ll[k] = copy.deepcopy(v)

    anwenden(h)
    if je:
        if not olg:
            raise Fehler(f"{ll['name']}: {jahr} galten getrennte Leitlinien der OLG {', '.join(je)}. "
                         f"Zuständiges OLG als 'olg' angeben.")
        treffer = [k for k in je if _olg_schluessel(k) == _olg_schluessel(olg)]
        if not treffer:
            raise Fehler(f"olg '{olg}' passt nicht zu {lid} {jahr} (möglich: {', '.join(je)})")
        anwenden(je[treffer[0]])
        ll["fassung"] = f"{jahr} ({treffer[0]})"
    return ll


# --------------------------------------------------------------- Monate

def monat(s):
    j, m = s.split("-")[:2]
    return int(j), int(m)


def monate(von, bis):
    j, m = monat(von)
    je, me = monat(bis)
    out = []
    while (j, m) <= (je, me):
        out.append((j, m))
        m += 1
        if m == 13:
            j, m = j + 1, 1
    if len(out) > 120:
        raise Fehler("Zeitraum über 10 Jahre")
    return out


def mstr(jm):
    return f"{jm[0]:04d}-{jm[1]:02d}"


def gueltig(liste, jm, name):
    """Wählt aus einer Liste von Abschnitten [{"ab": "JJJJ-MM", ...}] den für den Monat geltenden."""
    if isinstance(liste, dict):
        liste = [liste]
    kand = [e for e in liste if monat(e.get("ab", "1900-01")) <= jm]
    if not kand:
        raise Fehler(f"Kein Einkommensabschnitt für {name} im Monat {mstr(jm)}")
    return max(kand, key=lambda e: monat(e.get("ab", "1900-01")))


def altersstufe(geburt, jm):
    """§ 1612a Abs. 3 BGB: höhere Stufe ab Beginn des Monats, in dem das Lebensjahr vollendet wird.
    Ein Lebensjahr ist mit Ablauf des Tages vor dem Geburtstag vollendet (§§ 187 Abs. 2 S. 2, 188 Abs. 2 BGB);
    wer am Monatsersten geboren ist, wechselt deshalb schon im Vormonat. Volljährigkeit und 4. Altersstufe
    ab dem Monat des 18. Geburtstags (Beginn des Geburtstags, § 2 BGB)."""
    g = date.fromisoformat(geburt)
    v = g - timedelta(days=1)
    alter_stufe = jm[0] - v.year - (1 if jm[1] < v.month else 0)
    alter = jm[0] - g.year - (1 if jm[1] < g.month else 0)
    if alter < 0 and alter_stufe < 0:
        return None, alter
    if alter >= 18:
        return 3, alter
    if alter_stufe >= 12:
        return 2, max(alter, 0)
    if alter_stufe >= 6:
        return 1, max(alter, 0)
    return 0, max(alter, 0)


# --------------------------------------------------------------- Einkommen

def fahrtkosten(fk_eing, ll, hinweise):
    p = ll["fahrtkosten"]
    entf = dec(fk_eing.get("entfernung_km"))
    if p["modell"] == "monat_je_entfernungskm":
        ab = fk_eing.get("staffel_ab_km", p["staffel_ab_entfernung_km"])
        grenze = dec(ab) if (fk_eing.get("staffel", True) and ab is not None) else entf
        bis = min(entf, grenze)
        rest = max(entf - grenze, D(0))
        betrag = bis * dec(p["satz"]) + rest * dec(p["satz_mehrkilometer"] or p["satz"])
        formel = f"{bis} km x {p['satz']} €" + (f" + {rest} km x {p['satz_mehrkilometer']} €" if rest else "")
        return cent(betrag), formel
    tage = dec(fk_eing.get("arbeitstage") or p["arbeitstage_default"] or 220)
    if not fk_eing.get("arbeitstage") and not p.get("arbeitstage_in_leitlinie"):
        hinweise.add(f"Fahrtkosten: {tage} Arbeitstage angenommen, die Leitlinie nennt keine Zahl.")
    ab = fk_eing.get("staffel_ab_km", p["staffel_ab_entfernung_km"])
    staffel = fk_eing.get("staffel", True) and p["satz_mehrkilometer"] is not None and ab is not None
    if p["satz_mehrkilometer"] is not None and ab is None and entf > 30:
        hinweise.add(f"Fahrtkosten: Leitlinie erlaubt bei langen Strecken {p['satz_mehrkilometer']} € je km, nennt aber keine Schwelle. Ohne 'fahrt.staffel_ab_km' kein geringerer Satz angesetzt.")
    grenze = dec(ab) if staffel else entf
    bis = min(entf, grenze)
    rest = max(entf - grenze, D(0))
    satz = dec(p["satz"])
    satz2 = dec(p["satz_mehrkilometer"]) if staffel else satz
    betrag = (bis * 2 * satz + rest * 2 * satz2) * tage / 12
    formel = f"{bis} km x 2 x {satz} € x {tage} : 12"
    if rest:
        formel += f" + {rest} km x 2 x {satz2} € x {tage} : 12"
    return cent(betrag), formel


UNSICHERE_QUELLEN = {"bwa": "BWA", "schaetzung": "Schätzung", "angabe": "eigene Angabe"}


def selbstaendig_netto(sd, rolle, schritte, hinweise):
    """Netto bei Selbstständigen: Durchschnittsgewinn je Monat abzüglich Steuern und Vorsorge."""
    zr = sd.get("zeitraeume") or []
    if not zr:
        raise Fehler(f"{rolle}: selbstaendig.zeitraeume fehlt")
    summe = sum((dec(z.get("gewinn")) for z in zr), D(0))
    monate = sum((int(z.get("monate", 12)) for z in zr))
    for z in zr:
        schritte.append(f"Gewinn {z.get('bezeichnung', '?')} ({z.get('quelle', 'ohne Quellenangabe')}, {z.get('monate', 12)} Monate): {cent(z.get('gewinn'))} €")
    schnitt = summe / monate
    schritte.append(f"Durchschnitt {cent(summe)} € : {monate} Monate = {cent(schnitt)} € monatlich")
    unsicher = sorted({UNSICHERE_QUELLEN[z.get("quelle")] for z in zr if z.get("quelle") in UNSICHERE_QUELLEN})
    ohne = [z.get("bezeichnung", "?") for z in zr if not z.get("quelle")]
    if unsicher or ohne:
        hinweise.add(f"VORLÄUFIG: {rolle}: Einkommen beruht auf {', '.join(unsicher + (['Zeiträumen ohne Quellenangabe'] if ohne else []))}. Eine BWA ist eine ungeprüfte, vorläufige Auswertung ohne Abschlussbuchungen (Abschreibungen, Rückstellungen, Privatanteile). Ergebnis nur Platzhalter bis zur Vorlage von Steuerbescheiden und Gewinnermittlungen bzw. Jahresabschlüssen; Auskunft und Belege nach § 1605 BGB bzw. § 1580 BGB, § 235 FamFG.")
    if monate < 36:
        hinweise.add(f"{rolle}: Selbstständigeneinkommen über {monate} Monate statt des üblichen Durchschnitts der letzten drei Jahre. Schwankungen und Saisonalität können nicht ausgeglichen werden.")
    st = sd.get("steuern_jahr")
    if st is None:
        hinweise.add(f"{rolle}: Steuern auf den Gewinn fehlen (Einkommensteuer, Solidaritätszuschlag, Kirchensteuer). Netto ist zu hoch. Steuerlast aus Bescheiden (In-Prinzip) oder Berechnung des Steuerberaters ergänzen.")
        st = 0
    kv = dec(sd.get("kranken_pflege_monat"))
    av = dec(sd.get("altersvorsorge_monat"))
    netto = schnitt - dec(st) / 12 - kv - av
    schritte.append(f"- Steuern {cent(dec(st) / 12)} € (Jahr {cent(st)} € : 12)")
    schritte.append(f"- Kranken- und Pflegeversicherung {cent(kv)} €")
    schritte.append(f"- Altersvorsorge {cent(av)} €")
    if schnitt > 0 and av > schnitt * D("0.24"):
        hinweise.add(f"{rolle}: Altersvorsorge über 24 % des Gewinns (rund 20 % primär plus 4 % sekundär). Angemessenheit prüfen.")
    if not sd.get("entnahmen_geprueft"):
        hinweise.add(f"{rolle}: Privatentnahmen und Liquidität zur Plausibilisierung des Gewinns prüfen (Entnahmen deutlich über dem Gewinn sprechen für höheres verfügbares Einkommen).")
    schritte.append(f"= Nettoeinkommen aus selbstständiger Tätigkeit {cent(netto)} €")
    return cent(netto)


def bereinige(abschnitt, ll, rolle, hinweise):
    """Liefert bereinigtes Erwerbs- und sonstiges Einkommen mit Rechenschritten."""
    schritte = []
    sonst = dec(abschnitt.get("sonstige_einkuenfte")) + dec(abschnitt.get("wohnvorteil"))
    if abschnitt.get("selbstaendig"):
        netto = selbstaendig_netto(abschnitt["selbstaendig"], rolle, schritte, hinweise)
        if (abschnitt.get("berufsbedingt") or {}).get("modus") == "pauschal":
            hinweise.add(f"{rolle}: Pauschale für berufsbedingte Aufwendungen bei Selbstständigen nicht ansetzen; Betriebsausgaben sind im Gewinn bereits abgezogen.")
    else:
        netto = dec(abschnitt.get("netto"))
        schritte.append(f"Nettoerwerbseinkommen {cent(netto)} €")
        if netto > 0 and abschnitt.get("netto_basis") != "jahresschnitt":
            hinweise.add(f"{rolle}: Netto als Jahresschnitt ansetzen (Lohnsteuerbescheinigung bzw. letzte 12 Monate : 12) einschließlich Urlaubs- und Weihnachtsgeld, Boni, Überstunden, Sachbezügen und Steuererstattung im Zahlungsjahr (In-Prinzip, z. B. Leitlinien NRW 1.7). Danach 'netto_basis': 'jahresschnitt' setzen.")
    bb = abschnitt.get("berufsbedingt") or {"modus": "keine"}
    modus = bb.get("modus", "keine")
    abzug_bb = D(0)
    p = ll["berufsbedingt"]
    if modus == "pauschal":
        erlaubt = p["pauschale"]
        if erlaubt == "nein":
            hinweise.add(f"{rolle}: Leitlinie {ll['name']} kennt keine Pauschale (Nr. {p['nr']}). Pauschale trotzdem angesetzt, weil so eingegeben. Prüfen.")
        if erlaubt == "nur_fiktiv" and not abschnitt.get("fiktiv"):
            hinweise.add(f"{rolle}: Pauschale nach Nr. {p['nr']} nur bei fiktivem Einkommen. Pauschale trotzdem angesetzt, weil so eingegeben. Prüfen.")
        abzug_bb = netto * dec(p["prozent"] or 5) / 100
        if p.get("min") is not None and netto > 0:
            mindest = dec(p["min"])
            mn = p.get("min_niedrig")
            if mn and netto < dec(mn["unter_netto"]):
                mindest = dec(mn["betrag"])
            if abschnitt.get("teilzeit"):
                hinweise.add(f"{rolle}: Teilzeit, Mindestbetrag der Pauschale nicht angewandt.")
            else:
                abzug_bb = max(abzug_bb, mindest)
        if p.get("max") is not None:
            abzug_bb = min(abzug_bb, dec(p["max"]))
        abzug_bb = cent(abzug_bb)
        schritte.append(f"- Pauschale berufsbedingte Aufwendungen {abzug_bb} € (Nr. {p['nr']})")
    elif modus == "konkret":
        teile = []
        if bb.get("fahrt"):
            fkb, formel = fahrtkosten(bb["fahrt"], ll, hinweise)
            abzug_bb += fkb
            teile.append(f"Fahrtkosten {fkb} € ({formel}, Nr. {ll['fahrtkosten']['nr']})")
            if netto > 0 and fkb > netto * D("0.15"):
                hinweise.add(f"{rolle}: Fahrtkosten über 15 % des Nettoeinkommens. Unzumutbarkeit öffentlicher Verkehrsmittel und ggf. Obliegenheit zum Umzug darlegen (Leitlinien Schleswig-Holstein 10.2.2; BGH FamRZ 2002, 535).")
        if bb.get("weitere"):
            abzug_bb += dec(bb["weitere"])
            teile.append(f"weitere {cent(bb['weitere'])} €")
        abzug_bb = cent(abzug_bb)
        schritte.append(f"- berufsbedingte Aufwendungen konkret {abzug_bb} €: " + "; ".join(teile))
    erwerb_bb = max(netto - abzug_bb, D(0))
    abzuege = abschnitt.get("abzuege") or []
    summe_abz = sum((dec(a.get("betrag")) for a in abzuege), D(0))
    brutto = dec(abschnitt.get("brutto"))
    for a in abzuege:
        schritte.append(f"- {a.get('bezeichnung', 'Abzug')} {cent(a.get('betrag'))} €")
        art = a.get("art")
        if art == "altersvorsorge_sekundaer" and brutto and dec(a.get("betrag")) > brutto * D("0.04"):
            hinweise.add(f"{rolle}: Sekundäre Altersvorsorge über 4 % des Bruttoeinkommens ({cent(brutto * D('0.04'))} €). Nur bis 4 % abziehbar (5 % beim Elternunterhalt), nur tatsächlich gezahlte Beträge.")
        if art == "altersvorsorge_sekundaer" and not brutto:
            hinweise.add(f"{rolle}: Für die 4-%-Grenze der sekundären Altersvorsorge das Bruttoeinkommen ('brutto') angeben.")
        if art == "schulden":
            hinweise.add(f"{rolle}: Schulden nur mit Tilgungsplan und angemessenen Raten; beim Ehegattenunterhalt nur ehebedingte oder in der Ehe angelegte; beim Kindesunterhalt regelmäßig nur, wenn der Mindestunterhalt gesichert ist (Leitlinien Nr. 10.4). Kredite in Kenntnis der Unterhaltspflicht regelmäßig nicht.")
        if art == "umgangskosten":
            hinweise.add(f"{rolle}: Umgangskosten nur, soweit sie deutlich über den verbleibenden Kindergeldanteil hinausgehen (Leitlinien NRW 10.7); alternativ Erhöhung des Selbstbehalts.")
    if sonst:
        schritte.append(f"+ sonstige Einkünfte/Wohnvorteil {cent(sonst)} €")
    if abschnitt.get("wohnvorteil"):
        hinweise.add(f"{rolle}: Wohnvorteil: im Trennungsjahr in der Regel angemessener (subjektiver) Wohnwert, nach endgültigem Scheitern bzw. Scheidungsantrag objektiver Marktmietwert; Zinsen und Tilgung bis zur Höhe des Wohnwerts abziehen, darüber nur als Altersvorsorge oder Schuld (Leitlinien Nr. 5; BGH XII ZR 21/05).")
    # Abzüge anteilig auf Erwerb und sonstige Einkünfte (Mischeinkünfte, vgl. Leitlinien NRW 15.2)
    basis = erwerb_bb + sonst
    anteil_e = (erwerb_bb / basis) if basis else D(1)
    erwerb = erwerb_bb - summe_abz * anteil_e
    sonstige = sonst - summe_abz * (1 - anteil_e)
    gesamt = cent(erwerb + sonstige)
    schritte.append(f"= bereinigt {gesamt} €")
    return {"netto": cent(netto), "berufsbedingt": abzug_bb, "erwerb_vor_abzuege": cent(erwerb_bb),
            "abzuege": cent(summe_abz), "abzug_arten": [a.get("art") for a in abzuege], "erwerb": cent(erwerb), "sonstige": cent(sonstige),
            "gesamt": gesamt, "schritte": schritte}


def runde(betrag, ll, ehegatte=False):
    if betrag <= 0:
        return D(0)
    if ehegatte and ll["rundung"].get("ehegatte") == "fuenf_euro":
        return (betrag / 5).quantize(D(1), ROUND_HALF_UP) * 5
    if ll["rundung"]["modus"] == "aufrunden":
        return betrag.quantize(D(1), ROUND_CEILING)
    return betrag.quantize(D(1), ROUND_HALF_UP)


# --------------------------------------------------------------- Kindesunterhalt

def gruppe_fuer(dtj, einkommen):
    for g in dtj["gruppen"]:
        if einkommen <= g["bis"]:
            return g["nr"]
    return None


def kinder_monat(e, jm, dtj, ll, ein, pfl_bereinigt, hinweise):
    """Berechnet Bedarf und Zahlbeträge aller Kinder für einen Monat."""
    erw = bool(ein["pflichtiger"].get("erwerbstaetig", True))
    sb = dtj["selbstbehalt"]
    sb_notw = dec(sb["notwendig_erwerbstaetig"] if erw else sb["notwendig_nicht_erwerbstaetig"])
    sb_notw += zuschlag_wohnen(ein["pflichtiger"], sb["notwendig_wohnkosten"])
    sb_notw = kuerzung(sb_notw, ein["pflichtiger"])
    sb_angem = kuerzung(dec(sb["angemessen"]) + zuschlag_wohnen(ein["pflichtiger"], sb["angemessen_wohnkosten"]), ein["pflichtiger"])
    kg = dec(dtj["kindergeld"])
    kinder = []
    for k in ein.get("kinder", []):
        stufe, alter = altersstufe(k["geburtsdatum"], jm)
        if stufe is None:
            continue
        status = k.get("status_ab_18", "privilegiert") if stufe == 3 else "minderjaehrig"
        if k.get("ende") and jm > monat(k["ende"]):
            continue
        kinder.append({"name": k["name"], "stufe": stufe, "alter": alter, "status": status, "def": k})
    if not kinder:
        return [], {}
    n_ber = len(kinder) + (1 if ein.get("ehegatte") else 0) + int(ein.get("weitere_berechtigte", 0))
    E = pfl_bereinigt["gesamt"]
    info = {"anzahl_berechtigte": n_ber, "einkommen": E}
    if E > dtj["hoechstes_einkommen"]:
        hinweise.add(f"{mstr(jm)}: Einkommen über {dtj['hoechstes_einkommen']} €, Tabelle endet; Bedarf konkret darzulegen. Rechner nutzt Gruppe 15.")
    basis = gruppe_fuer(dtj, E) or 15
    gm = ein.get("gruppe") or {}
    if gm.get("fest"):
        gruppe = int(gm["fest"])
        info["eingruppierung"] = f"Gruppe {gruppe} fest vorgegeben"
    else:
        korr = 1 if n_ber == 1 else -(n_ber - 2) if n_ber > 2 else 0
        if gm.get("korrektur") is not None:
            korr = int(gm["korrektur"])
        gruppe = min(15, max(1, basis + korr))
        info["eingruppierung"] = f"Einkommen {E} € -> Gruppe {basis}; {n_ber} Berechtigte -> Korrektur {korr:+d} -> Gruppe {gruppe}"

    anderer = ein.get("anderer_elternteil")
    minderj = [k for k in kinder if k["status"] == "minderjaehrig" or (k["status"] == "privilegiert" and not anderer)]
    priv_quote = [k for k in kinder if k["status"] == "privilegiert" and anderer]
    volljaehrig = [k for k in kinder if k["status"] not in ("minderjaehrig", "privilegiert")]
    for k in kinder:
        if k["status"] == "privilegiert" and not anderer:
            hinweise.add(f"{k['name']}: privilegiert volljährig ohne Einkommen des anderen Elternteils. Rechner behandelt den Pflichtigen als allein barunterhaltspflichtig (wie Beispiel DT Anm. C). Bei Leistungsfähigkeit des anderen Elternteils dessen Einkommen angeben (§ 1606 Abs. 3 S. 1 BGB).")

    def volljaehrig_anteil(k, rang, vorrang, sockel_p):
        d = k["def"]
        schritt = []
        ab = gueltig(anderer["einkommen"], jm, "anderer Elternteil") if anderer else None
        ea = bereinige(ab, ll, "Anderer Elternteil", hinweise)["gesamt"] if ab else D(0)
        if k["status"] == "student_eigener_haushalt":
            bedarf = dec(dtj["student_eigener_haushalt"]["bedarf"])
            schritt.append(f"Bedarf Kind mit eigenem Haushalt {bedarf} € (DT Anm. A IV)")
        else:
            summe_eltern = E + ea
            gr = gruppe_fuer(dtj, summe_eltern) or 15
            bedarf = dec(dtj["gruppen"][gr - 1]["bedarf"][3])
            schritt.append(f"Bedarf nach Einkommen beider Eltern {cent(E)} + {cent(ea)} = {cent(summe_eltern)} € -> Gruppe {gr}, 4. Altersstufe: {bedarf} € (keine Höher-/Herabstufung)")
        if d.get("mehrbedarf"):
            bedarf += dec(d["mehrbedarf"])
            schritt.append(f"+ Mehrbedarf {cent(d['mehrbedarf'])} €")
        kgv = kg if d.get("kindergeld", True) else D(0)
        ke, ktxt = kind_einkommen(d, False)
        offen = max(bedarf - kgv - ke, D(0))
        schritt.append(f"- Kindergeld voll {kgv} € - Einkommen des Kindes {ke} €{' (' + ktxt + ')' if ktxt else ''} = offener Bedarf {cent(offen)} €")
        if anderer:
            vorweg_a = dec(ab.get("vorrangiger_kindesunterhalt"))
            sbe_a = dec(dtj["selbstbehalt"]["angemessen"])
            a1 = max(E - vorrang - sockel_p, D(0))
            a2 = max(ea - vorweg_a - sbe_a, D(0))
            quote = a1 / (a1 + a2) if (a1 + a2) else D(0)
            anteil = cent(offen * quote)
            schritt.append(f"Haftungsanteil (§ 1606 Abs. 3 S. 1 BGB): Pflichtiger {cent(E)} - Vorrang {cent(vorrang)} - Sockel {sockel_p} € = {cent(a1)} €; anderer Elternteil {cent(ea)} - Vorrang {cent(vorweg_a)} - Sockel {sbe_a} € = {cent(a2)} €; Quote {(quote * 100).quantize(D('0.01'))} % -> {anteil} €")
        else:
            anteil = cent(offen)
            hinweise.add(f"{k['name']}: volljährig, Einkommen des anderen Elternteils fehlt. Rechner setzt den vollen offenen Bedarf an; Haftungsquote nach § 1606 Abs. 3 S. 1 BGB ergänzen.")
        if anderer:
            hinweise.add("Quotenbeträge Volljähriger centgenau ausgewiesen; ob sie nach Leitlinien Nr. 25 auf volle Euro zu runden sind, wird nicht einheitlich gehandhabt.")
        return {"name": k["name"], "rang": rang, "bedarf": cent(bedarf), "zahlbetrag": anteil, "schritte": schritt, "status": k["status"]}

    def bedarf_rang1(gr):
        g = dtj["gruppen"][gr - 1]
        out = []
        for k in minderj:
            d = k["def"]
            if k["status"] == "privilegiert" and gr > basis and not gm.get("fest"):
                # keine Höherstufung bei Volljährigen (z. B. Leitlinien NRW Nr. 11.2)
                gk = basis
                bedarf = dec(dtj["gruppen"][gk - 1]["bedarf"][k["stufe"]])
                schritt = [f"Gruppe {gk} (keine Höherstufung bei Volljährigen), Altersstufe 4 (Alter {k['alter']}): {bedarf} €"]
            else:
                bedarf = dec(g["bedarf"][k["stufe"]])
                schritt = [f"Gruppe {gr}, Altersstufe {k['stufe'] + 1} (Alter {k['alter']}): {bedarf} €"]
            if d.get("umgang_abzug_prozent"):
                p = dec(d["umgang_abzug_prozent"])
                if p > 15:
                    hinweise.add(f"{k['name']}: Abzug wegen erweitertem Umgang über 15 %. BGH XII ZB 415/25: 10 bis höchstens 15 %.")
                hinweise.add(f"{k['name']}: Erweiterter Umgang (BGH XII ZB 415/25 vom 15.04.2026): nur bei deutlich über das Übliche hinausgehendem Umgang; regelmäßig 10 %, ausnahmsweise bis 15 % vom Tabellenbedarf als teilweise Erfüllung. Herabstufung wegen Mehraufwendungen ist ein getrennter Schritt ('gruppe.korrektur'). Keine Quotenberechnung wie im paritätischen Wechselmodell.")
                abz = cent(bedarf * p / 100)
                bedarf -= abz
                schritt.append(f"- Abzug erweiterter Umgang {p} % = {abz} €")
            if d.get("mehrbedarf") and not anderer:
                bedarf += dec(d["mehrbedarf"])
                schritt.append(f"+ Mehrbedarf {cent(d['mehrbedarf'])} € voll (Einkommen des anderen Elternteils fehlt)")
                hinweise.add(f"{k['name']}: Mehrbedarf tragen beide Eltern anteilig nach Einkommen (§ 1606 Abs. 3 S. 1 BGB, Leitlinien Nr. 12.4). Ohne Einkommen des anderen Elternteils setzt der Rechner ihn voll an. Kita-Verpflegung ist kein Mehrbedarf; Betreuung allein wegen Berufstätigkeit des Betreuenden auch nicht (Nr. 12.4 Abs. 2 bis 4). Mehrbedarf erst ab Verzug, Sonderbedarf auch rückwirkend.")
            kga = kg / 2 if k["status"] == "minderjaehrig" else kg
            if not d.get("kindergeld", True):
                kga = D(0)
            zahl = bedarf - kga
            schritt.append(f"- Kindergeld {'hälftig' if k['status'] == 'minderjaehrig' else 'voll'} {cent(kga)} €")
            ke, ktxt = kind_einkommen(d, k["status"] == "minderjaehrig")
            if ke:
                zahl -= ke
                schritt.append(f"- Einkommen des Kindes {ke} € ({ktxt})")
            zahl = max(cent(zahl), D(0))
            schritt.append(f"= Zahlbetrag {zahl} €")
            einfach = not (d.get("umgang_abzug_prozent") or d.get("mehrbedarf") or ke or not d.get("kindergeld", True))
            if einfach and k["status"] == "minderjaehrig":
                schritt.append(f"Dynamischer Titel: {g['prozent']} % des Mindestunterhalts der jeweiligen Altersstufe (§ 1612a BGB) abzüglich hälftiges Kindergeld")
            out.append({"name": k["name"], "rang": 1, "bedarf": cent(bedarf), "zahlbetrag": zahl, "schritte": schritt,
                        "status": k["status"]})
        return out

    # Bedarfskontrolle und Herabstufung bis Leistungsfähigkeit
    protokoll = []
    while True:
        res = bedarf_rang1(gruppe)
        summe = sum((r["zahlbetrag"] for r in res), D(0))
        rest = E - summe
        g = dtj["gruppen"][gruppe - 1]
        bkb = g["bedarfskontrollbetrag"] or (dtj["bedarfskontrollbetrag_gruppe1"]["erwerbstaetig" if erw else "nicht_erwerbstaetig"])
        if gruppe > 1 and gm.get("bedarfskontrolle", True) and not gm.get("fest") and rest < bkb:
            protokoll.append(f"Gruppe {gruppe}: Rest {cent(rest)} € unter Bedarfskontrollbetrag {bkb} € -> Herabstufung")
            gruppe -= 1
            continue
        if gruppe > 1 and rest < sb_notw:
            protokoll.append(f"Gruppe {gruppe}: Rest {cent(rest)} € unter Selbstbehalt {sb_notw} € -> Herabstufung")
            gruppe -= 1
            continue
        break
    info["herabstufung"] = protokoll
    info["gruppe"] = gruppe
    mb_kinder = [k for k in minderj if k["def"].get("mehrbedarf")] if anderer else []
    if mb_kinder:
        ab = gueltig(anderer["einkommen"], jm, "anderer Elternteil")
        ea = bereinige(ab, ll, "Anderer Elternteil", hinweise)["gesamt"]
        summe_r = sum((r["zahlbetrag"] for r in res), D(0))
        sock = dec(dtj["selbstbehalt"]["angemessen"])
        a1 = max(E - summe_r - sock, D(0))
        a2 = max(ea - sock, D(0))
        q = a1 / (a1 + a2) if (a1 + a2) else D(0)
        for k in mb_kinder:
            r = next(x for x in res if x["name"] == k["name"])
            mb = dec(k["def"]["mehrbedarf"])
            anteil = cent(mb * q)
            r["zahlbetrag"] += anteil
            r["schritte"].append(f"+ Mehrbedarf {cent(mb)} € anteilig: Pflichtiger ({cent(E)} - Kindesunterhalt {cent(summe_r)} - Sockel {sock} €) = {cent(a1)} €, anderer Elternteil ({cent(ea)} - Sockel {sock} €) = {cent(a2)} €, Quote {(q * 100).quantize(D('0.01'))} % -> {anteil} € (Leitlinien Nr. 12.4, 13.3)")
            r["schritte"].append(f"= Zahlbetrag mit Mehrbedarf {r['zahlbetrag']} €")
        hinweise.add("Mehrbedarf: Kita-Verpflegung ist kein Mehrbedarf; Sockel angemessener Selbstbehalt, bei Mangellage ggf. notwendiger (Nr. 13.3). Mehrbedarf erst ab Verzug, Sonderbedarf auch rückwirkend.")
    if priv_quote:
        vorab = sum((r["zahlbetrag"] for r in res), D(0)) if (ein.get("gruppe") or {}).get("vorabzug_minderjaehrige", True) else D(0)
        for k in priv_quote:
            res.append(volljaehrig_anteil(k, 1, vorab, sb_angem))
        hinweise.add("Privilegierte Volljährige: Sockel angemessener Selbstbehalt; Kindesunterhalt Minderjähriger vorab abgezogen (Leitlinien NRW 13.3 Abs. 2, kann). Reicht es für den Bedarf nach Gruppe 1 nicht, Sockel bis zum notwendigen Selbstbehalt herabsetzen (Nr. 13.3).")
    info["selbstbehalt_notwendig"] = sb_notw
    summe = sum((r["zahlbetrag"] for r in res), D(0))
    if res and E - summe < sb_notw:
        masse = max(E - sb_notw, D(0))
        einsatz = sum((r["zahlbetrag"] for r in res), D(0))
        info["mangelfall"] = f"Verteilungsmasse {cent(E)} - {sb_notw} = {cent(masse)} €; Einsatzbeträge (Zahlbeträge Gruppe 1) {cent(einsatz)} €; Quote {(masse / einsatz * 100).quantize(D('0.01')) if einsatz else 0} %"
        # Verteilung nach Einsatzbeträgen; Cent nach der Methode der größten Reste, damit die Summe genau der
        # Masse entspricht (deckt sich mit dem Beispiel DT Anm. C und überschreitet die Masse nie)
        roh = [((masse * r["zahlbetrag"] / einsatz) if einsatz else D(0)) for r in res]
        unten = [min(x.quantize(C, ROUND_FLOOR), r["zahlbetrag"]) for x, r in zip(roh, res)]
        rest_cent = int(((min(masse, einsatz) - sum(unten, D(0))) / C).to_integral_value(ROUND_FLOOR))
        reihenfolge = sorted(range(len(res)), key=lambda i: roh[i] - unten[i], reverse=True)
        for i in reihenfolge[:max(rest_cent, 0)]:
            if unten[i] + C <= res[i]["zahlbetrag"]:
                unten[i] += C
        for r, x, neu in zip(res, roh, unten):
            r["schritte"].append(f"Mangelfall (DT Anm. C): {r['zahlbetrag']} x {cent(masse)} : {cent(einsatz)} = {x.quantize(D('0.001'))} €, verteilt {neu} € (Cent nach größten Resten)")
            r["zahlbetrag"] = neu
        hinweise.add(f"{mstr(jm)}: Mangelfall. Gesteigerte Erwerbsobliegenheit (§ 1603 Abs. 2 BGB): fiktives Einkommen, Überstunden oder Nebentätigkeit im Rahmen des ArbZG prüfen (Leitlinien NRW 1.3); ggf. Obliegenheit zur Verbraucherinsolvenz (Nr. 10.4 Abs. 3).")
        if int(ein.get("weitere_berechtigte", 0)):
            hinweise.add(f"{mstr(jm)}: Mangelfall mit 'weitere_berechtigte': deren Unterhalt ist in der Mangelverteilung nicht enthalten. Gleichrangige Kinder aus anderen Beziehungen als eigene Einträge unter 'kinder' aufnehmen, sonst ist die Verteilung falsch.")

    # Volljährige, nicht privilegierte Kinder (Rang 4, § 1609 Nr. 4 BGB)
    vorrang = sum((r["zahlbetrag"] for r in res), D(0))
    for k in volljaehrig:
        res.append(volljaehrig_anteil(k, 4, vorrang, sb_angem))
    return res, info


def kind_einkommen(d, haelftig):
    """Anrechenbares Einkommen des Kindes: Ausbildungsvergütung minus Ausbildungsaufwand, bei Minderjährigen hälftig
    (Leitlinien Nr. 10.2.3, 12.2, 13.2). 'eigenes_einkommen' gilt als bereits anrechenbar."""
    betrag, txt = D(0), []
    if d.get("ausbildungsverguetung"):
        av = dec(d["ausbildungsverguetung"])
        aufw = dec(d.get("ausbildungsaufwand", 0 if d.get("status_ab_18") == "student_eigener_haushalt" else 100))
        rest = max(av - aufw, D(0))
        anr = rest / 2 if haelftig else rest
        betrag += anr
        txt.append(f"Ausbildungsvergütung {cent(av)} - Ausbildungsaufwand {cent(aufw)} = {cent(rest)} €" + (f", hälftig {cent(anr)} € (Nr. 12.2)" if haelftig else " (voll, Nr. 13.2)"))
    if d.get("eigenes_einkommen"):
        betrag += dec(d["eigenes_einkommen"])
        txt.append(f"weiteres anrechenbares Einkommen {cent(d['eigenes_einkommen'])} €")
    return cent(betrag), "; ".join(txt)


def zuschlag_wohnen(person, enthalten):
    wm = person.get("warmmiete")
    if wm is None:
        return D(0)
    return max(dec(wm) - dec(enthalten), D(0))


def kuerzung(sb, person):
    p = person.get("selbstbehalt_kuerzung_prozent")
    return cent(sb * (100 - dec(p)) / 100) if p else sb


# --------------------------------------------------------------- Ehegattenunterhalt

RV_BEITRAGSSATZ = {2024: D("18.6"), 2025: D("18.6"), 2026: D("18.6")}


def bremer_zuschlag(av, eu, jm):
    """Zuschlag in Prozent nach Bremer Tabelle für den vorläufigen Elementarunterhalt."""
    if av.get("bremer_tabelle"):
        for z in sorted(av["bremer_tabelle"], key=lambda r: r["bis"]):
            if eu <= dec(z["bis"]):
                return dec(z["prozent"])
        raise Fehler(f"{mstr(jm)}: vorläufiger Elementarunterhalt {cent(eu)} € liegt über der letzten Zeile der eingegebenen Bremer Tabelle")
    return dec(av["bremer_zuschlag_prozent"])


def anrechenbar_pfl(ll, pfl, ku, erw_p, vorabzug, schritte):
    anteil = dec(ll["bonus"]["anteil"])
    basis_p = pfl["erwerb"] + pfl["sonstige"]
    ant = (pfl["erwerb"] / basis_p) if basis_p > 0 else D(1)
    if ll["bonus"]["basis"] == "vor_kindesunterhalt":
        bonus_p = cent(max(pfl["erwerb_vor_abzuege"] - vorabzug, D(0)) * anteil) if erw_p else D(0)
        e_p = pfl["erwerb"] - vorabzug - bonus_p - ku * ant
        schritte.append(f"Pflichtiger: Bonus {anteil} vom Erwerbseinkommen vor Abzug Kindesunterhalt und Verbindlichkeiten"
                        + (f" (nach Abzug Altersvorsorgeunterhalt {cent(vorabzug)})" if vorabzug else "") + f" = {bonus_p} € (Nr. {ll['bonus']['nr']})")
    else:
        e_vor = pfl["erwerb"] - ku * ant - vorabzug
        bonus_p = cent(max(e_vor, D(0)) * anteil) if erw_p else D(0)
        e_p = e_vor - bonus_p
        schritte.append(f"Pflichtiger: Erwerb {pfl['erwerb']} - Kindesunterhalt (Anteil) {cent(ku * ant)}"
                        + (f" - Altersvorsorgeunterhalt {cent(vorabzug)}" if vorabzug else "") + f" = {cent(e_vor)}; Bonus {anteil} = {bonus_p} € (Nr. {ll['bonus']['nr']})")
    s_p = pfl["sonstige"] - ku * (1 - ant)
    if e_p < 0:
        s_p += e_p
        e_p = D(0)
    anr_p = cent(e_p + s_p)
    schritte.append(f"Pflichtiger anrechenbar: {cent(e_p)} € Erwerb + {cent(s_p)} € sonstige = {anr_p} €")
    return anr_p


def anrechenbar_einkommen(ll, b, erw):
    if not b:
        return D(0)
    bonus = cent(max(b["erwerb"], D(0)) * dec(ll["bonus"]["anteil"])) if erw else D(0)
    return cent(b["erwerb"] - bonus + b["sonstige"])


def ehegatte_monat(jm, dtj, ll, ein, pfl, ku_zahl_rang1, ku_zahl_r4, hinweise):
    eh = ein["ehegatte"]
    schritte = []
    berech = bereinige(gueltig(eh["einkommen"], jm, "Ehegatte"), ll, "Berechtigter", hinweise) if eh.get("einkommen") else None
    erw_p = bool(ein["pflichtiger"].get("erwerbstaetig", True))
    erw_b = bool(eh.get("erwerbstaetig", False))
    ku = ku_zahl_rang1 + ku_zahl_r4
    mb = dec(dtj["ehegatte_mindestbedarf"]["nicht_erwerbstaetig"])
    anr_b = anrechenbar_einkommen(ll, berech, erw_b)

    def stufe(vorabzug, s):
        anr_p = anrechenbar_pfl(ll, pfl, ku, erw_p, vorabzug, s)
        if berech:
            s.append(f"Berechtigter: bereinigt {berech['gesamt']} € - Bonus {cent(berech['gesamt'] - anr_b)} € = {anr_b} €")
        else:
            s.append("Berechtigter: kein Einkommen")
        bedarf = (anr_p + anr_b) / 2
        s.append(f"Bedarf (Halbteilung): ({anr_p} + {anr_b}) / 2 = {cent(bedarf)} €")
        mindest = False
        if eh.get("mindestbedarf", True) and bedarf < mb:
            s.append(f"Mindestbedarf {mb} € (Existenzminimum, BGH XII ZR 64/09; DT B III) statt {cent(bedarf)} €")
            bedarf, mindest = mb, True
        anspruch = max(bedarf - anr_b, D(0))
        s.append(f"Anspruch: {cent(bedarf)} - {anr_b} = {cent(anspruch)} €")
        return anr_p, anspruch, mindest

    # Altersvorsorgeunterhalt (§§ 1361 Abs. 1 S. 2, 1578 Abs. 3 BGB), zweistufig nach Bremer Tabelle (Leitlinien Nr. 15.4)
    av = eh.get("altersvorsorge")
    avu = D(0)
    av_aktiv = bool(av) and monat(av.get("ab") or "1900-01") <= jm
    anr_p, anspruch, mindest = stufe(D(0), schritte)
    anr_p1 = anr_p
    if av_aktiv:
        if mindest or anspruch <= 0:
            schritte.append("Kein Altersvorsorgeunterhalt: Elementarunterhalt erreicht nur den Mindestbedarf; Vorrang des Existenzminimums (Leitlinien Nr. 15.4).")
        else:
            satz = dec(av.get("rv_beitragssatz") or RV_BEITRAGSSATZ.get(jm[0], D("18.6")))
            zuschlag = bremer_zuschlag(av, anspruch, jm)
            brutto = cent(anspruch * (100 + zuschlag) / 100)
            avu = cent(brutto * satz / 100)
            schritte.append(f"Altersvorsorge Stufe 1: vorläufiger Elementarunterhalt {cent(anspruch)} € + {zuschlag} % Zuschlag (Bremer Tabelle) = Bruttobemessung {brutto} € x {satz} % Rentenversicherung = {avu} €")
            if av.get("einstufig"):
                schritte.append("Einstufige Berechnung (Leitlinien Nr. 15.4 Abs. 3): Elementarunterhalt bleibt unverändert.")
            else:
                schritte.append("Altersvorsorge Stufe 2: Altersvorsorgeunterhalt vom Einkommen des Pflichtigen vorweg abziehen, Elementarunterhalt neu:")
                anr_p, anspruch, mindest = stufe(avu, schritte)
            if not av.get("bremer_tabelle"):
                hinweise.add("Altersvorsorgeunterhalt: Zuschlag nach Bremer Tabelle ist als fester Prozentsatz eingegeben. Prüfen, ob er zur Höhe des vorläufigen Elementarunterhalts jedes Monats passt (Bremer Tabelle des jeweiligen Jahres).")
            hinweise.add("Altersvorsorgeunterhalt: vorläufiger Elementarunterhalt ohne Einkünfte des Berechtigten, die selbst zu Altersvorsorge führen, nicht gesondert bereinigt (Leitlinien NRW 15.4 Abs. 2); bei sehr guten Verhältnissen einstufig rechnen; zusätzliche Altersvorsorge des Pflichtigen kann bis 4 % Erhöhung rechtfertigen.")

    # Dreiteilung bei neuem Ehegatten (BGH FamRZ 2012, 281; Leitlinien Nr. 15.5 und 24.3)
    ne = ein["pflichtiger"].get("neuer_ehegatte")
    if ne and monat(ne.get("ab") or "1900-01") <= jm:
        rang = ne.get("rang", "gleich")
        if rang == "neuer_nachrangig":
            schritte.append("Neuer Ehegatte nachrangig (§ 1609 BGB): Anspruch des geschiedenen Ehegatten unberührt (Leitlinien Nr. 24.3 Abs. 3).")
        else:
            nb = bereinige(gueltig(ne["einkommen"], jm, "neuer Ehegatte"), ll, "neuer Ehegatte", hinweise) if ne.get("einkommen") else None
            anr_n = anrechenbar_einkommen(ll, nb, bool(ne.get("erwerbstaetig", False)))
            # Dreiteilung auf Basis des Einkommens vor Abzug des Altersvorsorgeunterhalts; begrenzt wird der Gesamtanspruch
            anr_p_dt = anr_p1 if not ne.get("anrechenbar_pflichtiger") else dec(ne["anrechenbar_pflichtiger"])
            drittel = (anr_p_dt + anr_b + anr_n) / 3
            dt_anspruch = max(drittel - anr_b, D(0))
            schritte.append(f"Dreiteilung (Leistungsfähigkeit, § 1581 BGB): ({anr_p_dt} + {anr_b} + neuer Ehegatte {anr_n}) / 3 = {cent(drittel)} €; abzüglich eigenes Einkommen {anr_b} = {cent(dt_anspruch)} €")
            gesamt = anspruch + avu
            if dt_anspruch < gesamt:
                if avu:
                    f = dt_anspruch / gesamt
                    schritte.append(f"Elementar- und Altersvorsorgeunterhalt zusammen {cent(gesamt)} € über dem Dreiteilungsbetrag: beide anteilig gekürzt (Faktor {str(f.quantize(D('0.0001'))).replace(".", ",")})")
                    anspruch, avu = anspruch * f, cent(avu * f)
                    hinweise.add(f"{mstr(jm)}: Dreiteilung begrenzt Elementar- und Altersvorsorgeunterhalt; anteilige Kürzung ist eine Annahme des Rechners, Verteilung im Einzelfall prüfen.")
                else:
                    schritte.append(f"Begrenzt auf Dreiteilungsbetrag {cent(dt_anspruch)} € (statt {cent(anspruch)} €)")
                    anspruch = dt_anspruch
            else:
                schritte.append("Dreiteilungsbetrag nicht niedriger: keine Begrenzung.")
            if rang == "neuer_vorrangig":
                hinweise.add("Neuer Ehegatte vorrangig (§ 1609 Nr. 2 BGB): Sein Anspruch geht im Rahmen der Leistungsfähigkeit vor (Leitlinien Nr. 24.3 Abs. 3); Dreiteilung ist hier nur Obergrenze. Weitere Kürzung im Einzelfall prüfen.")
            hinweise.add("Dreiteilung: Einkommen des Pflichtigen einschließlich Splittingvorteil aus der neuen Ehe ansetzen ('neuer_ehegatte.anrechenbar_pflichtiger', falls abweichend), Ersparnis durch Zusammenleben (Synergie) und Billigkeitsabwägung im Einzelfall prüfen (BGH FamRZ 2012, 281; Leitlinien Nr. 15.5).")
    if eh.get("altersvorsorge") is None:
        hinweise.add("Ehegattenunterhalt: Wird Altersvorsorgeunterhalt verlangt, 'ehegatte.altersvorsorge' mit Zuschlag nach Bremer Tabelle angeben; dann zweistufige Berechnung, der Elementarunterhalt sinkt.")

    # Leistungsfähigkeit ohne Bonus
    sbx = ll["selbstbehalt"]
    sb = sbx["ehegatte_erwerbstaetig" if erw_p else "ehegatte_nicht_erwerbstaetig"]
    if sb is None:
        sb = dtj["selbstbehalt"]["ehegatte_erwerbstaetig" if erw_p else "ehegatte_nicht_erwerbstaetig"]
    sb = kuerzung(dec(sb) + zuschlag_wohnen(ein["pflichtiger"], dtj["selbstbehalt"]["ehegatte_wohnkosten"]), ein["pflichtiger"])
    verfuegbar = pfl["gesamt"] - ku_zahl_rang1 - sb
    schritte.append(f"Leistungsfähigkeit: {pfl['gesamt']} - vorrangiger Kindesunterhalt {cent(ku_zahl_rang1)} - Selbstbehalt {sb} € (Nr. {sbx['nr']}) = {cent(verfuegbar)} €")
    begrenzt = verfuegbar < anspruch
    if begrenzt:
        anspruch = max(verfuegbar, D(0))
        schritte.append(f"Begrenzt auf {cent(anspruch)} € (Mangelfall Ehegatte)")
        hinweise.add(f"{mstr(jm)}: Ehegattenunterhalt durch Selbstbehalt begrenzt. Rang (§ 1609 Nr. 2/3 BGB) und Billigkeit prüfen.")
    if ku_zahl_r4 > 0:
        hinweise.add("Volljährige nicht privilegierte Kinder sind beim Bedarf vorweg abgezogen, aber nachrangig (§ 1609 Nr. 4 BGB). Ob der Vorwegabzug angemessen ist, im Einzelfall prüfen.")
    if pfl["gesamt"] + (berech["gesamt"] if berech else 0) > dtj["hoechstes_einkommen"]:
        hinweise.add(f"{mstr(jm)}: Familieneinkommen über {dtj['hoechstes_einkommen']} €; konkrete Bedarfsbemessung prüfen (Nr. 15.3).")
    grenze = max(verfuegbar, D(0)).quantize(D(1), ROUND_FLOOR)
    if begrenzt:
        betrag = anspruch.quantize(D(1), ROUND_FLOOR)
        schritte.append(f"Zahlbetrag auf volle Euro abgerundet, damit der Selbstbehalt gewahrt bleibt: {betrag} €")
    else:
        betrag = runde(anspruch, ll, ehegatte=True)
        if betrag > grenze:
            betrag = grenze
            schritte.append(f"Zahlbetrag gerundet, aber nicht über die Leistungsfähigkeit ({cent(verfuegbar)} €): {betrag} €")
        else:
            schritte.append(f"Zahlbetrag gerundet ({ll['rundung']['text'].rstrip('.')}, Nr. {ll['rundung']['nr']}): {betrag} €")
    avu_betrag = None
    if av_aktiv:
        rest = max(verfuegbar - betrag, D(0))
        avu_lf = min(avu, rest)
        if avu_lf < avu:
            schritte.append(f"Altersvorsorgeunterhalt durch Leistungsfähigkeit begrenzt (Vorrang Elementarunterhalt): {cent(avu)} € auf {cent(avu_lf)} €")
        avu_betrag = min(runde(avu_lf, ll, ehegatte=True), rest.quantize(D(1), ROUND_FLOOR)) if avu_lf > 0 else D(0)
        schritte.append(f"Altersvorsorgeunterhalt Zahlbetrag: {avu_betrag} € (zweckgebunden, § 1578 Abs. 3 BGB)")
    return {"anspruch": cent(anspruch), "zahlbetrag": betrag, "altersvorsorge": avu_betrag, "schritte": schritte, "art": eh.get("art", "trennung")}


# --------------------------------------------------------------- Hauptlauf

def verzugsmonat(wert):
    """Monat, ab dem Unterhalt für die Vergangenheit geschuldet ist (§ 1613 Abs. 1 S. 2 BGB: ab dem Ersten des Monats)."""
    return monat(wert) if wert else None


def pruefungen_eingabe(ein, hinweise):
    """Fallstricke, die sich aus der Eingabe allein erkennen lassen."""
    pfl = ein["pflichtiger"]
    eh = ein.get("ehegatte")
    abschnitte_p = pfl["einkommen"] if isinstance(pfl["einkommen"], list) else [pfl["einkommen"]]
    z = ein["zeitraum"]
    for a in abschnitte_p:
        sk = str(a.get("steuerklasse", "")).upper()
        if eh and eh.get("trennung") and sk in ("III", "IV", "V", "4", "3", "5"):
            tj = monat(eh["trennung"])[0]
            if monat(z["bis"])[0] > tj:
                hinweise.add(f"Pflichtiger: Steuerklasse {sk} ab Januar {tj + 1} nicht mehr maßgeblich (Zusammenveranlagung nur im Trennungsjahr). Für Zeiträume ab {tj + 1} Netto fiktiv nach Steuerklasse I bzw. II neu berechnen.")
        if pfl.get("neue_ehe") and sk in ("III", "3"):
            hinweise.add("Pflichtiger: Splittingvorteil aus neuer Ehe ist beim Kindesunterhalt (gesteigerte Unterhaltspflicht) einzusetzen, beim Unterhalt des geschiedenen Ehegatten nicht (BVerfG; BGH). Netto ggf. getrennt berechnen (vgl. OLG München 12 UF 824/24 e).")
    if eh:
        hinweise.add("Ehegattenunterhalt: Obliegenheit, Steuervorteile zu nutzen; Realsplitting (§ 10 Abs. 1a Nr. 1 EStG) bei unstreitigem oder tituliertem Unterhalt im Netto des Pflichtigen berücksichtigen (Leitlinien Nr. 10.1.1).")
        if eh.get("art") == "nachehelich":
            if not eh.get("rechtskraft_scheidung"):
                hinweise.add("Nachehelicher Unterhalt erst ab Rechtskraft der Scheidung; davor Trennungsunterhalt (nicht identisch, eigener Titel). 'ehegatte.rechtskraft_scheidung' angeben.")
            elif monat(z["von"]) < monat(eh["rechtskraft_scheidung"]):
                hinweise.add("Zeitraum beginnt vor Rechtskraft der Scheidung: für diese Monate besteht kein nachehelicher, sondern Trennungsunterhalt.")
    for k in ein.get("kinder", []):
        g = date.fromisoformat(k["geburtsdatum"])
        v, b = monat(z["von"]), monat(z["bis"])
        if v <= (g.year + 18, g.month) <= b:
            hinweise.add(f"{k['name']}: wird im Zeitraum volljährig. Ab dann haften beide Eltern anteilig, Kindergeld voll, Altersstufe 4; Einkommen des anderen Elternteils angeben. Ein Titel aus der Minderjährigkeit gilt fort (§ 244 FamFG), Abänderung prüfen.")


def rueckstand_rechnen(ein, monate_out, hinweise):
    """Rückstand je Berechtigtem mit Verzugsbeginn, Unterhaltsvorschuss und Verjährungs-/Verwirkungshinweisen."""
    stichtag = monat(ein.get("stichtag") or date.today().isoformat()[:7])
    verzug = {k["name"]: verzugsmonat(k.get("verzug_ab")) for k in ein.get("kinder", [])}
    uvg = {k["name"]: k.get("unterhaltsvorschuss") or [] for k in ein.get("kinder", [])}
    eh = ein.get("ehegatte") or {}
    if eh:
        verzug["Ehegatte"] = verzugsmonat(eh.get("verzug_ab"))
        if eh.get("altersvorsorge"):
            verzug["Ehegatte Altersvorsorge"] = verzugsmonat(eh["altersvorsorge"].get("verzug_ab") or eh.get("verzug_ab"))
            if not eh["altersvorsorge"].get("verzug_ab"):
                hinweise.add("Altersvorsorgeunterhalt für die Vergangenheit nur ab Verzug oder Auskunftsverlangen, das erkennbar auch Vorsorgeunterhalt betrifft (BGH FamRZ 2007, 193). Hier Verzugsbeginn des Elementarunterhalts übernommen; 'ehegatte.altersvorsorge.verzug_ab' prüfen.")
    rh = monat(eh["rechtshaengig_ab"]) if eh.get("rechtshaengig_ab") else None
    hat_zahlungen = bool(ein.get("zahlungen"))
    rueck = {}
    for m in monate_out:
        jm = monat(m["monat"])
        for name, soll in m["soll"].items():
            r = rueck.setdefault(name, {"soll": D(0), "ist": D(0), "soll_ab_verzug": D(0), "ist_ab_verzug": D(0),
                                        "land_uvg": D(0), "alt_verwirkung": D(0), "alt_verjaehrung": D(0), "ausgeschlossen_1585b": D(0)})
            ist = m["ist"].get(name, D(0))
            r["soll"] += soll
            r["ist"] += ist
            vz = verzug.get(name)
            if vz and jm < vz:
                continue
            if name.startswith("Ehegatte") and eh.get("art") == "nachehelich" and rh and (jm[0] * 12 + jm[1]) < (rh[0] * 12 + rh[1]) - 12:
                r["ausgeschlossen_1585b"] += max(soll - ist, D(0))
                continue
            r["soll_ab_verzug"] += soll
            r["ist_ab_verzug"] += ist
            offen = max(soll - ist, D(0))
            for u in uvg.get(name, []):
                if monat(u["von"]) <= jm <= monat(u.get("bis", "2999-12")):
                    land = min(dec(u.get("betrag")), offen)
                    r["land_uvg"] += land
            alter = (stichtag[0] * 12 + stichtag[1]) - (jm[0] * 12 + jm[1])
            if offen and alter > 12:
                r["alt_verwirkung"] += offen
            if offen and stichtag[0] > jm[0] + 3:
                r["alt_verjaehrung"] += offen
    for name, r in rueck.items():
        r["differenz"] = r["soll_ab_verzug"] - r["ist_ab_verzug"]
        r["davon_kind"] = r["differenz"] - r["land_uvg"]
        if name in verzug and verzug[name] is None and (hat_zahlungen or monat(ein["zeitraum"]["von"]) < stichtag):
            hinweise.add(f"{name}: Kein Verzugsbeginn angegeben ('verzug_ab'). Unterhalt für die Vergangenheit nur ab Auskunftsverlangen, Mahnung oder Rechtshängigkeit, jeweils ab dem Monatsersten (§ 1613 Abs. 1 BGB; nachehelich § 1585b Abs. 2 BGB). Rückstand ist ohne diese Angabe ab Zeitraumbeginn gerechnet.")
        if r["land_uvg"]:
            hinweise.add(f"{name}: In Höhe des Unterhaltsvorschusses ({cent(r['land_uvg'])} €) ist der Anspruch auf das Land übergegangen (§ 7 Abs. 1 UVG). Nur der Rest steht dem Kind zu.")
        if r["alt_verwirkung"]:
            hinweise.add(f"{name}: {cent(r['alt_verwirkung'])} € Rückstand sind älter als ein Jahr. Verwirkung prüfen: Zeitmoment kann nach gut einem Jahr erfüllt sein; bloßes Nichtgeltendmachen begründet aber noch kein Umstandsmoment (BGH, Beschluss vom 30.01.2018, XII ZB 133/17).")
        if r["alt_verjaehrung"]:
            hinweise.add(f"{name}: {cent(r['alt_verjaehrung'])} € Rückstand könnten verjährt sein (drei Jahre ab Jahresende, §§ 195, 199 BGB; titulierte künftige Ansprüche § 197 Abs. 2 BGB). Hemmung prüfen: Kinder bis 21 gegenüber Eltern, Ehegatten während der Ehe (§ 207 BGB).")
        if r["ausgeschlossen_1585b"]:
            hinweise.add(f"Ehegatte: {cent(r['ausgeschlossen_1585b'])} € nachehelicher Unterhalt liegen mehr als ein Jahr vor Rechtshängigkeit und sind nach § 1585b Abs. 3 BGB ausgeschlossen, außer bei absichtlichem Entziehen.")
    return rueck


def hinweise_buendeln(hinweise):
    """Fasst gleichlautende Monatshinweise ("JJJJ-MM: Text") zu Zeiträumen zusammen."""
    import re
    monatlich, rest = {}, []
    for h in hinweise:
        m = re.match(r"^(\d{4}-\d{2}): (.*)$", h)
        if m:
            monatlich.setdefault(m.group(2), []).append(monat(m.group(1)))
        else:
            rest.append(h)
    for text, ms in monatlich.items():
        ms.sort()
        teile, start, prev = [], ms[0], ms[0]
        for jm in ms[1:] + [None]:
            folge = jm is not None and (jm[0] * 12 + jm[1]) == (prev[0] * 12 + prev[1]) + 1
            if folge:
                prev = jm
                continue
            teile.append(mstr(start) if start == prev else f"{mstr(start)} bis {mstr(prev)}")
            if jm is not None:
                start = prev = jm
        rest.append(f"{', '.join(teile)}: {text}")
    return sorted(rest, key=lambda h: (not h.startswith("VORLÄUFIG"), h))


STATUS_AB_18 = ("privilegiert", "volljaehrig", "student_eigener_haushalt")


def validiere(ein):
    """Prüft die Eingabe vollständig, bevor gerechnet wird. Wirft Fehler mit verständlicher Meldung."""
    import re
    fehler = []

    def jm(wert, feld, tag=False):
        if not isinstance(wert, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])" + (r"(-\d{2})?" if tag else ""), wert):
            fehler.append(f"{feld}: '{wert}' ist kein gültiger Monat (JJJJ-MM{' oder JJJJ-MM-TT' if tag else ''})")
            return False
        if tag and len(wert) == 10:
            try:
                date.fromisoformat(wert)
            except ValueError:
                fehler.append(f"{feld}: '{wert}' ist kein gültiges Datum")
                return False
        return True

    def zahl(wert, feld, min0=False):
        if wert is None:
            return
        if isinstance(wert, bool) or not isinstance(wert, (int, float)):
            fehler.append(f"{feld}: '{wert}' muss eine Zahl sein (z. B. 3000.50, ohne Tausenderpunkt)")
        elif min0 and wert < 0:
            fehler.append(f"{feld}: darf nicht negativ sein ({wert})")

    def einkommen(liste, feld):
        if isinstance(liste, dict):
            liste = [liste]
        if not isinstance(liste, list) or not liste:
            fehler.append(f"{feld}: mindestens ein Einkommensabschnitt erforderlich")
            return
        for i, a in enumerate(liste):
            f = f"{feld}[{i}]"
            if not isinstance(a, dict):
                fehler.append(f"{f}: muss ein Objekt sein")
                continue
            if "ab" in a:
                jm(a["ab"], f + ".ab")
            for k in ("netto", "sonstige_einkuenfte", "wohnvorteil", "brutto", "vorrangiger_kindesunterhalt"):
                zahl(a.get(k), f"{f}.{k}", min0=True)
            for j, ab in enumerate(a.get("abzuege") or []):
                zahl(ab.get("betrag"), f"{f}.abzuege[{j}].betrag", min0=True)
                if ab.get("art") not in (None, "altersvorsorge_sekundaer", "schulden", "umgangskosten"):
                    fehler.append(f"{f}.abzuege[{j}].art: unbekannt '{ab.get('art')}'")
            bb = a.get("berufsbedingt") or {}
            if bb.get("modus") not in (None, "pauschal", "konkret", "keine"):
                fehler.append(f"{f}.berufsbedingt.modus: unbekannt '{bb.get('modus')}' (pauschal, konkret, keine)")
            if bb.get("fahrt") is not None:
                zahl(bb["fahrt"].get("entfernung_km"), f + ".berufsbedingt.fahrt.entfernung_km", min0=True)
                if bb["fahrt"].get("entfernung_km") is None:
                    fehler.append(f"{f}.berufsbedingt.fahrt.entfernung_km fehlt")
            sd = a.get("selbstaendig")
            if sd is not None:
                zr = sd.get("zeitraeume") or []
                if not zr:
                    fehler.append(f"{f}.selbstaendig.zeitraeume fehlt")
                for j, z in enumerate(zr):
                    zahl(z.get("gewinn"), f"{f}.selbstaendig.zeitraeume[{j}].gewinn")
                    mo = z.get("monate", 12)
                    if not isinstance(mo, int) or mo < 1:
                        fehler.append(f"{f}.selbstaendig.zeitraeume[{j}].monate: ganze Zahl ab 1 erforderlich")
                for k in ("steuern_jahr", "kranken_pflege_monat", "altersvorsorge_monat"):
                    zahl(sd.get(k), f"{f}.selbstaendig.{k}", min0=True)
            elif "netto" not in a:
                fehler.append(f"{f}: 'netto' oder 'selbstaendig' angeben")

    z = ein.get("zeitraum") or {}
    if jm(z.get("von"), "zeitraum.von") and jm(z.get("bis"), "zeitraum.bis") and monat(z["von"]) > monat(z["bis"]):
        fehler.append("zeitraum: 'von' liegt nach 'bis'")
    pfl = ein.get("pflichtiger")
    if not isinstance(pfl, dict):
        fehler.append("pflichtiger fehlt")
    else:
        einkommen(pfl.get("einkommen"), "pflichtiger.einkommen")
        zahl(pfl.get("warmmiete"), "pflichtiger.warmmiete", min0=True)
        zahl(pfl.get("selbstbehalt_kuerzung_prozent"), "pflichtiger.selbstbehalt_kuerzung_prozent", min0=True)
        ne = pfl.get("neuer_ehegatte")
        if ne is not None:
            if not isinstance(ne, dict):
                fehler.append("pflichtiger.neuer_ehegatte: Objekt erforderlich")
            else:
                if ne.get("rang", "gleich") not in ("gleich", "neuer_vorrangig", "neuer_nachrangig"):
                    fehler.append(f"pflichtiger.neuer_ehegatte.rang: unbekannt '{ne.get('rang')}' (gleich, neuer_vorrangig, neuer_nachrangig)")
                if ne.get("einkommen") is not None:
                    einkommen(ne["einkommen"], "pflichtiger.neuer_ehegatte.einkommen")
                if ne.get("ab"):
                    jm(ne["ab"], "pflichtiger.neuer_ehegatte.ab")
                zahl(ne.get("anrechenbar_pflichtiger"), "pflichtiger.neuer_ehegatte.anrechenbar_pflichtiger", min0=True)
                eh0 = ein.get("ehegatte") or {}
                if not eh0 or eh0.get("art", "trennung") != "nachehelich":
                    fehler.append("pflichtiger.neuer_ehegatte: Dreiteilung nur beim nachehelichen Unterhalt (ehegatte.art = nachehelich)")
    namen = set()
    for i, k in enumerate(ein.get("kinder") or []):
        f = f"kinder[{i}]"
        n = k.get("name")
        if not n:
            fehler.append(f"{f}.name fehlt")
        elif n in namen or n.startswith("Ehegatte"):
            fehler.append(f"{f}.name '{n}' doppelt oder reserviert; Namen müssen eindeutig sein")
        namen.add(n)
        g = k.get("geburtsdatum")
        try:
            date.fromisoformat(g) if isinstance(g, str) and len(g) == 10 else (_ for _ in ()).throw(ValueError())
        except ValueError:
            fehler.append(f"{f}.geburtsdatum: '{g}' fehlt oder ist kein Datum im Format JJJJ-MM-TT")
        if k.get("status_ab_18", "privilegiert") not in STATUS_AB_18:
            fehler.append(f"{f}.status_ab_18: unbekannt '{k.get('status_ab_18')}' ({', '.join(STATUS_AB_18)})")
        for feld in ("eigenes_einkommen", "mehrbedarf", "ausbildungsverguetung", "ausbildungsaufwand", "umgang_abzug_prozent"):
            zahl(k.get(feld), f"{f}.{feld}", min0=True)
        if isinstance(k.get("umgang_abzug_prozent"), (int, float)) and k["umgang_abzug_prozent"] > 50:
            fehler.append(f"{f}.umgang_abzug_prozent: {k['umgang_abzug_prozent']} % ist kein erweiterter Umgang mehr (BGH: höchstens 15 %)")
        for feld in ("verzug_ab",):
            if k.get(feld):
                jm(k[feld], f"{f}.{feld}", tag=True)
        if k.get("ende"):
            jm(k["ende"], f + ".ende")
        for j, u_ in enumerate(k.get("unterhaltsvorschuss") or []):
            jm(u_.get("von"), f"{f}.unterhaltsvorschuss[{j}].von")
            if u_.get("bis"):
                jm(u_["bis"], f"{f}.unterhaltsvorschuss[{j}].bis")
            zahl(u_.get("betrag"), f"{f}.unterhaltsvorschuss[{j}].betrag", min0=True)
    eh = ein.get("ehegatte")
    if eh is not None:
        if not isinstance(eh, dict) or not eh:
            fehler.append("ehegatte: leeres Objekt; weglassen oder Angaben machen (mindestens 'art')")
        else:
            if eh.get("art", "trennung") not in ("trennung", "nachehelich"):
                fehler.append(f"ehegatte.art: unbekannt '{eh.get('art')}' (trennung, nachehelich)")
            if eh.get("einkommen") is not None:
                einkommen(eh["einkommen"], "ehegatte.einkommen")
            for feld in ("trennung", "rechtskraft_scheidung", "rechtshaengig_ab"):
                if eh.get(feld):
                    jm(eh[feld], f"ehegatte.{feld}", tag=True)
            if eh.get("verzug_ab"):
                jm(eh["verzug_ab"], "ehegatte.verzug_ab", tag=True)
            namen.add("Ehegatte")
            av = eh.get("altersvorsorge")
            if av is not None:
                if not isinstance(av, dict):
                    fehler.append("ehegatte.altersvorsorge: Objekt erforderlich")
                else:
                    namen.add("Ehegatte Altersvorsorge")
                    if av.get("bremer_tabelle"):
                        for j, z_ in enumerate(av["bremer_tabelle"]):
                            if not isinstance(z_, dict):
                                fehler.append(f"ehegatte.altersvorsorge.bremer_tabelle[{j}]: Objekt mit 'bis' und 'prozent' erforderlich")
                                continue
                            zahl(z_.get("bis"), f"ehegatte.altersvorsorge.bremer_tabelle[{j}].bis", min0=True)
                            zahl(z_.get("prozent"), f"ehegatte.altersvorsorge.bremer_tabelle[{j}].prozent", min0=True)
                            if z_.get("bis") is None or z_.get("prozent") is None:
                                fehler.append(f"ehegatte.altersvorsorge.bremer_tabelle[{j}]: 'bis' und 'prozent' erforderlich")
                    elif av.get("bremer_zuschlag_prozent") is None:
                        fehler.append("ehegatte.altersvorsorge: 'bremer_zuschlag_prozent' oder 'bremer_tabelle' (Zeilen aus der Bremer Tabelle des Jahres) angeben")
                    else:
                        zahl(av["bremer_zuschlag_prozent"], "ehegatte.altersvorsorge.bremer_zuschlag_prozent", min0=True)
                    zahl(av.get("rv_beitragssatz"), "ehegatte.altersvorsorge.rv_beitragssatz", min0=True)
                    if av.get("ab"):
                        jm(av["ab"], "ehegatte.altersvorsorge.ab")
                    elif eh.get("art", "trennung") == "trennung":
                        fehler.append("ehegatte.altersvorsorge.ab fehlt: Trennungsunterhalt umfasst Altersvorsorge erst ab Rechtshängigkeit des Scheidungsantrags (§ 1361 Abs. 1 S. 2 BGB); Monat der Zustellung angeben")
                    if av.get("verzug_ab"):
                        jm(av["verzug_ab"], "ehegatte.altersvorsorge.verzug_ab", tag=True)
    if ein.get("anderer_elternteil") is not None:
        einkommen((ein["anderer_elternteil"] or {}).get("einkommen"), "anderer_elternteil.einkommen")
    gm = ein.get("gruppe") or {}
    if gm.get("fest") is not None and (not isinstance(gm["fest"], int) or not 1 <= gm["fest"] <= 15):
        fehler.append(f"gruppe.fest: {gm['fest']} ungültig (1 bis 15)")
    if gm.get("korrektur") is not None and not isinstance(gm["korrektur"], int):
        fehler.append("gruppe.korrektur: ganze Zahl erforderlich")
    for j, zg in enumerate(ein.get("zahlungen") or []):
        jm(zg.get("monat"), f"zahlungen[{j}].monat")
        zahl(zg.get("betrag"), f"zahlungen[{j}].betrag", min0=True)
        if zg.get("an") not in namen:
            fehler.append(f"zahlungen[{j}].an: '{zg.get('an')}' ist kein Berechtigter ({', '.join(sorted(n for n in namen if n))})")
    if ein.get("stichtag"):
        jm(ein["stichtag"], "stichtag")
    if ein.get("olg") is not None and not isinstance(ein["olg"], str):
        fehler.append("olg: Name des Oberlandesgerichts als Text (z. B. \"Celle\")")
    if fehler:
        raise Fehler("Eingabe unvollständig oder fehlerhaft:\n- " + "\n- ".join(fehler))


def berechne(ein):
    dt, lls = lade_daten()
    validiere(ein)
    ll = leitlinie_aufloesen(lls, ein.get("leitlinie"))
    hinweise = set()
    z = ein.get("zeitraum") or {}
    if not z.get("von") or not z.get("bis"):
        raise Fehler("zeitraum.von und zeitraum.bis (JJJJ-MM) fehlen")
    olg = ein.get("olg")
    if olg and not any(_olg_schluessel(o) == _olg_schluessel(olg) for o in ll["olg"]):
        raise Fehler(f"olg '{olg}' gehört nicht zur Leitlinie {ll['name']} ({', '.join(ll['olg'])})")
    fassungen = {}
    for jahr in sorted({jm[0] for jm in monate(z["von"], z["bis"])}):
        if str(jahr) in dt:
            fassungen[jahr] = leitlinie_fuer(lls, ein["leitlinie"], jahr, olg)
    zahlungen = ein.get("zahlungen", [])
    pruefungen_eingabe(ein, hinweise)
    monate_out = []
    for jm in monate(z["von"], z["bis"]):
        dtj = dt.get(str(jm[0]))
        if not dtj:
            raise Fehler(f"Keine Düsseldorfer Tabelle für {jm[0]} hinterlegt (vorhanden: {', '.join(sorted(dt))})")
        ll = fassungen[jm[0]]
        if ll.get("fassung_hinweis"):
            hinweise.add(ll["fassung_hinweis"])
        elif jm[0] < 2026:
            hinweise.add("Monate vor 2026 (Rückstand): Düsseldorfer Tabelle und Leitlinienfassung des jeweiligen Jahres angewandt.")
        if "[UNSICHER]" in json.dumps(ll, ensure_ascii=False):
            hinweise.add(f"Leitlinie {ll['name']}, Fassung {ll['fassung']}: einzelne Parameter nicht aus einer eigenen Leitlinie belegt [UNSICHER]; Annahmen im Abschnitt Parameter prüfen.")
        abschnitt = gueltig(ein["pflichtiger"]["einkommen"], jm, "Pflichtiger")
        pfl = bereinige(abschnitt, ll, "Pflichtiger", hinweise)
        kinder, kinfo = kinder_monat(None, jm, dtj, ll, ein, pfl, hinweise)
        if kinfo.get("mangelfall") and "altersvorsorge_sekundaer" in pfl["abzug_arten"]:
            ohne = dict(abschnitt)
            ohne["abzuege"] = [a for a in abschnitt.get("abzuege", []) if a.get("art") != "altersvorsorge_sekundaer"]
            pfl = bereinige(ohne, ll, "Pflichtiger", hinweise)
            pfl["schritte"].append("Sekundäre Altersvorsorge nicht abgezogen: Mindestunterhalt nicht gedeckt (z. B. Leitlinien Rostock 10.1, NRW 10.1.2).")
            kinder, kinfo = kinder_monat(None, jm, dtj, ll, ein, pfl, hinweise)
            hinweise.add(f"{mstr(jm)}: Sekundäre Altersvorsorge wegen Mangelfall nicht abgezogen und neu gerechnet.")
        r1 = sum((k["zahlbetrag"] for k in kinder if k["rang"] == 1), D(0))
        r4 = sum((k["zahlbetrag"] for k in kinder if k["rang"] == 4), D(0))
        eh = ehegatte_monat(jm, dtj, ll, ein, pfl, r1, r4, hinweise) if ein.get("ehegatte") else None
        # Leistungsfähigkeit gegenüber Rang-4-Kindern nach Ehegatten
        if r4 > 0:
            sb_angem = kuerzung(dec(dtj["selbstbehalt"]["angemessen"]) + zuschlag_wohnen(ein["pflichtiger"], dtj["selbstbehalt"]["angemessen_wohnkosten"]), ein["pflichtiger"])
            frei = pfl["gesamt"] - r1 - (eh["zahlbetrag"] if eh else 0) - sb_angem
            if frei < r4:
                faktor = max(frei, D(0)) / r4
                for k in kinder:
                    if k["rang"] == 4:
                        neu = cent(k["zahlbetrag"] * faktor)
                        k["schritte"].append(f"Leistungsfähigkeit: frei {cent(frei)} € nach Vorrang und angemessenem Selbstbehalt {sb_angem} € -> gekürzt auf {neu} €")
                        k["zahlbetrag"] = neu
        soll = {k["name"]: k["zahlbetrag"] for k in kinder}
        if eh:
            soll["Ehegatte"] = eh["zahlbetrag"]
            if eh.get("altersvorsorge") is not None:
                soll["Ehegatte Altersvorsorge"] = eh["altersvorsorge"]
        ist = {}
        for zg in zahlungen:
            if zg.get("monat") == mstr(jm):
                ist[zg["an"]] = ist.get(zg["an"], D(0)) + dec(zg.get("betrag"))
        monate_out.append({"monat": mstr(jm), "dt": jm[0], "leitlinie_fassung": ll["fassung"], "pflichtiger": pfl, "kinder": kinder, "kinder_info": kinfo,
                           "ehegatte": eh, "soll": soll, "ist": ist})
    rueck = rueckstand_rechnen(ein, monate_out, hinweise)
    basis = leitlinie_aufloesen(lls, ein["leitlinie"])

    def parameter(x):
        return {"berufsbedingt": x["berufsbedingt"], "fahrtkosten": x["fahrtkosten"], "bonus": x["bonus"],
                "selbstbehalt_ehegatte": x["selbstbehalt"], "rundung": x["rundung"], "eingruppierung": x.get("eingruppierung")}
    letzte = fassungen[max(fassungen)]
    return {"version": VERSION, "leitlinie": {k: basis.get(k) for k in ("id", "name", "olg", "quelle", "quelle_art", "verweis")},
            "olg": olg,
            "vorlaeufig": any(h.startswith("VORLÄUFIG") for h in hinweise),
            "monate": monate_out, "rueckstand": rueck, "hinweise": hinweise_buendeln(hinweise),
            "fassungen": {str(j): {"fassung": x["fassung"], "name": x["name"], "quelle": x.get("quelle"), "quelle_art": x.get("quelle_art"),
                                   "parameter": parameter(x)} for j, x in fassungen.items()},
            "parameter": parameter(letzte)}


# --------------------------------------------------------------- Ausgabe

def eur(x):
    s = f"{D(x):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def abschnitte(monate_out):
    """Fasst Monate mit identischem Ergebnis zu Zeitabschnitten zusammen."""
    out = []
    for m in monate_out:
        key = json.dumps({k: str(v) for k, v in m["soll"].items()}, sort_keys=True) + str(m["kinder_info"].get("gruppe")) + str(m["pflichtiger"]["gesamt"]) + str(m.get("leitlinie_fassung"))
        if out and out[-1]["key"] == key:
            out[-1]["bis"] = m["monat"]
            out[-1]["anzahl"] += 1
        else:
            out.append({"key": key, "von": m["monat"], "bis": m["monat"], "anzahl": 1, "m": m})
    return out


def de(text):
    """Rechenschritt für die Ausgabe: deutsche Zahlen, Rechenzeichen als Wort am Zeilenanfang."""
    import re
    for pre, wort in (("- ", "abzüglich "), ("+ ", "zuzüglich "), ("= ", "ergibt ")):
        if text.startswith(pre):
            text = wort + text[len(pre):]
            break

    def zahl(m):
        vor = m.string[max(0, m.start() - 20):m.start()]
        if vor.endswith(("Nr. ", "NRW ", "Leitlinien ", "Holstein ", "SüdL ", "Ziffer ")):
            return m.group(0)
        ganz, nach = m.group(1), m.group(2)
        if nach is None:
            if not m.string[m.end():m.end() + 2] == " €":
                return m.group(0)
            return f"{int(ganz):,}".replace(",", ".")
        return f"{int(ganz):,}".replace(",", ".") + "," + nach
    return re.sub(r"(?<![\d.,/-])(\d+)(?:\.(\d{1,2}))?(?![\d,/-]|\.\d)", zahl, text)


def markdown(r):
    L = []
    ll = r["leitlinie"]
    if any(h.startswith("VORLÄUFIG") for h in r["hinweise"]):
        L.append("# VORLÄUFIGE Unterhaltsberechnung (Testphase)\n")
        L.append("**Vorläufig:** Das Einkommen beruht ganz oder teilweise auf BWA, Schätzung oder ungeprüfter Angabe. Die Zahlen sind Platzhalter bis zur Belegprüfung.\n")
    else:
        L.append("# Unterhaltsberechnung (Testphase)\n")
    L.append(f"Leitlinie: **{ll['name']}** (OLG {', '.join(ll['olg'])}), Quelle: {ll['quelle']} ({ll['quelle_art']}). Rechner v{r['version']}, eigene Ergänzung von digitalmann, nicht von Klotzkette. Ergebnis vor Verwendung nachprüfen.\n")
    namen = []
    for m in r["monate"]:
        for n in m["soll"]:
            if n not in namen:
                namen.append(n)
    L.append("## Übersicht\n")
    L.append("| Zeitraum | Monate | bereinigtes Einkommen | Gruppe | " + " | ".join(namen) + " |")
    L.append("|---|---|---|---|" + "---|" * len(namen))
    for a in abschnitte(r["monate"]):
        m = a["m"]
        zr = a["von"] if a["von"] == a["bis"] else f"{a['von']} bis {a['bis']}"
        L.append(f"| {zr} | {a['anzahl']} | {eur(m['pflichtiger']['gesamt'])} | {m['kinder_info'].get('gruppe', '')} | " + " | ".join(eur(m["soll"].get(n, 0)) for n in namen) + " |")
    L.append("\n## Rechenweg je Zeitabschnitt\n")
    for a in abschnitte(r["monate"]):
        m = a["m"]
        zr = a["von"] if a["von"] == a["bis"] else f"{a['von']} bis {a['bis']}"
        L.append(f"### {zr} (Düsseldorfer Tabelle {m['dt']}, Leitlinie Fassung {m.get('leitlinie_fassung', m['dt'])})\n")
        L.append("**Einkommen Pflichtiger**\n")
        for s in m["pflichtiger"]["schritte"]:
            L.append(f"- {de(s)}")
        ki = m["kinder_info"]
        if ki:
            L.append(f"\n**Eingruppierung:** {de(ki.get('eingruppierung'))}")
            for p in ki.get("herabstufung", []):
                L.append(f"- {de(p)}")
            L.append(f"- maßgebende Gruppe {ki.get('gruppe')}, notwendiger Selbstbehalt {eur(ki.get('selbstbehalt_notwendig'))}")
            if ki.get("mangelfall"):
                L.append(f"- Mangelfall: {de(ki['mangelfall'])}")
        for k in m["kinder"]:
            L.append(f"\n**{k['name']}** (Rang {k['rang']}, {k['status']})\n")
            for s in k["schritte"]:
                L.append(f"- {de(s)}")
        if m["ehegatte"]:
            L.append(f"\n**Ehegattenunterhalt** ({m['ehegatte']['art']})\n")
            for s in m["ehegatte"]["schritte"]:
                L.append(f"- {de(s)}")
        L.append("")
    if any(m["ist"] for m in r["monate"]):
        L.append("## Rückstand\n")
        L.append("| Berechtigter | Soll gesamt | Soll ab Verzug | gezahlt ab Verzug | Rückstand | davon Land (UVG) | davon Berechtigter |")
        L.append("|---|---|---|---|---|---|---|")
        for n, x in r["rueckstand"].items():
            L.append(f"| {n} | {eur(x['soll'])} | {eur(x['soll_ab_verzug'])} | {eur(x['ist_ab_verzug'])} | {eur(x['differenz'])} | {eur(x['land_uvg'])} | {eur(x['davon_kind'])} |")
        L.append("")
    else:
        L.append("## Summe Zeitraum\n")
        for n, x in r["rueckstand"].items():
            L.append(f"- {n}: {eur(x['soll'])}")
        L.append("")
    L.append("## Hinweise und Annahmen\n")
    for h in r["hinweise"]:
        L.append(f"- {de(h)}")
    fs = r.get("fassungen") or {"": {"fassung": "", "name": ll["name"], "parameter": r["parameter"]}}
    for j, f in fs.items():
        p = f["parameter"]
        if len(fs) > 1 or j != "2026":
            L.append(f"\n**Parameter {f['name']}, Fassung {f['fassung']}** (Quelle: {f.get('quelle')}; {f.get('quelle_art')})\n")
        L.append(f"- Leitlinie berufsbedingte Aufwendungen (Nr. {p['berufsbedingt']['nr']}): {p['berufsbedingt']['text']}")
        L.append(f"- Leitlinie Fahrtkosten (Nr. {p['fahrtkosten']['nr']}): {p['fahrtkosten']['text']}")
        L.append(f"- Leitlinie Erwerbstätigenbonus (Nr. {p['bonus']['nr']}): {p['bonus']['text']}")
        L.append(f"- Leitlinie Ehegattenselbstbehalt (Nr. {p['selbstbehalt_ehegatte']['nr']}): {p['selbstbehalt_ehegatte']['text']}")
        L.append(f"- Leitlinie Rundung (Nr. {p['rundung']['nr']}): {p['rundung']['text']}")
        if p.get("eingruppierung"):
            L.append(f"- Leitlinie Eingruppierung: {p['eingruppierung']}")
    L.append("- Nicht automatisiert: Wechselmodell, Krankenvorsorgeunterhalt, Zuschlag nach Bremer Tabelle (Eingabe), Befristung und Herabsetzung (§ 1578b BGB), Verwirkung, Netto-Ermittlung aus Brutto, Steuern.")
    return "\n".join(L) + "\n"


def jsonable(o):
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(type(o))


def leitlinien_liste():
    _, lls = lade_daten()
    rows = ["| id | Leitlinie | OLG | Bundesland |", "|---|---|---|---|"]
    for x in lls.values():
        rows.append(f"| {x['id']} | {x['name']} | {', '.join(x['olg'])} | {', '.join(x['bundeslaender'])} |")
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("eingabe", nargs="?")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--leitlinien", action="store_true", help="verfügbare Leitlinien auflisten")
    ap.add_argument("--xlsx", metavar="PFAD", help="zusätzlich Excel-Berechnungsblatt schreiben")
    a = ap.parse_args()
    if a.leitlinien:
        print(leitlinien_liste())
        return
    if not a.eingabe:
        ap.error("eingabe.json fehlt")
    try:
        r = berechne(json.load(open(a.eingabe, encoding="utf-8")))
    except Fehler as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"FEHLER: Eingabedatei ist kein gültiges JSON ({e})", file=sys.stderr)
        sys.exit(2)
    except Exception as e:  # interner Fehler: keine Zahl ausgeben
        print(f"FEHLER (intern, bitte melden): {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(4)
    if a.xlsx:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import export_xlsx
        except ImportError:
            print("FEHLER: Für --xlsx wird openpyxl benötigt (pip install openpyxl).", file=sys.stderr)
            sys.exit(3)
        export_xlsx.schreibe(r, a.xlsx, abschnitte, de)
        print(f"Excel-Berechnungsblatt: {a.xlsx}", file=sys.stderr)
    if a.format == "json":
        print(json.dumps(r, default=jsonable, ensure_ascii=False, indent=1))
    else:
        print(markdown(r))


if __name__ == "__main__":
    main()
