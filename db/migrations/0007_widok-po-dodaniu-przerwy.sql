-- 0007_widok-po-dodaniu-przerwy.sql — odświeżenie widoku po migracji 0006
--
-- PUŁAPKA, która kosztowała jeden błąd 500 na żywo:
-- `training.performed_set_current` jest zdefiniowany jako `select ps.* from performed_set ps`.
-- PostgreSQL **rozwija `*` w momencie tworzenia widoku** i zapamiętuje listę kolumn.
-- Dodanie kolumny do tabeli NIE dokłada jej do widoku — a aplikacja czyta wyłącznie
-- z widoku (tak jak każe nagłówek `db.py`). Po migracji 0006 kolumna `rest_seconds`
-- istniała w tabeli i nie istniała w widoku.
--
-- Osobna migracja, a nie poprawka w 0006, bo 0006 została już wykonana na produkcji.
-- Przy odtwarzaniu bazy od zera obie wykonają się po kolei i dadzą ten sam wynik.
--
-- `create or replace view` wystarczy: nowa kolumna dochodzi na końcu listy, a kolumny
-- istniejące zachowują nazwy, typy i kolejność — tylko wtedy PostgreSQL to przyjmuje.
--
-- **Do zapamiętania przy każdej następnej kolumnie w `performed_set`:** dopisanie jej
-- do tabeli to połowa roboty. Druga połowa jest tutaj.

begin;

create or replace view training.performed_set_current as
select ps.*
  from training.performed_set ps
 where not exists (
       select 1
         from training.performed_set nastepnik
        where nastepnik.supersedes = ps.id
 );

commit;
