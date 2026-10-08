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
VERSION = "0.1.0"


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


def bereinige(abschnitt, ll, rolle, hinweise):
    """Liefert bereinigtes Erwerbs- und sonstiges Einkommen mit Rechenschritten."""
    schritte = []
    netto = dec(abschnitt.get("netto"))
    sonst = dec(abschnitt.get("sonstige_einkuenfte")) + dec(abschnitt.get("wohnvorteil"))
    schritte.append(f"Nettoerwerbseinkommen {cent(netto)} €")
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
        if bb.get("weitere"):
            abzug_bb += dec(bb["weitere"])
            teile.append(f"weitere {cent(bb['weitere'])} €")
        abzug_bb = cent(abzug_bb)
        schritte.append(f"- berufsbedingte Aufwendungen konkret {abzug_bb} €: " + "; ".join(teile))
    erwerb_bb = max(netto - abzug_bb, D(0))
    abzuege = abschnitt.get("abzuege") or []
    summe_abz = sum((dec(a.get("betrag")) for a in abzuege), D(0))
    for a in abzuege:
        schritte.append(f"- {a.get('bezeichnung', 'Abzug')} {cent(a.get('betrag'))} €")
    if sonst:
        schritte.append(f"+ sonstige Einkünfte/Wohnvorteil {cent(sonst)} €")
    # Abzüge anteilig auf Erwerb und sonstige Einkünfte (Mischeinkünfte, vgl. Leitlinien NRW 15.2)
    basis = erwerb_bb + sonst
    anteil_e = (erwerb_bb / basis) if basis else D(1)
    erwerb = erwerb_bb - summe_abz * anteil_e
    sonstige = sonst - summe_abz * (1 - anteil_e)
    gesamt = cent(erwerb + sonstige)
    schritte.append(f"= bereinigt {gesamt} €")
    return {"netto": cent(netto), "berufsbedingt": abzug_bb, "erwerb_vor_abzuege": cent(erwerb_bb),
            "abzuege": cent(summe_abz), "erwerb": cent(erwerb), "sonstige": cent(sonstige),
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
        offen = max(bedarf - kgv - dec(d.get("eigenes_einkommen")), D(0))
        schritt.append(f"- Kindergeld voll {kgv} € - eigenes Einkommen {cent(d.get('eigenes_einkommen'))} € = offener Bedarf {cent(offen)} €")
        if anderer:
            vorweg_a = dec(ab.get("vorrangiger_kindesunterhalt"))
            sbe_a = dec(dtj["selbstbehalt"]["angemessen"])
            a1 = max(E - vorrang - sockel_p, D(0))
            a2 = max(ea - vorweg_a - sbe_a, D(0))
            quote = a1 / (a1 + a2) if (a1 + a2) else D(0)
            anteil = cent(offen * quote)
            schritt.append(f"Haftungsanteil (§ 1606 Abs. 3 S. 1 BGB): Pflichtiger {cent(E)} - Vorrang {cent(vorrang)} - Sockel {sockel_p} = {cent(a1)} €; anderer Elternteil {cent(ea)} - Vorrang {cent(vorweg_a)} - Sockel {sbe_a} = {cent(a2)} €; Quote {(quote * 100).quantize(D('0.01'))} % -> {anteil} €")
        else:
            anteil = cent(offen)
            hinweise.add(f"{k['name']}: volljährig, Einkommen des anderen Elternteils fehlt. Rechner setzt den vollen offenen Bedarf an; Haftungsquote nach § 1606 Abs. 3 S. 1 BGB ergänzen.")
        return {"name": k["name"], "rang": rang, "bedarf": cent(bedarf), "zahlbetrag": anteil, "schritte": schritt, "status": k["status"]}

    def bedarf_rang1(gr):
        g = dtj["gruppen"][gr - 1]
        out = []
        for k in minderj:
            d = k["def"]
            bedarf = dec(g["bedarf"][k["stufe"]])
            schritt = [f"Gruppe {gr}, Altersstufe {k['stufe'] + 1} (Alter {k['alter']}): {bedarf} €"]
            if d.get("umgang_abzug_prozent"):
                p = dec(d["umgang_abzug_prozent"])
                if p > 15:
                    hinweise.add(f"{k['name']}: Abzug wegen erweitertem Umgang über 15 %. BGH XII ZB 415/25: 10 bis höchstens 15 %.")
                abz = cent(bedarf * p / 100)
                bedarf -= abz
                schritt.append(f"- Abzug erweiterter Umgang {p} % = {abz} €")
            if d.get("mehrbedarf"):
                bedarf += dec(d["mehrbedarf"])
                schritt.append(f"+ Mehrbedarf {cent(d['mehrbedarf'])} € (Haftungsanteil prüfen)")
            kga = kg / 2 if k["status"] == "minderjaehrig" else kg
            if not d.get("kindergeld", True):
                kga = D(0)
            zahl = bedarf - kga
            schritt.append(f"- Kindergeld {'hälftig' if k['status'] == 'minderjaehrig' else 'voll'} {cent(kga)} €")
            if d.get("eigenes_einkommen"):
                zahl -= dec(d["eigenes_einkommen"])
                schritt.append(f"- anrechenbares eigenes Einkommen {cent(d['eigenes_einkommen'])} €")
            zahl = max(cent(zahl), D(0))
            schritt.append(f"= Zahlbetrag {zahl} €")
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
        hinweise.add(f"{mstr(jm)}: Mangelfall. Erwerbsobliegenheit und fiktives Einkommen prüfen (gesteigerte Erwerbsobliegenheit § 1603 Abs. 2 BGB).")

    # Volljährige, nicht privilegierte Kinder (Rang 4, § 1609 Nr. 4 BGB)
    vorrang = sum((r["zahlbetrag"] for r in res), D(0))
    for k in volljaehrig:
        res.append(volljaehrig_anteil(k, 4, vorrang, sb_angem))
    return res, info


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
        schritte.append(f"Zahlbetrag gerundet ({ll['rundung']['text']}, Nr. {ll['rundung']['nr']}): {betrag} €")
    return {"anspruch": cent(anspruch), "zahlbetrag": betrag, "schritte": schritte, "art": eh.get("art", "trennung")}


# --------------------------------------------------------------- Hauptlauf

def berechne(ein):
    dt, lls = lade_daten()
    ll = leitlinie_aufloesen(lls, ein.get("leitlinie"))
    hinweise = set()
    z = ein.get("zeitraum") or {}
    if not z.get("von") or not z.get("bis"):
        raise Fehler("zeitraum.von und zeitraum.bis (JJJJ-MM) fehlen")
    zahlungen = ein.get("zahlungen", [])
    monate_out = []
    for jm in monate(z["von"], z["bis"]):
        dtj = dt.get(str(jm[0]))
        if not dtj:
            raise Fehler(f"Keine Düsseldorfer Tabelle für {jm[0]} hinterlegt (vorhanden: {', '.join(sorted(dt))})")
        if jm[0] < 2026:
            hinweise.add("Monate vor 2026: Tabellenwerte des jeweiligen Jahres, Leitlinienparameter Stand 2026. Damalige Leitlinienfassung prüfen.")
        pfl = bereinige(gueltig(ein["pflichtiger"]["einkommen"], jm, "Pflichtiger"), ll, "Pflichtiger", hinweise)
        kinder, kinfo = kinder_monat(None, jm, dtj, ll, ein, pfl, hinweise)
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
    # Rückstand
    rueck = {}
    for m in monate_out:
        for name, s in m["soll"].items():
            r = rueck.setdefault(name, {"soll": D(0), "ist": D(0)})
            r["soll"] += s
            r["ist"] += m["ist"].get(name, D(0))
    for r in rueck.values():
        r["differenz"] = r["soll"] - r["ist"]
    return {"version": VERSION, "leitlinie": {k: ll.get(k) for k in ("id", "name", "olg", "quelle", "quelle_art", "verweis")},
            "monate": monate_out, "rueckstand": rueck, "hinweise": sorted(hinweise),
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


def markdown(r):
    L = []
    ll = r["leitlinie"]
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
            L.append(f"- {s}")
        ki = m["kinder_info"]
        if ki:
            L.append(f"\n**Eingruppierung:** {ki.get('eingruppierung')}")
            for p in ki.get("herabstufung", []):
                L.append(f"- {p}")
            L.append(f"- maßgebende Gruppe {ki.get('gruppe')}, notwendiger Selbstbehalt {eur(ki.get('selbstbehalt_notwendig'))}")
            if ki.get("mangelfall"):
                L.append(f"- Mangelfall: {ki['mangelfall']}")
        for k in m["kinder"]:
            L.append(f"\n**{k['name']}** (Rang {k['rang']}, {k['status']})\n")
            for s in k["schritte"]:
                L.append(f"- {s}")
        if m["ehegatte"]:
            L.append(f"\n**Ehegattenunterhalt** ({m['ehegatte']['art']})\n")
            for s in m["ehegatte"]["schritte"]:
                L.append(f"- {s}")
        L.append("")
    if any(m["ist"] for m in r["monate"]):
        L.append("## Rückstand\n")
        L.append("| Berechtigter | Soll | gezahlt | Differenz |")
        L.append("|---|---|---|---|")
        for n, x in r["rueckstand"].items():
            L.append(f"| {n} | {eur(x['soll'])} | {eur(x['ist'])} | {eur(x['differenz'])} |")
        L.append("")
    else:
        L.append("## Summe Zeitraum\n")
        for n, x in r["rueckstand"].items():
            L.append(f"- {n}: {eur(x['soll'])}")
        L.append("")
    L.append("## Hinweise und Annahmen\n")
    for h in r["hinweise"]:
        L.append(f"- {h}")
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
