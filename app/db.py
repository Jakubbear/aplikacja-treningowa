"""Połączenie z bazą i zapytania warstwy treningowej.

Cała reszta aplikacji czyta wyłącznie stąd. Zapytania odczytowe idą do widoku
`training.performed_set_current`, nigdy do tabeli wprost — inaczej po korekcie
widać byłoby obie wersje serii naraz.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_POOL: ConnectionPool | None = None


def dsn() -> str:
    """DSN składany z części, z hasłem czytanym z pliku.

    Ten sam wzorzec co `POSTGRES_PASSWORD_FILE` w stacku bazy: hasło nie jest
    zmienną środowiskową, więc nie widać go przez `docker inspect` ani ze
    środowiska sąsiedniego kontenera. `DATABASE_URL` zostaje jako droga na skróty
    do uruchomienia z laptopa.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    haslo_plik = os.environ.get("DATABASE_PASSWORD_FILE")
    if not haslo_plik:
        raise RuntimeError("Brak DATABASE_URL i DATABASE_PASSWORD_FILE — nie ma czym się połączyć.")

    haslo = Path(haslo_plik).read_text(encoding="utf-8").strip()
    host = os.environ.get("DATABASE_HOST", "postgres")
    port = os.environ.get("DATABASE_PORT", "5432")
    uzytkownik = os.environ.get("DATABASE_USER", "health")
    baza = os.environ.get("DATABASE_NAME", "health")
    return f"postgresql://{uzytkownik}:{quote(haslo)}@{host}:{port}/{baza}"


def pool() -> ConnectionPool:
    global _POOL
    if _POOL is None:
        # `check` sprawdza połączenie przed wydaniem z puli. Bez tego pierwsze
        # wejście po restarcie bazy (`docker compose restart postgres`) kończy się
        # błędem 500, bo pula oddaje połączenie zerwane po drugiej stronie.
        _POOL = ConnectionPool(
            dsn(), min_size=1, max_size=4, kwargs={"row_factory": dict_row},
            check=ConnectionPool.check_connection,
        )
    return _POOL


@contextmanager
def cursor():
    with pool().connection() as conn:
        with conn.cursor() as cur:
            yield cur


# ----------------------------------------------------------------- katalog


def exercises() -> list[dict]:
    with cursor() as cur:
        cur.execute(
            "select id, slug, name, equipment, default_bar_weight_kg, measure "
            "from training.exercise order by name"
        )
        return cur.fetchall()


def find_or_create_exercise(name: str) -> int:
    """Podmiana ćwiczenia na coś spoza katalogu dopisuje nową pozycję.

    Świadomie liberalne: lepiej mieć w katalogu ćwiczenie wpisane w biegu
    niż stracić zapis serii, bo nazwa się nie zgadzała.
    """
    name = name.strip()
    with cursor() as cur:
        cur.execute(
            "select exercise_id as id from training.exercise_alias where alias = lower(%s)",
            (name,),
        )
        row = cur.fetchone()
        if row:
            return row["id"]

        cur.execute("select id from training.exercise where lower(name) = lower(%s)", (name,))
        row = cur.fetchone()
        if row:
            return row["id"]

        slug = _slugify(name)
        cur.execute(
            "insert into training.exercise (slug, name, notes) "
            "values (%s, %s, 'Dopisane z aplikacji przy podmianie ćwiczenia.') returning id",
            (slug, name),
        )
        new_id = cur.fetchone()["id"]
        cur.execute(
            "insert into training.exercise_alias (alias, exercise_id) values (lower(%s), %s) "
            "on conflict do nothing",
            (name, new_id),
        )
        return new_id


_ZNAKI = str.maketrans("ąćęłńóśźż ", "acelnoszz-")


def _slugify(name: str) -> str:
    base = name.lower().translate(_ZNAKI)
    base = "".join(ch for ch in base if ch.isalnum() or ch == "-")
    return (base or "cwiczenie")[:60]


# ----------------------------------------------------------------- plan


