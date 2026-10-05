-- 0001_training.sql — warstwa treningowa
-- Rozdziela PLAN (zamiar zapisany z wyprzedzeniem) od WYKONANIA (fakt).
-- Decyzje stojące za tym schematem: docs/decyzje.md.

begin;

create schema if not exists training;

-- ---------------------------------------------------------------- katalog

create table training.exercise (
    id                    bigserial primary key,
    slug                  text not null unique,
    name                  text not null,
    equipment             text,
    body_part             text,
    -- waga samego gryfu/sprzętu; podstawiana domyślnie przy zapisie serii,
    -- żeby nie powtórzyła się rozbieżność konwencji zapisu ciężaru
    default_bar_weight_kg numeric(5,2) not null default 0,
    measure               text not null default 'reps'
                          check (measure in ('reps', 'time')),
    notes                 text,
    created_at            timestamptz not null default now()
);

-- To samo ćwiczenie bywa zapisywane pod kilkoma nazwami
-- („Uginanie sztangą łamaną" / „Uginanie ramion gryfem łamanym"). Aliasy pozwalają
-- wciągnąć taką historię bez rozjeżdżania katalogu.
create table training.exercise_alias (
    alias       text primary key,
    exercise_id bigint not null references training.exercise(id) on delete cascade,
    check (alias = lower(alias))
);

-- ---------------------------------------------------------------- plan

create table training.training_plan (
    id         bigserial primary key,
    label      text not null,
    starts_on  date not null,
    ends_on    date not null,
    author     text not null default 'agent',
    version    int  not null default 1,
    created_at timestamptz not null default now(),
    -- plan się nie kasuje: nowa wersja wskazuje poprzednią (twarda zasada 1)
    supersedes bigint unique references training.training_plan(id),
    check (ends_on >= starts_on)
);

create table training.planned_session (
    id         bigserial primary key,
    plan_id    bigint not null references training.training_plan(id) on delete cascade,
    label      text not null,                        -- 'Tydzień 3'
    planned_on date not null,
    location   text not null default 'dom' check (location in ('dom', 'trasa')),
    ordinal    int  not null,
    notes      text,
    unique (plan_id, ordinal)
);

create table training.planned_item (
    id                bigserial primary key,
    session_id        bigint not null references training.planned_session(id) on delete cascade,
    ordinal           int    not null,
    exercise_id       bigint not null references training.exercise(id),
    sets              int    not null check (sets > 0),
    -- plan jest ZAKRESEM, nie punktem: bez tego nie da się odróżnić
    -- przekroczenia zamiaru od zwykłej realizacji
    reps_min          int,
    reps_max          int,
    duration_seconds  int,                           -- plank i spółka
    weight_planned_kg numeric(6,2),                  -- łącznie z gryfem
    superset_group    text,                          -- 'A' dla ćwiczeń 3+4 w serii łączonej
    rest_seconds      int default 120,               -- standard przyjęty w projekcie
    progression_note  text,
    unique (session_id, ordinal),
    check (reps_max is null or reps_min is null or reps_max >= reps_min),
    check (reps_min is not null or duration_seconds is not null)
);

-- ---------------------------------------------------------------- wykonanie

create table training.performed_session (
    id                 bigserial primary key,
    -- nullable: trening poza planem też ma prawo istnieć
    planned_session_id bigint references training.planned_session(id),
    performed_on       date not null,
    location           text not null default 'dom' check (location in ('dom', 'trasa')),
    feeling            text,
    notes              text,
    started_at         timestamptz not null default now(),
    -- dopóki null, trening trwa i poprawki są zwykłym UPDATE
    closed_at          timestamptz
);

create table training.performed_set (
    id                           bigserial primary key,
    session_id                   bigint not null references training.performed_session(id) on delete cascade,
    planned_item_id              bigint references training.planned_item(id),
    exercise_id                  bigint not null references training.exercise(id),
    -- wypełnione, gdy ćwiczenie zostało podmienione względem planu
    substituted_from_exercise_id bigint references training.exercise(id),
    set_number                   int not null check (set_number > 0),
    repetitions                  int,
    duration_seconds             int,
    bar_weight_kg                numeric(5,2) not null default 0,
    added_weight_kg              numeric(6,2) not null default 0,
    weight_total_kg              numeric(6,2)
                                 generated always as (bar_weight_kg + added_weight_kg) stored,
    note                         text,
    recorded_at                  timestamptz not null default now(),
    -- korekta po zamknięciu sesji nie nadpisuje: wskazuje poprzednika
    supersedes                   bigint unique references training.performed_set(id),
    check (repetitions is not null or duration_seconds is not null)
);

create index on training.performed_set (session_id);
create index on training.performed_set (exercise_id, recorded_at desc);

-- ---------------------------------------------------------------- niezmienność

-- Zasada niezmienności wykonania wymuszona w bazie, nie w aplikacji: po zamknięciu
-- sesji nie da się zatrzeć wcześniejszej wersji zapisu.
create function training.guard_closed_session() returns trigger as $guard$
declare
    is_closed boolean;
begin
    select closed_at is not null into is_closed
      from training.performed_session
     where id = coalesce(new.session_id, old.session_id);

    if is_closed then
        if tg_op = 'UPDATE' then
            raise exception
                'sesja % jest zamknieta: korekta musi byc nowym wierszem z supersedes',
                coalesce(new.session_id, old.session_id);
        elsif tg_op = 'DELETE' then
            raise exception
                'sesja % jest zamknieta: kasowanie serii zabronione', old.session_id;
        elsif tg_op = 'INSERT' and new.supersedes is null then
            raise exception
                'sesja % jest zamknieta: nowa seria musi wskazywac, co zastepuje',
                new.session_id;
        end if;
    end if;

    return coalesce(new, old);
end;
$guard$ language plpgsql;

create trigger guard_closed
    before insert or update or delete on training.performed_set
    for each row execute function training.guard_closed_session();

-- ---------------------------------------------------------------- widoki

-- Obowiązujący stan: serie, których nic nie zastąpiło.
create view training.performed_set_current as
select ps.*
  from training.performed_set ps
 where not exists (
       select 1
         from training.performed_set nastepnik
        where nastepnik.supersedes = ps.id
 );

-- To czyta agent na koniec tygodnia, żeby zaktualizować resztę planu.
create view training.deviation as
select
    plan_s.label                as plan_label,
    plan_s.planned_on,
    perf_s.performed_on,
    ex.name                     as exercise,
    pi.sets                     as sets_planned,
    count(cur.id)               as sets_done,
    pi.reps_min,
    pi.reps_max,
    min(cur.repetitions)        as reps_min_done,
    max(cur.repetitions)        as reps_max_done,
    pi.weight_planned_kg,
    max(cur.weight_total_kg)    as weight_max_done,
    bool_or(cur.substituted_from_exercise_id is not null) as substituted,
    bool_or(pi.reps_max is not null and cur.repetitions > pi.reps_max) as exceeded_plan
  from training.planned_item pi
  join training.planned_session plan_s on plan_s.id = pi.session_id
  join training.exercise ex on ex.id = pi.exercise_id
  left join training.performed_session perf_s
         on perf_s.planned_session_id = plan_s.id
  left join training.performed_set_current cur
         on cur.session_id = perf_s.id
        and (cur.planned_item_id = pi.id or cur.exercise_id = pi.exercise_id)
 group by plan_s.label, plan_s.planned_on, perf_s.performed_on, ex.name,
          pi.sets, pi.reps_min, pi.reps_max, pi.weight_planned_kg;

commit;
