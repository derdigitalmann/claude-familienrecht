#!/usr/bin/env python3
"""Unterhaltsrechner (Testphase). Deterministische Berechnung von Kindes- und
Ehegattenunterhalt nach Düsseldorfer Tabelle und OLG-Leitlinie, Monat für Monat.

Aufruf:
  python3 unterhalt.py eingabe.json [--format md|json] [--leitlinien]

Eigene Ergänzung von digitalmann, nicht von Klotzkette. Ergebnisse immer nachprüfen.
"""
import argparse
import json
import sys
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
D = Decimal
C = D("0.01")
VERSION = "0.2.0"


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
    """§ 1612a Abs. 3 BGB: höhere Stufe ab Beginn des Monats, in dem das Lebensjahr vollendet wird."""
    g = date.fromisoformat(geburt)
    alter = jm[0] - g.year - (1 if jm[1] < g.month else 0)
    if alter < 0:
        return None, alter
    if alter < 6:
        return 0, alter
    if alter < 12:
        return 1, alter
    if alter < 18:
        return 2, alter
    return 3, alter


# --------------------------------------------------------------- Einkommen

def fahrtkosten(fk_eing, ll, hinweise):
    p = ll["fahrtkosten"]
    entf = dec(fk_eing.get("entfernung_km"))
    if p["modell"] == "monat_je_entfernungskm":
        grenze = dec(p["staffel_ab_entfernung_km"] or 10 ** 6)
        bis = min(entf, grenze)
        rest = max(entf - grenze, D(0))
        betrag = bis * dec(p["satz"]) + rest * dec(p["satz_mehrkilometer"] or p["satz"])
        formel = f"{bis} km x {p['satz']} €" + (f" + {rest} km x {p['satz_mehrkilometer']} €" if rest else "")
        return cent(betrag), formel
    tage = dec(fk_eing.get("arbeitstage") or p["arbeitstage_default"] or 220)
    if not fk_eing.get("arbeitstage") and not p.get("arbeitstage_in_leitlinie"):
        hinweise.add(f"Fahrtkosten: {tage} Arbeitstage angenommen, die Leitlinie nennt keine Zahl.")
    staffel = fk_eing.get("staffel", True) and p["satz_mehrkilometer"] is not None
    grenze = dec(p["staffel_ab_entfernung_km"]) if staffel else entf
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
            if abschnitt.get("teilzeit"):
                hinweise.add(f"{rolle}: Teilzeit, Mindestbetrag der Pauschale nicht angewandt.")
            else:
                abzug_bb = max(abzug_bb, dec(p["min"]))
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


def runde(betrag, ll):
    if betrag <= 0:
        return D(0)
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
        for r in res:
            anteil = (masse * r["zahlbetrag"] / einsatz) if einsatz else D(0)
            neu = min(cent(anteil), r["zahlbetrag"])
            r["schritte"].append(f"Mangelfall (DT Anm. C): {r['zahlbetrag']} x {cent(masse)} : {cent(einsatz)} = {neu} € (centgenau wie Beispiel DT Anm. C, ohne Aufrundung)")
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
        aufw = dec(d.get("ausbildungsaufwand", 100))
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

def ehegatte_monat(jm, dtj, ll, ein, pfl, ku_zahl_rang1, ku_zahl_r4, hinweise):
    eh = ein["ehegatte"]
    schritte = []
    berech = bereinige(gueltig(eh["einkommen"], jm, "Ehegatte"), ll, "Berechtigter", hinweise) if eh.get("einkommen") else None
    erw_p = bool(ein["pflichtiger"].get("erwerbstaetig", True))
    erw_b = bool(eh.get("erwerbstaetig", False))
    anteil = dec(ll["bonus"]["anteil"])
    ku = ku_zahl_rang1 + ku_zahl_r4
    # Kindesunterhalt anteilig von Erwerb und sonstigen Einkünften (Mischeinkünfte)
    basis_p = pfl["erwerb"] + pfl["sonstige"]
    ant = (pfl["erwerb"] / basis_p) if basis_p > 0 else D(1)
    if ll["bonus"]["basis"] == "vor_kindesunterhalt":
        bonus_p = cent(pfl["erwerb_vor_abzuege"] * anteil) if erw_p else D(0)
        e_p = pfl["erwerb"] - bonus_p - ku * ant
        schritte.append(f"Pflichtiger: Bonus {anteil} vom Erwerbseinkommen vor Abzug Kindesunterhalt und Verbindlichkeiten = {bonus_p} € (Nr. {ll['bonus']['nr']})")
    else:
        e_vor = pfl["erwerb"] - ku * ant
        bonus_p = cent(max(e_vor, D(0)) * anteil) if erw_p else D(0)
        e_p = e_vor - bonus_p
        schritte.append(f"Pflichtiger: Erwerb {pfl['erwerb']} - Kindesunterhalt (Anteil) {cent(ku * ant)} = {cent(e_vor)}; Bonus {anteil} = {bonus_p} € (Nr. {ll['bonus']['nr']})")
    s_p = pfl["sonstige"] - ku * (1 - ant)
    anr_p = cent(e_p + s_p)
    schritte.append(f"Pflichtiger anrechenbar: {cent(e_p)} € Erwerb + {cent(s_p)} € sonstige = {anr_p} €")
    if berech:
        bonus_b = cent(max(berech["erwerb"], D(0)) * anteil) if erw_b else D(0)
        anr_b = cent(berech["erwerb"] - bonus_b + berech["sonstige"])
        schritte.append(f"Berechtigter: bereinigt {berech['gesamt']} € - Bonus {bonus_b} € = {anr_b} €")
    else:
        anr_b = D(0)
        schritte.append("Berechtigter: kein Einkommen")
    bedarf = (anr_p + anr_b) / 2
    schritte.append(f"Bedarf (Halbteilung): ({anr_p} + {anr_b}) / 2 = {cent(bedarf)} €")
    mb = dec(dtj["ehegatte_mindestbedarf"]["nicht_erwerbstaetig"])
    if eh.get("mindestbedarf", True) and bedarf < mb:
        schritte.append(f"Mindestbedarf {mb} € (Existenzminimum, BGH XII ZR 64/09; DT B III) statt {cent(bedarf)} €")
        bedarf = mb
    anspruch = max(bedarf - anr_b, D(0))
    schritte.append(f"Anspruch vor Leistungsfähigkeit: {cent(bedarf)} - {anr_b} = {cent(anspruch)} €")
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
    if begrenzt:
        betrag = anspruch.quantize(D(1), ROUND_FLOOR)
        schritte.append(f"Zahlbetrag auf volle Euro abgerundet, damit der Selbstbehalt gewahrt bleibt: {betrag} €")
    else:
        betrag = runde(anspruch, ll)
        schritte.append(f"Zahlbetrag gerundet ({ll['rundung']['text'].rstrip('.')}, Nr. {ll['rundung']['nr']}): {betrag} €")
    return {"anspruch": cent(anspruch), "zahlbetrag": betrag, "schritte": schritte, "art": eh.get("art", "trennung")}


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
        hinweise.add("Ehegattenunterhalt: Wird Altersvorsorgeunterhalt verlangt, ist zweistufig zu rechnen (Bremer Tabelle); der Elementarunterhalt sinkt dann. Der Rechner berechnet nur Elementarunterhalt.")
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
            if name == "Ehegatte" and eh.get("art") == "nachehelich" and rh and (jm[0] * 12 + jm[1]) < (rh[0] * 12 + rh[1]) - 12:
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