def next_session() -> dict | None:
    """Sesja do zrobienia: otwarta, jeśli trwa, inaczej najbliższa niezrobiona.

    Nie filtruje po dacie dziennej. Przy jednym treningu w tygodniu widok
    przywiązany do „dziś" byłby pusty przez sześć dni z siedmiu.

    Pomija plany, które zostały zastąpione. Bez tego nowy plan nigdy by się nie
    pokazał: sesje planu zastąpionego są na zawsze „niezrobione", bo importer
    historii wstawia treningi z `planned_session_id = NULL` i nic ich nie zamyka.
    Telefon wyświetlałby najstarszy tydzień do końca świata.
    """
    with cursor() as cur:
        cur.execute(
            """
            select ps.id as performed_id, pl.id as planned_id, pl.label, pl.planned_on,
                   pl.location, pl.notes
              from training.performed_session ps
              join training.planned_session pl on pl.id = ps.planned_session_id
             where ps.closed_at is null
             order by ps.started_at desc
             limit 1
            """
        )
        trwa = cur.fetchone()
        if trwa:
            return trwa

        cur.execute(
            """
            select null::bigint as performed_id, pl.id as planned_id, pl.label,
                   pl.planned_on, pl.location, pl.notes
              from training.planned_session pl
             where not exists (
                   select 1 from training.performed_session done
                    where done.planned_session_id = pl.id
                      and done.closed_at is not null
             )
               and not exists (
                   select 1 from training.training_plan nastepnik
                    where nastepnik.supersedes = pl.plan_id
             )
             order by pl.planned_on, pl.ordinal
             limit 1
            """
        )
        return cur.fetchone()


def open_session() -> dict | None:
    """Trening w toku, jeśli jest — ten sam warunek co pierwsza połowa `next_session()`."""
    with cursor() as cur:
        cur.execute(
            """
            select ps.id as performed_id, pl.id as planned_id, pl.label, ps.performed_on
              from training.performed_session ps
              join training.planned_session pl on pl.id = ps.planned_session_id
             where ps.closed_at is null
             order by ps.started_at desc
             limit 1
            """
        )
        return cur.fetchone()


def plan_queue() -> list[dict]:
    """Niezrobione treningi aktywnego planu, po kolei.

    Widok jest tygodniowy, a plan to kolejka: data `planned_on`
    jest orientacyjna, a o tym, w którym tygodniu wypada trening, decyduje
    rozkład w `main.rozloz_kolejke`. Pomija treningi w toku — te są już
    wykonane w jakimś tygodniu, nie zaplanowane. `plan_ruszyl` mówi, czy z tego
    planu zrobiono już cokolwiek: dopóki nie, plan nie wchodzi przed swoją datę.
    """
    with cursor() as cur:
        cur.execute(
            """
            select pl.id as planned_id, pl.label, pl.planned_on, pl.location, pl.notes,
                   exists (
                       select 1 from training.performed_session ps
                         join training.planned_session p2 on p2.id = ps.planned_session_id
                        where p2.plan_id = pl.plan_id
                   ) as plan_ruszyl
              from training.planned_session pl
             where not exists (
                   select 1 from training.performed_session ps
                    where ps.planned_session_id = pl.id
             )
               and not exists (
                   select 1 from training.training_plan nastepnik
                    where nastepnik.supersedes = pl.plan_id
             )
             order by pl.planned_on, pl.ordinal
            """
        )
        return cur.fetchall()


def sessions_in_week(monday) -> list[dict]:
    """Treningi wykonane (albo w toku) w tygodniu od poniedziałku `monday`."""
    with cursor() as cur:
        cur.execute(
            """
            select ps.id as performed_id, ps.performed_on, ps.location, ps.closed_at,
                   coalesce(pl.label, 'Trening') as label,
                   (select count(distinct c.exercise_id)
                      from training.performed_set_current c
                     where c.session_id = ps.id) as cwiczen
              from training.performed_session ps
              left join training.planned_session pl on pl.id = ps.planned_session_id
             where ps.performed_on between %s and %s::date + 6
             order by ps.started_at
            """,
            (monday, monday),
        )
        return cur.fetchall()


