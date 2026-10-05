# Architektura — jak to jest zbudowane

## Obieg

```
   Ty przy komputerze              Ty przy treningu            Ty po tygodniu
          │                              │                            │
   piszesz plan w JSON          widzisz bieżący tydzień      czytasz `deviation`
          │                     zapisujesz serie na bieżąco   i poprawiasz plan
          ▼                              ▼                            ▲
  write_training_plan.py  ───►      PostgreSQL       ──────────────────┘
```

Plan i wykonanie to **dwie osobne rzeczy w bazie**, nie jedna tabela z flagą.
`planned_item` mówi, co miało być zrobione; `performed_set` — co faktycznie poszło.
Widok `training.deviation` odejmuje jedno od drugiego. Bez tego rozdzielenia nie
da się odpowiedzieć na pytanie „czy plan był za łatwy", bo plan znikałby pod
wykonaniem.

## Stos

| Warstwa | Czym |
|---|---|
| Serwer | FastAPI (Python 3.12) + Uvicorn |
| Widoki | Jinja2, HTML renderowany po stronie serwera |
| Baza | PostgreSQL 17 |
| Wykresy | SVG składany w `postep.py`, bez żadnej biblioteki |
| JS | ok. 220 linii, wyłącznie jako ulepszenie |
| Budowanie frontu | **żadne** — nie ma npm, nie ma bundlera |

**Dlaczego bez Reacta:** to chodziło na Raspberry Pi 4 z 1,8 GB RAM. Kontener
aplikacji zajmuje kilkadziesiąt megabajtów. Serwerowy HTML nie potrzebuje builda,
więc wdrożenie to skopiowanie plików i restart kontenera.

## Trzy pliki Pythona

### `app/main.py` — trasy i przeliczenia formularza

Wszystkie ścieżki HTTP i cała robota na tym, co przysłał formularz: przecinek
dziesiętny na kropkę, ciężar łączny na rozbity, wysiłek poza skalą na „brak oceny".

Dwie stałe na górze pliku, obie świadome:

- `UKLAD = None` — ustaw `"test"`, a w pasku na każdym ekranie pojawi się
  pomarańczowa plakietka. Znacznik na czas przebudowy karty ćwiczenia: układ
  do sprawdzenia w realnym treningu, a nie skończony.
- `LIMIT_SERII = 3` — sufit serii na ćwiczenie. Pilnowany tu, a szablon bierze
  go stąd: telefon z otwartą starą kartą wysłałby serię ponad limit.
- `PROG_POWTORZEN = 10`, `PODBICIE_KG = 2.5` — reguła ramki „Idzie w górę"
  (niżej).

## Widok tygodnia i kolejka treningów

Jednostką ekranu **Trening** jest tydzień kalendarzowy (poniedziałek–niedziela).
Strzałki przechodzą między tygodniami, mini-kalendarz obok pozwala skoczyć
o kilka tygodni jednym dotknięciem.

Plan jest **kolejką**, nie kalendarzem. `rozloz_kolejke()` w `main.py` kładzie
niezrobione treningi po jednym na tydzień, od bieżącego. Data `planned_on`
z pliku planu jest orientacyjna — trening z zeszłego tygodnia, którego nie
zrobiłeś, nie przepada, tylko przesuwa się na ten. Jedyny wyjątek: plan,
z którego nic jeszcze nie zrobiono, nie wejdzie przed tydzień swojej
pierwszej daty.

Drugi trening w tym samym tygodniu (urlop, wolne) dodaje się przyciskiem
**„+ Dodaj trening w tym tygodniu"** — pojawia się, gdy trening bieżącego
tygodnia jest już zamknięty. Zamknięcie treningu **nie przeskakuje** samo na
następny. Następny w kolejce da się też zacząć wcześniej, wchodząc w jego
(przyszły) tydzień.

**„Idzie w górę"** — ramka przy kalendarzu. Dla każdego ćwiczenia z treningu,
który da się teraz zacząć, patrzy na ostatni raz, kiedy było robione: jeśli
wszystkie serie (co najmniej dwie) szły na jednym ciężarze i każda miała
≥ `PROG_POWTORZEN`, proponuje ciężar + `PODBICIE_KG`. Pomija ćwiczenia na czas
i pozycje z notą zawierającą „bez progresji". To tylko podpowiedź na ekranie —
plan w bazie się nie zmienia.

## Kolejność w trakcie treningu — „▶ Robię teraz"

Przycisk na karcie ćwiczenia przenosi ją na górę ekranu. Zapis idzie do tabeli
`training.performed_item_order` (migracja `0008`) — to kolejność **ekranu**.
Kolejność **wykonania** to co innego: liczy się ją z `min(recorded_at)` serii
każdej pozycji, bo czas zapisu nie kłamie. Podsumowanie i widok odchyleń są
ułożone w kolejności wykonania, z dopiskiem „w planie N." tam, gdzie się różni.

