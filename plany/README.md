# Plany treningowe

Plan piszesz jako plik JSON i wgrywasz do bazy skryptem. Nie klikasz go
w aplikacji — aplikacja służy do **wykonywania** planu, nie do układania go.

Gotowego planu tu nie ma — każdy układa swój (patrz onboarding w głównym
`README.md`). Plany trzymaj w `moje/` — ten katalog jest w `.gitignore`.

## Jak wgrać

```sh
export DATABASE_URL="postgresql://trening:HASLO@localhost:5432/trening"

python narzedzia/write_training_plan.py plany/moje/2026-01.json --dry-run
python narzedzia/write_training_plan.py plany/moje/2026-01.json
```

`--na-biezacy-tydzien` przesuwa cały plan tak, żeby pierwsza sesja wypadła
w bieżącym tygodniu, zachowując odstępy między sesjami. Przy planie z realnymi
datami niepotrzebny.

`--dry-run` przepuszcza cały wsad przez bazę i **wycofuje go na końcu**:
pokazuje, co by wjechało, nie zapisując nic. Warto go zawsze użyć, bo nieznana
nazwa ćwiczenia zatrzymuje wsad dopiero w trakcie.

## Format

```json
{
  "label": "nazwa bloku",
  "starts_on": "2026-01-05",
  "ends_on": "2026-01-18",
  "supersedes": null,
  "sessions": [
    {
      "label": "Trening 1",
      "planned_on": "2026-01-05",
      "location": "dom",
      "notes": "kontekst całej sesji",
      "items": [
        {
          "exercise": "slug-albo-alias-z-katalogu",
          "sets": 3,
          "reps_min": 10,
          "reps_max": 12,
          "weight_kg": 35,
          "rest_seconds": 120,
          "superset": "A",
          "note": "uzasadnienie progresji"
        }
      ]
    }
  ]
}
```

### Pola

| Pole | Gdzie | Znaczenie |
|---|---|---|
| `label` | plan, sesja | nazwa; sesja pokazuje ją w pasku aplikacji |
| `starts_on` / `ends_on` | plan | zakres bloku |
| `supersedes` | plan | id planu, który ten zastępuje — patrz niżej |
| `planned_on` | sesja | data sesji; widok liczy od niej cały tydzień |
| `location` | sesja | `dom`, `trasa` albo `silownia`; domyślnie `dom` |
| `exercise` | pozycja | `slug` z katalogu albo alias |
| `sets` | pozycja | liczba serii |
| `reps_min` / `reps_max` | pozycja | zakres powtórzeń |
| `duration_seconds` | pozycja | **zamiast** `reps_*` przy ćwiczeniach na czas |
| `weight_kg` | pozycja | ciężar **łączny, razem z gryfem** |
| `rest_seconds` | pozycja | przerwa; domyślnie 120 |
| `superset` | pozycja | litera grupy dla serii łączonych |
| `note` | pozycja | dlaczego akurat tyle — widoczne w aplikacji |

Pominięty `reps_max` przyjmuje wartość `reps_min`.

### Zakres, nie punkt

`reps_min` i `reps_max` są osobno celowo. `3×10–12` znaczy „trzy serie, od
dziesięciu do dwunastu powtórzeń". Dopiero to pozwala odróżnić wykonanie zgodne
z zamiarem od przekroczenia — a przekroczenia są sygnałem do zmiany reszty
planu. Gdy min i max są równe, widok pokazuje jedną liczbę.

### Ciężar łączny

`weight_kg` to ciężar razem z gryfem. Aplikacja sama odejmuje
`default_bar_weight_kg` ćwiczenia, żeby w formularzu podstawić to, co faktycznie
nakładasz na gryf. 35 kg na ławce = sztanga 20 kg + 15 kg talerzy.

### Ćwiczenia po nazwie

`exercise` dopasowuje się najpierw po `slug`, potem po aliasie. **Nieznana nazwa
zatrzymuje cały wsad** — celowo. Lepiej dopisać ćwiczenie świadomie do katalogu
(`db/seeds/`), niż rozjechać historię dwiema nazwami tego samego ruchu.

Lista tego, co masz w katalogu:

```sh
docker compose exec -T postgres psql -U trening -d trening -c \
  "select slug, name, equipment, default_bar_weight_kg from training.exercise order by name"
```

## Poprawianie planu, który już jest w bazie

**Nie edytujesz go.** Piszesz nowy plan z `supersedes` wskazującym id starego:

```json
{ "label": "Blok styczniowy, wersja 2", "supersedes": 1, ... }
```

Aplikacja pomija plany zastąpione, więc od razu pokaże nowy. Stary zostaje
w bazie — razem z tym, co już na nim zrobiłeś.

**Nowa wersja zawiera tylko treningi jeszcze niezrobione.** Trening liczy się
jako zrobiony w tej wersji planu, w której go wykonano — powtórzony w nowej
wersji „Trening 1" wróci jako niezrobiony. Pierwszy trening nowej wersji
dostaje `planned_on` w tygodniu, w którym ma wypaść.

Id planów sprawdzisz tak:

```sh
docker compose exec -T postgres psql -U trening -d trening -c \
  "select id, label, starts_on, supersedes from training.training_plan order by id"
```