def plan_items(planned_session_id: int, performed_session_id: int | None = None) -> list[dict]:
    """Pozycje planu w kolejności ekranu.

    Bez wykonania (widok tygodnia) — kolejność z planu. W trwającej sesji
    — kolejność przestawiona przez użytkownika, jeśli ją ruszał
    (`training.performed_item_order`), a pozycje bez wpisu idą na koniec
    w porządku planu.
    """
    with cursor() as cur:
        cur.execute(
            """
            select pi.id, pi.ordinal, pi.sets, pi.reps_min, pi.reps_max,
                   pi.duration_seconds, pi.weight_planned_kg, pi.superset_group,
                   pi.rest_seconds, pi.progression_note,
                   ex.id as exercise_id, ex.name as exercise, ex.measure,
                   ex.default_bar_weight_kg
              from training.planned_item pi
              join training.exercise ex on ex.id = pi.exercise_id
              left join training.performed_item_order o
                     on o.planned_item_id = pi.id and o.session_id = %s
             where pi.session_id = %s
             order by o.position nulls last, pi.ordinal
            """,
            (performed_session_id, planned_session_id),
        )
        return cur.fetchall()


def do_now(performed_session_id: int, planned_item_id: int) -> None:
    """„Robię teraz": karta idzie zaraz za ćwiczeniami już zaczętymi.

    Nie na sam szczyt ekranu — wtedy zaczęte ćwiczenia spadałyby pod nią i ekran
    przestawałby pokazywać przebieg treningu. Seria łączona przesuwa się w całości,
    bo jej pozycje robi się na zmianę.

    Zapisuje pełną kolejność sesji naraz (kasuje i wstawia), więc nie ma stanu
    pośredniego z dwiema kartami na tym samym miejscu. Po zamknięciu treningu
    trigger `guard_closed_order` odrzuci zmianę.
    """
    with cursor() as cur:
        cur.execute(
            "select planned_session_id from training.performed_session where id = %s",
            (performed_session_id,),
        )
        sesja = cur.fetchone()
        if sesja is None or sesja["planned_session_id"] is None:
            return
        pozycje = plan_items(sesja["planned_session_id"], performed_session_id)
        wybrana = next((p for p in pozycje if p["id"] == planned_item_id), None)
        if wybrana is None:
            return

        grupa = wybrana["superset_group"]
        przesuwane = [
            p["id"] for p in pozycje
            if p["id"] == planned_item_id or (grupa and p["superset_group"] == grupa)
        ]

        cur.execute(
            "select distinct planned_item_id from training.performed_set "
            " where session_id = %s and planned_item_id is not null",
            (performed_session_id,),
        )
        zaczete = {r["planned_item_id"] for r in cur.fetchall()}

        reszta = [p["id"] for p in pozycje if p["id"] not in przesuwane]
        nowa = (
            [i for i in reszta if i in zaczete]
            + przesuwane
            + [i for i in reszta if i not in zaczete]
        )

        cur.execute(
            "delete from training.performed_item_order where session_id = %s",
            (performed_session_id,),
        )
        for pozycja, item_id in enumerate(nowa, start=1):
            cur.execute(
                "insert into training.performed_item_order (session_id, planned_item_id, position) "
                "values (%s, %s, %s)",
                (performed_session_id, item_id, pozycja),
            )


