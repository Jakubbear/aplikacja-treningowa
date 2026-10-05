-- 0003_odczucia-cwiczenia.sql — ból i intensywność wysiłku, per ćwiczenie
--
-- Makieta z 2026-09-13 dokłada do karty ćwiczenia dwa pola, których schemat nie ma:
-- „Czy coś boli?" (tekst) oraz „Intensywność wysiłku" 1–10, gdzie 10 to upadek
-- mięśniowy. Oba dotyczą CAŁEGO ćwiczenia w danej sesji, nie pojedynczej serii —
-- dlatego nie idą do `performed_set`, tylko do osobnej tabeli.
--
-- Dlaczego nie kolumna w `performed_set`: ból i wysiłek wpisuje się raz, po ostatniej
-- serii. Trzymanie ich przy serii kazałoby albo powtarzać tę samą wartość w każdym
-- wierszu, albo wybierać jedną „właściwą" serię — i psułoby korektę przez `supersedes`,
-- bo nowy wiersz serii ciągnąłby za sobą odczucie, którego nikt nie poprawiał.
--
-- Dlaczego nie kolumna w `performed_session`: ból jest informacją o konkretnym ruchu.
-- „Lekki dyskomfort w prawym barku" przy wyciskaniu znaczy co innego niż przy
-- podciąganiu, a to właśnie ten rozdział ma czytać agent przy aktualizacji planu.
-- Ogólne wrażenie z treningu ma już swoje miejsce: `performed_session.feeling`.

begin;

create table training.performed_item_feedback (
    id              bigserial primary key,
    session_id      bigint not null references training.performed_session(id) on delete cascade,
    -- nullable tak samo jak w `performed_set`: ćwiczenie poza planem też ma prawo boleć
    planned_item_id bigint references training.planned_item(id),
    -- ćwiczenie FAKTYCZNIE wykonane; po podmianie to zamiennik, nie pozycja z planu
    exercise_id     bigint not null references training.exercise(id),
    pain_note       text,
    -- 10 = upadek mięśniowy, tak jak podpisano w makiecie
    effort          int check (effort between 1 and 10),
    recorded_at     timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    -- jedno odczucie na ćwiczenie w sesji; po tym kluczu idzie upsert z aplikacji
    unique (session_id, exercise_id),
    -- pusty wiersz nie ma po co istnieć
    check (pain_note is not null or effort is not null)
);

create index on training.performed_item_feedback (session_id);

-- Ta sama zasada co przy seriach: po zamknięciu sesji zapisu nie da się zatrzeć.
-- Różnica jest świadoma — tu nie ma `supersedes`, więc zamknięta sesja jest po prostu
-- zamknięta. Korekta odczucia po fakcie byłaby wspomnieniem, nie zapisem z treningu.
create function training.guard_closed_feedback() returns trigger as $guard$
declare
    is_closed boolean;
begin
    select closed_at is not null into is_closed
      from training.performed_session
     where id = coalesce(new.session_id, old.session_id);

    if is_closed then
        raise exception
            'sesja % jest zamknieta: odczucia do cwiczen sa juz nieedytowalne',
            coalesce(new.session_id, old.session_id);
    end if;

    return coalesce(new, old);
end;
$guard$ language plpgsql;

create trigger guard_closed_feedback
    before insert or update or delete on training.performed_item_feedback
    for each row execute function training.guard_closed_feedback();

commit;
