# Dlaczego tak, a nie inaczej

Każda z tych decyzji kosztowała czas albo błąd. Przeczytaj to, zanim zaczniesz
coś przebudowywać — inaczej odkryjesz je drugi raz, tak samo drogo.

## Dane

### Ciężar rozbity na gryf i talerze

W bazie ciężar serii to dwie kolumny: `bar_weight_kg` i `added_weight_kg`.
`weight_total_kg` jest kolumną **wyliczaną**, więc nie da się jej rozjechać
ze składnikami.

Powód jest empiryczny. W trakcie prowadzenia zapisów zmieniła się konwencja:
waga gryfu zaczęła wchodzić do zapisu obciążenia. Przy jednym polu `weight`
przejście 10 → 17 kg wygląda w danych jak skok siły, a było zmianą sposobu
liczenia. Rozbicie sprawia, że taka zmiana jest widoczna, zamiast udawać postęp.

**Formularz pyta o ciężar łączny**, bo tak myśli człowiek stojący nad ławką.
Pytanie o same talerze kazałoby liczyć w pamięci przy każdej serii.
Rozbicia dokonuje `_rozbij_ciezar` w `main.py`.

Jeden przypadek brzegowy: **ciężar mniejszy od gryfu** znaczy, że katalog kłamie
o sprzęcie (albo ktoś wpisał wagę własnego ciała). Wtedy całość zapisuje się jako
obciążenie i gryf nie jest zgadywany — suma zostaje prawdziwa, a rozbicie da się
poprawić później.

Przy podmianie ćwiczenia gryf brany jest **z katalogu zamiennika**, nie z pozycji
planu. Bez tego 35 kg na sztandze zapisałoby się jako 28 kg talerzy na gryfie
łamanym: suma dobra, rozbicie fałszywe.

### `reps_min` i `reps_max` zamiast jednej liczby

Plan jest **zakresem zamiaru**, nie punktem. `2×10–12` znaczy „dwie serie, od
dziesięciu do dwunastu powtórzeń". Bez tego nie da się odróżnić przekroczenia
od zwykłej realizacji — a to właśnie przekroczenia są sygnałem, żeby zmienić
resztę planu. Gdy min i max są równe, widok pokazuje jedną liczbę.

### `NULL` to nie zero

Pusta przerwa między seriami zostaje pusta. `NULL` znaczy „nie zapisano",
a zero byłoby twierdzeniem, że serie poszły bez żadnej przerwy.

Przerwa należy do odstępu **przed** serią, więc pierwsza seria ćwiczenia
jej nie dostaje.

### Skala wysiłku 1–5, nie 1–10

Skala zeszła z dziesięciu stopni na pięć po pierwszym realnym przejściu przez
aplikację. Dziesięć pól w rzędzie było **za wąskie na kciuk**, a różnica między
„7" a „8" i tak jest zmyślona — pięć stopni da się odróżnić czuciem,
dziesięciu nie.

**Znany problem, nierozwiązany:** ta skala okazała się polem na dwa pytania
naraz — „jak daleko do upadku" i „jak bardzo paliło". To są różne rzeczy
i jedną liczbą nie da się odpowiedzieć na obie. Kierunek naprawy, gdybyś chciał
go dokończyć: osobne pole „ile jeszcze byś zrobił" (0/1/2/3+) plus haczyk
„do upadku", a 1–5 zostaje jako palenie.

### Niezmienność jest w bazie, nie w aplikacji

Trigger `training.guard_closed` pilnuje tego w PostgreSQL:

- dopóki `performed_session.closed_at IS NULL`, trening trwa i poprawka serii
  to zwykły `UPDATE`;
- **po zamknięciu `UPDATE` i `DELETE` są odrzucane**. Korekta musi być nowym
  wierszem z `supersedes` wskazującym poprzednika.

Widok `performed_set_current` pokazuje tylko serie, których nic nie zastąpiło.
Wszystko, co czyta dane, czyta ten widok.

Powód, dla którego to stoi w bazie, a nie w kodzie: skrypt, który się pomyli,
i tak nie przejdzie. Trigger chroni także przed narzędziami, które napiszesz
później i o których dziś nie wiesz.

Zostało to sprawdzone w obie strony na czystej bazie: `UPDATE` na zamkniętej
sesji odrzucony, korekta przez `supersedes` przyjęta, widok pokazał nową wersję
i ukrył starą.

## Zachowanie aplikacji

### Zapis po każdej serii, nie na końcu treningu

Utrata sieci w połowie treningu kosztuje wtedy jedną serię, a nie cały trening.
To samo dotyczy odczuć — ból i wysiłek mają osobny endpoint i dojeżdżają
do bazy od razu, a nie przy zamykaniu sesji.

### Sufit trzech serii na ćwiczenie

Po okresie adaptacyjnym trening idzie do upadku mięśniowego, a wtedy dwie–trzy
serie wyczerpują ruch; dalej idzie się ciężarem, nie objętością.