def split_superset_group(group: str) -> dict:
    """Nowa wersja aktywnego planu z rozdzieloną wskazaną grupą serii łączonych.

    Zgodnie z zasadą projektu poprawka planu to nowa wersja (`supersedes`),
    nie edycja istniejących wierszy — inaczej zatarłaby się historia zamiaru.
    Kopiuje wyłącznie sesje, do których nie ma jeszcze ŻADNEGO wpisu wykonania
    (otwartego ani zamkniętego) — surowszy warunek niż w `next_session()`,
    bo to funkcja wywoływana też W TRAKCIE trwającego treningu (przycisk
    w `sesja.html`). Bez tego zaostrzenia trwająca sesja duplikowałaby się
    w nowym planie i po zamknięciu wracałaby jako „do zrobienia" jeszcze raz.
    Pozycje z podaną grupą tracą `superset_group`, reszta przechodzi bez zmian.
    """
    with cursor() as cur:
        cur.execute(
            """
            select tp.id, tp.label, tp.starts_on, tp.ends_on, tp.author
              from training.training_plan tp
             where not exists (
                   select 1 from training.training_plan n where n.supersedes = tp.id
             )
             order by tp.created_at desc, tp.id desc
             limit 1
            """
        )
        stary = cur.fetchone()
        if stary is None:
            raise RuntimeError("Brak aktywnego planu.")

        cur.execute(
            "insert into training.training_plan (label, starts_on, ends_on, author, supersedes) "
            "values (%s, %s, %s, %s, %s) returning id",
            (stary["label"], stary["starts_on"], stary["ends_on"], stary["author"], stary["id"]),
        )
        nowy_plan_id = cur.fetchone()["id"]

        cur.execute(
            """
            select ps.id, ps.label, ps.planned_on, ps.location, ps.ordinal, ps.notes
              from training.planned_session ps
             where ps.plan_id = %s
               and not exists (
                     select 1 from training.performed_session done
                      where done.planned_session_id = ps.id
               )
             order by ps.ordinal
            """,
            (stary["id"],),
        )
        sesje = cur.fetchall()

        skopiowane = 0
        rozdzielone = 0
        for s in sesje:
            cur.execute(
                "insert into training.planned_session "
                "    (plan_id, label, planned_on, location, ordinal, notes) "
                "values (%s, %s, %s, %s, %s, %s) returning id",
                (nowy_plan_id, s["label"], s["planned_on"], s["location"], s["ordinal"], s["notes"]),
            )
            nowa_sesja_id = cur.fetchone()["id"]
            skopiowane += 1

            cur.execute(
                """
                select ordinal, exercise_id, sets, reps_min, reps_max, duration_seconds,
                       weight_planned_kg, superset_group, rest_seconds, progression_note
                  from training.planned_item
                 where session_id = %s
                 order by ordinal
                """,
                (s["id"],),
            )
            for poz in cur.fetchall():
                grupa = poz["superset_group"]
                if grupa == group:
                    grupa = None
                    rozdzielone += 1
                cur.execute(
                    """
                    insert into training.planned_item
                        (session_id, ordinal, exercise_id, sets, reps_min, reps_max,
                         duration_seconds, weight_planned_kg, superset_group,
                         rest_seconds, progression_note)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        nowa_sesja_id, poz["ordinal"], poz["exercise_id"], poz["sets"],
                        poz["reps_min"], poz["reps_max"], poz["duration_seconds"],
                        poz["weight_planned_kg"], grupa, poz["rest_seconds"], poz["progression_note"],
                    ),
                )

        return {"plan_id": nowy_plan_id, "sesje": skopiowane, "pozycje_rozdzielone": rozdzielone}


def clear_superset_group_for_session(planned_session_id: int, group: str) -> None:
    """Zdejmuje oznaczenie grupy z pozycji BIEŻĄCEJ, trwającej sesji.

    To metadane planu, nie wynik: `planned_item` nie ma triggera niezmienności
    (ten pilnuje tylko `performed_set`), więc dopóki sesja trwa, korekta
    „to jednak nie jest seria łączona" idzie wprost, bez nowej wersji planu.
    Wersją planu na przyszłe tygodnie zajmuje się osobno `split_superset_group`.
    """
    with cursor() as cur:
        cur.execute(
            "update training.planned_item set superset_group = null "
            " where session_id = %s and superset_group = %s",
            (planned_session_id, group),
        )


def last_results() -> dict[int, dict]:
    """Co podniosłeś ostatnim razem, per ćwiczenie. Rdzeń użyteczności widoku."""
    with cursor() as cur:
        cur.execute(
            """
            select distinct on (c.exercise_id)
                   c.exercise_id, c.weight_total_kg, c.repetitions,
                   c.duration_seconds, s.performed_on
              from training.performed_set_current c
              join training.performed_session s on s.id = c.session_id
             where s.closed_at is not null
             order by c.exercise_id, s.performed_on desc, c.recorded_at desc
            """
        )
        return {r["exercise_id"]: r for r in cur.fetchall()}


def last_session_sets(exercise_ids: list[int]) -> dict[int, dict]:
    """Serie ćwiczenia z ostatniego zamkniętego treningu, w którym było robione.

    Podstawa „Idzie w górę" (`main.do_podbicia`): reguła progresji patrzy na
    wszystkie serie z ostatniego razu, nie na ostatnią serię jak `last_results()`.
    """
    if not exercise_ids:
        return {}
    with cursor() as cur:
        cur.execute(
            """
            with ostatnia as (
                select distinct on (c.exercise_id) c.exercise_id, c.session_id
                  from training.performed_set_current c
                  join training.performed_session s on s.id = c.session_id
                 where s.closed_at is not null
                   and c.exercise_id = any(%s)
                 order by c.exercise_id, s.performed_on desc, s.started_at desc
            )
            select o.exercise_id,
                   count(*) as serie,
                   min(c.repetitions) as min_powt,
                   min(c.weight_total_kg) as min_kg,
                   max(c.weight_total_kg) as max_kg
              from ostatnia o
              join training.performed_set_current c
                on c.session_id = o.session_id and c.exercise_id = o.exercise_id
             group by o.exercise_id
            """,
            (exercise_ids,),
        )
        return {r["exercise_id"]: r for r in cur.fetchall()}


# ----------------------------------------------------------------- wykonanie


def start_session(planned_session_id: int, location: str) -> int:
    with cursor() as cur:
        cur.execute(
            "select planned_on, location from training.planned_session where id = %s",
            (planned_session_id,),
        )
        plan = cur.fetchone()
        cur.execute(
            "insert into training.performed_session (planned_session_id, performed_on, location) "
            "values (%s, current_date, %s) returning id",
            (planned_session_id, location or plan["location"]),
        )
        return cur.fetchone()["id"]


def sets_of(performed_session_id: int) -> list[dict]:
    with cursor() as cur:
        cur.execute(
            """
            select c.id, c.planned_item_id, c.exercise_id, c.set_number,
                   c.repetitions, c.duration_seconds, c.bar_weight_kg,
                   c.added_weight_kg, c.weight_total_kg, c.note, c.rest_seconds,
                   ex.name as exercise, ex.measure,
                   zam.name as substituted_from
              from training.performed_set_current c
              join training.exercise ex on ex.id = c.exercise_id
              left join training.exercise zam on zam.id = c.substituted_from_exercise_id
             where c.session_id = %s
             order by c.planned_item_id nulls last, c.set_number
            """,
            (performed_session_id,),
        )
        return cur.fetchall()


def add_set(
    performed_session_id: int,
    planned_item_id: int | None,
    exercise_id: int,
    set_number: int,
    repetitions: int | None,
    duration_seconds: int | None,
    bar_weight_kg: float,
    added_weight_kg: float,
    substituted_from_exercise_id: int | None,
    note: str | None,
    rest_seconds: int | None = None,
) -> int:
    with cursor() as cur:
        # Data treningu to dzień pierwszej serii, nie dzień otwarcia sesji.
        # Sesja otwarta i porzucona 27.09 przejęła trening z 4.10 — strona główna
        # przekierowuje do otwartej sesji, więc stara data szła razem z nią.
        # Ten sam błąd dał sesji 53 datę 16.09 zamiast 19.09.
        cur.execute(
            """
            update training.performed_session
               set performed_on = (now() at time zone 'Europe/Warsaw')::date,
                   started_at = now()
             where id = %s
               and not exists (select 1 from training.performed_set where session_id = %s)
            """,
            (performed_session_id, performed_session_id),
        )
        cur.execute(
            """
            insert into training.performed_set
                (session_id, planned_item_id, exercise_id, substituted_from_exercise_id,
                 set_number, repetitions, duration_seconds, bar_weight_kg, added_weight_kg,
                 note, rest_seconds)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                performed_session_id,
                planned_item_id,
                exercise_id,
                substituted_from_exercise_id,
                set_number,
                repetitions,
                duration_seconds,
                bar_weight_kg,
                added_weight_kg,
                note,
                rest_seconds,
            ),
        )
        return cur.fetchone()["id"]


