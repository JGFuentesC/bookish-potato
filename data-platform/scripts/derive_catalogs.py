"""Deriva los catálogos OLTP (E1-H1-T1.2) de los JSON reales de StatsBomb en data/raw/data/.

Genera data-platform/migrations/0001_catalogs.seed.sql con INSERTs ordenados por id.
Uso (desde la raíz del repo):
    uv run --project data-platform python -m scripts.derive_catalogs
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "data"
OUT = ROOT / "data-platform" / "migrations" / "0001_catalogs.seed.sql"

TABLES = [
    "country",
    "competition_stage",
    "event_type",
    "play_pattern",
    "position",
    "body_part",
    "outcome",
    "technique",
    "pass_height",
    "pass_type",
    "shot_type",
    "duel_type",
    "goalkeeper_type",
    "card_type",
    "formation",
]

COLUMNS = {
    "country": ("country_id", "country_name"),
    "competition_stage": ("competition_stage_id", "competition_stage_name"),
    "event_type": ("event_type_id", "event_type_name"),
    "play_pattern": ("play_pattern_id", "play_pattern_name"),
    "position": ("position_id", "position_name"),
    "body_part": ("body_part_id", "body_part_name"),
    "outcome": ("outcome_id", "outcome_name"),
    "technique": ("technique_id", "technique_name"),
    "pass_height": ("pass_height_id", "pass_height_name"),
    "pass_type": ("pass_type_id", "pass_type_name"),
    "shot_type": ("shot_type_id", "shot_type_name"),
    "duel_type": ("duel_type_id", "duel_type_name"),
    "goalkeeper_type": ("goalkeeper_type_id", "goalkeeper_type_name"),
    "card_type": ("card_type_id", "card_type_name"),
    "formation": ("formation_id", "formation_name"),
}


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class Catalogs:
    def __init__(self) -> None:
        self.values: dict[str, dict[int, str]] = {t: {} for t in TABLES}

    def add(self, table: str, obj: dict | None) -> None:
        if not isinstance(obj, dict) or "id" not in obj or "name" not in obj:
            return
        values = self.values[table]
        values.setdefault(int(obj["id"]), str(obj["name"]))

    def add_formation(self, formation: int | None) -> None:
        if formation is None:
            return
        self.values["formation"].setdefault(int(formation), "-".join(str(int(formation))))

    def iter_json(self, relative: str) -> Iterable[dict]:
        for path in sorted((RAW / relative).glob("*.json")):
            yield json.loads(path.read_text())

    def from_competitions(self) -> None:
        for comp in self.iter_json("."):
            for item in comp if isinstance(comp, list) else [comp]:
                self.add("country", item.get("competition", {}).get("country"))

    def from_matches(self) -> None:
        for path in sorted((RAW / "matches").rglob("*.json")):
            for match in json.loads(path.read_text()):
                self.add("country", match.get("competition", {}).get("country"))
                self.add("competition_stage", match.get("competition_stage"))
                for side in ("home_team", "away_team"):
                    self.add("country", match.get(side, {}).get("country"))

    def from_lineups(self) -> None:
        for entries in self.iter_json("lineups"):
            for lineup in entries if isinstance(entries, list) else [entries]:
                self.add("country", lineup.get("team", {}).get("country"))
                self.add_formation(lineup.get("tactics", {}).get("formation"))
                players = lineup.get("tactics", {}).get("lineup") or lineup.get("lineup") or []
                for player in players:
                    self.add("position", player.get("position"))

    def from_events(self) -> None:
        for events in self.iter_json("events"):
            for event in events:
                self.add("event_type", event.get("type"))
                self.add("play_pattern", event.get("play_pattern"))
                self.add("position", event.get("position"))
                if event.get("type", {}).get("name") in ("Starting XI", "Tactical Shift"):
                    self.add_formation(event.get("tactics", {}).get("formation"))
                for key in ("body_part", "outcome", "technique"):
                    self.add(key, event.get(key))
                for sub, *map_keys in (
                    ("pass", "height", "pass_height", "type", "pass_type", "technique", "technique", "outcome", "outcome", "body_part", "body_part"),
                    ("shot", "type", "shot_type", "body_part", "body_part", "technique", "technique", "outcome", "outcome"),
                    ("duel", "type", "duel_type", "outcome", "outcome"),
                    ("goalkeeper", "type", "goalkeeper_type", "outcome", "outcome", "body_part", "body_part"),
                    ("interception", "outcome", "outcome"),
                    ("clearance", "body_part", "body_part"),
                    ("block", "body_part", "body_part"),
                    ("substitution", "outcome", "outcome"),
                    ("miscontrol", "outcome", "outcome"),
                    ("ball_receipt", "outcome", "outcome"),
                    ("50_50", "outcome", "outcome"),
                ):
                    payload = event.get(sub)
                    if not isinstance(payload, dict):
                        continue
                    for i in range(0, len(map_keys), 2):
                        self.add(map_keys[i + 1], payload.get(map_keys[i]))
                for sub in ("foul_committed", "bad_behaviour"):
                    payload = event.get(sub)
                    if isinstance(payload, dict):
                        self.add("card_type", payload.get("card"))

    def build_sql(self) -> str:
        lines = ["-- Generado por scripts/derive_catalogs.py desde data/raw/data (StatsBomb open-data).", "-- No editar a mano: regenérase con uv run --project data-platform python -m scripts.derive_catalogs"]
        for table in TABLES:
            id_col, name_col = COLUMNS[table]
            lines.append(f"-- {table}")
            for obj_id in sorted(self.values[table]):
                name = self.values[table][obj_id]
                lines.append(f"INSERT INTO oltp.{table} ({id_col}, {name_col}) VALUES ({obj_id}, {sql_literal(name)});")
        return "\n".join(lines) + "\n"


def main() -> None:
    catalogs = Catalogs()
    catalogs.from_competitions()
    catalogs.from_matches()
    catalogs.from_lineups()
    catalogs.from_events()
    OUT.write_text(catalogs.build_sql())
    for table in TABLES:
        print(f"{table}: {len(catalogs.values[table])}")
    print(f"seed escrito en {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()