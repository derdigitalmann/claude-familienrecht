#!/usr/bin/env python3
"""Regressionstests mit handgerechneten Erwartungswerten. Aufruf: python3 tests/test_unterhalt.py"""
import json
import sys
from decimal import Decimal as D
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "scripts"))
import unterhalt as u  # noqa: E402

FEHLER = []


def pruefe(name, ist, soll):
    if D(str(ist)) != D(str(soll)):
        FEHLER.append(f"{name}: ist {ist}, soll {soll}")
    else:
        print(f"ok  {name}: {soll}")


def basis(**kw):
    e = {"leitlinie": "suedl", "zeitraum": {"von": "2026-01", "bis": "2026-01"},
         "pflichtiger": {"erwerbstaetig": True, "einkommen": [{"ab": "2026-01", "netto": 2000}]}, "kinder": []}
    e.update(kw)
    return e


def m0(e):
    return u.berechne(e)["monate"][0]


# 1. Beispiel DT 2026 Anm. C (Mangelfall, drei Kinder, eines privilegiert volljährig)
r = m0(json.load(open(HIER / "dt-anm-c.json")))
pruefe("DT Anm. C K1", r["soll"]["K1"], "107.60")
pruefe("DT Anm. C K2", r["soll"]["K2"], "105.02")
pruefe("DT Anm. C K3", r["soll"]["K3"], "87.38")

# 2. Ein Kind, Höherstufung um eine Gruppe: 3.000 € -> Gruppe 4, ein Berechtigter -> Gruppe 5; Kind 8 Jahre: 670 - 129,50
r = m0(basis(pflichtiger={"einkommen": [{"ab": "2026-01", "netto": 3000}]}, kinder=[{"name": "A", "geburtsdatum": "2018-05-05"}]))
pruefe("Höherstufung Gruppe", r["kinder_info"]["gruppe"], 5)
pruefe("Höherstufung Zahlbetrag", r["soll"]["A"], "540.50")

# 3. Altersstufenwechsel im Geburtsmonat (§ 1612a Abs. 3): Kind wird im März 2026 6 Jahre
e = basis(zeitraum={"von": "2026-02", "bis": "2026-03"}, kinder=[{"name": "B", "geburtsdatum": "2020-03-31"}],
          pflichtiger={"einkommen": [{"ab": "2026-01", "netto": 2000}]})
ms = u.berechne(e)["monate"]
# Gruppe 1 +1 = 2, aber Rest 2.000 - 381,50 unter Bedarfskontrollbetrag 1.750 -> zurück auf Gruppe 1
pruefe("Stufe Februar", ms[0]["soll"]["B"], "356.50")   # 486 - 129,50
pruefe("Stufe März", ms[1]["soll"]["B"], "428.50")      # 558 - 129,50

# 4. Pauschale Niedersachsen: 5 % von 4.000 = 200, gedeckelt 150; von 600 = 30, Mindestbetrag 50
x = u.bereinige({"netto": 4000, "berufsbedingt": {"modus": "pauschal"}}, u.leitlinie_aufloesen(u.lade_daten()[1], "niedersachsen"), "P", set())
pruefe("Pauschale max", x["berufsbedingt"], "150.00")
x = u.bereinige({"netto": 600, "berufsbedingt": {"modus": "pauschal"}}, u.leitlinie_aufloesen(u.lade_daten()[1], "niedersachsen"), "P", set())
pruefe("Pauschale min", x["berufsbedingt"], "50.00")
x = u.bereinige({"netto": 4000, "berufsbedingt": {"modus": "pauschal"}}, u.leitlinie_aufloesen(u.lade_daten()[1], "suedl"), "P", set())
pruefe("Pauschale SüdL ohne Deckel", x["berufsbedingt"], "200.00")

# 5. Fahrtkosten Koblenz: 40 km -> 30 x 14 + 10 x 7 = 490
x = u.bereinige({"netto": 3000, "berufsbedingt": {"modus": "konkret", "fahrt": {"entfernung_km": 40}}}, u.leitlinie_aufloesen(u.lade_daten()[1], "koblenz"), "P", set())
pruefe("Fahrtkosten Koblenz", x["berufsbedingt"], "490.00")
# Schleswig-Holstein, Beispiel der Leitlinie Nr. 10.2.2: 50 km -> 667,33
x = u.bereinige({"netto": 3000, "berufsbedingt": {"modus": "konkret", "fahrt": {"entfernung_km": 50}}}, u.leitlinie_aufloesen(u.lade_daten()[1], "schleswig"), "P", set())
pruefe("Fahrtkosten SH (Leitlinienbeispiel)", x["berufsbedingt"], "667.33")

# 6. Ehegattenunterhalt ohne Kinder, SüdL: P 3.000, B 1.000 (beide erwerbstätig)
#    (2.700 - 900) / 2 = 900 -> aufgerundet 900
e = basis(pflichtiger={"einkommen": [{"ab": "2026-01", "netto": 3000}]},
          ehegatte={"erwerbstaetig": True, "einkommen": [{"ab": "2026-01", "netto": 1000}]})
pruefe("Ehegatte SüdL", m0(e)["soll"]["Ehegatte"], 900)
# Brandenburg: Bonus vor Abzug Kredit: Erwerb 3.000, Kredit 300 -> 3.000 x 0,1 = 300 Bonus; P = 2.700 - 300 = 2.400; B = 900; (2.400 - 900)/2 = 750
e["leitlinie"] = "brandenburg"
e["pflichtiger"]["einkommen"][0]["abzuege"] = [{"bezeichnung": "Kredit", "betrag": 300}]
pruefe("Ehegatte Brandenburg Bonus vorab", m0(e)["soll"]["Ehegatte"], 750)
#    SüdL zum Vergleich: (2.700 x 0,9 = 2.430 - 900)/2 = 765
e["leitlinie"] = "suedl"
pruefe("Ehegatte SüdL mit Kredit", m0(e)["soll"]["Ehegatte"], 765)

