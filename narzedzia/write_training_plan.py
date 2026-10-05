#!/usr/bin/env python3
"""Wsad planu treningowego do PostgreSQL.

Plan piszesz jako plik JSON i wgrywasz tym skryptem — nie przepisujesz go
ręcznie do bazy. Format opisuje `plany/README.md`.

    export DATABASE_URL="postgresql://trening:HASLO@localhost:5432/trening"
    python narzedzia/write_training_plan.py plany/moje/plan-1.json --dry-run
    python narzedzia/write_training_plan.py plany/moje/plan-1.json

`--dry-run` przepuszcza cały wsad przez bazę i wycofuje go na końcu: pokazuje,
co by wjechało, nie zapisując nic. Warto, bo nieznana nazwa ćwiczenia zatrzymuje
wsad dopiero w trakcie.

JSON, a nie YAML, bo YAML nie jest zależnością tego projektu, a ręcznie pisany
plik potrafi się cicho źle sparsować.

Ćwiczenia są dopasowywane po `slug` albo po aliasie. Nieznane ćwiczenie
zatrzymuje wsad — lepiej dopisać je świadomie do katalogu, niż rozjechać
historię dwiema nazwami tego samego ruchu.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    sys.exit("Brak psycopg. Zainstaluj: pip install 'psycopg[binary]'")


def wczytaj(sciezka: Path) -> dict:
    return json.loads(sciezka.read_text(encoding="utf-8"))


def przesun_na_biezacy_tydzien(plan: dict) -> dict:
    """Przesuwa cały plan tak, żeby pierwsza sesja wypadła w tym tygodniu.

    Potrzebne przy planie przykładowym: daty w pliku są sztywne, a widok postępu
    rysuje wykres w oknie tygodni planu. Plan sprzed pół roku daje pusty wykres
    z napisem „brak pomiarów" — poprawnie, ale myląco przy pierwszym uruchomieniu.

    Odstępy między sesjami zostają zachowane; przesuwana jest cała oś czasu.
    """
    pierwsza = min(date.fromisoformat(s["planned_on"]) for s in plan["sessions"])
    dzis = date.today()
    docelowy_poniedzialek = dzis - timedelta(days=dzis.weekday())
    przesuniecie = docelowy_poniedzialek - (pierwsza - timedelta(days=pierwsza.weekday()))

    def plus(iso: str) -> str:
        return (date.fromisoformat(iso) + przesuniecie).isoformat()

    plan["starts_on"] = plus(plan["starts_on"])
    plan["ends_on"] = plus(plan["ends_on"])
    for s in plan["sessions"]:
        s["planned_on"] = plus(s["planned_on"])
    return plan


def znajdz_cwiczenie(cur, nazwa: str) -> int:
    cur.execute("select id from training.exercise where slug = %s", (nazwa,))
    row = cur.fetchone()
    if row:
        return row["id"]

    cur.execute(
        "select exercise_id as id from training.exercise_alias where alias = lower(%s)",
        (nazwa,),
    )
    row = cur.fetchone()
    if row:
        return row["id"]

    raise SystemExit(
        f"Nieznane ćwiczenie: {nazwa!r}. Dopisz je do katalogu "
        f"(db/seeds/) albo popraw nazwę w planie."
    )


def wsadz(plan: dict, dsn: str, dry_run: bool) -> None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into training.training_plan (label, starts_on, ends_on, author, supersedes) "
                "values (%s, %s, %s, %s, %s) returning id",
                (
                    plan["label"],
                    plan["starts_on"],
                    plan["ends_on"],
                    plan.get("author", "agent"),
                    plan.get("supersedes"),
                ),
            )
            plan_id = cur.fetchone()["id"]
            print(f"plan #{plan_id}: {plan['label']}")

            for i, sesja in enumerate(plan["sessions"], start=1):
                cur.execute(
                    "insert into training.planned_session "
                    "    (plan_id, label, planned_on, location, ordinal, notes) "
                    "values (%s, %s, %s, %s, %s, %s) returning id",
                    (
                        plan_id,
                        sesja["label"],
                        sesja["planned_on"],
                        sesja.get("location", "dom"),
                        i,
                        sesja.get("notes"),
                    ),
                )
                sesja_id = cur.fetchone()["id"]
                print(f"  {sesja['label']} — {sesja['planned_on']}")

                for j, poz in enumerate(sesja["items"], start=1):
                    cwiczenie_id = znajdz_cwiczenie(cur, poz["exercise"])
                    cur.execute(
                        """
                        insert into training.planned_item
                            (session_id, ordinal, exercise_id, sets, reps_min, reps_max,
                             duration_seconds, weight_planned_kg, superset_group,
                             rest_seconds, progression_note)
                        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            sesja_id,
                            j,
                            cwiczenie_id,
                            poz["sets"],
                            poz.get("reps_min"),
                            poz.get("reps_max", poz.get("reps_min")),
                            poz.get("duration_seconds"),
                            poz.get("weight_kg"),
                            poz.get("superset"),
                            poz.get("rest_seconds", 120),
                            poz.get("note"),
                        ),
                    )
                    print(f"    {j}. {poz['exercise']}")

            if dry_run:
                conn.rollback()
                print("\n--dry-run: wycofane, nic nie zostało zapisane.")
            else:
                conn.commit()
                print("\nZapisane.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--na-biezacy-tydzien",
        action="store_true",
        help="przesuń daty planu tak, żeby pierwsza sesja wypadła w tym tygodniu",
    )
    args = ap.parse_args()

    if not args.dsn:
        sys.exit("Brak DSN. Podaj --dsn albo ustaw DATABASE_URL.")

    plan = wczytaj(args.plan)
    if args.na_biezacy_tydzien:
        plan = przesun_na_biezacy_tydzien(plan)

    wsadz(plan, args.dsn, args.dry_run)


if __name__ == "__main__":
    main()
