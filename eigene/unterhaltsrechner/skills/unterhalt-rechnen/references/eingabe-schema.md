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
| `abzuege[]` | Kredite, Altersvorsorge, Betreuungskosten usw. Werden anteilig auf Erwerb und sonstige Einkünfte verteilt. |
| `warmmiete` | erhöht den Selbstbehalt um den Betrag über dem enthaltenen Wohnanteil. Angemessenheit prüfen. |
| `selbstbehalt_kuerzung_prozent` | z. B. 10 bei Zusammenleben mit leistungsfähigem Partner. |
| `status_ab_18` | `privilegiert` (§ 1603 Abs. 2 S. 2 BGB, Rang 1), `volljaehrig` (Rang 4), `student_eigener_haushalt` (Rang 4, fester Bedarf). |
| `eigenes_einkommen` | anrechenbares Einkommen des Kindes, bei Ausbildungsvergütung nach Abzug des ausbildungsbedingten Mehrbedarfs (Leitlinien Nr. 10.2.3, i. d. R. 100 €). |
| `umgang_abzug_prozent` | Abzug vom Tabellenbedarf bei erweitertem Umgang, 10 bis 15 (BGH XII ZB 415/25). |
| `mehrbedarf` | wird dem Bedarf zugeschlagen; anteilige Haftung beider Eltern gesondert prüfen. |
| `ende` | letzter Unterhaltsmonat eines Kindes. |
| `ehegatte.mindestbedarf` | Bedarf mindestens Existenzminimum 1.200 € (Standard `true`). |
| `anderer_elternteil` | nur für volljährige Kinder (Haftungsquote). `vorrangiger_kindesunterhalt`: dessen vorrangige Unterhaltslasten. |
| `gruppe.fest` | erzwingt eine Einkommensgruppe. Herabstufung wegen Selbstbehalt bleibt aktiv. |
| `gruppe.korrektur` | ersetzt die automatische Höher-/Herabstufung nach Zahl der Berechtigten (Standard: +1 bei einem, -1 je Berechtigten über zwei). |
| `gruppe.bedarfskontrolle` | Herabstufung, wenn der Rest nach Kindesunterhalt unter dem Bedarfskontrollbetrag liegt (Standard `true`). |
| `weitere_berechtigte` | zusätzliche Unterhaltsberechtigte für die Eingruppierung (z. B. Kind aus anderer Beziehung). |
| `zahlungen[]` | für den Rückstand; `an` ist der Kindesname oder `Ehegatte`. |

## Rechenregeln des Skripts

- Altersstufe wechselt ab dem Monat, in dem das Kind 6, 12 oder 18 wird (§ 1612a Abs. 3 BGB). Für die 4. Altersstufe gilt dieselbe Regel.
- Tabellenwerte des jeweiligen Kalenderjahres (DT 2024, 2025, 2026). Leitlinienparameter Stand 2026.
- Herabstufung Gruppe für Gruppe, bis Bedarfskontrollbetrag und notwendiger Selbstbehalt gewahrt sind; reicht auch Gruppe 1 nicht, Mangelverteilung nach DT Anm. C, centgenau.
- Ehegattenunterhalt: Vorwegabzug Kindesunterhalt (Zahlbeträge), Erwerbstätigenbonus nach Leitlinie, Halbteilung, Mindestbedarf, Leistungsfähigkeit ohne Bonus gegen den Ehegattenselbstbehalt der Leitlinie. Bei Begrenzung durch den Selbstbehalt wird abgerundet.
- Volljährige: Bedarf nach zusammengerechnetem Einkommen beider Eltern, volles Kindergeld, Haftungsquote nach Abzug Vorrang und Sockel 1.750 €.
