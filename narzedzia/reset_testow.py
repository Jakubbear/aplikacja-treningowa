#!/usr/bin/env python3
"""Kasowanie treningów testowych z bazy — po przejściach po aplikacji.

Przejście po aplikacji zakończone przyciskiem „Zamykam trening" zapisuje się
jako prawdziwy trening i blokuje tydzień w widoku. Dopóki klikasz po aplikacji
na próbę, takie sesje będą powstawać regularnie — to jest narzędzie do ich
sprzątania.

Zanim go użyjesz, ustaw `NAJWCZESNIEJSZA_DATA` niżej w pliku.

    python narzedzia/reset_testow.py       # pokazuje, co by skasował (nic nie rusza)
    python narzedzia/reset_testow.py --wykonaj   # kasuje
    python narzedzia/reset_testow.py --data 2026-01-20 --wykonaj

Trzy zabezpieczenia, bo to jedyne narzędzie w tym projekcie, które kasuje z historii:

1. **Domyślnie nic nie kasuje.** Bez `--wykonaj` wypisuje listę i kończy.
2. **Twarda granica `NAJWCZESNIEJSZA_DATA`.** Skrypt nie tknie niczego sprzed dnia,
   w którym zaczęły się testy — wcześniejsza historia treningów jest poza jego
   zasięgiem i żaden argument tego nie zmienia.
3. **Kasuje całymi sesjami, nie seriami.** Nie da się nim wyciąć pojedynczej serii
   z prawdziwego treningu.

Zamknięta sesja jest otwierana przed kasowaniem, zamiast wyłączać trigger
`guard_closed`. Trigger zostaje na miejscu — chroni wtedy, gdy ten skrypt się myli.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    sys.exit("Brak psycopg. Zainstaluj: pip install 'psycopg[binary]'")


# USTAW TO NA SWÓJ DZIEŃ, zanim pierwszy raz odpalisz skrypt z `--wykonaj`.
#
# To ma być dzień, w którym zacząłeś klikać po aplikacji na próbę. Wszystko
# wcześniejsze skrypt uznaje za prawdziwą historię i nie tknie jej — żaden
# argument tego nie obchodzi.
#
# Domyślna wartość jest celowo dzisiejsza i celowo bezużyteczna: dopóki jej nie
# zmienisz, skrypt nie skasuje niczego sprzed dziś, czyli praktycznie niczego.
NAJWCZESNIEJSZA_DATA = date.today()


def sesje_do_skasowania(cur, od: date) -> list[dict]:
    cur.execute(
        """
        select ps.id, ps.performed_on, ps.closed_at is not null as zamknieta,
               pl.label as plan,
               (select count(*) from training.performed_set s where s.session_id = ps.id) as serie,
               (select count(*) from training.performed_item_feedback f
                 where f.session_id = ps.id) as odczucia
          from training.performed_session ps
          left join training.planned_session pl on pl.id = ps.planned_session_id
         where ps.performed_on >= %s
         order by ps.performed_on, ps.id
        """,
        (od,),
    )
    return cur.fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        default=NAJWCZESNIEJSZA_DATA.isoformat(),
        help=f"kasuj sesje od tej daty włącznie (domyślnie {NAJWCZESNIEJSZA_DATA})",
    )
    parser.add_argument("--wykonaj", action="store_true", help="faktycznie skasuj")
    args = parser.parse_args()

    od = date.fromisoformat(args.data)
    if od < NAJWCZESNIEJSZA_DATA:
        return _blad(
            f"data {od} jest wcześniejsza niż granica {NAJWCZESNIEJSZA_DATA}.\n"
            "Przed tym dniem leży prawdziwa historia treningów — ten skrypt jej nie rusza."
        )

    url = os.environ.get("DATABASE_URL")
    if not url:
        return _blad("Brak DATABASE_URL.")

    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            sesje = sesje_do_skasowania(cur, od)

            if not sesje:
                print(f"Brak sesji od {od} — nie ma czego kasować.")
                return 0

            print(f"Sesje od {od}:\n")
            for s in sesje:
                stan = "zamknięta" if s["zamknieta"] else "otwarta"
                print(
                    f"  id={s['id']}  {s['performed_on']}  {stan}"
                    f"  plan: {s['plan'] or 'poza planem'}"
                    f"  serie: {s['serie']}  odczucia: {s['odczucia']}"
                )

            if not args.wykonaj:
                print("\nNic nie skasowano. Powtórz z --wykonaj.")
                return 0

            ident = [s["id"] for s in sesje]
            # Otwarcie przed kasowaniem: trigger `guard_closed` broni serii
            # w sesjach zamkniętych, a my nie chcemy go wyłączać.
            cur.execute(
                "update training.performed_session set closed_at = null where id = any(%s)",
                (ident,),
            )
            cur.execute(
                "delete from training.performed_session where id = any(%s)", (ident,)
            )
            usuniete = cur.rowcount
            conn.commit()

            cur.execute("select count(*) as ile from training.performed_session")
            sesji = cur.fetchone()["ile"]
            cur.execute("select count(*) as ile from training.performed_set")
            serii = cur.fetchone()["ile"]

    print(f"\nSkasowano sesji: {usuniete}. Zostaje {sesji} sesji i {serii} serii.")
    return 0


def _blad(tresc: str) -> int:
    print(f"BŁĄD: {tresc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