def berechne(ein):
    dt, lls = lade_daten()
    ll = leitlinie_aufloesen(lls, ein.get("leitlinie"))
    hinweise = set()
    z = ein.get("zeitraum") or {}
    if not z.get("von") or not z.get("bis"):
        raise Fehler("zeitraum.von und zeitraum.bis (JJJJ-MM) fehlen")
    zahlungen = ein.get("zahlungen", [])
    pruefungen_eingabe(ein, hinweise)
    monate_out = []
    for jm in monate(z["von"], z["bis"]):
        dtj = dt.get(str(jm[0]))
        if not dtj:
            raise Fehler(f"Keine Düsseldorfer Tabelle für {jm[0]} hinterlegt (vorhanden: {', '.join(sorted(dt))})")
        if jm[0] < 2026:
            hinweise.add("Monate vor 2026: Tabellenwerte des jeweiligen Jahres, Leitlinienparameter Stand 2026. Damalige Leitlinienfassung prüfen.")
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
        ist = {}
        for zg in zahlungen:
            if zg.get("monat") == mstr(jm):
                ist[zg["an"]] = ist.get(zg["an"], D(0)) + dec(zg.get("betrag"))
        monate_out.append({"monat": mstr(jm), "dt": jm[0], "pflichtiger": pfl, "kinder": kinder, "kinder_info": kinfo,
                           "ehegatte": eh, "soll": soll, "ist": ist})
    rueck = rueckstand_rechnen(ein, monate_out, hinweise)
    return {"version": VERSION, "leitlinie": {k: ll.get(k) for k in ("id", "name", "olg", "quelle", "quelle_art", "verweis")},
            "vorlaeufig": any(h.startswith("VORLÄUFIG") for h in hinweise),
            "monate": monate_out, "rueckstand": rueck, "hinweise": hinweise_buendeln(hinweise),
            "parameter": {"berufsbedingt": ll["berufsbedingt"], "fahrtkosten": ll["fahrtkosten"], "bonus": ll["bonus"],
                          "selbstbehalt_ehegatte": ll["selbstbehalt"], "rundung": ll["rundung"], "eingruppierung": ll.get("eingruppierung")}}


# --------------------------------------------------------------- Ausgabe

def eur(x):
    s = f"{D(x):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def abschnitte(monate_out):
    """Fasst Monate mit identischem Ergebnis zu Zeitabschnitten zusammen."""
    out = []
    for m in monate_out:
        key = json.dumps({k: str(v) for k, v in m["soll"].items()}, sort_keys=True) + str(m["kinder_info"].get("gruppe")) + str(m["pflichtiger"]["gesamt"])
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
        L.append(f"### {zr} (Düsseldorfer Tabelle {m['dt']})\n")
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
    p = r["parameter"]
    L.append(f"- Leitlinie berufsbedingte Aufwendungen (Nr. {p['berufsbedingt']['nr']}): {p['berufsbedingt']['text']}")
    L.append(f"- Leitlinie Fahrtkosten (Nr. {p['fahrtkosten']['nr']}): {p['fahrtkosten']['text']}")
    L.append(f"- Leitlinie Erwerbstätigenbonus (Nr. {p['bonus']['nr']}): {p['bonus']['text']}")
    L.append(f"- Leitlinie Ehegattenselbstbehalt (Nr. {p['selbstbehalt_ehegatte']['nr']}): {p['selbstbehalt_ehegatte']['text']}")
    L.append(f"- Leitlinie Eingruppierung: {p['eingruppierung']}")
    L.append("- Nicht automatisiert: Wechselmodell, Altersvorsorge- und Krankenvorsorgeunterhalt, Dreiteilung mit neuem Ehegatten, Befristung und Herabsetzung (§ 1578b BGB), Verwirkung, Netto-Ermittlung aus Brutto, Steuern.")
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
    if a.format == "json":
        print(json.dumps(r, default=jsonable, ensure_ascii=False, indent=1))
    else:
        print(markdown(r))


if __name__ == "__main__":
    main()
