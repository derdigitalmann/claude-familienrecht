---
name: unterhalt-rechnen
description: Berechnet Kindes- und Ehegattenunterhalt (Trennung, nachehelich) mit festem Rechenkern nach Düsseldorfer Tabelle 2024 bis 2026 und der Leitlinie des zuständigen OLG, Monat für Monat mit Mangelfall, Haftungsquote Volljähriger und Rückstand; prüft auch Gegenrechnungen. Testphase, eigene Ergänzung von digitalmann, nicht von Klotzkette.
---

# Unterhalt rechnen (Testphase)

Eigene Ergänzung von digitalmann, **nicht von Klotzkette**. Der Rechner ist in der Testphase. Jede Ausgabe trägt diesen Hinweis; das Ergebnis ist vor Verwendung anhand des Rechenwegs nachzuprüfen.

Grundsatz: **Claude rechnet nicht selbst.** Alle Zahlen kommen aus `scripts/unterhalt.py`. Claude ermittelt die Eingaben, wertet rechtlich und erklärt das Ergebnis. Rechnet Claude doch etwas nebenher (Plausibilisierung), wird es als Kontrollrechnung gekennzeichnet und nie an die Stelle des Skriptergebnisses gesetzt.

## Ablauf

### 1. Leitlinie abfragen, bevor irgendetwas gerechnet wird

Ohne Leitlinie bricht das Skript ab. Nie eine Leitlinie unterstellen, auch nicht aus dem Wohnort des Nutzers.

1. Fragen, welches Familiengericht zuständig ist oder wäre. Hilfe zur Bestimmung:
   - Ist eine Ehesache anhängig: Gericht der Ehesache, für Ehegattenunterhalt und Unterhalt gemeinschaftlicher Kinder (§ 232 Abs. 1 Nr. 1 FamFG).
   - Sonst Kindesunterhalt Minderjähriger und privilegierter Volljähriger: Gericht am gewöhnlichen Aufenthalt des Kindes oder des handelnden Elternteils (§ 232 Abs. 1 Nr. 2 FamFG).
   - Übrige Fälle: § 232 Abs. 3 FamFG in Verbindung mit der ZPO, in der Regel Wohnsitz des Antragsgegners.
   - Maßgebend ist die Leitlinie des OLG, zu dessen Bezirk dieses Amtsgericht gehört.
2. Die Auswahl mit der Liste aus `python3 scripts/unterhalt.py --leitlinien` vorlegen (AskUserQuestion, falls verfügbar; sonst als Liste). Bei Rheinland-Pfalz nach OLG-Bezirk unterscheiden: Koblenz eigene Leitlinie, Zweibrücken SüdL. Saarbrücken orientiert sich an den Leitlinien NRW.
3. Die gewählte `id` in die Eingabe übernehmen und im Ergebnis nennen.

### 2. Daten erheben

Zuerst aus den Unterlagen (Gehaltsabrechnungen, Jahresmeldung, Steuerbescheid, Kreditverträge, Geburtsurkunden, Kontoauszüge), dann gezielt nachfragen. Checkliste:

| Bereich | Angaben |
|---|---|
| Zeitraum | von, bis (JJJJ-MM); für Rückstand auch Zahlungen je Monat und Empfänger |
| Pflichtiger | erwerbstätig ja/nein; Nettoerwerbseinkommen (Jahresschnitt inkl. Sonderzahlungen, Steuererstattungen); sonstige Einkünfte (Rente, ALG, Miete); Wohnvorteil; berufsbedingte Aufwendungen (Pauschale oder konkret: Entfernung km, Arbeitstage); Abzüge (Kredite, Altersvorsorge bis 4 % brutto, Kinderbetreuung); Warmmiete, falls über dem im Selbstbehalt enthaltenen Anteil; Zusammenleben mit Partner (Kürzung Selbstbehalt) |
| Kinder | Name, Geburtsdatum, Status ab 18 (privilegiert, volljährig, Student mit eigenem Haushalt), Kindergeldbezug, eigenes Einkommen, Mehrbedarf, erweiterter Umgang (Abzug 10 bis 15 %, BGH XII ZB 415/25) |
| Ehegatte | Trennung oder nachehelich, erwerbstätig ja/nein, Einkommen wie oben |
| anderer Elternteil | nur bei volljährigen Kindern: Einkommen für die Haftungsquote |
| Änderungen | jede Einkommensänderung als eigener Abschnitt mit `ab` |

Einkommensermittlung bei Selbstständigen, fiktives Einkommen, Wohnvorteil und Erwerbsobliegenheit sind Wertungsfragen. Hierfür die Klotzkette-Skills nutzen, wenn installiert (`fachanwalt-familienrecht:unterhalt-berechnen-und-gegenrechnen`, `fachanwalt-familienrecht:unterhalt-selbstaendige-einkommensaufklaerung`). Das Ergebnis der Wertung geht als Zahl in die Eingabe.

### 3. Eingabe schreiben und rechnen

Eingabe nach `references/eingabe-schema.md` als JSON-Datei schreiben, dann:

```
python3 <Skill-Ordner>/scripts/unterhalt.py eingabe.json            # Markdown
python3 <Skill-Ordner>/scripts/unterhalt.py eingabe.json --format json
```

`<Skill-Ordner>` ist der Ordner dieser SKILL.md. Beispiel: `beispiele/beispiel-trennung.json`. Bei `FEHLER:` die Eingabe korrigieren, nicht selbst rechnen.

### 4. Ergebnis prüfen und erläutern

1. Hinweise und Annahmen des Skripts vollständig an den Nutzer weitergeben, insbesondere Abweichungen von der Leitlinie (Pauschale, wo die Leitlinie keine kennt), Mangelfall, Begrenzung durch Selbstbehalt.
2. Plausibilität: Eingruppierung, Altersstufenwechsel, Kindergeldanteil, Selbstbehalt.
3. Nicht automatisiert und daher gesondert zu prüfen: Wechselmodell, Altersvorsorge- und Krankenvorsorgeunterhalt, Dreiteilung bei neuem Ehegatten, § 1578b BGB, Verwirkung, konkreter Bedarf bei hohem Einkommen, Brutto-Netto-Rechnung.
4. Ausgabe nach Bedarf: Markdown im Chat, Excel-Berechnungsblatt (xlsx-Skill) oder PDF. Der Testphasen-Hinweis und die Leitlinie mit Fundstelle bleiben in jeder Ausgabe stehen.

## Prüfmodus: Gegenrechnung

Liegt eine Berechnung der Gegenseite oder des Gerichts vor:

1. Deren Eingangswerte unverändert als Eingabe übernehmen und rechnen.
2. Abweichungen Zeile für Zeile tabellieren: Position, Gegenseite, Rechner, Differenz, Ursache (Rechenfehler, andere Wertung, andere Leitlinie, anderer Tabellenstand).
3. Danach mit den eigenen Eingangswerten rechnen und beide Ergebnisse gegenüberstellen.

## Pflege

- Neue Düsseldorfer Tabelle: Jahr in `data/dt.json` ergänzen (Werte aus dem amtlichen PDF; Stufen 1 bis 3 müssen Mindestbedarf x Prozentsatz aufgerundet ergeben).
- Neue Leitlinien: `data/leitlinien.json` aktualisieren, `references/leitlinien-uebersicht.md` anpassen.
- Nach jeder Änderung `python3 tests/test_unterhalt.py` ausführen.