def update_set(
    set_id: int,
    repetitions: int | None,
    duration_seconds: int | None,
    bar_weight_kg: float,
    added_weight_kg: float,
    rest_seconds: int | None = None,
) -> None:
    """Poprawka serii w trakcie treningu.

    Działa tylko przy otwartej sesji — po zamknięciu trigger `guard_closed`
    odrzuci UPDATE i trzeba zapisać korektę jako nowy wiersz.
    """
    with cursor() as cur:
        cur.execute(
            "update training.performed_set "
            "   set repetitions = %s, duration_seconds = %s, "
            "       bar_weight_kg = %s, added_weight_kg = %s, rest_seconds = %s "
            " where id = %s",
            (repetitions, duration_seconds, bar_weight_kg, added_weight_kg,
             rest_seconds, set_id),
        )


def delete_set(set_id: int) -> None:
    """Skasowanie omyłkowej serii. Też tylko przy otwartej sesji."""
    with cursor() as cur:
        cur.execute("delete from training.performed_set where id = %s", (set_id,))


def close_session(performed_session_id: int, feeling: str | None, notes: str | None) -> None:
    with cursor() as cur:
        cur.execute(
            "update training.performed_session "
            "   set closed_at = now(), feeling = %s, notes = %s "
            " where id = %s and closed_at is null",
            (feeling or None, notes or None, performed_session_id),
        )


