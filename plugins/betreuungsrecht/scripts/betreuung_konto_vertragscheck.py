#!/usr/bin/env python3
"""Verdachts-Scoring für Konto- und Vertragsdaten in Betreuungsfällen.

Das Werkzeug ist bewusst klein und deterministisch. Es ersetzt keine
juristische Prüfung, liefert aber eine reproduzierbare Priorisierung für
Betreuerberichte, Vermögensverzeichnisse und Maßnahmenlisten.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


CATEGORY_POINTS = {
    "fake-authority": 7,
    "remote-access": 6,
    "foreign-investment": 6,
    "foreign-property": 6,
    "high-risk-investment": 5,
    "precious-assets": 5,
    "senior-pressure-sale": 4,
    "lottery": 3,
    "subscription": 3,
    "private-care": 2,
    "unexplained": 3,
}


ACTION_LIBRARY = {
    "fake-authority": [
        "Bankrückholung und Strafanzeige prüfen",
        "Telefon-/Kontaktspur sichern",
        "Betreuungsgericht über akutes Schutzthema informieren",
    ],
    "remote-access": [
        "Fernwartungszugang sofort sperren",
        "Gerät durch unabhängige IT prüfen lassen",
        "Onlinebanking und Karten absichern",
    ],
    "foreign-investment": [
        "Vertrag, Geeignetheit und Rückabwicklung prüfen",
        "Auslandsüberweisungen mit Bank abgleichen",
        "Genehmigungs- und Einwilligungsvorbehalt prüfen",
    ],
    "foreign-property": [
        "Reservierungsvertrag und Rücktrittsrechte prüfen",
        "Zahlplan stoppen, soweit keine Pflicht besteht",
        "Betreuungsgericht wegen erheblichem Vermögensrisiko informieren",
    ],
    "high-risk-investment": [
        "Zeichnungsschein, Risikoaufklärung und Laufzeit prüfen",
        "Rückabwicklung und Schadensersatzspur sichern",
        "Vermögensverzeichnis als zweifelhafte Anlage ergänzen",
    ],
    "precious-assets": [
        "Lieferung, Verwahrung und Echtheitsnachweis sichern",
        "Angemessenheit und Rückgabe prüfen",
    ],
    "senior-pressure-sale": [
        "Widerruf, Anfechtung und Bedarf prüfen",
        "Liefer- und Beratungssituation dokumentieren",
    ],
    "lottery": [
        "Kündigungszeitpunkt und SEPA-Mandat prüfen",
        "Wunsch der betreuten Person gesondert dokumentieren",
    ],
    "subscription": [
        "Laufzeit, Kündigung und Nutzen prüfen",
        "SEPA-Mandat bei fehlendem Nutzen beenden",
    ],
    "private-care": [
        "Leistungsnachweise, Vertrag und Angemessenheit anfordern",
        "Abhängigkeit oder Einflussnahme gesondert prüfen",
    ],
    "unexplained": [
        "Beleg anfordern und Zahlung bis zur Klärung markieren",
    ],
}


def money(value: Any) -> Decimal:
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        normalized = value.replace(".", "").replace(",", ".").replace(" EUR", "").strip()
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise SystemExit(f"Ungültiger Betrag: {value!r}") from exc
    raise SystemExit(f"Ungültiger Betragstyp: {type(value).__name__}")


def amount_points(amount: Decimal) -> int:
    value = abs(amount)
    if value >= Decimal("10000"):
        return 5
    if value >= Decimal("5000"):
        return 4
    if value >= Decimal("1000"):
        return 3
    if value >= Decimal("250"):
        return 1
    return 0


def risk_level(points: int) -> str:
    if points >= 11:
        return "akut"
    if points >= 8:
        return "hoch"
    if points >= 4:
        return "mittel"
    return "niedrig"


def score_transaction(tx: dict[str, Any]) -> dict[str, Any]:
    category = tx.get("category", "unexplained")
    amount = money(tx.get("amount_eur", 0))
    factors = list(tx.get("risk_factors", []))
    points = CATEGORY_POINTS.get(category, CATEGORY_POINTS["unexplained"]) + amount_points(amount)

    if tx.get("foreign_iban"):
        points += 2
        factors.append("Auslands-IBAN oder SWIFT-Zahlung")
    if tx.get("contract_missing"):
        points += 2
        factors.append("Vertrag oder Mandat fehlt")
    if tx.get("repeat_counterparty"):
        points += 1
        factors.append("wiederholter Empfänger")
    if tx.get("remote_access_related"):
        points += 2
        factors.append("Zusammenhang mit Fernzugriff möglich")

    actions = []
    actions.extend(ACTION_LIBRARY.get(category, ACTION_LIBRARY["unexplained"]))
    if abs(amount) >= Decimal("5000"):
        actions.append("Sofortige Vermögenssicherungsmaßnahme prüfen")

    enriched = dict(tx)
    enriched["amount_eur"] = float(amount)
    enriched["score"] = points
    enriched["risk_level"] = risk_level(points)
    enriched["risk_factors"] = sorted(set(factors))
    enriched["recommended_actions"] = actions
    return enriched


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    transactions = [score_transaction(tx) for tx in data.get("transactions", [])]
    transactions.sort(key=lambda tx: (tx["score"], abs(money(tx["amount_eur"]))), reverse=True)

    by_level = Counter(tx["risk_level"] for tx in transactions)
    by_category = Counter(tx.get("category", "unexplained") for tx in transactions)
    by_counterparty: dict[str, Decimal] = defaultdict(Decimal)
    for tx in transactions:
        by_counterparty[tx.get("counterparty", "unbekannt")] += abs(money(tx["amount_eur"]))

    top_counterparties = [
        {"counterparty": name, "total_abs_eur": float(total)}
        for name, total in sorted(by_counterparty.items(), key=lambda item: item[1], reverse=True)[:10]
    ]

    akut = [tx for tx in transactions if tx["risk_level"] == "akut"]
    hoch = [tx for tx in transactions if tx["risk_level"] == "hoch"]
    measures = [
        "Originale Kontoauszüge und Verträge unverändert sichern",
        "Bankkontakt herstellen und weitere atypische Abflüsse monitoren",
        "SEPA-Mandate, Daueraufträge, Karten und Onlinebanking prüfen",
    ]
    if akut:
        measures.insert(0, "Akute Positionen noch heute priorisieren")
    if any(tx.get("remote_access_related") or tx.get("category") == "remote-access" for tx in transactions):
        measures.append("Fernwartungs- und Gerätezugriff unabhängig prüfen lassen")
    if any(tx.get("foreign_iban") for tx in transactions):
        measures.append("Auslandszahlungen mit Bank und Vertragslage abgleichen")

    return {
        "case": data.get("case", {}),
        "summary": {
            "transactions_checked": len(transactions),
            "risk_levels": dict(by_level),
            "categories": dict(by_category),
            "acute_count": len(akut),
            "high_count": len(hoch),
        },
        "top_counterparties": top_counterparties,
        "ranked_transactions": transactions,
        "measures": measures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Betreuungsrechtlicher Konto- und Vertragsverdachtscheck")
    parser.add_argument("input", type=Path, help="JSON-Datei mit Transaktionen")
    parser.add_argument("--output", type=Path, help="Optionaler Ausgabepfad für JSON")
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = analyze(data)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
