# unterhaltsrechner (Testphase)

Eigene Ergänzung von digitalmann, **nicht von Klotzkette** und nicht mit Klotzkette abgestimmt. Testphase: Rechenwege und hinterlegte Werte können Fehler enthalten. Ergebnisse vor jeder Verwendung anhand des ausgegebenen Rechenwegs nachprüfen. Keine Rechtsberatung.

## Inhalt

- Skill `unterhalt-rechnen`: Ablauf mit Abfrage der OLG-Leitlinie vor der Berechnung, Datenerhebung, Prüfmodus für Gegenrechnungen
- Befehl `/unterhalt`
- `scripts/unterhalt.py`: Rechenkern (Python 3, ohne Zusatzpakete)
- `data/dt.json`: Düsseldorfer Tabelle 2026 (Haupttabelle); 2024 und 2025 nur für Rückstände
- `data/leitlinien.json`: 15 Leitlinien bzw. OLG-Bezirke, Stand 01.01.2026; Abweichungen der Fassungen 2024 und 2025 unter `historie` (2024/2025 getrennte Leitlinien Celle, Braunschweig, Oldenburg; 2024 getrennte Leitlinien Düsseldorf, Hamm, Köln; Saarbrücken bis 2025 ohne eigene Leitlinien)
- `references/fallstricke.md`: 29 typische Fehler mit Quellen und Umsetzung im Rechner
- `scripts/export_xlsx.py`: Excel-Berechnungsblatt (`--xlsx`)
- `tests/test_referenzfaelle.py`: Referenzfälle aus öffentlichen Fallbeispielen mit dokumentierten Abweichungen
- `tests/test_unterhalt.py`: Regressionstests, u. a. Beispiel DT 2026 Anm. C und Fahrtkostenbeispiel der Leitlinien Schleswig-Holstein

## Grenzen

Nicht automatisiert: Wechselmodell, Krankenvorsorgeunterhalt, Werte der Bremer Tabelle (nicht frei verfügbar, Zuschlag wird eingegeben), § 1578b BGB, Verwirkung, konkreter Bedarf bei hohem Einkommen, Netto aus Brutto. Dreiteilung nur als Begrenzung der Leistungsfähigkeit; die Rangfrage nach § 1609 BGB gibt der Nutzer vor.

Lizenz: MIT, © Mehmet Aydoğdu, digitalmann.