## Zapis odporny na zacięcie sieci

Nowa seria ma ukryty identyfikator `zapis_id`. Telefon, który nie dostał
odpowiedzi, ponawia zapis — a serwer, który już taki identyfikator widział,
nie dopisuje serii drugi raz. Pamięć tych identyfikatorów jest w procesie
(`_ZAPISANE_SERIE`), co wystarcza przy jednym workerze Uvicorna.

### `app/db.py` — wszystkie zapytania

Reszta aplikacji nie dotyka SQL-a. Zapytania odczytowe idą do widoku
`training.performed_set_current`, **nigdy do tabeli wprost** — inaczej po
korekcie serii widać byłoby obie wersje naraz.

Połączenie składane jest z części, z hasłem czytanym z pliku
(`DATABASE_PASSWORD_FILE`). `DATABASE_URL` zostaje jako droga na skróty
do uruchomienia z laptopa. Pula sprawdza połączenie przed wydaniem, więc
restart kontenera bazy nie kończy się błędem 500 przy pierwszym wejściu.

### `app/postep.py` — wykresy

Liczy metryki z historii ćwiczenia i rysuje SVG. Metryki: szacowany ciężar
maksymalny (1RM), ciężar, tonaż, powtórzenia, czas. Które są dostępne, zależy
od tego, czy ćwiczenie ma obciążenie i czy mierzy się je w powtórzeniach
czy w sekundach.

**Oś pozioma liczy treningi, nie tygodnie.** Dwa treningi w jednym tygodniu to
dwa punkty. Trening, w którym ćwiczenia nie było, nie robi dziury w linii —
pominięcie nie jest spadkiem. Gdy ćwiczenie nie ma jeszcze żadnej serii, strona
pisze „brak pomiarów w treningach 1–N".

**O wiarygodności 1RM warto wiedzieć:** wzór jest ekstrapolacją. Jeśli wszystkie
Twoje serie są na 10–15 powtórzeń, oszacowanie ciężaru maksymalnego leży poza
zakresem, w którym wzór działa. Punkty policzone z takich serii aplikacja
oznacza jako niepewne. Chcąc mieć z tego coś sensownego, zrób raz na jakiś czas
serię na 5–8 powtórzeń.

## Karta ćwiczenia — jak działa bez JS-u

**Ołówek w nagłówku przełącza tryb poprawiania.** Zapisana seria jest domyślnie
faktem do przeczytania: bez ramek, bez kosza. Dopiero ołówek odsłania edycję
i kosze. Zrobione ukrytym `checkbox`-em stojącym przed treścią karty; reszta
sięga do niego przez `:checked ~ …`. `pointer-events: none` zastępuje `readonly`,
bo tego CSS nie przełącza.

**Formularze tworzące serię zostają przy jawnym potwierdzeniu.** `app.js` chowa
przyciski tylko tam, gdzie zapis nie zmienia układu strony — przy edycji
istniejącej serii i przy odczuciach. Ciche dopisanie wiersza do bazy przy
przypadkowym dotknięciu pola byłoby gorsze niż jedno kliknięcie.

**Nic, co się rozwija, nie jest nakładką.** Wszystko rozwijane jest blokiem
w normalnym przepływie. Powód jest w [decyzje.md](decyzje.md) — to nie jest
kwestia gustu, tylko błędu renderowania na iPhonie.

## Bezpieczeństwo — stan faktyczny

**Aplikacja nie ma żadnej autoryzacji.** Kto dojdzie do adresu, ten ma pełen
dostęp: czyta historię, dopisuje serie, zamyka treningi. Została zbudowana
do sieci domowej i tak ma być używana, chyba że postawisz coś przed nią.

Co jest zrobione dobrze:

- Hasło bazy nie jest zmienną środowiskową, więc nie widać go przez
  `docker inspect` ani ze środowiska sąsiedniego kontenera.
- Konto bazodanowe ma dostęp wyłącznie do własnej bazy.
- Zapytania są parametryzowane — nie ma sklejania SQL-a ze stringów.
- Jest przełącznik `HEALTH_PREVIEW_READONLY=1`, który blokuje wszystkie metody
  poza `GET` i `HEAD`. Przydaje się, gdy chcesz komuś pokazać działającą kopię.

Wystawienie na internet: [wdrozenie.md](wdrozenie.md).

## Endpoint zdrowia

`GET /zdrowie` zwraca `{"status": "ok"}` i **sprawdza przy tym połączenie
z bazą**, nie tylko to, czy proces żyje. Gotowe pod podpięcie do Uptime Kumy
albo czegokolwiek innego, co pinguje usługi.
