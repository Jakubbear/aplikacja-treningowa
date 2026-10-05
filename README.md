# Aplikacja treningowa

Prywatna aplikacja do prowadzenia **własnego** treningu siłowego. Plan układasz
razem ze swoim asystentem AI, serie zapisujesz z telefonu w trakcie ćwiczenia,
a aplikacja pokazuje, co poszło inaczej niż w planie i jak idzie postęp.
Asystent czyta te odchylenia i po każdym treningu poprawia resztę planu.

**Nie ma tu gotowego planu.** Każdy ma inny cel, sprzęt, czas i ciało — plan
powstaje w rozmowie, według instrukcji niżej.

```
┌──────────────┐        ┌──────────────────┐        ┌──────────────┐
│ plan w JSON  │  ───►  │   PostgreSQL     │  ◄───  │   telefon    │
│ (układa go   │        │  (cała prawda)   │        │ (zapisujesz  │
│  asystent)   │        │                  │        │  serie)      │
└──────────────┘        └────────┬─────────┘        └──────────────┘
                                 │
                                 ▼
                    widok `training.deviation`
            (co poszło inaczej — asystent poprawia plan)
```

## Jak zacząć

Otwórz ten folder w swoim asystencie AI (Claude Code, Codex, Gemini CLI,
Cursor…) i napisz:

> Przeczytaj README.md i przeprowadź mnie przez całość od początku.

Asystent zrobi wywiad, postawi aplikację, ułoży plan i powie, co kliknąć.
Instrukcja dla niego jest w sekcji **„Instrukcja dla asystenta AI"** niżej.

---

## Co to umie

**Trzy zakładki na dole ekranu, obsługiwane kciukiem jednej ręki:**

- **Trening** — tydzień, strzałkami w przód i w tył, z mini-kalendarzem.
  Plan jest kolejką: jeden trening na tydzień, a drugi w tym samym tygodniu
  dodajesz przyciskiem „+". Ramka **„Idzie w górę"** podpowiada, gdzie dołożyć
  ciężar, bo ostatnio wszystkie serie doszły do górnego progu powtórzeń.
  W trakcie treningu wszystkie serie widać od razu, z podstawionym ciężarem
  i liczbą powtórzeń. Potwierdzasz zielonym haczykiem albo poprawiasz liczby.
  **„▶ Robię teraz"** przenosi ćwiczenie na górę, gdy robisz je w innej
  kolejności niż w planie.
- **Historia** — zamknięte treningi, od najnowszego, z podsumowaniem każdego.
- **Postęp** — wykres na ćwiczenie: szacowany ciężar maksymalny (1RM), ciężar,
  tonaż albo powtórzenia.

**Przy każdym ćwiczeniu:** podmiana na inne (gdy sprzęt zajęty), pytanie „czy coś
boli?" z opisem, skala wysiłku 1–5 i faktyczna przerwa przed serią.

**Zapis idzie do bazy po każdej serii**, nie na końcu treningu. Utrata zasięgu
w połowie kosztuje najwyżej jedną serię, a ponowiony zapis jej nie zdubluje.

## Czego to NIE umie

- **Nie ma logowania ani kont.** Kto dojdzie do adresu, ten wchodzi. To aplikacja
  dla jednej osoby w sieci domowej. Wystawienie na internet wymaga bramki przed
  nią — patrz [docs/wdrozenie.md](docs/wdrozenie.md).
- **Nie ma stopera.** Przerwę wpisujesz z pamięci.
- **Nie ma aplikacji mobilnej.** To strona; dodana do ekranu głównego telefonu
  wygląda jak aplikacja.
- **Nie ma wagi ciała, pomiarów, jedzenia ani snu.** Sam trening — pomiary
  prowadzi asystent osobno (patrz faza 6).
- **Nie ma testów automatycznych.**

---

## Instrukcja dla asystenta AI

Czytasz to, bo użytkownik poprosił, żebyś go przeprowadził przez całość.
Pracuj **fazami, po kolei**. Nie przeskakuj do planu przed wywiadem — plan
ułożony bez wywiadu jest zgadywaniem.

### Zasady rozmowy

- Mów po polsku, prosto. Użytkownik nie musi znać terminologii — gdy jej
  używasz (1RM, upadek mięśniowy, superseria), wyjaśnij jednym zdaniem.
- **Pytaj blokami po 2–4 pytania**, nie listą trzydziestu naraz. Czekaj na
  odpowiedź.
- Niczego nie zakładaj za użytkownika: ani celu, ani sprzętu, ani częstotliwości.
  Jak czegoś nie wie — zaproponuj rozsądny domyślny wybór i powiedz dlaczego.
