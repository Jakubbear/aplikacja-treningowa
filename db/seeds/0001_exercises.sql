-- 0001_exercises.sql — katalog ćwiczeń
--
-- Wyprowadzony z realnych zapisów treningowych, nie wymyślony. Aliasy to nazwy,
-- pod którymi te same ćwiczenia faktycznie się pojawiały — służą dopasowaniu
-- przy imporcie historii z zewnątrz.
--
-- To jest katalog pod konkretny domowy sprzęt: ława z drążkami do dipów, sztanga
-- prosta 20 kg, gryf łamany 7 kg, drążek. Potraktuj go jako punkt wyjścia.
--
-- `default_bar_weight_kg` odzwierciedla zasadę projektu: waga gryfu wchodzi
-- do zapisu obciążenia.

begin;

insert into training.exercise
    (slug, name, equipment, body_part, default_bar_weight_kg, measure, notes)
values
    ('wyciskanie-lawka-plaska', 'Wyciskanie sztangi — ławka płaska',
     'sztanga', 'klatka', 0, 'reps', null),

    ('wyciskanie-lawka-skosna', 'Wyciskanie sztangi — ławka skośna',
     'sztanga', 'klatka', 0, 'reps', null),

    ('goblet-squat', 'Goblet squat',
     'hantel', 'nogi', 0, 'reps', null),

    ('uginanie-gryf-lamany', 'Uginanie ramion — gryf łamany',
     'gryf łamany', 'biceps', 7, 'reps',
     'Gryf 7 kg wliczany do obciążenia.'),

    ('pullover-hantlem', 'Pullover hantlem',
     'hantel', 'klatka', 0, 'reps', null),

    ('plank', 'Plank',
     'masa ciała', 'core', 0, 'time', null),

    ('bird-dog', 'Bird dog',
     'masa ciała', 'core', 0, 'reps',
     'Zapis w powtórzeniach na stronę.');

insert into training.exercise_alias (alias, exercise_id)
select a.alias, e.id
  from (values
        ('wyciskanie na ławce płaskiej',        'wyciskanie-lawka-plaska'),
        ('wyciskanie sztangi na ławce płaskiej', 'wyciskanie-lawka-plaska'),
        -- celowo BEZ aliasu 'wyciskanie sztangi': w zapisach bywa to nagłówek
        -- obu ławek naraz, więc przypisałby skośną do płaskiej
        ('wyciskanie na ławce skośnej',          'wyciskanie-lawka-skosna'),
        ('wyciskanie sztangi na ławce skośnej',  'wyciskanie-lawka-skosna'),
        ('goblet squat',                         'goblet-squat'),
        ('uginanie sztangą łamaną',              'uginanie-gryf-lamany'),
        ('uginanie ramion gryfem łamanym',       'uginanie-gryf-lamany'),
        ('uginanie ramion',                      'uginanie-gryf-lamany'),
        ('pullover',                             'pullover-hantlem'),
        ('pullover hantlem',                     'pullover-hantlem'),
        ('plank',                                'plank'),
        ('bird dog',                             'bird-dog')
       ) as a(alias, slug)
  join training.exercise e on e.slug = a.slug;

commit;