# 7. Selbstbehalt Ehegatte, nicht erwerbstätiger Pflichtiger (Rente 2.000): DT 1.475, Brandenburg 1.600
e = basis(pflichtiger={"erwerbstaetig": False, "einkommen": [{"ab": "2026-01", "netto": 0, "sonstige_einkuenfte": 2000}]},
          ehegatte={"einkommen": [{"ab": "2026-01", "netto": 0}]})
pruefe("SB Ehegatte DT 1.475", m0(e)["soll"]["Ehegatte"], 525)
e["leitlinie"] = "brandenburg"
pruefe("SB Ehegatte Brandenburg 1.600", m0(e)["soll"]["Ehegatte"], 400)

# 8. Rundung: NRW kaufmännisch, SüdL aufrunden. P 3.001 ohne Bonusfragen: Rente 3.001, B 0 -> 1.500,50
e = basis(pflichtiger={"erwerbstaetig": False, "einkommen": [{"ab": "2026-01", "netto": 0, "sonstige_einkuenfte": 3001}]},
          ehegatte={"einkommen": [{"ab": "2026-01", "netto": 0}]})
pruefe("Rundung SüdL", m0(e)["soll"]["Ehegatte"], 1501)
e["leitlinie"] = "nrw"
pruefe("Rundung NRW", m0(e)["soll"]["Ehegatte"], 1501)  # 1.500,50 kaufmännisch -> 1.501
e["pflichtiger"]["einkommen"][0]["sonstige_einkuenfte"] = 3000.8   # 1.500,40
pruefe("Rundung NRW abwärts", m0(e)["soll"]["Ehegatte"], 1500)
e["leitlinie"] = "suedl"
pruefe("Rundung SüdL aufwärts", m0(e)["soll"]["Ehegatte"], 1501)

# 9. Volljähriges Kind in Ausbildung (nicht privilegiert), beide Eltern: 3.000 + 2.000 = 5.000 -> Gruppe 9: 1.061
#    offen 1.061 - 259 = 802; Quote (3.000-1.750)/((3.000-1.750)+(2.000-1.750)) = 1.250/1.500 -> 668,33
e = basis(pflichtiger={"einkommen": [{"ab": "2026-01", "netto": 3000}]},
          kinder=[{"name": "V", "geburtsdatum": "2006-01-10", "status_ab_18": "volljaehrig"}],
          anderer_elternteil={"einkommen": [{"ab": "2026-01", "netto": 2000}]})
pruefe("Volljährig Quote", m0(e)["soll"]["V"], "668.33")

# 10. Student mit eigenem Haushalt, Pflichtiger allein: 990 - 259 = 731
e = basis(pflichtiger={"einkommen": [{"ab": "2026-01", "netto": 4000}]},
          kinder=[{"name": "S", "geburtsdatum": "2005-01-10", "status_ab_18": "student_eigener_haushalt"}])
pruefe("Student", m0(e)["soll"]["S"], "731.00")

# 11. Saarbrücken verweist auf NRW
ll = u.leitlinie_aufloesen(u.lade_daten()[1], "saarbruecken")
pruefe("Saarbrücken Rundung wie NRW", int(ll["rundung"]["modus"] == "kaufmaennisch"), 1)

# 12. Leitlinie fehlt -> Fehler
try:
    u.berechne(basis(leitlinie=None))
    FEHLER.append("Leitlinie fehlt: kein Fehler ausgelöst")
except u.Fehler:
    print("ok  Leitlinie fehlt -> Fehler")

# 13. Rückstand 2025 mit DT 2025: Kind 3 Jahre, 2.000 €, Gruppe 2 scheitert am Bedarfskontrollbetrag -> Gruppe 1: 482 - 127,50 = 354,50; gezahlt 300
e = basis(zeitraum={"von": "2025-06", "bis": "2025-06"}, pflichtiger={"einkommen": [{"ab": "2025-01", "netto": 2000}]}, kinder=[{"name": "R", "geburtsdatum": "2022-01-01"}],
          zahlungen=[{"monat": "2025-06", "an": "R", "betrag": 300}])
pruefe("Rückstand 2025", u.berechne(e)["rueckstand"]["R"]["differenz"], "54.50")

# 14. Privilegiert volljährig, Pflichtiger allein: keine Höherstufung. 3.000 -> Gruppe 4: 803 - 259 = 544
e = basis(pflichtiger={"einkommen": [{"ab": "2026-01", "netto": 3000}]},
          kinder=[{"name": "P", "geburtsdatum": "2007-01-10", "status_ab_18": "privilegiert"}])
pruefe("Privilegiert ohne Höherstufung", m0(e)["soll"]["P"], "544.00")
# Mit minderjährigem Geschwister: Gruppe 4 -> Rest 3.000 - 512,50 - 544 = 1.943,50 < BKB 1.950 -> Gruppe 3
e["kinder"].append({"name": "M", "geburtsdatum": "2015-06-01"})
r = m0(e)
pruefe("Geschwister minderjährig", r["soll"]["M"], "484.50")   # 614 - 129,50
pruefe("Geschwister privilegiert", r["soll"]["P"], "509.00")   # 768 - 259

if FEHLER:
    print("\nFEHLER:\n" + "\n".join(FEHLER))
    sys.exit(1)
print("\nalle Tests bestanden")
