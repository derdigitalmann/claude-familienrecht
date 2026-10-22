#!/usr/bin/env python3
"""Referenzfälle aus fremden, öffentlich zugänglichen Berechnungen (Stand 22.10.2026).

Quelle: smartunterhalt.de, Ratgeber > Fallbeispiele (nur Eingangs- und Ergebniszahlen übernommen).
Wo der Rechner bewusst anders rechnet, ist der Unterschied mit Begründung als ABWEICHUNG festgehalten.
Aufruf: python3 tests/test_referenzfaelle.py
"""
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


def monat(e, i=0):
    return u.berechne(e)["monate"][i]


def eink(netto, ab="2026-01"):
    return {"ab": ab, "netto": netto, "netto_basis": "jahresschnitt"}


# 1. Kindesunterhalt nach Trennung (Familie Müller), DT 2026
#    https://www.smartunterhalt.de/ratgeber/fallbeispiele/fallbeispiel-kindesunterhalt-nach-trennung
#    Vater 3.400 € bereinigt, Mutter 1.600 €, Kinder 11 und 6, Mehrbedarf Geige 120 €.
#    Erwartet: Gruppe 5, je 540,50 €; Mutter unter 1.750 € -> Vater trägt Mehrbedarf allein (120 €).
e = {"leitlinie": "nrw", "zeitraum": {"von": "2026-05", "bis": "2026-05"},
     "pflichtiger": {"einkommen": [eink(3400)]},
     "anderer_elternteil": {"einkommen": [eink(1600)]},
     "kinder": [{"name": "Lena", "geburtsdatum": "2014-09-01", "mehrbedarf": 120},
                {"name": "Noah", "geburtsdatum": "2019-09-01"}]}
m = monat(e)
pruefe("Müller Gruppe", m["kinder_info"]["gruppe"], 5)
pruefe("Müller Noah", m["soll"]["Noah"], "540.50")
pruefe("Müller Lena inkl. Mehrbedarf 120", m["soll"]["Lena"], "660.50")
# ABWEICHUNG (bewusst): Für Lena mit 12 Jahren prüft die Quelle den Bedarfskontrollbetrag mit Tabellenbeträgen
# (784 + 670) und stuft auf Gruppe 4 herab. Der Rechner prüft mit Zahlbeträgen (654,50 + 540,50 = 1.195;
# Rest 2.205 > 2.050) und bleibt bei Gruppe 5. DT Anm. A III legt die Bezugsgröße nicht ausdrücklich fest.
e["zeitraum"] = {"von": "2026-09", "bis": "2026-09"}
e["kinder"][0]["mehrbedarf"] = 0
pruefe("Müller Lena 12 J. (Rechner: Gruppe 5)", monat(e)["soll"]["Lena"], "654.50")

# 2. Unterhalt bei Selbständigen, Kind 8 Jahre, DT 2026
#    https://www.smartunterhalt.de/ratgeber/fallbeispiele/fallbeispiel-unterhalt-selbstaendige
#    Netto 2023-2025: 21.000 / 24.000 / 27.500 € (Gewinn - Steuern - Vorsorge). Erwartet 428,50 €.
sd = {"zeitraeume": [{"bezeichnung": "2023", "quelle": "steuerbescheid", "gewinn": 44000},
                     {"bezeichnung": "2024", "quelle": "steuerbescheid", "gewinn": 50000},
                     {"bezeichnung": "2025", "quelle": "steuerbescheid", "gewinn": 57000}],
      "steuern_jahr": (12200 + 14500 + 17200) / 3,
      "kranken_pflege_monat": (10800 + 11500 + 12300) / 36,
      "altersvorsorge_monat": 0, "entnahmen_geprueft": True}
e = {"leitlinie": "nrw", "zeitraum": {"von": "2026-04", "bis": "2026-04"},
     "pflichtiger": {"einkommen": [{"ab": "2026-01", "selbstaendig": sd}]},
     "kinder": [{"name": "Noah", "geburtsdatum": "2018-01-15"}]}
m = monat(e)
pruefe("Selbständige Netto 3-Jahres-Schnitt", m["pflichtiger"]["gesamt"], "2013.89")
pruefe("Selbständige Variante 1", m["soll"]["Noah"], "428.50")
#    Variante 2 (Prognose 1.833 €): Mangelfall, 1.833 - 1.450 = 383 €
e["pflichtiger"]["einkommen"] = [eink(1833)]
pruefe("Selbständige Variante 2 Mangelfall", monat(e)["soll"]["Noah"], "383.00")

