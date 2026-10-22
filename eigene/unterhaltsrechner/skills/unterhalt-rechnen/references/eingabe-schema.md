# Eingabeschema

Alle Beträge in Euro je Monat. Monate als `JJJJ-MM`. Felder ohne Angabe gelten als 0 bzw. Standard.

```json
{
  "leitlinie": "suedl",
  "zeitraum": {"von": "2025-11", "bis": "2026-06"},

  "pflichtiger": {
    "erwerbstaetig": true,
    "warmmiete": 700,
    "selbstbehalt_kuerzung_prozent": 10,
    "einkommen": [
      {
        "ab": "2025-01",
        "netto": 3600,
        "sonstige_einkuenfte": 0,
        "wohnvorteil": 0,
        "fiktiv": false,
        "teilzeit": false,
        "berufsbedingt": {"modus": "konkret", "fahrt": {"entfernung_km": 40, "arbeitstage": 220, "staffel": true}, "weitere": 0},
        "abzuege": [{"bezeichnung": "Kredit ehebedingt", "betrag": 150}]
      }
    ]
  },

  "kinder": [
    {"name": "Lena", "geburtsdatum": "2014-03-15", "status_ab_18": "privilegiert",
     "kindergeld": true, "eigenes_einkommen": 0, "mehrbedarf": 0, "umgang_abzug_prozent": 0, "ende": null}
  ],

  "ehegatte": {
    "art": "trennung",
    "erwerbstaetig": true,
    "mindestbedarf": true,
    "einkommen": [{"ab": "2025-01", "netto": 1300, "berufsbedingt": {"modus": "pauschal"}}]
  },

  "anderer_elternteil": {
    "einkommen": [{"ab": "2025-01", "netto": 2000, "vorrangiger_kindesunterhalt": 0}]
  },

  "gruppe": {"fest": null, "korrektur": null, "bedarfskontrolle": true, "vorabzug_minderjaehrige": true},
  "weitere_berechtigte": 0,

  "zahlungen": [{"monat": "2025-11", "an": "Lena", "betrag": 400}, {"monat": "2025-11", "an": "Ehegatte", "betrag": 300}]
}
```

## Felder

| Feld | Bedeutung |
|---|---|
| `leitlinie` | Pflicht. `id` aus `--leitlinien`. Vorher abfragen. |
| `einkommen[]` | Abschnitte; je Monat gilt der letzte Abschnitt mit `ab` kleiner oder gleich dem Monat. |
| `netto` | Nettoerwerbseinkommen (Jahresschnitt). Der Erwerbstätigenbonus gilt nur hierfür. |
| `sonstige_einkuenfte`, `wohnvorteil` | Einkünfte ohne Bonus (Rente, ALG, Miete, Wohnwert nach Abzug von Zins und Tilgung). |
| `berufsbedingt.modus` | `pauschal` (Prozentsatz, Mindest- und Höchstbetrag der Leitlinie), `konkret` (Fahrtkosten nach Leitliniensatz und/oder `weitere`), `keine`. |
| `fahrt.staffel` | `false` schaltet den geringeren Satz für Mehrkilometer ab (Leitlinien: "kann"). |
| `fiktiv`, `teilzeit` | Steuern die Pauschale (NRW nur bei fiktivem Einkommen; Mindestbetrag nicht bei Teilzeit). |
| `netto_basis` | `jahresschnitt`, wenn das Netto als Jahresschnitt inkl. Sonderzahlungen ermittelt ist (sonst Hinweis). |
| `brutto` | Bruttoeinkommen für die 4-%-Grenze der sekundären Altersvorsorge. |
| `steuerklasse` | z. B. `III`; mit `ehegatte.trennung` Hinweis auf fiktive Steuerklasse ab dem Folgejahr. |
| `abzuege[]` | Kredite, Altersvorsorge, Betreuungskosten usw. Werden anteilig auf Erwerb und sonstige Einkünfte verteilt. Optional `art`: `altersvorsorge_sekundaer` (entfällt automatisch im Mangelfall, 4-%-Prüfung), `schulden`, `umgangskosten` (jeweils Prüfhinweis). |
| `warmmiete` | erhöht den Selbstbehalt um den Betrag über dem enthaltenen Wohnanteil. Angemessenheit prüfen. |
| `selbstbehalt_kuerzung_prozent` | z. B. 10 bei Zusammenleben mit leistungsfähigem Partner. |
| `status_ab_18` | `privilegiert` (§ 1603 Abs. 2 S. 2 BGB, Rang 1), `volljaehrig` (Rang 4), `student_eigener_haushalt` (Rang 4, fester Bedarf). |
| `eigenes_einkommen` | anrechenbares Einkommen des Kindes, bei Ausbildungsvergütung nach Abzug des ausbildungsbedingten Mehrbedarfs (Leitlinien Nr. 10.2.3, i. d. R. 100 €). |
| `ausbildungsverguetung`, `ausbildungsaufwand` | Vergütung des Kindes; minus Aufwand (Standard 100 €), bei Minderjährigen hälftig, bei Volljährigen voll angerechnet. |
| `verzug_ab` | Datum des Auskunftsverlangens, der Mahnung oder Rechtshängigkeit; Rückstand ab dem Monatsersten (§ 1613 Abs. 1 BGB). Auch bei `ehegatte`. |
| `unterhaltsvorschuss[]` | `{"von", "bis", "betrag"}`; Rückstand wird in Anteil Land (§ 7 UVG) und Kind geteilt. |
| `umgang_abzug_prozent` | Abzug vom Tabellenbedarf bei erweitertem Umgang, 10 bis 15 (BGH XII ZB 415/25). |
| `mehrbedarf` | wird dem Bedarf zugeschlagen; anteilige Haftung beider Eltern gesondert prüfen. |
| `ende` | letzter Unterhaltsmonat eines Kindes. |
| `ehegatte.trennung` | Trennungsmonat (Steuerklassenhinweis). |
| `ehegatte.rechtskraft_scheidung`, `ehegatte.rechtshaengig_ab` | nachehelicher Unterhalt erst ab Rechtskraft; Monate mehr als ein Jahr vor Rechtshängigkeit ausgeschlossen (§ 1585b Abs. 3 BGB). |
| `pflichtiger.neue_ehe` | `true` bei Wiederheirat (Hinweis zum Splittingvorteil). |
| `stichtag` | JJJJ-MM für Verwirkungs- und Verjährungshinweise (Standard: heute). |
| `ehegatte.mindestbedarf` | Bedarf mindestens Existenzminimum 1.200 € (Standard `true`). |
| `anderer_elternteil` | nur für volljährige Kinder (Haftungsquote). `vorrangiger_kindesunterhalt`: dessen vorrangige Unterhaltslasten. |
| `gruppe.fest` | erzwingt eine Einkommensgruppe. Herabstufung wegen Selbstbehalt bleibt aktiv. |
| `gruppe.korrektur` | ersetzt die automatische Höher-/Herabstufung nach Zahl der Berechtigten (Standard: +1 bei einem, -1 je Berechtigten über zwei). |
| `gruppe.bedarfskontrolle` | Herabstufung, wenn der Rest nach Kindesunterhalt unter dem Bedarfskontrollbetrag liegt (Standard `true`). |
| `weitere_berechtigte` | zusätzliche Unterhaltsberechtigte für die Eingruppierung (z. B. Kind aus anderer Beziehung). |
| `zahlungen[]` | für den Rückstand; `an` ist der Kindesname oder `Ehegatte`. |