def session_header(performed_session_id: int) -> dict | None:
    with cursor() as cur:
        cur.execute(
            """
            select ps.id, ps.performed_on, ps.location, ps.closed_at, ps.feeling, ps.notes,
                   pl.id as planned_id, pl.label
              from training.performed_session ps
              left join training.planned_session pl on pl.id = ps.planned_session_id
             where ps.id = %s
            """,
            (performed_session_id,),
        )
        return cur.fetchone()


def deviations(performed_session_id: int) -> list[dict]:
    """Odchylenia wykonania od planu — to czyta agent na koniec tygodnia.

    Ułożone w kolejności WYKONANIA (pierwsza seria każdej pozycji), nie planu:
    użytkownik może przestawiać ćwiczenia w trakcie i ta kolejność jest
    informacją dla korekty planu. `plan_nr` zostaje, żeby było widać różnicę.
    """
    with cursor() as cur:
        cur.execute(
            """
            select ex.name as exercise, pi.ordinal as plan_nr, pi.sets as sets_planned,
                   pi.reps_min, pi.reps_max, pi.weight_planned_kg,
                   count(c.id) as sets_done,
                   min(c.repetitions) as reps_min_done,
                   max(c.repetitions) as reps_max_done,
                   max(c.weight_total_kg) as weight_max_done,
                   bool_or(c.substituted_from_exercise_id is not null) as substituted,
                   bool_or(pi.reps_max is not null and c.repetitions > pi.reps_max) as exceeded,
                   min(c.recorded_at) as pierwsza_seria
              from training.planned_item pi
              join training.exercise ex on ex.id = pi.exercise_id
              join training.performed_session ps on ps.id = %s
              left join training.performed_set_current c
                     on c.session_id = ps.id and c.planned_item_id = pi.id
             where pi.session_id = ps.planned_session_id
             group by ex.name, pi.ordinal, pi.sets, pi.reps_min, pi.reps_max, pi.weight_planned_kg
             order by min(c.recorded_at) nulls last, pi.ordinal
            """,
            (performed_session_id,),
        )
        return cur.fetchall()