- **Rób sam, co się da.** Komendy uruchamiasz Ty. Ręce użytkownika są potrzebne
  tylko tam, gdzie fizycznie musi coś zrobić (zainstalować Dockera, otworzyć
  stronę na telefonie, zmierzyć ramię) — wtedy instrukcja krok po kroku,
  jak dla kogoś, kto nie zna terminala.
- Dane użytkownika (profil, plany, pomiary) trzymaj **wyłącznie w `plany/moje/`**
  — ten katalog jest poza Gitem. Nigdy ich nie commituj.

### Faza 1 — wywiad (onboarding)

Cel: poznać człowieka na tyle, żeby plan pasował do **niego**. Przejdź przez
te bloki, w tej kolejności:

1. **Cel.** Po co trenuje? Siła, sylwetka (jakie partie — konkretnie: „większe
   ramiona", „plecy"), zdrowie, sport? Co ma być widać za 2–3 miesiące?
   Jak będziemy mierzyć, że idzie (obwody, zdjęcia, ciężary, waga)?
2. **Doświadczenie.** Jak długo trenuje, czy ma przerwę, jakie ciężary robi
   teraz w podstawowych ruchach (jeśli wie — ciężar × powtórzenia). Czy zna
   technikę ćwiczeń, które chcesz zaproponować?
3. **Czas i rytm.** Ile treningów w tygodniu realnie (nie ambitnie)? Ile minut
   na trening? Czy tydzień jest stały, czy zmienny (zmiany, wyjazdy)?
   Aplikacja zakłada **jeden trening na tydzień w kolejce**, a dodatkowy
   dodaje się „+" — przy 2–3 treningach tygodniowo też działa, tylko „+"
   używa się częściej.
4. **Miejsce i sprzęt.** Dom, siłownia, oba? **Dokładna lista sprzętu**: gryfy
   (i ile ważą — sztanga prosta, łamany), jakie talerze i ile sztuk, ławka,
   drążek, poręcze, hantle, gumy. Od tego zależy, jakie ćwiczenia w ogóle
   wchodzą i jakie skoki ciężaru są możliwe.
5. **Ciało.** Kontuzje, bóle (kręgosłup, barki, kolana, nadgarstki), czego
   unikać. Ruchy, które lubi i których nie znosi. Przy poważnym problemie
   zdrowotnym — powiedz wprost, że plan nie zastępuje lekarza ani fizjoterapeuty.
6. **Styl treningu.** Zaproponuj i ustal razem:
   - ile ćwiczeń na partię i ile serii (np. 2 ćwiczenia na partię docelową,
     po 1 na resztę ciała);
   - zakres powtórzeń (np. 8–10, 10–12);
   - czy serie do upadku mięśniowego, czy z zapasem 1–2 powtórzeń
     (początkujący i po przerwie — z zapasem przez pierwsze tygodnie);
   - przerwa między seriami (domyślnie 120 s);
   - **reguła progresji**, np. „wszystkie serie doszły do górnej granicy
     zakresu → +2,5 kg";
   - jak długo ćwiczenia zostają stałe (np. blok 6–8 treningów — zmiana
     ćwiczeń co trening uniemożliwia ocenę postępu).

Na koniec **pokaż podsumowanie wywiadu i poproś o potwierdzenie.** Zapisz je
do `plany/moje/profil.md` — to Twoja pamięć na kolejne rozmowy.

### Faza 2 — postawienie aplikacji

Potrzebny jest **Docker** (Docker Desktop na Windows/macOS). Jeśli go nie ma,
poprowadź instalację krok po kroku. Potem, w katalogu repo:

```sh
# 1. Hasło do bazy — losowe, do pliku (plik jest poza Gitem)
mkdir -p sekrety
head -c 24 /dev/urandom | base64 > sekrety/haslo-bazy
chmod 600 sekrety/haslo-bazy

# 2. Baza i aplikacja
docker compose up -d --build

# 3. Schemat i katalog ćwiczeń (kolejność jest wiążąca — patrz db/zaloz.sh)
sh db/zaloz.sh

# 4. Narzędzia do wgrywania planu
pip install 'psycopg[binary]'
```

Aplikacja stoi pod **http://localhost:8002** i pokazuje „Brak planu" — dobrze.

> **Windows:** `sh` i `/dev/urandom` działają w Git Bashu albo WSL. Zamiast
> `head … | base64` można wpisać do `sekrety/haslo-bazy` dowolne długie hasło.
> Port 5432 zajęty (jest już inny PostgreSQL)? Zmień lewą liczbę w
> `docker-compose.yml` przy `127.0.0.1:5432:5432` i w `DATABASE_URL` niżej.