Pilnowane w **dwóch** miejscach: szablon nie rysuje „+ Dodaj serię" powyżej
sufitu, a `LIMIT_SERII` w `main.py` odrzuca zapis, gdyby przyszedł ze starej
karty otwartej w telefonie. Szablon bierze liczbę z tej samej stałej.

To jest założenie treningowe, nie prawo natury. Przy dwóch seriach do upadku
sufit 2 też ma sens. Chcesz inaczej — zmień `LIMIT_SERII` w `main.py`.
Plan może przewidywać mniej serii niż sufit, nigdy więcej.

### Tydzień jako jednostka, plan jako kolejka

Pierwsza wersja pokazywała „następny trening z planu" i po zamknięciu
treningu sama przeskakiwała dalej. W praktyce trening wypada raz w tygodniu
i nie zawsze w tym samym dniu, więc przeskok mylił: zamykałeś trening
i od razu widziałeś następny, jakby był na dziś. Teraz ekran pokazuje tydzień,
a dodatkowy trening w tym samym tygodniu wymaga świadomego „+".

### Kolejność ekranu ≠ kolejność wykonania

„▶ Robię teraz" zapisuje zamiar (także przed pierwszą serią), a faktyczna
kolejność wynika z czasów zapisu serii. Gdyby trzymać jedno pole, przestawienie
karty „na zapas" udawałoby wykonanie.

### Podmiana ćwiczenia dopisuje do katalogu

Świadomie liberalne: lepiej mieć w katalogu ćwiczenie wpisane w biegu niż
stracić zapis serii, bo nazwa się nie zgadzała. Zapisywane jest i co zrobiono,
i co miało być zrobione (`substituted_from_exercise_id`).

**Znana niedoróbka:** podmiana jest przypięta do pojedynczej serii, a powinna
do pozycji planu. Przez to pyta o serię, zamiast po prostu wybrać ćwiczenie
na całą pozycję. Naprawa wymaga miejsca w schemacie.

### „Nie boli" kasuje opis, zamiast go chować

Schowane pole formularza **i tak wysyła swoją zawartość**. Bez jawnego
kasowania wcześniejszy opis bólu zostawałby w bazie przy ćwiczeniu, o którym
przed chwilą powiedziałeś, że nie boli.

### Wartość spoza skali ≠ brak wartości

To był prawdziwy błąd, który cicho kasował dane. Telefon z kartą sprzed zmiany
skali wysyłał „8", parser zwracał `None`, i zapis bez bólu i bez wysiłku
**kasował wcześniejszy wpis**. Bez śladu.

Dziś wartość spoza zakresu odrzuca cały zapis zamiast go interpretować.
Morał ogólniejszy: stary klient w cudzej kieszeni to nie teoria.

## Pułapki CSS, które kosztowały najwięcej

### Nakładka zostawała na ekranie na iPhonie

Panel podmiany był początkowo `position: absolute` chowany przez `display: none`.
**WebKit na iPhonie nie odrysowywał jego obszaru po zamknięciu**, więc panel
zostawał na ekranie jako duch wymieszany z treścią pod spodem. Na Chromium
na laptopie to się nie odtwarza — czyli nie zobaczysz tego, testując na kompie.

Stąd zasada: wszystko rozwijane jest blokiem w normalnym przepływie, rozwijanym
ukrytym `checkbox`-em. Zmiana wysokości karty wymusza przeliczenie układu
i artefakt nie ma jak powstać.

### Zwinięty `<details>` nadal układa swoją zawartość

W Chromium panel schowany w kolumnie o szerokości 44 px **rozpychał całą stronę
do 481 px**, mimo że nic nie było widać. Potrzebne jest jawne `display: none`
na zwiniętej treści.

### `fieldset` i kolumny `1fr` nie schodzą poniżej `min-content`

Skala wysiłku wymaga `min-width: 0` na polach i `minmax(0, 1fr)` na kolumnach
siatki. Inaczej rząd kwadratów wypycha stronę poza szerokość telefonu.

### Przy sprawdzaniu zrzutami ekranu

Przy skalowaniu Windows 125% `--window-size=390` daje viewport 481 px CSS
i **przycina** zrzut zamiast go skalować. Wygląda dokładnie jak przepełnienie,
którym nie jest. Szerokość okna trzeba przemnożyć przez skalowanie.

## Pułapki narzędziowe

**`docker exec -i` zjada resztę skryptu podanego przez `ssh 'bash -s'`.**
Kontener dziedziczy standardowe wejście, z którego bash czyta sam siebie, więc
wszystko po pierwszym `docker exec` znika bez śladu i bez błędu — polecenia
po prostu się nie wykonują. Poprawka: `docker exec -i … < /dev/null` przy każdym
wywołaniu, które nie potrzebuje wejścia.

**`curl -L -X POST` wymusza POST także po przekierowaniu 303** i zwraca mylące
`405`. Wygląda jak błąd aplikacji, a jest artefaktem testu. Przekierowania
sprawdzaj bez `-L`, patrząc na kod odpowiedzi i `redirect_url`.