# 3. Volljährige: privilegierte Schülerin (18) und Student mit eigenem Haushalt (20), DT 2026
#    https://www.smartunterhalt.de/ratgeber/fallbeispiele/fallbeispiel-unterhalt-volljaehrige-kinder
#    Vater 4.100 €, Mutter 1.900 €. Erwartet Leonie (nur Vater) 635 €, Jonas: 990 - 380 BAföG - 259 = 351 € offen.
e = {"leitlinie": "nrw", "zeitraum": {"von": "2026-06", "bis": "2026-06"},
     "pflichtiger": {"einkommen": [eink(4100)]},
     "kinder": [{"name": "Leonie", "geburtsdatum": "2008-03-01", "status_ab_18": "privilegiert"},
                {"name": "Jonas", "geburtsdatum": "2006-02-01", "status_ab_18": "student_eigener_haushalt",
                 "eigenes_einkommen": 380}]}
m = monat(e)
pruefe("Volljährige Leonie (Vater allein)", m["soll"]["Leonie"], "635.00")
pruefe("Volljährige Jonas offener Bedarf (Vater allein)", m["soll"]["Jonas"], "351.00")
# ABWEICHUNG (bewusst): Mit Einkommen der Mutter verteilt die Quelle Jonas' 351 € im Verhältnis 2.350 : 150
# (94 %, 329,94 €) ohne Abzug des vorrangigen Unterhalts für Leonie. Der Rechner kürzt nach Leitlinien NRW 13.3 Abs. 2
# vorher um vorrangige Unterhaltsleistungen. Zudem bemisst er Leonies Bedarf nach dem Einkommen beider Eltern
# (Quelle: nur Vater). Daher keine Gleichheit erwartet; nur Plausibilität geprüft.
e["anderer_elternteil"] = {"einkommen": [eink(1900)]}
m = monat(e)
jonas = D(str(m["soll"]["Jonas"]))
if not (D("0") < jonas < D("351")):
    FEHLER.append(f"Volljährige mit Mutter: Jonas {jonas} nicht im Bereich 0 bis 351")
else:
    print(f"ok  Volljährige mit Mutter: Jonas {jonas} (Quelle 329,94; Abweichung dokumentiert)")

# 4. Kindesunterhalt bei Selbständigkeit, 2 Kinder (7 und 10), bereinigt 4.430 €, DT 2026
#    https://www.smartunterhalt.de/ratgeber/fallbeispiele/kindesunterhalt-bei-selbstaendigkeit
#    Erwartet: Gruppe 7, je 629,50 €.
e = {"leitlinie": "nrw", "zeitraum": {"von": "2026-06", "bis": "2026-06"},
     "pflichtiger": {"einkommen": [eink(4430)]},
     "kinder": [{"name": "K7", "geburtsdatum": "2019-01-01"}, {"name": "K10", "geburtsdatum": "2016-01-01"}]}
m = monat(e)
pruefe("Grafikdesigner Gruppe", m["kinder_info"]["gruppe"], 7)
pruefe("Grafikdesigner K7", m["soll"]["K7"], "629.50")
pruefe("Grafikdesigner K10", m["soll"]["K10"], "629.50")

# 5. Ausbildungsvergütung, DT 2026
#    https://www.smartunterhalt.de/ratgeber/grundlagen/unterhalt-ausbildung-ausbildungsverguetung
#    a) 17 Jahre, 700 € netto, Pflichtiger 3.000 €: Quelle 751 - 129,50 - 300 = 321,50 € (Gruppe 4, ohne Höherstufung).
e = {"leitlinie": "nrw", "zeitraum": {"von": "2026-06", "bis": "2026-06"},
     "pflichtiger": {"einkommen": [eink(3000)]},
     "kinder": [{"name": "A17", "geburtsdatum": "2009-01-01", "ausbildungsverguetung": 700}],
     "gruppe": {"korrektur": 0}}
