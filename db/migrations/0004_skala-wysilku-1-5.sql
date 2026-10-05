-- 0004_skala-wysilku-1-5.sql — intensywność wysiłku schodzi z 1–10 na 1–5
--
-- Zmiana po pierwszym realnym przejściu aplikacji w trakcie treningu.
-- Dwa powody, oba z tego przejścia:
--
-- 1. Dziesięć pól w rzędzie ma na ekranie 390 px po ok. 30 px szerokości. To mniej
--    niż opuszek kciuka, a wybór robi się spoconą ręką między seriami.
-- 2. Różnica między „7" a „8" jest zmyślona. Pięć stopni da się odróżnić czuciem
--    i nazwać słowami: lekko, spokojnie, solidnie, ciężko, upadek.
--
-- Aplikacja pilnuje zakresu 1–5 od 2026-09-13 (`_wysilek` w `main.py`), więc ta
-- migracja tylko dociąga bazę do tego, co i tak jest zapisywane.
--
-- UWAGA — migracja CELOWO się wywali, jeśli w bazie leży wartość powyżej 5.
-- Nie przeliczamy starych ocen na nową skalę: „8 na dziesięć" nie jest tym samym
-- co „4 na pięć", a zgadywanie przelicznika zamieniłoby zapis obserwacji w zapis
-- domysłu. Wiersze powyżej 5 trzeba najpierw rozstrzygnąć ręcznie — na dzień
-- napisania tej migracji jedyne takie wiersze pochodzą z sesji testowej 41.

begin;

do $sprawdz$
declare
    ile int;
begin
    select count(*) into ile
      from training.performed_item_feedback
     where effort > 5;

    if ile > 0 then
        raise exception
            'w bazie jest % ocen wysilku powyzej 5 — rozstrzygnij je recznie przed ta migracja',
            ile;
    end if;
end;
$sprawdz$;

alter table training.performed_item_feedback
    drop constraint performed_item_feedback_effort_check;

alter table training.performed_item_feedback
    add constraint performed_item_feedback_effort_check
    check (effort between 1 and 5);

comment on column training.performed_item_feedback.effort is
    'Intensywność 1–5: 1 lekko, 2 spokojnie, 3 solidnie, 4 ciężko, 5 upadek mięśniowy. '
    'Skala zmieniona z 1–10 dnia 2026-09-13.';

commit;
