-- 0006_faktyczna-przerwa.sql — ile faktycznie trwała przerwa przed serią
--
-- Plan mówi, ile przerwa ma trwać (`planned_item.rest_seconds`). Do tej pory nie było
-- gdzie zapisać, ile trwała naprawdę. Standardem są dwie minuty, ale bywa, że nie
-- da się odpocząć do końca — i to ma być widać w statystykach, a nie zgubione.
--
-- Kolumna opisuje przerwę PRZED tą serią, nie po niej. Pierwsza seria ćwiczenia
-- zostaje z `NULL`: przerwa przed nią to czas po poprzednim ćwiczeniu, czyli zupełnie
-- inna wielkość, i nie udajemy, że ją mierzymy.
--
-- `NULL` znaczy „nie zapisano", nie „zero". Zero byłoby twierdzeniem, że serie poszły
-- bez żadnej przerwy — a to jest informacja, nie brak informacji.

begin;

alter table training.performed_set
    add column rest_seconds int check (rest_seconds >= 0);

comment on column training.performed_set.rest_seconds is
    'Faktyczna przerwa PRZED tą serią, w sekundach. NULL = nie zapisano. '
    'Standard przyjęty w tym projekcie: 120 s. Pierwsza seria ćwiczenia '
    'zostaje pusta, bo przerwa przed nią należy do poprzedniego ćwiczenia.';

commit;