# ----------------------------------------------------- odczucia do ćwiczeń


def item_feedback(performed_session_id: int) -> dict[int, dict]:
    """Ból i intensywność wysiłku, per ćwiczenie. Klucz: `exercise_id`.

    Kluczem jest ćwiczenie faktycznie wykonane, nie pozycja planu — po podmianie
    odczucie należy do zamiennika, bo to jego się robiło.
    """
    with cursor() as cur:
        cur.execute(
            "select exercise_id, planned_item_id, pain_note, effort "
            "  from training.performed_item_feedback where session_id = %s",
            (performed_session_id,),
        )
        return {r["exercise_id"]: r for r in cur.fetchall()}


def save_item_feedback(
    performed_session_id: int,
    planned_item_id: int | None,
    exercise_id: int,
    pain_note: str | None,
    effort: int | None,
) -> None:
    """Zapis odczucia. Wyczyszczenie obu pól kasuje wiersz, bo pusty nic nie znaczy."""
    with cursor() as cur:
        if pain_note is None and effort is None:
            cur.execute(
                "delete from training.performed_item_feedback "
                " where session_id = %s and exercise_id = %s",
                (performed_session_id, exercise_id),
            )
            return

        cur.execute(
            """
            insert into training.performed_item_feedback
                (session_id, planned_item_id, exercise_id, pain_note, effort)
            values (%s, %s, %s, %s, %s)
            on conflict (session_id, exercise_id) do update
               set pain_note = excluded.pain_note,
                   effort = excluded.effort,
                   planned_item_id = coalesce(excluded.planned_item_id,
                                              training.performed_item_feedback.planned_item_id),
                   updated_at = now()
            """,
            (performed_session_id, planned_item_id, exercise_id, pain_note, effort),
        )


def session_feedback(performed_session_id: int) -> list[dict]:
    """To samo, ale do podsumowania — z nazwą ćwiczenia i w kolejności planu."""
    with cursor() as cur:
        cur.execute(
            """
            select ex.name as exercise, f.pain_note, f.effort
              from training.performed_item_feedback f
              join training.exercise ex on ex.id = f.exercise_id
              left join training.planned_item pi on pi.id = f.planned_item_id
             where f.session_id = %s
             order by pi.ordinal nulls last, ex.name
            """,
            (performed_session_id,),
        )
        return cur.fetchall()


def bar_weight(exercise_id: int) -> float:
    """Waga samego gryfu dla ćwiczenia — potrzebna przy podmianie.

    Formularz przysyła gryf ćwiczenia z planu. Po podmianie sprzęt bywa inny
    (sztanga 20 kg zamiast gryfu łamanego 7 kg), więc rozbicie ciężaru łącznego
    musi iść po katalogu zamiennika, nie po tym, co było w planie.
    """
    with cursor() as cur:
        cur.execute(
            "select default_bar_weight_kg from training.exercise where id = %s",
            (exercise_id,),
        )
        row = cur.fetchone()
        return float(row["default_bar_weight_kg"]) if row else 0.0


# ----------------------------------------------------------------- historia


def closed_sessions(limit: int = 50) -> list[dict]:
    """Zamknięte treningi, od najnowszego. To karmi zakładkę „Historia"."""
    with cursor() as cur:
        cur.execute(
            """
            select ps.id, ps.performed_on, ps.location, ps.feeling, ps.notes,
                   pl.label,
                   (select count(*) from training.performed_set_current c
                     where c.session_id = ps.id) as serie,
                   (select count(distinct c.exercise_id) from training.performed_set_current c
                     where c.session_id = ps.id) as cwiczenia,
                   (select coalesce(sum(c.weight_total_kg * c.repetitions), 0)
                      from training.performed_set_current c
                     where c.session_id = ps.id) as tonaz
              from training.performed_session ps
              left join training.planned_session pl on pl.id = ps.planned_session_id
             where ps.closed_at is not null
             order by ps.performed_on desc, ps.id desc
             limit %s
            """,
            (limit,),
        )
        return cur.fetchall()


