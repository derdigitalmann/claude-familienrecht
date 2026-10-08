# Fallstricke der Unterhaltsberechnung

Gesammelt aus Foren (finanztip-Community, 123recht, rund-ums-baby), Fachportalen und Kanzleiartikeln (iww, anwaltspraxis-magazin, kanzlei-hasselbach, otto-schmidt) und abgeglichen mit den Leitlinien 2026. Stand 08.10.2026. Spalte "Rechner": **R** = Rechenregel im Skript, **H** = Prüfhinweis im Ergebnis, **S** = Prüfpunkt nur im Skill (Wertung).

| Nr. | Fallstrick | Richtig | Rechner |
|---|---|---|---|
| 1 | Bedarfskontrollbetrag übersehen, Gruppe zu hoch | Herabstufen, bis der Rest den BKB der Gruppe erreicht (DT Anm. A III) | R |
| 2 | Zahlbetrag mit Tabellenbetrag oder 105 % mit 100 % verwechselt | Zahlbetrag = Bedarf minus Kindergeldanteil; Vorwegabzug beim Ehegattenunterhalt mit Zahlbetrag; dynamischer Prozentsatz ausgewiesen | R |
| 3 | Altersstufe erst ab dem Geburtstag statt ab Monatsbeginn | ab dem Ersten des Geburtsmonats (§ 1612a Abs. 3 BGB) | R |
| 4 | Netto aus einer Monatsabrechnung, Sonderzahlungen vergessen | Jahresschnitt inkl. Urlaubs- und Weihnachtsgeld, Boni, Überstunden, Sachbezüge; Steuererstattung im Zahlungsjahr (In-Prinzip, NRW 1.7) | H (`netto_basis`) |
| 5 | Steuerklasse III/V nach dem Trennungsjahr weiter angesetzt | ab 1.1. des Folgejahres fiktiv Steuerklasse I/II | H (`steuerklasse`, `ehegatte.trennung`) |
| 6 | Splittingvorteil neuer Ehe falsch zugeordnet | beim Kindesunterhalt einsetzen, beim geschiedenen Ehegatten nicht (OLG München 12 UF 824/24 e) | H (`neue_ehe`) |
| 7 | Realsplitting nicht genutzt | Obliegenheit, Steuervorteile zu nutzen (Nr. 10.1.1) | H |
| 8 | Fahrtkosten ohne Prüfung der Zumutbarkeit des ÖPNV, Pauschale und km-Satz doppelt | entweder Pauschale oder konkret; über 15 % des Nettos Darlegung (SH 10.2.2; BGH FamRZ 2002, 535) | R (ein Modus) + H |
| 9 | Pauschale berufsbedingte Aufwendungen, wo die Leitlinie keine kennt (Bremen, Rostock, SH) oder nur fiktiv (NRW) | Leitlinie des zuständigen OLG | H |
| 10 | Schulden ohne Prüfung abgezogen | Tilgungsplan, angemessene Raten; Kindesunterhalt regelmäßig nur bei gesichertem Mindestunterhalt; Kredite in Kenntnis der Unterhaltspflicht nicht (Nr. 10.4) | H (`art: schulden`) |
| 11 | Sekundäre Altersvorsorge über 4 % oder trotz Mangelfall | höchstens 4 % brutto, nur tatsächlich gezahlt; nicht bei ungedecktem Mindestunterhalt | R (Mangelfall) + H (4 %) |
| 12 | Wohnvorteil falsch: objektiv statt subjektiv im Trennungsjahr, Tilgung voll | Trennungsjahr angemessener Wohnwert, danach objektiv; Tilgung bis Wohnwert (BGH XII ZR 21/05) | H |
| 13 | Mehrbedarf (Kita) allein dem Pflichtigen auferlegt, Verpflegung als Mehrbedarf | beide Eltern anteilig nach § 1606 Abs. 3 BGB mit Sockel; Verpflegung kein Mehrbedarf (Nr. 12.4) | R (mit `anderer_elternteil`) + H |
| 14 | Ausbildungsvergütung voll beim Minderjährigen angerechnet, Ausbildungsaufwand vergessen | minus 100 € Aufwand; Minderjährige hälftig, Volljährige voll (Nr. 10.2.3, 12.2, 13.2) | R (`ausbildungsverguetung`) |
| 15 | Volljähriges Kind wie Minderjähriges gerechnet | Bedarf nach Einkommen beider Eltern, Kindergeld voll, keine Höherstufung, Haftungsquote mit Sockel | R + H beim 18. Geburtstag |
| 16 | Erweiterter Umgang als halbes Wechselmodell gerechnet | Herabstufung und Abzug getrennt; Abzug regelmäßig 10 %, höchstens 15 % vom Tabellenbedarf (BGH XII ZB 415/25 vom 15.04.2026) | R + H |
| 17 | Kinder aus anderen Beziehungen in der Mangelverteilung vergessen | alle gleichrangigen Kinder in die Verteilung | H |
| 18 | Mangelfall ohne Prüfung fiktiven Einkommens | gesteigerte Erwerbsobliegenheit, Überstunden, Nebentätigkeit im Rahmen des ArbZG (NRW 1.3), ggf. Verbraucherinsolvenz | H |
| 19 | Rückstand ab Trennung statt ab Verzug | ab Auskunftsverlangen, Mahnung, Rechtshängigkeit, jeweils ab Monatsersten (§ 1613 Abs. 1 BGB; nachehelich § 1585b Abs. 2 BGB) | R (`verzug_ab`) |
| 20 | Nachehelicher Unterhalt mehr als ein Jahr vor Rechtshängigkeit | ausgeschlossen, außer bei absichtlichem Entziehen (§ 1585b Abs. 3 BGB) | R (`rechtshaengig_ab`) |
| 21 | Nachehelicher Unterhalt vor Rechtskraft der Scheidung | davor Trennungsunterhalt, eigener Anspruch | H |
| 22 | Unterhaltsvorschuss im Rückstand nicht abgezogen | Anspruch in Höhe der Leistung auf das Land übergegangen (§ 7 Abs. 1 UVG) | R (`unterhaltsvorschuss`) |
| 23 | Verwirkung und Verjährung alter Rückstände übersehen | Zeitmoment nach gut einem Jahr möglich, Umstandsmoment nötig (BGH XII ZB 133/17; AG Hagen 130 F 131/11); Verjährung drei Jahre, Hemmung § 207 BGB | H (`stichtag`) |
| 24 | Altersvorsorgeunterhalt ohne zweistufige Rechnung | Bremer Tabelle, Elementarunterhalt sinkt | H (nicht berechnet) |
| 25 | Selbstständige nur mit BWA oder einem Jahr | Drei-Jahres-Schnitt aus Steuerbescheiden und Abschlüssen, Steuern, Vorsorge, Entnahmen | R + H, Ergebnis VORLÄUFIG |
| 26 | Unvollständige Auskunft als Rechengrundlage | erst Auskunft und Belege (§ 1605 BGB, § 235 FamFG), Beweislast für Abzüge beim Pflichtigen | S |
| 27 | Präklusion bei Abänderung übersehen | Tatsachen, die bei der Erstberechnung bekannt waren, sind ausgeschlossen (§ 238 Abs. 2 FamFG) | S |

