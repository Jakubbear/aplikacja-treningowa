-- 0003_cwiczenia-plecy-biceps.sql — podciąganie i rozdzielone uginanie
--
-- Doszły podciągania w dwóch chwytach oraz rozdzielenie uginania na gryfie łamanym
-- na chwyt standardowy i wąski. Ławka skośna i pullover wypadły z programu — zostają
-- w katalogu, bo odwołuje się do nich starsza historia.

begin;

insert into training.exercise
    (slug, name, equipment, body_part, default_bar_weight_kg, measure, notes)
values
    ('podciaganie-podchwytem', 'Podciąganie podchwytem',
     'drążek', 'plecy', 0, 'reps',
     'Zapis bywa listą powtórzeń na serię, np. 4 / 4 / 3.'),

    ('podciaganie-nachwytem', 'Podciąganie nachwytem',
     'drążek', 'plecy', 0, 'reps', null),

    ('uginanie-gryf-lamany-wasko', 'Uginanie ramion — gryf łamany, wąski chwyt',
     'gryf łamany', 'biceps', 7, 'reps',
     'Chwyt na środkowej części gryfu, ręce blisko siebie. Gryf 7 kg w obciążeniu.')
  on conflict (slug) do nothing;

insert into training.exercise_alias (alias, exercise_id)
select a.alias, e.id
  from (values
        ('podciaganie podchwytem',                    'podciaganie-podchwytem'),
        ('podciaganie',                               'podciaganie-podchwytem'),
        ('podciaganie nachwytem',                     'podciaganie-nachwytem'),
        -- „Biceps — gryf łamany" bez dopisku to chwyt standardowy, czyli to samo
        -- ćwiczenie, które wcześniej nazywało się „Uginanie ramion".
        ('biceps gryf lamany',                        'uginanie-gryf-lamany'),
        ('biceps gryf lamany standardowy chwyt',      'uginanie-gryf-lamany'),
        ('biceps ez standard',                        'uginanie-gryf-lamany'),
        ('biceps gryf lamany waski chwyt',            'uginanie-gryf-lamany-wasko'),
        ('biceps ez wasko',                           'uginanie-gryf-lamany-wasko'),
        ('lawka plaska',                              'wyciskanie-lawka-plaska'),
        ('lawka skosna',                              'wyciskanie-lawka-skosna')
       ) as a(alias, slug)
  join training.exercise e on e.slug = a.slug
  on conflict (alias) do nothing;

commit;
