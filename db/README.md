# Baza — schemat `training`

Schemat, seed i triggery były uruchomione na PostgreSQL 17 w kontenerze
na Raspberry Pi 4, a potem **drugi raz na czystej bazie**, żeby sprawdzić,
czy migracja jest odtwarzalna. Obie próby przeszły bez błędu.

Poza tymi warunkami schemat pozostaje niesprawdzony.

## Co tu jest

| Plik | Rola |
|---|---|
| `migrations/0001_training.sql` | schemat: plan, wykonanie, niezmienność, widoki |
| `migrations/0002_ciezar-gryfu.sql` | poprawka wagi gryfu **w katalogu** |
| `migrations/0003_odczucia-cwiczenia.sql` | ból i wysiłek przy ćwiczeniu |
| `migrations/0004_skala-wysilku-1-5.sql` | skala z 1–10 na 1–5 |
| `migrations/0005_miejsce-silownia.sql` | trzecie miejsce treningu |
| `migrations/0006_faktyczna-przerwa.sql` | zapis faktycznej przerwy przed serią |
| `migrations/0007_widok-po-dodaniu-przerwy.sql` | przebudowa widoku po 0006 |
| `migrations/0008_kolejnosc-w-sesji.sql` | kolejność kart w trwającym treningu („▶ Robię teraz") |
| `seeds/0001…0006` | katalog 16 ćwiczeń z aliasami |
| `zaloz.sh` | wgrywa to wszystko w prawidłowej kolejności |

Migracje są **jedynym źródłem prawdy** o schemacie. Świadomie nie ma obok nich
pliku `schema.sql` — dwie definicje tego samego zawsze się w końcu rozjadą.

## Kolejność wgrywania nie jest alfabetyczna

```
1. migrations/0001_training.sql     schemat
2. seeds/*.sql                      katalog ćwiczeń
3. migrations/0002 i dalsze         poprawki
```

Migracja `0002` **aktualizuje wiersze z seeda** (ustawia wagę gryfu dla ławki
i goblet squata), więc musi wejść po nim. Robi to za Ciebie `zaloz.sh`.

Seed **nie jest idempotentny**: drugie uruchomienie wywali się na `slug unique`.
Tak ma być — to sygnał, że baza nie była pusta.

## Tabele

```
training_plan ──┬── planned_session ──── planned_item
                │                              │
                │                              │ (co miało być)
                │                              │
performed_session ──┬── performed_set ─────────┘  (co faktycznie poszło)
                    └── performed_item_feedback     (ból, wysiłek)

exercise ──── exercise_alias
```

**Plan i wykonanie to dwie osobne gałęzie.** Bez tego rozdzielenia plan znikałby
pod wykonaniem i nie dałoby się odpowiedzieć na pytanie „czy plan był za łatwy".

## Niezmienność

Wymuszona **w bazie**, triggerem `training.guard_closed`, a nie w aplikacji:

- `performed_session.closed_at IS NULL` — trening trwa, poprawka serii
  to zwykły `UPDATE`;
- po zamknięciu `UPDATE` i `DELETE` są **zablokowane**, a korekta musi być
  nowym wierszem z `supersedes` wskazującym poprzednika.

Ten sam mechanizm chroni odczucia (`guard_closed_feedback`, migracja 0003).

Widok `performed_set_current` pokazuje tylko serie, których nic nie zastąpiło.
**Wszystko, co czyta dane, czyta ten widok, nigdy tabelę wprost** — inaczej
po korekcie widać byłoby obie wersje serii naraz.

Sprawdzone w obie strony: `UPDATE` na zamkniętej sesji odrzucony przez trigger,
korekta przez `supersedes` przyjęta, widok pokazał nową wersję i ukrył starą.

## Widok `deviation`

To jest miejsce, z którego czytasz na koniec tygodnia, co poszło inaczej niż
w planie: mniej serii, więcej powtórzeń niż `reps_max`, inny ciężar, podmienione
ćwiczenie. Stąd bierze się poprawka reszty bloku.

```sh
docker compose exec -T postgres psql -U trening -d trening -c \
  "select * from training.deviation order by performed_on desc limit 20"
```

## Kolumny wyliczane

`performed_set.weight_total_kg` jest kolumną wyliczaną z `bar_weight_kg`
i `added_weight_kg`. Nie da się jej ustawić ręcznie i nie da się jej rozjechać
ze składnikami. Dlaczego ciężar jest w ogóle rozbity — patrz
[docs/decyzje.md](../docs/decyzje.md).

## Dopisanie własnego ćwiczenia

Wzór masz w każdym pliku seeda. Najkrócej:

```sql
begin;

insert into training.exercise
    (slug, name, equipment, body_part, default_bar_weight_kg, measure, notes)
values
    ('martwy-ciag', 'Martwy ciąg', 'sztanga', 'plecy', 20, 'reps', null)
  on conflict (slug) do nothing;

insert into training.exercise_alias (alias, exercise_id)
select a.alias, e.id
  from (values
        ('martwy ciag',  'martwy-ciag'),
        ('deadlift',     'martwy-ciag')
       ) as a(alias, slug)
  join training.exercise e on e.slug = a.slug
  on conflict (alias) do nothing;

commit;
```

`measure` to `reps` albo `time`. `default_bar_weight_kg` to waga samego gryfu —
zobacz, dlaczego to ma znaczenie, w `docs/decyzje.md`.

**Aliasy trzymamy znormalizowane**: małe litery, bez polskich znaków, myślniki
zamienione na spacje, pojedyncze odstępy.