## Quellen

- finanztip-Community, Bedarfskontrollbetrag Kindesunterhalt: https://www.finanztip.de/community/forum/thema/21774-bedarfskontrollbetrag-kindesunterhalt/
- 123recht-Forum, Kindesunterhalt 9 Jahre Tochter: https://www.123recht.de/forum/familienrecht/Kindesunterhalt-9-Jahre-Tochter-__f579914.html
- rund-ums-baby Expertenforum, Kreditkosten und Selbstbehalt: https://www.rund-ums-baby.de/experten-forum/recht/bei-unterhaltspflicht-anrechnung-von-kreditkosten-in-selbstbehalt__828421
- anwaltspraxis-magazin, Basiswissen Einkommensermittlung: https://anwaltspraxis-magazin.de/kanzleimagazin/basiswissen-einkommensermittlung-im-unterhaltsrecht/
- anwaltspraxis-magazin, Steuerklassenwahl (OLG München 12 UF 824/24 e): https://anwaltspraxis-magazin.de/fachbeitraege/familienrecht/2025/10/31/steuerklassenwahl-bei-unterhaltspflicht-fuer-minderjaehrige-kinder/
- iww, Verzug des Unterhaltsschuldners: https://www.iww.de/fk/archiv/der-praktische-fall-der-verzug-des-unterhaltsschuldners-f30672
- iww, 8 Beratungspunkte Wohnvorteil: https://www.iww.de/fk/archiv/unterhalt-8-wichtige-beratungspunkte-zum-wohnvorteil-f13768
- kanzlei-hasselbach, Mehrbedarf und Sonderbedarf: https://www.kanzlei-hasselbach.de/blog/mehrbedarf-sonderbedarf-kindesunterhalt/
- 123recht-Ratgeber, AG Hagen 130 F 131/11 (Verwirkung): https://www.123recht.de/ratgeber/familienrecht/AG-Hagen-Wer-zu-lange-wartet,-verliert-den-Kindesunterhalt-vollstrecken-Sie-regelmaessig-__a119736.html
- BGH XII ZB 133/17 (Verwirkung): https://gesetze.co/urteile/XII_ZB_133-17
- BÖHM Rechtsanwälte zu BGH XII ZB 415/25: https://boehm-anwaelte.de/bgh-konkretisiert-kindesunterhalt-bei-erweitertem-umgang/
- otto-schmidt FamRB-Blog, erweiterter Umgang: https://www.otto-schmidt.de/blog/familienrecht-blog/kindesunterhalt-bei-erweitertem-umgang-asymmetrisches-wechselmodell-FAMRBLOG0001313.html
- Leitlinien NRW 2026 (Nr. 1.3, 1.7, 10.1, 10.4, 10.7, 12.2, 12.4, 13.2, 13.3): siehe `leitlinien-uebersicht.md`