**Telefon:** aplikacja jest widoczna w sieci domowej pod
`http://<adres-komputera>:8002`. Znajdź adres komputera (`ipconfig` na
Windows, `ip a` na Linuksie), podaj użytkownikowi pełny link i poproś, żeby
otworzył go na telefonie i dodał do ekranu głównego. Komputer musi być
włączony w czasie treningu — jeśli to niewygodne, opcja z małym serwerem
domowym jest w [docs/wdrozenie.md](docs/wdrozenie.md).

**Ustawienia z wywiadu** — stałe na górze `app/main.py`:

| Stała | Domyślnie | Co znaczy |
|---|---|---|
| `LIMIT_SERII` | 3 | sufit serii na ćwiczenie; plan nie może mieć więcej |
| `PROG_POWTORZEN` | 10 | ile powtórzeń w każdej serii uruchamia „Idzie w górę" |
| `PODBICIE_KG` | 2.5 | o ile „Idzie w górę" proponuje podnieść ciężar |

Ustaw je zgodnie z fazą 1 (np. zakres 8–10 → `PROG_POWTORZEN = 10`), potem
`docker compose up -d --build`, żeby zmiana weszła.

### Faza 3 — katalog ćwiczeń

W bazie jest 16 ćwiczeń pod domowy sprzęt (ławka, sztanga prosta 20 kg, gryf
łamany 7 kg, drążek, poręcze). Lista:

```sh
docker compose exec -T postgres psql -U trening -d trening -c \
  "select slug, name, equipment, default_bar_weight_kg from training.exercise order by body_part, name"
```

Porównaj z tym, co wyszło z wywiadu. **Brakujące ćwiczenia dopisz nowym
plikiem** `db/seeds/0007_<opis>.sql` według wzoru z
`db/seeds/0006_barki-przedramiona.sql` (`slug`, nazwa, sprzęt, partia,
**waga gryfu** w `default_bar_weight_kg` — 0 dla masy ciała i hantli liczonych
w całości, `measure` = `reps` albo `time`, plus aliasy). Wgraj go:

```sh
docker compose exec -T postgres psql -U trening -d trening -v ON_ERROR_STOP=1 < db/seeds/0007_<opis>.sql
```

Waga gryfu jest ważna: aplikacja przyjmuje ciężar **łączny** (gryf + talerze)
i sama go rozbija.

### Faza 4 — plan

Ułóż plan jako JSON w `plany/moje/plan-1.json`. Format i wszystkie pola:
[plany/README.md](plany/README.md). Zasady:

- **Sesje to „Trening 1", „Trening 2"…**, nie dni tygodnia. `planned_on`
  rozłóż według rytmu z wywiadu, od bieżącego tygodnia — daty są orientacyjne,
  aplikacja traktuje plan jak kolejkę.
- **Ćwiczenia stałe przez cały blok**, ten sam układ w każdym treningu bloku
  (albo naprzemiennie A/B przy 2+ treningach tygodniowo).
- **Kolejność pod sprzęt:** ustaw ćwiczenia tak, żeby między nimi tylko
  zdejmować talerze, a nie przekładać w tę i z powrotem. Ćwiczenia na partię
  docelową — wcześnie, na świeżo.
- **Ciężary startowe:** jeśli użytkownik podał wynik (ciężar × powtórzenia),
  policz 1RM wzorem Epleya (`1RM = ciężar × (1 + powt/30)`) i z niego ciężar
  na górę zakresu, lekko w dół. Jeśli nie wie — zachowawczo, a **pierwszy
  trening traktuj jako kalibrację**. Zaokrąglaj do kroku, jaki dają jego talerze.
- Każda pozycja ma `note` — krótko **dlaczego** taki ciężar/zakres. Widać to
  w aplikacji podczas treningu.
- Serie łączone (`superset`) tylko, gdy użytkownik ich chce.

Pokaż plan w czytelnej tabeli, poproś o akceptację, potem:

```sh
export DATABASE_URL="postgresql://trening:$(cat sekrety/haslo-bazy)@localhost:5432/trening"
python narzedzia/write_training_plan.py plany/moje/plan-1.json --dry-run
python narzedzia/write_training_plan.py plany/moje/plan-1.json
```

`--dry-run` przepuszcza wsad przez bazę i wycofuje — nieznana nazwa ćwiczenia
wychodzi wtedy, a nie w połowie zapisu. Na koniec poproś użytkownika, żeby
odświeżył stronę na telefonie i potwierdził, że widzi Trening 1.

### Faza 5 — po każdym treningu

Gdy użytkownik napisze, że trenował:

```sh
docker compose exec -T postgres psql -U trening -d trening -c \
  "select * from training.deviation where performed_on is not null order by performed_on desc, exercise"
docker compose exec -T postgres psql -U trening -d trening -c \
  "select s.performed_on, e.name, f.effort, f.pain_note from training.performed_item_feedback f
     join training.performed_session s on s.id = f.session_id
     join training.exercise e on e.id = f.exercise_id order by s.performed_on desc"
```

