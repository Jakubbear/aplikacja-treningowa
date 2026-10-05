-- 0008_kolejnosc-w-sesji.sql — kolejność kart w trwającym treningu
--
-- Ćwiczenia robi się często w innej kolejności niż plan (talerze, zajęty sprzęt,
-- samopoczucie). Przycisk „▶ Robię teraz" przestawia kartę, żeby ekran szedł za
-- ćwiczącym, a przy korekcie planu było widać, w jakiej kolejności naprawdę ćwiczył.
--
-- Dwie różne rzeczy, świadomie rozdzielone:
--   * kolejność EKRANU — ta tabela; zapisuje zamiar, także przed pierwszą serią;
--   * kolejność WYKONANIA — wyprowadzana z `min(recorded_at)` serii per pozycja,
--     bo czas zapisu serii nie kłamie i nie wymaga od nikogo dodatkowego klikania.
--
-- Kluczem jest pozycja planu, nie ćwiczenie: po podmianie ćwiczenia karta zostaje
-- tą samą kartą. Brak wierszy znaczy „kolejność z planu" — tabela zapełnia się
-- dopiero przy pierwszym przestawieniu.

begin;

create table training.performed_item_order (
    session_id      bigint not null references training.performed_session(id) on delete cascade,
    planned_item_id bigint not null references training.planned_item(id),
    position        int    not null check (position > 0),
    primary key (session_id, planned_item_id)
);

-- Zamknięty trening ma zamrożoną także kolejność — ta sama zasada co przy seriach.
create function training.guard_closed_order() returns trigger as $guard$
declare
    is_closed boolean;
begin
    select closed_at is not null into is_closed
      from training.performed_session
     where id = coalesce(new.session_id, old.session_id);

    if is_closed then
        raise exception 'sesja % jest zamknieta: kolejnosci nie da sie zmienic',
            coalesce(new.session_id, old.session_id);
    end if;
    return coalesce(new, old);
end;
$guard$ language plpgsql;

create trigger guard_closed_order
    before insert or update or delete on training.performed_item_order
    for each row execute function training.guard_closed_order();

commit;