pruefe("Azubi 17 ohne Höherstufung", monat(e)["soll"]["A17"], "321.50")
# ABWEICHUNG (bewusst): Ohne Vorgabe stuft der Rechner bei nur einem Berechtigten eine Gruppe hoch (DT Anm. A I,
# Leitlinien Nr. 11.2: "Zuschläge"): 784 - 129,50 - 300 = 354,50 €.
del e["gruppe"]
pruefe("Azubi 17 mit Höherstufung (Rechner)", monat(e)["soll"]["A17"], "354.50")
#    b) 19 Jahre, im Haushalt, 780 € netto; Eltern 3.400 € und 1.900 €: Restbedarf 1.061 - 680 - 259 = 122 €,
#       Quote 1.650 : 150 -> 111,83 € für Elternteil A.
e = {"leitlinie": "nrw", "zeitraum": {"von": "2026-06", "bis": "2026-06"},
     "pflichtiger": {"einkommen": [eink(3400)]},
     "anderer_elternteil": {"einkommen": [eink(1900)]},
     "kinder": [{"name": "A19", "geburtsdatum": "2007-01-01", "status_ab_18": "volljaehrig", "ausbildungsverguetung": 780}]}
pruefe("Azubi 19 Anteil Elternteil A", monat(e)["soll"]["A19"], "111.83")
#    c) 21 Jahre, eigener Haushalt, 850 € netto: 990 - 850 - 259 < 0 -> kein Anspruch (kein Ausbildungsaufwand abzuziehen).
e = {"leitlinie": "nrw", "zeitraum": {"von": "2026-06", "bis": "2026-06"},
     "pflichtiger": {"einkommen": [eink(3400)]},
     "kinder": [{"name": "A21", "geburtsdatum": "2005-01-01", "status_ab_18": "student_eigener_haushalt", "ausbildungsverguetung": 850}]}
pruefe("Azubi 21 eigener Haushalt", monat(e)["soll"]["A21"], "0.00")

# 6. Bedarfskontrollbetrag, 3.400 €, Kinder 4, 8 und 14 Jahre, DT 2026
#    https://www.smartunterhalt.de/ratgeber/grundlagen/bedarfskontrollbetrag-duesseldorfer-tabelle
#    Quelle: mit Zahlbeträgen Herabstufung bis Gruppe 3 (Rest 1.920,50 € >= 1.850 €); mit Tabellenbeträgen Gruppe 1.
e = {"leitlinie": "nrw", "zeitraum": {"von": "2026-06", "bis": "2026-06"},
     "pflichtiger": {"einkommen": [eink(3400)]},
     "kinder": [{"name": "K4", "geburtsdatum": "2022-01-01"}, {"name": "K8", "geburtsdatum": "2018-01-01"},
                {"name": "K14", "geburtsdatum": "2012-01-01"}]}
m = monat(e)
pruefe("BKB drei Kinder Gruppe (Zahlbetragsmethode)", m["kinder_info"]["gruppe"], 3)
pruefe("BKB K14", m["soll"]["K14"], "589.50")   # 719 - 129,50

# 7. Kita-Mehrbedarf 180 €, Kind 3 Jahre, Eltern 3.400 € und 2.600 €, ohne Höherstufung
#    https://www.smartunterhalt.de/ratgeber/grundlagen/kindesunterhalt-mehrbedarf-sonderbedarf
#    ABWEICHUNG (bewusst): Quelle 66 % ohne Vorabzug des Kindesunterhalts (118,80 €). Rechner zieht den Zahlbetrag
#    454,50 € vorab ab (Leitlinien NRW 12.4 i. V. m. 13.3): (3.400 - 454,50 - 1.750) : ((1.195,50) + 850) -> 105,20 €.
e = {"leitlinie": "nrw", "zeitraum": {"von": "2026-06", "bis": "2026-06"},
     "pflichtiger": {"einkommen": [eink(3400)]},
     "anderer_elternteil": {"einkommen": [eink(2600)]},
     "kinder": [{"name": "Kita", "geburtsdatum": "2023-01-01", "mehrbedarf": 180}],
     "gruppe": {"korrektur": 0}}
pruefe("Kita Zahlbetrag inkl. Mehrbedarfsanteil", monat(e)["soll"]["Kita"], "559.70")

if FEHLER:
    print("\nFEHLER:\n" + "\n".join(FEHLER))
    sys.exit(1)
print("\nalle Referenzfälle bestanden")
