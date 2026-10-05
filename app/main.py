"""Health Dashboard — warstwa treningowa.

Trzy widoki: bieżący tydzień, sesja w toku, podsumowanie. Nic więcej.
Zapis idzie do PostgreSQL po każdej serii, nie na końcu treningu — utrata
sieci w połowie kosztuje wtedy jedną serię, a nie cały trening.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db
import postep

BASE = Path(__file__).parent

# Znacznik układu karty ćwiczenia. Nowy układ warto oznaczyć jako testowy: wchodzi
# na najbliższy tydzień po to, żeby sprawdzić go w realnym treningu, a nie
# dlatego, że jest skończony. Ustaw UKLAD = "test", jeśli przebudowujesz kartę
# i chcesz, żeby w pasku wisiał napis TEST, dopóki nie uznasz, że układ zostaje.
UKLAD = None

# Sufit serii na ćwiczenie. Założenie treningowe tego projektu: po okresie
# adaptacyjnym trening idzie do upadku mięśniowego, a wtedy dwie–trzy serie
# wyczerpują ruch. Trzy to bezpieczny start — ustal liczbę przy onboardingu
# (README) i zmień, jeśli plan zakłada inaczej. Pilnowany także tutaj, nie tylko
# w szablonie — telefon z otwartą starą kartą wysłałby serię ponad limit.
LIMIT_SERII = 3

# Identyfikatory zapisów serii, które już przeszły. Telefon ponawia zapis, gdy nie
# dostał odpowiedzi — a zapis mógł dojść, tylko odpowiedź zginęła po drodze. Bez tego
# ponowienie dopisałoby tę samą serię drugi raz. Pamięć procesu wystarcza: uvicorn
# chodzi na jednym workerze, a ponowienie przychodzi w ciągu minut, nie dni.
_ZAPISANE_SERIE: dict[str, None] = {}
_ZAPISANE_SERIE_LIMIT = 500

app = FastAPI(title="Health Dashboard — trening")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


@app.middleware("http")
async def blokada_zapisu_w_podgladzie(request: Request, call_next):
    """Testowy kontener pokazuje realne dane, ale nie może ich zmieniać."""
    if os.environ.get("HEALTH_PREVIEW_READONLY") == "1" and request.method not in ("GET", "HEAD"):
        return PlainTextResponse("Podgląd testowy jest tylko do odczytu.", status_code=403)
    return await call_next(request)


def kg(wartosc) -> str:
    """Ciężar po polsku: 32,5 a nie 32.5, i bez zbędnego zera na końcu."""
    if wartosc is None:
        return ""
    return f"{float(wartosc):g}".replace(".", ",")


def zakres_tygodnia(data) -> str:
    """Zakres tygodnia, poniedziałek–niedziela, wokół daty planu.

    Sama data planu nie wystarczy, odkąd doszedł trening w trasie: ten wypada
    innego dnia niż domowy, a widok i tak dotyczy całego tygodnia, nie jednego dnia.
    """
    if data is None:
        return ""
    poniedzialek = data - timedelta(days=data.weekday())
    niedziela = poniedzialek + timedelta(days=6)
    if poniedzialek.month == niedziela.month:
        return f"{poniedzialek.day}–{niedziela.strftime('%d.%m.%Y')}"
    return f"{poniedzialek.strftime('%d.%m')}–{niedziela.strftime('%d.%m.%Y')}"


MIEJSCA = {"dom": "dom", "trasa": "trasa", "silownia": "siłownia"}


def miejsce(kod) -> str:
    """Kod miejsca na napis dla człowieka.

    W bazie `location` jest identyfikatorem bez polskich znaków, tak jak `dom`
    i `trasa`. Ogonek dorabiamy tutaj, żeby nie trzymać w kolumnie warunkowej
    napisu, który kiedyś ktoś zechce przetłumaczyć albo skrócić.
    """
    return MIEJSCA.get(kod, kod or "")


templates.env.filters["kg"] = kg
templates.env.filters["tydzien"] = zakres_tygodnia
templates.env.filters["miejsce"] = miejsce
templates.env.filters["nazwa_metryki"] = lambda k: postep.SKROTY.get(k, k)
templates.env.globals["uklad"] = UKLAD


def _liczba(wartosc: str | None) -> float | None:
    """Przecinek dziesiętny jest tu normą: '32,5' ma znaczyć to samo co '32.5'."""
    if wartosc is None or str(wartosc).strip() == "":
        return None
    return float(str(wartosc).strip().replace(",", "."))


def _rozbij_ciezar(lacznie: float | None, gryf: float) -> tuple[float, float]:
    """Formularz pyta o ciężar ŁĄCZNY, baza trzyma gryf i talerze osobno.

    Zasada projektu: każdy zapisany ciężar jest łączny — 35 kg na ławce to
    sztanga 20 kg plus 15 kg talerzy. Pytanie o same talerze kazałoby liczyć
    w pamięci przy każdej serii, więc formularz pyta o to, czym się myśli.

    Ciężar mniejszy od gryfu znaczy, że katalog kłamie o sprzęcie (albo ktoś
    wpisał wagę własnego ciała). Zapisujemy wtedy całość jako obciążenie i nie
    zgadujemy gryfu — suma zostaje prawdziwa, a rozbicie da się poprawić później.
    """
    if lacznie is None:
        return gryf, 0.0
    if lacznie < gryf:
        return 0.0, lacznie
    return gryf, lacznie - gryf


def _przerwa(wartosc: str | None) -> int | None:
    """Faktyczna przerwa przed serią, w sekundach.

    Puste pole zostaje puste — `NULL` znaczy „nie zapisano", a nie „zero".
    Zero byłoby twierdzeniem, że serie poszły bez żadnej przerwy.
    """
    liczba = _liczba(wartosc)
    if liczba is None or liczba < 0:
        return None
    return int(liczba)


def _wysilek(wartosc: str | None) -> int | None:
    """Intensywność 1–5; 5 to upadek mięśniowy. Poza zakresem = brak oceny.

    Skala zeszła z dziesięciu stopni na pięć po pierwszym realnym przejściu
    aplikacji w trakcie treningu. Dziesięć pól w rzędzie było za wąskie na kciuk,
    a różnica między „7" a „8" i tak jest zmyślona — pięć stopni da się odróżnić
    czuciem, dziesięciu nie.
    """
    if wartosc is None or str(wartosc).strip() == "":
        return None
    try:
        liczba = int(str(wartosc).strip())
    except ValueError:
        return None
    return liczba if 1 <= liczba <= 5 else None


def _zamknieta(performed_id: int) -> bool:
    """Zapis do zamkniętej sesji blokuje trigger w bazie.

    Bez tego sprawdzenia telefon z otwartą starą kartą dostaje 500 zamiast
    odpowiedzi. Baza i tak obroni dane — tu chodzi o to, co widzi człowiek.
    """
    naglowek = db.session_header(performed_id)
    return naglowek is None or naglowek["closed_at"] is not None


@app.get("/zdrowie")
def zdrowie():
    """Endpoint dla Uptime Kumy — sprawdza też, czy baza odpowiada."""
    with db.cursor() as cur:
        cur.execute("select 1 as ok")
        cur.fetchone()
    return {"status": "ok"}


DNI = ("pon", "wt", "śr", "czw", "pt", "sob", "nd")


def poniedzialek(dzien: date) -> date:
    return dzien - timedelta(days=dzien.weekday())


def zakres_krotki(pon: date) -> str:
    """„5–11.10", a na przełomie miesięcy „29.09–5.10". Rok tylko, gdy nie bieżący."""
    nd = pon + timedelta(days=6)
    if pon.month == nd.month:
        tekst = f"{pon.day}–{nd.day}.{nd.month:02d}"
    else:
        tekst = f"{pon.day}.{pon.month:02d}–{nd.day}.{nd.month:02d}"
    if nd.year != date.today().year:
        tekst += f".{nd.year}"
    return tekst


MIESIACE = ("styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec",
            "sierpień", "wrzesień", "październik", "listopad", "grudzień")


def mini_kalendarz(pon: date) -> dict:
    """Miesiąc wokół wybranego tygodnia, tygodniami od poniedziałku.

    Tydzień na przełomie miesięcy należy do miesiąca swojego czwartku (jak
    w numeracji ISO) — „29.09–5.10" pokazuje październik, bo w nim ma 5 dni z 7.
    """
    czwartek = pon + timedelta(days=3)
    pierwszy = czwartek.replace(day=1)
    dzis = date.today()
    tygodnie = []
    start = poniedzialek(pierwszy)
    while start.month == pierwszy.month or start < pierwszy:
        dni = [start + timedelta(days=i) for i in range(7)]
        tygodnie.append({
            "pon": start.isoformat(),
            "wybrany": start == pon,
            "dni": [{"dzien": d.day, "w_miesiacu": d.month == pierwszy.month, "dzis": d == dzis} for d in dni],
        })
        start += timedelta(days=7)
    return {"miesiac": f"{MIESIACE[pierwszy.month - 1]} {pierwszy.year}", "tygodnie": tygodnie}


PROG_POWTORZEN = 10
PODBICIE_KG = 2.5


def do_podbicia(pozycje: list[dict]) -> list[dict]:
    """Ćwiczenia, które ostatnim razem spełniły regułę progresji.

    Reguła: wszystkie serie (co najmniej dwie) po ≥10 powtórzeń → +2,5 kg.
    Próg i krok są w stałych `PROG_POWTORZEN` i `PODBICIE_KG` wyżej.
    Liczy się ostatni trening, w którym ćwiczenie było robione, i tylko serie
    z jednym ciężarem — jeśli któraś szła lżej, to nie były „wszystkie serie" na tym
    ciężarze. Ćwiczenia na czas i bez obciążenia (podciąganie, dipy) pomijamy.
    """
    # Pozycje z notą „bez progresji" (np. partia poza celem bloku) wypadają: inaczej ramka podpowiadałaby dokładanie wbrew planowi.
    powtorzeniowe = [
        p for p in pozycje
        if p["measure"] != "time" and "bez progresji" not in (p["progression_note"] or "").lower()
    ]
    ostatnio = db.last_session_sets([p["exercise_id"] for p in powtorzeniowe])
    wynik = []
    for p in powtorzeniowe:
        o = ostatnio.get(p["exercise_id"])
        if not o or not o["max_kg"] or o["min_kg"] != o["max_kg"]:
            continue
        if o["serie"] >= 2 and (o["min_powt"] or 0) >= PROG_POWTORZEN:
            wynik.append({
                "exercise": p["exercise"],
                "z": o["max_kg"],
                "na": float(o["max_kg"]) + PODBICIE_KG,
            })
    return wynik


def opis_tygodnia(pon: date, biezacy: date) -> str:
    roznica = (pon - biezacy).days // 7
    if roznica == 0:
        return "ten tydzień"
    if roznica == 1:
        return "następny tydzień"
    if roznica == -1:
        return "poprzedni tydzień"
    return f"za {roznica} tyg." if roznica > 0 else f"{-roznica} tyg. temu"


def rozloz_kolejke(kolejka: list[dict], biezacy: date, biezacy_zajety: bool) -> dict[date, dict]:
    """Przypisuje niezrobione treningi planu do tygodni: jeden na tydzień, po kolei.

    Jednostką jest tydzień, a drugi trening
    w tym samym tygodniu (urlop, wolne w domu) dodaje się plusem — nie przez
    automatyczne przeskoczenie na kolejny trening po zamknięciu poprzedniego.
    Data z planu jest orientacyjna, więc kolejka startuje od bieżącego tygodnia,
    a jeśli w nim już był trening — od następnego. Wyjątek: plan, z którego
    jeszcze nic nie zrobiono, nie wchodzi przed tydzień swojej pierwszej daty.
    """
    rozklad: dict[date, dict] = {}
    if not kolejka:
        return rozklad
    termin = biezacy + timedelta(days=7 if biezacy_zajety else 0)
    if not kolejka[0]["plan_ruszyl"]:
        termin = max(termin, poniedzialek(kolejka[0]["planned_on"]))
    for pozycja in kolejka:
        rozklad[termin] = pozycja
        termin += timedelta(days=7)
    return rozklad


templates.env.globals["dni"] = DNI


@app.get("/")
def tydzien(request: Request, tydzien: str | None = None, dodaj: int = 0):
    trwa = db.open_session()
    # Wejście bez wskazanego tygodnia (zakładka „Trening") prowadzi prosto do
    # trwającego treningu — tak jak dotąd. Strzałki tygodni zawsze pokazują tydzień.
    if trwa and tydzien is None:
        return RedirectResponse(f"/sesja/{trwa['performed_id']}", status_code=303)

    biezacy = poniedzialek(date.today())
    try:
        wybrany = poniedzialek(date.fromisoformat(tydzien)) if tydzien else biezacy
    except ValueError:
        wybrany = biezacy

    kolejka = db.plan_queue()
    wykonane = db.sessions_in_week(wybrany)
    w_biezacym = wykonane if wybrany == biezacy else db.sessions_in_week(biezacy)

    if not kolejka and not wykonane and wybrany == biezacy:
        return templates.TemplateResponse(
            request, "brak-planu.html", {"tytul": "Brak planu"}
        )

    sesja = rozloz_kolejke(kolejka, biezacy, bool(w_biezacym)).get(wybrany)
    # Plus pojawia się tylko w bieżącym tygodniu, gdy jego trening już jest zrobiony:
    # trening da się zacząć tylko dziś, a przed pierwszym plus nie ma czego dodawać.
    mozna_dodac = wybrany == biezacy and bool(wykonane) and bool(kolejka) and not trwa
    dodany = bool(dodaj) and mozna_dodac
    if dodany:
        sesja = kolejka[0]

    pozycje = db.plan_items(sesja["planned_id"]) if sesja else []
    # Następny trening w kolejce da się zacząć także z jego (przyszłego) tygodnia
    # Zapisze się z dzisiejszą datą, czyli w bieżącym
    # tygodniu; dalszych treningów nie zaczyna się przed poprzednimi.
    nastepny_w_kolejce = bool(sesja and kolejka and sesja["planned_id"] == kolejka[0]["planned_id"])
    mozna_startowac = sesja is not None and not trwa and (
        wybrany == biezacy or (wybrany > biezacy and nastepny_w_kolejce)
    )
    wczesniej = mozna_startowac and wybrany != biezacy
    zakres = zakres_krotki(wybrany)
    # Na górze nazwa treningu, daty w karcie pod nią.
    # Tydzień bez treningu do zrobienia bierze nazwę ostatniego zrobionego.
    if sesja:
        tytul_tygodnia = sesja["label"]
    elif wykonane:
        tytul_tygodnia = wykonane[-1]["label"]
    else:
        tytul_tygodnia = "Bez treningu"
    return templates.TemplateResponse(
        request,
        "tydzien.html",
        {
            "tytul": zakres,
            "tytul_paska": f"Tydzień {zakres}",
            "zakladka": "trening",
            "zakres": zakres,
            "tytul_tygodnia": tytul_tygodnia,
            "kalendarz": mini_kalendarz(wybrany),
            "opis": opis_tygodnia(wybrany, biezacy),
            "poprzedni": (wybrany - timedelta(days=7)).isoformat(),
            "nastepny": (wybrany + timedelta(days=7)).isoformat(),
            "wybrany": wybrany.isoformat(),
            "biezacy": wybrany == biezacy,
            "wykonane": wykonane,
            "sesja": sesja,
            "mozna_startowac": mozna_startowac,
            # Tylko dla treningu, który da się zacząć teraz: dla dalszych tygodni
            # podbicie zależy od treningów, których jeszcze nie było.
            "podbicie": do_podbicia(pozycje) if mozna_startowac else None,
            "mozna_dodac": mozna_dodac and not dodany,
            "dodany": dodany,
            "wczesniej": wczesniej,
            "zakres_biezacy": zakres_krotki(biezacy),
            "poprzedni_w_kolejce": None if (mozna_startowac or not kolejka or wybrany < biezacy) else kolejka[0]["label"],
            "pozycje": pozycje,
            "ostatnie": db.last_results(),
        },
    )


@app.post("/plan/rozdziel-serie")
def rozdziel_serie(group: str = Form(...)):
    """Rozdziela serię łączoną na przyszłość — patrz `db.split_superset_group`.

    Nie dotyka sesji już wykonanych ani trwającej: nowa wersja planu obejmuje
    tylko to, co jeszcze niezrobione, więc trwający trening spokojnie kończy się
    na starym planie.
    """
    grupa = group.strip()
    if grupa:
        db.split_superset_group(grupa)
    return RedirectResponse("/", status_code=303)


@app.post("/sesja/start")
def start(planned_id: int = Form(...), location: str = Form("dom")):
    nowa = db.start_session(planned_id, location)
    return RedirectResponse(f"/sesja/{nowa}", status_code=303)


@app.get("/sesja/{performed_id}")
def sesja(request: Request, performed_id: int):
    naglowek = db.session_header(performed_id)
    if naglowek is None:
        return RedirectResponse("/", status_code=303)
    if naglowek["closed_at"]:
        return RedirectResponse(f"/sesja/{performed_id}/podsumowanie", status_code=303)

    pozycje = db.plan_items(naglowek["planned_id"], performed_id) if naglowek["planned_id"] else []
    zrobione = db.sets_of(performed_id)

    wg_pozycji: dict[int | None, list[dict]] = {}
    for s in zrobione:
        wg_pozycji.setdefault(s["planned_item_id"], []).append(s)

    return templates.TemplateResponse(
        request,
        "sesja.html",
        {
            "tytul": naglowek["label"] or "Trening",
            "zakladka": "trening",
            "naglowek": naglowek,
            "pozycje": pozycje,
            "serie": wg_pozycji,
            "poza_planem": wg_pozycji.get(None, []),
            "ostatnie": db.last_results(),
            "katalog": db.exercises(),
            "odczucia": db.item_feedback(performed_id),
            "limit_serii": LIMIT_SERII,
        },
    )


@app.post("/sesja/{performed_id}/robie-teraz")
def robie_teraz(performed_id: int, planned_item_id: int = Form(...)):
    """Przestawienie karty w trwającym treningu — patrz `db.do_now`.

    Dotyczy wyłącznie tej sesji: plan na kolejne treningi się nie zmienia.
    Faktyczną kolejność agent i tak czyta z czasu pierwszej serii.
    """
    if _zamknieta(performed_id):
        return RedirectResponse(f"/sesja/{performed_id}/podsumowanie", status_code=303)
    db.do_now(performed_id, planned_item_id)
    return RedirectResponse(f"/sesja/{performed_id}#poz-{planned_item_id}", status_code=303)


@app.post("/sesja/{performed_id}/rozdziel-serie")
def rozdziel_serie_w_sesji(performed_id: int, group: str = Form(...)):
    """Odklikniecie „seria łączona" na karcie ćwiczenia w trakcie treningu.

    Zdejmuje oznaczenie z BIEŻĄCEJ sesji od razu — stąd znika po przeładowaniu
    karty w tym samym treningu — i przy okazji poprawia przyszłe tygodnie tą
    samą ścieżką co przycisk w widoku tygodnia. Patrz `db.split_superset_group`
    i `db.clear_superset_group_for_session`.
    """
    if _zamknieta(performed_id):
        return RedirectResponse(f"/sesja/{performed_id}/podsumowanie", status_code=303)

    grupa = group.strip()
    if grupa:
        naglowek = db.session_header(performed_id)
        if naglowek and naglowek["planned_id"]:
            db.clear_superset_group_for_session(naglowek["planned_id"], grupa)
        db.split_superset_group(grupa)
    return RedirectResponse(f"/sesja/{performed_id}", status_code=303)


@app.post("/sesja/{performed_id}/seria")
def dodaj_serie(
    performed_id: int,
    planned_item_id: str = Form(""),
    exercise_id: int = Form(...),
    zamiennik: str = Form(""),
    repetitions: str = Form(""),
    duration_seconds: str = Form(""),
    bar_weight_kg: str = Form("0"),
    weight_total_kg: str = Form(""),
    note: str = Form(""),
    rest_seconds: str = Form(""),
    zapis_id: str = Form(""),
):
    if _zamknieta(performed_id):
        return RedirectResponse(f"/sesja/{performed_id}/podsumowanie", status_code=303)

    zapis_id = zapis_id.strip()[:64]
    if zapis_id and zapis_id in _ZAPISANE_SERIE:
        return RedirectResponse(f"/sesja/{performed_id}", status_code=303)

    podmienione_z = None
    docelowe = exercise_id
    gryf_katalogowy = _liczba(bar_weight_kg) or 0

    if zamiennik.strip():
        # Podmiana: zapisujemy i co zrobiono, i co miało być zrobione.
        podmienione_z = exercise_id
        docelowe = db.find_or_create_exercise(zamiennik)
        if docelowe == podmienione_z:
            podmienione_z = None
        else:
            # Zamiennik bywa na innym sprzęcie, a formularz przysłał gryf z planu.
            # Bez tego 35 kg na sztandze zapisałoby się jako 28 kg talerzy na
            # gryfie łamanym — suma dobra, rozbicie fałszywe.
            gryf_katalogowy = db.bar_weight(docelowe)

    pozycja = int(planned_item_id) if planned_item_id.strip() else None
    juz = [s for s in db.sets_of(performed_id) if s["planned_item_id"] == pozycja]
    if pozycja is not None and len(juz) >= LIMIT_SERII:
        return RedirectResponse(f"/sesja/{performed_id}#poz-{pozycja}", status_code=303)

    numer = max((s["set_number"] for s in juz), default=0) + 1

    gryf, talerze = _rozbij_ciezar(_liczba(weight_total_kg), gryf_katalogowy)

    db.add_set(
        performed_session_id=performed_id,
        planned_item_id=pozycja,
        exercise_id=docelowe,
        set_number=numer,
        repetitions=int(_liczba(repetitions)) if _liczba(repetitions) else None,
        duration_seconds=int(_liczba(duration_seconds)) if _liczba(duration_seconds) else None,
        bar_weight_kg=gryf,
        added_weight_kg=talerze,
        substituted_from_exercise_id=podmienione_z,
        note=note.strip() or None,
        # Przerwa należy do odstępu PRZED serią, więc pierwsza jej nie dostaje.
        rest_seconds=_przerwa(rest_seconds) if numer > 1 else None,
    )
    if zapis_id:
        _ZAPISANE_SERIE[zapis_id] = None
        if len(_ZAPISANE_SERIE) > _ZAPISANE_SERIE_LIMIT:
            del _ZAPISANE_SERIE[next(iter(_ZAPISANE_SERIE))]
    return RedirectResponse(f"/sesja/{performed_id}#poz-{pozycja or 'extra'}", status_code=303)


@app.post("/sesja/{performed_id}/seria/{set_id}/popraw")
def popraw_serie(
    performed_id: int,
    set_id: int,
    planned_item_id: str = Form(""),
    repetitions: str = Form(""),
    duration_seconds: str = Form(""),
    bar_weight_kg: str = Form("0"),
    weight_total_kg: str = Form(""),
    rest_seconds: str = Form(""),
):
    if _zamknieta(performed_id):
        return RedirectResponse(f"/sesja/{performed_id}/podsumowanie", status_code=303)

    gryf, talerze = _rozbij_ciezar(_liczba(weight_total_kg), _liczba(bar_weight_kg) or 0)

    db.update_set(
        set_id,
        repetitions=int(_liczba(repetitions)) if _liczba(repetitions) else None,
        duration_seconds=int(_liczba(duration_seconds)) if _liczba(duration_seconds) else None,
        bar_weight_kg=gryf,
        added_weight_kg=talerze,
    )
    kotwica = planned_item_id.strip() or "extra"
    return RedirectResponse(f"/sesja/{performed_id}#poz-{kotwica}", status_code=303)


@app.post("/sesja/{performed_id}/seria/{set_id}/skasuj")
def skasuj_serie(performed_id: int, set_id: int, planned_item_id: str = Form("")):
    if _zamknieta(performed_id):
        return RedirectResponse(f"/sesja/{performed_id}/podsumowanie", status_code=303)

    db.delete_set(set_id)
    kotwica = planned_item_id.strip() or "extra"
    return RedirectResponse(f"/sesja/{performed_id}#poz-{kotwica}", status_code=303)


@app.post("/sesja/{performed_id}/odczucie")
def odczucie(
    performed_id: int,
    exercise_id: int = Form(...),
    planned_item_id: str = Form(""),
    pain_note: str = Form(""),
    effort: str = Form(""),
    boli: str = Form(""),
):
    """Ból i intensywność wysiłku dla jednego ćwiczenia.

    Osobny endpoint, a nie część zamknięcia treningu: oba pola wypełnia się przy
    ćwiczeniu, zaraz po ostatniej serii, i mają dojechać do bazy od razu — tak samo
    jak serie. Utrata sieci ma kosztować jeden wpis, nie cały trening.
    """
    if _zamknieta(performed_id):
        return RedirectResponse(f"/sesja/{performed_id}/podsumowanie", status_code=303)

    # Wartość spoza skali nie jest tym samym co brak wartości. Bez tego telefon
    # z kartą sprzed zmiany skali (1–10) wysyłał „8", `_wysilek` zwracał None,
    # a zapis bez bólu i bez wysiłku KASOWAŁ wcześniejszy wpis. Cicho.
    if effort.strip() and _wysilek(effort) is None:
        return RedirectResponse(f"/sesja/{performed_id}", status_code=303)

    # Wskazanie „nie" kasuje opis, zamiast go tylko chować. Schowane pole i tak
    # wysyła swoją zawartość, więc bez tego wcześniejszy opis bólu zostawałby
    # w bazie przy ćwiczeniu, o którym użytkownik właśnie powiedział, że nie boli.
    opis = "" if boli == "nie" else pain_note.strip()

    db.save_item_feedback(
        performed_session_id=performed_id,
        planned_item_id=int(planned_item_id) if planned_item_id.strip() else None,
        exercise_id=exercise_id,
        pain_note=opis or None,
        effort=_wysilek(effort),
    )
    kotwica = planned_item_id.strip() or "extra"
    return RedirectResponse(f"/sesja/{performed_id}#poz-{kotwica}", status_code=303)


@app.post("/sesja/{performed_id}/zamknij")
def zamknij(performed_id: int, feeling: str = Form(""), notes: str = Form("")):
    db.close_session(performed_id, feeling, notes)
    return RedirectResponse(f"/sesja/{performed_id}/podsumowanie", status_code=303)


@app.get("/sesja/{performed_id}/podsumowanie")
def podsumowanie(request: Request, performed_id: int):
    naglowek = db.session_header(performed_id)
    if naglowek is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "podsumowanie.html",
        {
            "tytul": "Podsumowanie",
            "zakladka": "historia",
            "naglowek": naglowek,
            "odchylenia": db.deviations(performed_id) if naglowek["planned_id"] else [],
            "serie": db.sets_of(performed_id),
            "odczucia": db.session_feedback(performed_id),
        },
    )


# ------------------------------------------------------------------ historia


@app.get("/historia")
def historia(request: Request):
    """Zamknięte treningi, od najnowszego. Stąd wchodzi się w podsumowanie."""
    return templates.TemplateResponse(
        request,
        "historia.html",
        {"tytul": "Historia", "sesje": db.closed_sessions(), "zakladka": "historia"},
    )


# ------------------------------------------------------------------ postęp


@app.get("/postep")
def postep_lista(request: Request):
    return templates.TemplateResponse(
        request,
        "postep.html",
        {
            "tytul": "Postęp",
            "cwiczenia": db.exercises_with_history(),
            "zakladka": "postep",
        },
    )


@app.get("/postep/{exercise_id}")
def postep_cwiczenia(
    request: Request, exercise_id: int, metryka: str = "", widok: str = ""
):
    cwiczenie = db.exercise(exercise_id)
    if cwiczenie is None:
        return RedirectResponse("/postep", status_code=303)

    ostatni = db.closed_session_count()
    historia_ = db.exercise_history(exercise_id)
    dostepne = postep.dostepne_metryki(cwiczenie, historia_)
    wybrana = metryka if metryka in dostepne else postep.domyslna_metryka(cwiczenie, historia_)
    punkty = postep.punkty(historia_, wybrana)
    start = punkty[0].wartosc if punkty else None
    teraz = punkty[-1].wartosc if punkty else None
    jednostka = "kg" if wybrana in ("1rm", "ciezar", "tonaz") else ("s" if wybrana == "czas" else "powt.")
    od_pomiaru = widok == "pomiar"
    pierwszy = punkty[0].nr if od_pomiaru and punkty else 1

    return templates.TemplateResponse(
        request,
        "postep-cwiczenie.html",
        {
            "tytul": cwiczenie["name"],
            "tytul_paska": "",
            "wstecz_href": "/postep",
            "wstecz_tekst": "‹ Postęp",
            "cwiczenie": cwiczenie,
            "cwiczenia": db.exercises_with_history(),
            "historia": list(reversed(historia_)),
            "metryka": wybrana,
            "metryki": dostepne,
            "opis_metryki": postep.METRYKI[wybrana],
            "punkty": punkty,
            "svg": postep.wykres(
                punkty,
                pierwszy,
                ostatni,
                jednostka,
            ),
            "niepewne": [p for p in punkty if not p.pewny],
            "start": start,
            "teraz": teraz,
            "roznica": teraz - start if teraz is not None and start is not None else None,
            "jednostka": jednostka,
            "od_pomiaru": od_pomiaru,
            "widok_query": "?widok=pomiar" if od_pomiaru else "",
            "ostatni_trening": ostatni,
            "zakladka": "postep",
        },
    )
