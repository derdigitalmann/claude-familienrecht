---
name: unterhalt-rechnen
description: Berechnet Kindes- und Ehegattenunterhalt (Trennung, nachehelich) mit festem Rechenkern nach Düsseldorfer Tabelle 2026 (2024 und 2025 nur für Rückstände) und der Leitlinie des zuständigen OLG in der Fassung des jeweiligen Jahres, Monat für Monat mit Mangelfall, Haftungsquote Volljähriger und Rückstand; prüft auch Gegenrechnungen. Testphase, eigene Ergänzung von digitalmann, nicht von Klotzkette.
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
2. Die Auswahl mit der Liste aus `python3 scripts/unterhalt.py --leitlinien` vorlegen (AskUserQuestion, falls verfügbar; sonst als Liste). Bei Rheinland-Pfalz nach OLG-Bezirk unterscheiden: Koblenz eigene Leitlinie, Zweibrücken SüdL. Saarbrücken orientiert sich seit 2026 an den Leitlinien NRW, davor gab es nur Selbstbehalte.
3. Die gewählte `id` in die Eingabe übernehmen und im Ergebnis nennen.
4. Reicht der Zeitraum in Jahre mit getrennten Leitlinien (Niedersachsen 2024 und 2025: Braunschweig, Celle, Oldenburg; NRW 2024: Düsseldorf, Hamm, Köln), zusätzlich das OLG abfragen und als `olg` setzen. Ohne diese Angabe bricht das Skript ab.

Die Düsseldorfer Tabelle 2026 ist die Haupttabelle. Die Tabellen 2024 und 2025 und die Leitlinienfassungen dieser Jahre dienen nur der Berechnung von Rückständen.

### 2. Daten erheben

Zuerst aus den Unterlagen (Gehaltsabrechnungen, Jahresmeldung, Steuerbescheid, Kreditverträge, Geburtsurkunden, Kontoauszüge), dann gezielt nachfragen. Checkliste:

| Bereich | Angaben |
|---|---|
| Zeitraum | von, bis (JJJJ-MM); für Rückstand auch Zahlungen je Monat und Empfänger |
| Pflichtiger | erwerbstätig ja/nein; Nettoerwerbseinkommen (Jahresschnitt inkl. Sonderzahlungen, Steuererstattungen); sonstige Einkünfte (Rente, ALG, Miete); Wohnvorteil; berufsbedingte Aufwendungen (Pauschale oder konkret: Entfernung km, Arbeitstage); Abzüge (Kredite, Altersvorsorge bis 4 % brutto, Kinderbetreuung); Warmmiete, falls über dem im Selbstbehalt enthaltenen Anteil; Zusammenleben mit Partner (Kürzung Selbstbehalt) |
| Kinder | Name, Geburtsdatum, Status ab 18 (privilegiert, volljährig, Student mit eigenem Haushalt), Kindergeldbezug, eigenes Einkommen, Mehrbedarf, erweiterter Umgang (Abzug 10 bis 15 %, BGH XII ZB 415/25) |
| Ehegatte | Trennung oder nachehelich, erwerbstätig ja/nein, Einkommen wie oben; Altersvorsorgeunterhalt verlangt? Dann Zuschlag aus der Bremer Tabelle des Jahres (Prozentsatz oder Tabellenzeilen vom Nutzer, nicht schätzen) und beim Trennungsunterhalt Monat der Rechtshängigkeit des Scheidungsantrags |
| neuer Ehegatte | nur nachehelich: Wiederheirat seit wann, Einkommen des neuen Ehegatten, Rang nach § 1609 BGB (Kinderbetreuung, lange Ehe); Rang ist eine Wertung, mit dem Nutzer klären |
| anderer Elternteil | nur bei volljährigen Kindern: Einkommen für die Haftungsquote |
| Änderungen | jede Einkommensänderung als eigener Abschnitt mit `ab` |
| Rückstand | Datum von Auskunftsverlangen oder Mahnung je Berechtigtem, Unterhaltsvorschuss je Kind, bei nachehelichem Unterhalt Rechtskraft der Scheidung und Rechtshängigkeit |
| Steuern | Steuerklasse, Trennungsmonat, Wiederheirat, Realsplitting |

