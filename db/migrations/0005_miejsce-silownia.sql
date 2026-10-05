-- 0005_miejsce-silownia.sql — trzecie miejsce treningu: siłownia
--
-- Dodane, zanim wartość zaczęła być potrzebna — świadomie, nie z zapasu.
--
-- To jest właściwy moment na taką zmianę: dopóki wartość nie zostanie użyta, jej
-- dodanie kosztuje jeden `check`. Później oznaczałoby albo zgadywanie, gdzie odbył
-- się trening zapisany jako „dom", albo osobną kolumnę na sprostowanie.
--
-- Kod jest bez polskich znaków, jak `dom` i `trasa` — to identyfikator, nie napis
-- dla człowieka. Za wyświetlenie „siłownia" odpowiada filtr `miejsce` w `main.py`.

begin;

alter table training.planned_session
    drop constraint planned_session_location_check;
alter table training.planned_session
    add constraint planned_session_location_check
    check (location in ('dom', 'trasa', 'silownia'));

alter table training.performed_session
    drop constraint performed_session_location_check;
alter table training.performed_session
    add constraint performed_session_location_check
    check (location in ('dom', 'trasa', 'silownia'));

comment on column training.performed_session.location is
    'Gdzie odbył się trening: dom, trasa albo silownia. '
    'Siłownia dodana 2026-09-13, jeszcze nieużywana.';

commit;