# ----------------------------------------------------------------- postęp


def closed_session_count() -> int:
    """Ile treningów zamknięto w ogóle — prawy koniec osi wykresu.

    Oś liczy treningi, nie tygodnie. Tydzień przestał być
    jednostką, kiedy w jednym tygodniu wypadły dwa treningi: grupowanie po
    tygodniu zlewało je w jeden punkt, a numer z etykiety planu („Tydzień 7")
    nic nie znaczy przy planie pisanym jako „Trening 1…8".
    """
    with cursor() as cur:
        cur.execute(
            "select count(*) as n from training.performed_session where closed_at is not null"
        )
        return cur.fetchone()["n"]


def exercises_with_history() -> list[dict]:
    """Ćwiczenia, które mają cokolwiek w historii — reszty nie ma po co pokazywać."""
    with cursor() as cur:
        cur.execute(
            """
            select ex.id, ex.slug, ex.name, ex.measure,
                   count(c.id) as serie,
                   count(distinct s.performed_on) as dni,
                   max(s.performed_on) as ostatnio,
                   max(c.weight_total_kg) as max_ciezar
              from training.exercise ex
              join training.performed_set_current c on c.exercise_id = ex.id
              join training.performed_session s on s.id = c.session_id
             where s.closed_at is not null
             group by ex.id, ex.slug, ex.name, ex.measure
             order by max(s.performed_on) desc, count(c.id) desc
            """
        )
        return cur.fetchall()


def exercise_history(exercise_id: int) -> list[dict]:
    """Wszystkie serie jednego ćwiczenia, pogrupowane po treningu.

    Jeden trening daje jeden punkt na wykresie, a `nr` to jego numer w całej
    historii zamkniętych treningów — także tych, w których tego ćwiczenia nie było,
    więc przerwa w ćwiczeniu widać jako odstęp na osi. Bierzemy serię najlepszą,
    nie średnią: średnia z serii do upadku mięśniowego mówi głównie o tym, ile
    serii zrobiono, a nie o tym, na co było stać.
    """
    with cursor() as cur:
        cur.execute(
            """
            with kolejne as (
                select id, performed_on,
                       row_number() over (order by performed_on, id) as nr
                  from training.performed_session
                 where closed_at is not null
            )
            select s.nr, s.performed_on,
                   count(c.id) as serie,
                   max(c.weight_total_kg) as ciezar_max,
                   max(c.repetitions) as powt_max,
                   max(c.duration_seconds) as czas_max,
                   sum(c.weight_total_kg * c.repetitions) as tonaz,
                   sum(c.repetitions) as powt_razem,
                   sum(c.duration_seconds) as czas_razem,
                   -- ciężar i powtórzenia z serii o największym iloczynie: to ona
                   -- jest kandydatem na rekord dnia, a nie najcięższa przy jednym powtórzeniu
                   (array_agg(c.weight_total_kg order by c.weight_total_kg * coalesce(c.repetitions, 0) desc))[1] as rekord_ciezar,
                   (array_agg(c.repetitions order by c.weight_total_kg * coalesce(c.repetitions, 0) desc))[1] as rekord_powt
              from training.performed_set_current c
              join kolejne s on s.id = c.session_id
             where c.exercise_id = %s
             group by s.nr, s.performed_on
             order by s.nr
            """,
            (exercise_id,),
        )
        return cur.fetchall()


def exercise(exercise_id: int) -> dict | None:
    with cursor() as cur:
        cur.execute(
            "select id, slug, name, measure, default_bar_weight_kg, equipment, notes "
            "  from training.exercise where id = %s",
            (exercise_id,),
        )
        return cur.fetchone()