**Selbstständige:** Eingabe über `selbstaendig` (siehe Schema). Maßstab ist der Durchschnitt der letzten drei abgeschlossenen Jahre aus Steuerbescheiden und Gewinnermittlungen bzw. Jahresabschlüssen. Liegt nur eine BWA vor:
1. Nicht als endgültiges Ergebnis rechnen. Das Skript kennzeichnet die Berechnung als VORLÄUFIG; diese Kennzeichnung bleibt in jeder Ausgabe.
2. Fehlende Steuern nicht schätzen, sondern beim Steuerberater erfragen oder als Spanne mit zwei Varianten rechnen und beide ausweisen.
3. Auskunfts- und Belegplan mitliefern: Steuerbescheide und Erklärungen der letzten drei Jahre, Gewinnermittlungen bzw. Jahresabschlüsse mit Anlagenverzeichnis, Summen- und Saldenliste, Entnahmen und Einlagen, Darlehensverträge, Nachweise Kranken- und Altersvorsorge (§ 1605 BGB, § 1580 BGB, § 235 FamFG; ggf. Stufenantrag).
4. BWA-Werte kritisch lesen: keine Abschreibungen, Rückstellungen, Privatanteile (Kfz, Telefon), Saisonverlauf; vorläufiges Ergebnis nicht einfach hochrechnen.

Einkommensermittlung bei Selbstständigen im Einzelnen, fiktives Einkommen, Wohnvorteil und Erwerbsobliegenheit sind Wertungsfragen. Hierfür die Klotzkette-Skills nutzen, wenn installiert (`fachanwalt-familienrecht:unterhalt-berechnen-und-gegenrechnen`, `fachanwalt-familienrecht:unterhalt-selbstaendige-einkommensaufklaerung`). Das Ergebnis der Wertung geht als Zahl in die Eingabe.

### 3. Eingabe schreiben und rechnen

Eingabe nach `references/eingabe-schema.md` als JSON-Datei schreiben, dann:

```
python3 <Skill-Ordner>/scripts/unterhalt.py eingabe.json            # Markdown
python3 <Skill-Ordner>/scripts/unterhalt.py eingabe.json --format json
```

`<Skill-Ordner>` ist der Ordner dieser SKILL.md. Beispiel: `beispiele/beispiel-trennung.json`. Bei `FEHLER:` die Eingabe korrigieren, nicht selbst rechnen.

### 4. Ergebnis prüfen und erläutern

Vor der Ausgabe `references/fallstricke.md` durchgehen. Punkte mit "S" (nur Skill) selbst prüfen, Punkte mit "H" aus den Hinweisen des Skripts aufgreifen und beim Nutzer nachfragen, wenn eine Angabe fehlt (z. B. Verzugsbeginn, Steuerklasse, Jahresnetto).

1. Hinweise und Annahmen des Skripts vollständig an den Nutzer weitergeben, insbesondere Abweichungen von der Leitlinie (Pauschale, wo die Leitlinie keine kennt), Mangelfall, Begrenzung durch Selbstbehalt.
2. Plausibilität: Eingruppierung, Altersstufenwechsel, Kindergeldanteil, Selbstbehalt.
3. Nicht automatisiert und daher gesondert zu prüfen: Wechselmodell, Krankenvorsorgeunterhalt, Zuschlag nach Bremer Tabelle (Nutzer liefert Prozentsatz oder Tabellenzeilen des Jahres), Rangfrage beim neuen Ehegatten (§ 1609 BGB), § 1578b BGB, Verwirkung, konkreter Bedarf bei hohem Einkommen, Brutto-Netto-Rechnung.
4. Ausgabe nach Bedarf: Markdown im Chat oder Excel-Berechnungsblatt direkt aus dem Skript (`--xlsx berechnung.xlsx`; Blätter Übersicht, Monate mit Summenformeln, Rechenweg, Rückstand, Hinweise). PDF bei Bedarf aus der Markdown-Ausgabe. Der Testphasen-Hinweis, gegebenenfalls VORLÄUFIG, und die Leitlinie mit Fundstelle bleiben in jeder Ausgabe stehen.

## Prüfmodus: Gegenrechnung

Liegt eine Berechnung der Gegenseite oder des Gerichts vor:

1. Deren Eingangswerte unverändert als Eingabe übernehmen und rechnen.
2. Abweichungen Zeile für Zeile tabellieren: Position, Gegenseite, Rechner, Differenz, Ursache (Rechenfehler, andere Wertung, andere Leitlinie, anderer Tabellenstand).
3. Danach mit den eigenen Eingangswerten rechnen und beide Ergebnisse gegenüberstellen.

## Pflege

- Neue Düsseldorfer Tabelle: Jahr in `data/dt.json` ergänzen (Werte aus dem amtlichen PDF; Stufen 1 bis 3 müssen Mindestbedarf x Prozentsatz aufgerundet ergeben).
- Neue Leitlinien: `data/leitlinien.json` aktualisieren, `references/leitlinien-uebersicht.md` anpassen.
- Nach jeder Änderung `python3 tests/test_unterhalt.py` und `python3 tests/test_referenzfaelle.py` ausführen. Der GitHub-Workflow `tests.yml` führt beide bei jedem Pull Request aus.