- `exceeded_plan` = zrobił więcej powtórzeń niż górna granica → ciężar w górę.
- `reps_max_done` poniżej `reps_min` → ciężar w dół albo zostaje.
- `substituted` = podmienił ćwiczenie → zapytaj dlaczego (sprzęt? ból?).
- **Ból (`pain_note`) ma pierwszeństwo przed progresją.** Zapytaj o szczegóły,
  zanim cokolwiek podniesiesz.

Skoryguj ciężary **na kolejne treningi** nową wersją planu: skopiuj plik
(np. `plan-1-v2.json`), popraw, ustaw `"supersedes": <id starego planu>`
i wgraj. Starego planu nie edytuje się w bazie — historia zostaje.

**Nowa wersja zawiera tylko treningi jeszcze niezrobione** (np. od Treningu 2
w górę), a `planned_on` pierwszego z nich to tydzień, w którym ma wypaść.
Trening liczy się jako zrobiony tylko w tej wersji planu, w której go zrobiono
— jeśli nowa wersja znów zawiera „Trening 1", aplikacja pokaże go jako
niezrobiony. Id starego planu sprawdź zapytaniem (nie zgaduj — `--dry-run`
też zużywa numery):

```sh
docker compose exec -T postgres psql -U trening -d trening -c \
  "select id, label, starts_on, supersedes from training.training_plan order by id"
```

Powiedz użytkownikowi krótko, co zmieniłeś i dlaczego.

### Faza 6 — co kilka tygodni

Co 2 tygodnie (albo jak ustaliliście) poproś o miarę z fazy 1 — obwody,
zdjęcia, wagę — i zapisz w `plany/moje/pomiary.md` z datą. Zdjęcia też tylko
w `plany/moje/`. Ciężary rosną, a miara stoi? Najpierw jedzenie i sen,
dopiero potem dokładanie serii. Pod koniec bloku zaproponuj następny.

### Zasady techniczne — nie łam ich

1. **Wykonanie jest niezmienne.** Triggery w bazie odrzucają `UPDATE`/`DELETE`
   serii zamkniętego treningu; korekta to nowy wiersz z `supersedes`.
2. **Serie czytaj z widoku `training.performed_set_current`**, nie z tabeli
   `performed_set` — inaczej po korekcie widać obie wersje.
3. **Ciężar łączny** (gryf + talerze) w planie i w formularzu. `NULL` to „nie
   zapisano", nie zero.
4. **Zmiana schematu = nowa migracja** `db/migrations/00NN_opis.sql` z kolejnym
   numerem, w `begin; … commit;`. Starych migracji nie edytuj.
5. **Wszystko musi działać bez JavaScriptu** — zapis to zwykły formularz
   z przekierowaniem; `app.js` tylko ulepsza.
6. Zmiany w kodzie wchodzą po `docker compose up -d --build`.
7. **Testowy trening zamknięty przyciskiem „Zamykam trening" jest prawdziwym
   zapisem** i zajmuje tydzień. Sprzątanie: `python narzedzia/reset_testow.py`
   (pokazuje), potem z `--wykonaj` (kasuje sesje od dziś).

Przed przebudową czegokolwiek przeczytaj [docs/decyzje.md](docs/decyzje.md)
— tam jest, dlaczego rzeczy są zrobione tak, a nie inaczej.

---

## Co gdzie leży

| Ścieżka | Co |
|---|---|
| `app/main.py` | trasy HTTP, przeliczenia formularzy, stałe ustawień na górze |
| `app/db.py` | jedyne miejsce z SQL-em |
| `app/postep.py` | metryki i wykres SVG |
| `app/templates/`, `app/static/` | widoki (Jinja2), CSS, trochę JS |
| `db/migrations/` | schemat `training` — jedyne źródło prawdy o bazie |
| `db/seeds/` | katalog ćwiczeń z aliasami |
| `db/zaloz.sh` | zakłada schemat w świeżej bazie |
| `plany/README.md` | format planu |
| `plany/moje/` | profil, plany, pomiary użytkownika — **poza Gitem** |
| `narzedzia/` | wsad planu do bazy, sprzątanie po testach |
| `docs/architektura.md` | jak to działa, część po części |
| `docs/decyzje.md` | dlaczego tak, a nie inaczej |
| `docs/wdrozenie.md` | serwer domowy, dostęp z zewnątrz, kopie bazy |
| `db/README.md` | schemat bazy i zasada niezmienności |

## Licencja

Nie ustalona. Kod dostałeś do własnego użytku — jeśli chcesz z nim zrobić
coś więcej, dogadaj się z osobą, od której go masz.
