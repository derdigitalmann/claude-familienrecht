# unterhaltsrechner (Testphase)

Eigene Ergänzung von digitalmann, **nicht von Klotzkette** und nicht mit Klotzkette abgestimmt. Testphase: Rechenwege und hinterlegte Werte können Fehler enthalten. Ergebnisse vor jeder Verwendung anhand des ausgegebenen Rechenwegs nachprüfen. Keine Rechtsberatung.

## Inhalt

- Skill `unterhalt-rechnen`: Ablauf mit Abfrage der OLG-Leitlinie vor der Berechnung, Datenerhebung, Prüfmodus für Gegenrechnungen
- Befehl `/unterhalt`
- `scripts/unterhalt.py`: Rechenkern (Python 3, ohne Zusatzpakete)
- `data/dt.json`: Düsseldorfer Tabelle 2024, 2025, 2026
- `data/leitlinien.json`: 15 Leitlinien bzw. OLG-Bezirke, Stand 01.01.2026
- `tests/test_unterhalt.py`: Regressionstests, u. a. Beispiel DT 2026 Anm. C und Fahrtkostenbeispiel der Leitlinien Schleswig-Holstein

## Grenzen

Nicht automatisiert: Wechselmodell, Altersvorsorge- und Krankenvorsorgeunterhalt, Dreiteilung bei neuem Ehegatten, § 1578b BGB, Verwirkung, konkreter Bedarf bei hohem Einkommen, Netto aus Brutto. Leitlinienparameter für Monate vor 2026 entsprechen dem Stand 2026.

Lizenz: MIT, © Mehmet Aydoğdu, digitalmann.
