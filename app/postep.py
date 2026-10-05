"""Przeliczanie postępu i rysowanie wykresu.

Osobny plik, bo to jedyne miejsce w aplikacji, które **interpretuje** dane, zamiast
je przenosić. Wszystko, co tu policzone, jest oszacowaniem i ma być tak podpisane.

Wykres jest rysowany jako SVG po stronie serwera. Żadnej biblioteki: strona i tak
nie ma builda JS, a Pi ma 1,8 GB RAM-u. SVG generowane z danych jest lżejsze od
każdej biblioteki wykresów i działa bez internetu.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Powyżej tylu powtórzeń oszacowanie ciężaru maksymalnego przestaje być wiarygodne.
# Wzory 1RM powstały na seriach 1–10; przy 12 i 15 powtórzeniach ekstrapolują daleko
# poza swój zakres. Punkt policzony z takiej serii jest na wykresie oznaczany.
RZETELNY_ZAKRES_POWTORZEN = 10


def epley(ciezar: float, powtorzenia: int) -> float | None:
    """Szacowany ciężar maksymalny wg wzoru Epleya: `w × (1 + p/30)`.

    Przy jednym powtórzeniu daje dokładnie podniesiony ciężar, więc nie zmyśla
    tam, gdzie nie musi. Wybrany zamiast Brzyckiego, bo ten drugi rozjeżdża się
    przy wysokich powtórzeniach jeszcze mocniej (dzielenie przez `37 − p`).
    """
    if not ciezar or not powtorzenia or powtorzenia < 1:
        return None
    return round(float(ciezar) * (1 + powtorzenia / 30), 1)


@dataclass
class Punkt:
    data: object
    nr: int  # numer treningu w całej historii, nie tydzień
    wartosc: float
    podpis: str
    pewny: bool = True


METRYKI = {
    "1rm": "szacowany ciężar maksymalny",
    "ciezar": "najcięższa seria",
    "tonaz": "objętość (ciężar × powtórzenia)",
    "powtorzenia": "powtórzenia w najlepszej serii",
    "czas": "czas najdłuższej serii",
}


# Krótkie nazwy na przyciski — pełne opisy nie mieszczą się w rzędzie na telefonie.
SKROTY = {
    "1rm": "maks",
    "ciezar": "ciężar",
    "tonaz": "objętość",
    "powtorzenia": "powt.",
    "czas": "czas",
}


def dostepne_metryki(cwiczenie: dict, historia: list[dict]) -> dict[str, str]:
    """Nie pokazujemy przycisków, które dałyby pusty wykres.

    Plank nie ma ciężaru ani powtórzeń, podciąganie nie ma ciężaru. Przycisk,
    który prowadzi do „brak danych", jest gorszy od braku przycisku.
    """
    if cwiczenie["measure"] == "time":
        return {"czas": METRYKI["czas"]}

    z_ciezarem = any((w["ciezar_max"] or 0) > 0 for w in historia)
    if not z_ciezarem:
        return {k: METRYKI[k] for k in ("powtorzenia",)}
    return {k: METRYKI[k] for k in ("1rm", "ciezar", "tonaz", "powtorzenia")}


def domyslna_metryka(cwiczenie: dict, historia: list[dict]) -> str:
    """Nie każda metryka pasuje do każdego ruchu.

    Plank mierzy się sekundami, podciąganie powtórzeniami (ciężar jest tam zawsze
    zerowy), a ławka ciężarem. Domyślna metryka wynika z ćwiczenia, nie z wyboru
    z listy — listę zostawiamy do przełączania.
    """
    if cwiczenie["measure"] == "time":
        return "czas"
    if not any((w["ciezar_max"] or 0) > 0 for w in historia):
        return "powtorzenia"
    return "ciezar"


def punkty(historia: list[dict], metryka: str) -> list[Punkt]:
    wynik: list[Punkt] = []
    for w in historia:
        if metryka == "1rm":
            wartosc = epley(w["rekord_ciezar"], w["rekord_powt"])
            if wartosc is None:
                continue
            pewny = (w["rekord_powt"] or 0) <= RZETELNY_ZAKRES_POWTORZEN
            podpis = f"{_kg(wartosc)} kg  (z {_kg(w['rekord_ciezar'])}×{w['rekord_powt']})"
        elif metryka == "ciezar":
            wartosc = float(w["ciezar_max"] or 0)
            pewny = True
            podpis = f"{_kg(wartosc)} kg"
        elif metryka == "tonaz":
            wartosc = float(w["tonaz"] or 0)
            pewny = True
            podpis = f"{_kg(wartosc)} kg łącznie"
        elif metryka == "czas":
            wartosc = float(w["czas_max"] or 0)
            pewny = True
            podpis = f"{int(wartosc)} s"
        else:
            wartosc = float(w["powt_max"] or 0)
            pewny = True
            podpis = f"{int(wartosc)} powt."

        if wartosc <= 0:
            # Zero znaczy tu „nie zapisano", nie „podniósł zero". Starsze serie
            # potrafią mieć ciężar 0, bo katalog nie znał wtedy wagi gryfu —
            # wrysowanie ich jako spadku do zera byłoby kłamstwem na wykresie.
            continue

        wynik.append(
            Punkt(
                data=w["performed_on"],
                nr=w["nr"],
                wartosc=wartosc,
                podpis=podpis,
                pewny=pewny,
            )
        )
    return wynik


def _kg(wartosc) -> str:
    if wartosc is None:
        return ""
    return f"{float(wartosc):g}".replace(".", ",")


def _ladny_krok(surowy: float) -> float:
    """Zaokrągla krok osi do 1, 2, 2,5, 5 albo 10 × potęga dziesięciu."""
    if surowy <= 0:
        return 1
    potega = 10 ** math.floor(math.log10(surowy))
    czesc = surowy / potega
    for kandydat in (1, 2, 2.5, 5, 10):
        if czesc <= kandydat:
            return kandydat * potega
    return 10 * potega


def zakres_osi(punkty_: list[Punkt]) -> tuple[float, float] | None:
    """Dolna i górna wartość osi pionowej.

    Podawana osobno i wypisywana pod wykresem, a nie w środku SVG: wpisana w róg
    rysunku nachodziła na daty. Ważniejsze jednak, że **oś nie zaczyna się od zera**
    i człowiek ma prawo to wiedzieć bez mrużenia oczu — przy ławce stojącej
    świadomie na 35 kg oś od zera spłaszczyłaby wszystko w jedną kreskę.
    """
    if len(punkty_) < 2:
        return None
    wartosci = [p.wartosc for p in punkty_]
    return min(wartosci), max(wartosci)


def wykres(
    punkty_: list[Punkt],
    pierwszy: int,
    ostatni: int,
    jednostka: str,
    szerokosc: int = 400,
    wysokosc: int = 250,
) -> str:
    """Wykres liniowy jako SVG.

    Układ współrzędnych jest celowo bliski proporcjom telefonu (400×240), a SVG
    skaluje się z zachowaniem proporcji. Rozciąganie (`preserveAspectRatio="none"`)
    dawało owalne kropki i zgniecione podpisy — wykres wyglądał wtedy na zepsuty.

    Skala pionowa **nie zaczyna się od zera**, tylko od wartości minimalnej
    z zapasem. Przy ławce stojącej na 35 kg oś od zera spłaszczyłaby wszystko
    w jedną linię — a to właśnie drobne zmiany są tu treścią.
    Oś jest za to opisana wartościami, więc nie da się jej pomylić z osią od zera.

    Oś pozioma liczy treningi, nie tygodnie — dwa treningi
    w jednym tygodniu to dwa punkty. Punkty łączy jedna linia, także nad
    treningami, w których ćwiczenia nie było: pominięcie nie jest spadkiem.
    """
    if pierwszy > ostatni:
        pierwszy = ostatni

    widoczne = [p for p in punkty_ if pierwszy <= p.nr <= ostatni]
    if not widoczne:
        return ""

    wartosci = [p.wartosc for p in widoczne]
    minimum, maksimum = min(wartosci), max(wartosci)
    rozstep = maksimum - minimum
    margines = max(rozstep * 0.16, abs(maksimum) * 0.05, 1)
    surowe_lo, surowe_hi = minimum - margines, maksimum + margines
    krok = _ladny_krok((surowe_hi - surowe_lo) / 4)
    lo = math.floor(surowe_lo / krok) * krok
    hi = math.ceil(surowe_hi / krok) * krok

    gora, dol = 28, wysokosc - 34
    lewo, prawo = 44, szerokosc - 10
    rozpietosc = max(1, ostatni - pierwszy)

    def x(nr: int) -> float:
        return lewo + (prawo - lewo) * (nr - pierwszy) / rozpietosc

    def y(v: float) -> float:
        return dol - (dol - gora) * (v - lo) / (hi - lo)

    poziomy = []
    liczba_poziomow = round((hi - lo) / krok)
    for i in range(liczba_poziomow + 1):
        wartosc = lo + krok * i
        yy = y(wartosc)
        poziomy.append(
            f'<line class="siatka" x1="{lewo}" y1="{yy:.1f}" x2="{prawo}" y2="{yy:.1f}" />'
            f'<text class="etykieta-svg os-y" x="{lewo - 7}" y="{yy + 4:.1f}" '
            f'text-anchor="end">{_kg(wartosc)}</text>'
        )

    linie = []
    if len(widoczne) > 1:
        wspolrzedne = " ".join(f"{x(p.nr):.1f},{y(p.wartosc):.1f}" for p in widoczne)
        linie.append(f'<polyline class="linia" points="{wspolrzedne}" />')

    kropki = []
    for p in widoczne:
        klasa = "kropka" if p.pewny else "kropka niepewna"
        kropki.append(
            f'<circle class="{klasa}" cx="{x(p.nr):.1f}" cy="{y(p.wartosc):.1f}" r="4.5">'
            f"<title>Trening {p.nr}, {p.data.strftime('%d.%m.%Y')}: {p.podpis}</title></circle>"
        )

    podpisy = []
    # Najwyżej ok. 8 podpisów, żeby się nie zlewały; ostatni trening zawsze podpisany.
    krok_podpisu = max(1, math.ceil((ostatni - pierwszy + 1) / 8))
    for nr in range(pierwszy, ostatni + 1):
        if (nr - pierwszy) % krok_podpisu and nr != ostatni:
            continue
        if nr != ostatni and ostatni - nr < krok_podpisu / 2:
            continue
        podpisy.append(
            f'<text class="etykieta-svg" x="{x(nr):.1f}" y="{wysokosc - 7}" '
            f'text-anchor="middle">{nr}</text>'
        )

    return (
        f'<svg class="wykres" viewBox="0 0 {szerokosc} {wysokosc}" '
        f'role="img" aria-label="Wykres postępu">'
        f'<text class="etykieta-svg jednostka" x="{lewo}" y="14">{jednostka}</text>'
        + "".join(poziomy)
        + "".join(linie)
        + "".join(kropki)
        + "".join(podpisy)
        + "</svg>"
    )
