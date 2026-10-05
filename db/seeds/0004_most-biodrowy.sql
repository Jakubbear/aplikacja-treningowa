-- 0004_most-biodrowy.sql — ruch na tylny łańcuch
--
-- Program długo nie miał ani jednego ćwiczenia na tylny łańcuch. To typowa luka
-- w planie ułożonym wokół wyciskania i podciągania.
--
-- Most biodrowy wchodzi jako ruch BEZ obciążenia osiowego: nie dokłada kompresji
-- kręgosłupa, więc nadaje się także wtedy, gdy odcinek lędźwiowy
-- daje o sobie znać.

begin;

insert into training.exercise
    (slug, name, equipment, body_part, default_bar_weight_kg, measure, notes)
values
    ('most-biodrowy', 'Most biodrowy',
     'masa ciała', 'posladki', 0, 'reps',
     'Wersja obunóż, potem jednonóż — wtedy zapis w powtórzeniach na stronę.')
  on conflict (slug) do nothing;

insert into training.exercise_alias (alias, exercise_id)
select a.alias, e.id
  from (values
        ('most biodrowy',        'most-biodrowy'),
        ('glute bridge',         'most-biodrowy'),
        ('unoszenie bioder',     'most-biodrowy')
       ) as a(alias, slug)
  join training.exercise e on e.slug = a.slug
  on conflict (alias) do nothing;

commit;
