# claude-familienrecht

Claude-Plugin-Marketplace mit den Familienrecht-Plugins aus [Klotzkette/claude-fuer-deutsches-recht](https://github.com/Klotzkette/claude-fuer-deutsches-recht), automatisch gespiegelt.

Das Original-Repository ist für die Marketplace-Funktion in claude.ai zu groß (Download-Grenze 512 MB). Dieses Repository enthält deshalb nur die unten genannten Plugins und gleicht sie täglich mit dem Original ab.

**Kein offizielles Projekt von Klotzkette.** Urheber der Plugin-Inhalte ist Klotzkette (siehe `NOTICE`). Dieses Repository spiegelt die Inhalte unverändert; geändert wird nur das Marketplace-Manifest `.claude-plugin/marketplace.json` (Name, Beschreibung, Auswahl und Pfade der Plugins).

## Enthaltene Plugins

| Plugin | Inhalt |
|---|---|
| `fachanwalt-familienrecht` | Scheidung, Sorge, Umgang, Unterhalt, Zugewinn, Ehevertrag, FamFG |
| `zugewinnausgleich` | Berechnung des Zugewinns, Immobilien, Unternehmen, Auskunft, Vergleich |
| `richter-familiengericht` | Perspektive des Familiengerichts: Ehesachen, Versorgungsausgleich, Kindschaft, Gewaltschutz |
| `betreuungsrecht` | rechtliche Betreuung (BGB Buch 4, Abschnitt 3) |

Die Auswahl steht in `plugins.txt`.

## Installation

**claude.ai und Claude Desktop:** Anpassen > Plugins > Hinzufügen > Marketplace hinzufügen > Aus einem Repository hinzufügen > `derdigitalmann/claude-familienrecht` > Synchronisieren. Danach die gewünschten Plugins einzeln hinzufügen.

**Claude Code:**

```
claude plugin marketplace add derdigitalmann/claude-familienrecht
claude plugin install fachanwalt-familienrecht@mehmet-familienrecht
```

## Aktualisierung

Ein GitHub-Workflow gleicht täglich mit dem Original ab und öffnet bei Änderungen einen Pull Request. Nach dem Merge übernehmen Marketplaces mit aktivierter automatischer Synchronisierung die neue Fassung.

## Lizenz

Die gespiegelten Inhalte stehen unter `Apache-2.0 OR MIT` (Wahl des Nutzers, siehe `NOTICE`, `LICENSE-MIT`, `LICENSE-APACHE`). Dieses Repository nutzt sie unter der **MIT-Lizenz**. Skripte und Workflow dieses Repositorys stehen ebenfalls unter der MIT-Lizenz.

## Hinweis

Die Inhalte sind keine Rechtsberatung und ersetzen keine Prüfung im Einzelfall. Normen, Rechtsprechung und Fristen vor jeder Verwendung am Original prüfen. Bereitstellung unentgeltlich und ohne Gewähr.

Anbieter dieses Repositorys: Mehmet Aydoğdu, digitalmann. [Impressum](https://digitalmann.de/impressum)