## Selbstständige

Statt `netto` ein Objekt `selbstaendig` im Einkommensabschnitt:

```json
{"ab": "2026-01", "berufsbedingt": {"modus": "keine"},
 "selbstaendig": {
   "zeitraeume": [
     {"bezeichnung": "2023", "quelle": "steuerbescheid", "gewinn": 58000},
     {"bezeichnung": "2024", "quelle": "jahresabschluss", "gewinn": 64000},
     {"bezeichnung": "BWA 01-08/2026", "quelle": "bwa", "gewinn": 46400, "monate": 8}
   ],
   "steuern_jahr": 14800,
   "kranken_pflege_monat": 780,
   "altersvorsorge_monat": 600,
   "entnahmen_geprueft": true}}
```

| Feld | Bedeutung |
|---|---|
| `zeitraeume[].quelle` | `steuerbescheid`, `jahresabschluss`, `gewinnermittlung` gelten als belastbar; `bwa`, `schaetzung`, `angabe` oder fehlende Quelle machen das Ergebnis **vorläufig** (Kopfzeile und `vorlaeufig: true`). |
| `monate` | Standard 12; für unterjährige BWA die Zahl der Monate. Unter 36 Monaten gibt das Skript einen Hinweis aus. |
| `steuern_jahr` | Einkommensteuer, Soli, Kirchensteuer auf den Gewinn (In-Prinzip). Fehlt der Wert, warnt das Skript, weil das Netto dann zu hoch ist. |
| `altersvorsorge_monat` | Hinweis, wenn über 24 % des Gewinns. |
| `entnahmen_geprueft` | ohne `true` Hinweis auf Plausibilisierung über Privatentnahmen. |

Netto = Durchschnittsgewinn je Monat - Steuern/12 - Kranken- und Pflegeversicherung - Altersvorsorge. Keine Pauschale für berufsbedingte Aufwendungen (Hinweis, falls doch eingegeben). Der Erwerbstätigenbonus gilt auch für Selbstständigeneinkommen.

## Rechenregeln des Skripts

- Altersstufe wechselt ab dem Monat, in dem das Kind 6, 12 oder 18 wird (§ 1612a Abs. 3 BGB). Für die 4. Altersstufe gilt dieselbe Regel.
- Tabellenwerte des jeweiligen Kalenderjahres (DT 2024, 2025, 2026). Leitlinienparameter Stand 2026.
- Herabstufung Gruppe für Gruppe, bis Bedarfskontrollbetrag und notwendiger Selbstbehalt gewahrt sind; reicht auch Gruppe 1 nicht, Mangelverteilung nach DT Anm. C, centgenau.
- Ehegattenunterhalt: Vorwegabzug Kindesunterhalt (Zahlbeträge), Erwerbstätigenbonus nach Leitlinie, Halbteilung, Mindestbedarf, Leistungsfähigkeit ohne Bonus gegen den Ehegattenselbstbehalt der Leitlinie. Bei Begrenzung durch den Selbstbehalt wird abgerundet.
- Volljährige: Bedarf nach zusammengerechnetem Einkommen beider Eltern, volles Kindergeld, Haftungsquote nach Abzug Vorrang und Sockel 1.750 €.
