# claude-familienrecht

Claude-Plugin-Marketplace für Familienrecht. Das Repository besteht aus zwei klar getrennten Teilen:

1. **Gespiegelte Plugins von Klotzkette:** Die Familienrecht-Plugins aus [Klotzkette/claude-fuer-deutsches-recht](https://github.com/Klotzkette/claude-fuer-deutsches-recht) werden täglich automatisch und unverändert übernommen.
2. **Eigene Ergänzungen von digitalmann:** Eigene Plugins, die weder von Klotzkette stammen noch mit Klotzkette abgestimmt sind. Sie befinden sich in der **Testphase**.

**Kein offizielles Projekt von Klotzkette.** Klotzkette hat dieses Repository weder erstellt noch geprüft und unterstützt es nicht.

## Teil 1: Gespiegelte Plugins von Klotzkette

Das Original-Repository ist für die Marketplace-Funktion in claude.ai zu groß (Download-Grenze 512 MB). Hier liegen deshalb nur die unten genannten Plugins. Sie werden täglich mit dem Original abgeglichen.

| Plugin | Inhalt |
|---|---|
| `fachanwalt-familienrecht` | Scheidung, Sorge, Umgang, Unterhalt, Zugewinn, Ehevertrag, FamFG |
| `zugewinnausgleich` | Berechnung des Zugewinns, Immobilien, Unternehmen, Auskunft, Vergleich |
| `richter-familiengericht` | Perspektive des Familiengerichts: Ehesachen, Versorgungsausgleich, Kindschaft, Gewaltschutz |
| `betreuungsrecht` | rechtliche Betreuung (BGB Buch 4, Abschnitt 3) |

Die Auswahl steht in `plugins.txt`. Urheber der Inhalte ist Klotzkette (siehe `NOTICE`). Die Inhalte im Ordner `plugins/` werden nicht bearbeitet. Angepasst werden nur Name, Beschreibung, Auswahl und Pfade in `.claude-plugin/marketplace.json`. Für Inhalt und Qualität dieser Plugins ist Klotzkette verantwortlich. Fehler darin bitte im [Original-Repository](https://github.com/Klotzkette/claude-fuer-deutsches-recht/issues) melden, nicht hier.

## Teil 2: Eigene Ergänzungen (Testphase)

| Plugin | Inhalt | Status |
|---|---|---|
| `unterhaltsrechner` | Berechnung von Kindes- und Ehegattenunterhalt mit festem Rechenkern: Düsseldorfer Tabelle, Leitlinie des zuständigen OLG (wird vor der Berechnung abgefragt), Mangelfall, Rückstand je Monat | in Entwicklung, noch nicht im Marketplace |

Für die eigenen Ergänzungen gilt:

- **Nicht von Klotzkette.** Sie stammen von digitalmann und werden getrennt von den gespiegelten Plugins im Ordner `eigene/` gepflegt.
- **Testphase.** Funktionsumfang, Rechenwege und hinterlegte Werte können sich ändern und Fehler enthalten. Die Ergebnisse sind nicht für den ungeprüften Einsatz in Mandaten, Schriftsätzen oder Vergleichen bestimmt.
- **Ergebnisse immer selbst prüfen.** Jede Berechnung vor der Verwendung anhand des ausgegebenen Rechenwegs, der aktuellen Düsseldorfer Tabelle und der Leitlinie des zuständigen OLG nachrechnen.
- **Rückmeldungen** zu Fehlern bitte als [Issue in diesem Repository](https://github.com/derdigitalmann/claude-familienrecht/issues).

## Installation

**claude.ai und Claude Desktop:** Anpassen > Plugins > Hinzufügen > Marketplace hinzufügen > Aus einem Repository hinzufügen > `derdigitalmann/claude-familienrecht` > Synchronisieren. Danach die gewünschten Plugins einzeln hinzufügen.

**Claude Code:**

```
claude plugin marketplace add derdigitalmann/claude-familienrecht
claude plugin install fachanwalt-familienrecht@mehmet-familienrecht
```

## Aktualisierung

Ein GitHub-Workflow gleicht täglich mit dem Original ab und öffnet bei Änderungen einen Pull Request. Nach dem Merge übernehmen Marketplaces mit aktivierter automatischer Synchronisierung die neue Fassung. Der Abgleich ändert nur `plugins/`, die Klotzkette-Einträge im Manifest und die Lizenzdateien. Die eigenen Ergänzungen bleiben davon unberührt.

## Lizenz

- **Gespiegelte Inhalte (`plugins/`):** `Apache-2.0 OR MIT` nach Wahl des Nutzers, siehe `NOTICE`, `LICENSE-MIT`, `LICENSE-APACHE`. Dieses Repository nutzt sie unter der **MIT-Lizenz**.
- **Eigene Ergänzungen (`eigene/`), Skripte und Workflow:** MIT-Lizenz, © Mehmet Aydoğdu, digitalmann.

## Hinweis

Die Inhalte beider Teile sind keine Rechtsberatung und ersetzen keine Prüfung im Einzelfall. Normen, Rechtsprechung, Tabellenwerte und Fristen vor jeder Verwendung am Original prüfen. Bereitstellung unentgeltlich und ohne Gewähr.

Anbieter dieses Repositorys: Mehmet Aydoğdu, digitalmann. [Impressum](https://digitalmann.de/impressum)
