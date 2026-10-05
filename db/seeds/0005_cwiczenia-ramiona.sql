-- 0005_cwiczenia-ramiona.sql — ćwiczenia pod cel „grubsze ramię"
--
-- Triceps to około dwóch trzecich obwodu ramienia, a program długo nie miał na niego
-- ani jednego ruchu. Sprzęt był przy tym na miejscu od początku: ława ma przymocowane
-- drążki do dipów, a gryf łamany wystarcza do wyciskania francuskiego.
--
-- Klatka w tym bloku jest świadomie poza progresją — stąd uwaga przy dipach.

begin;

insert into training.exercise
    (slug, name, equipment, body_part, default_bar_weight_kg, measure, notes)
values
    ('dipy-na-drazkach', 'Dipy na drążkach przy ławce',
     'drążki przy ławce', 'triceps', 0, 'reps',
     'Tułów pionowo — pochylenie do przodu przenosi pracę z tricepsa na klatkę.'),

    ('wyciskanie-francuskie', 'Wyciskanie francuskie — gryf łamany',
     'gryf łamany', 'triceps', 7, 'reps',
     'Leżąc na ławce. Gryf 7 kg wliczany do obciążenia, jak przy uginaniu.'),

    ('podciaganie-chwyt-neutralny', 'Podciąganie chwytem neutralnym',
     'drążek', 'ramiona', 0, 'reps',
     'Uchwyty równoległe, dłonie zwrócone do siebie. Bierze ramienno-promieniowy ' ||
     'mocniej niż podchwyt, więc idzie pod cel „grubsze ramię", nie pod plecy.')
  on conflict (slug) do nothing;

insert into training.exercise_alias (alias, exercise_id)
select a.alias, e.id
  from (values
        ('dipy',                      'dipy-na-drazkach'),
        ('dipy na drazkach',          'dipy-na-drazkach'),
        ('pompki na porczach',        'dipy-na-drazkach'),
        ('wyciskanie francuskie',     'wyciskanie-francuskie'),
        ('francuskie',                'wyciskanie-francuskie'),
        ('lamacz czaszek',            'wyciskanie-francuskie'),
        ('podciaganie chwytem neutralnym', 'podciaganie-chwyt-neutralny'),
        ('podciaganie neutralnym',    'podciaganie-chwyt-neutralny'),
        ('podciaganie mlotkowe',      'podciaganie-chwyt-neutralny')
       ) as a(alias, slug)
  join training.exercise e on e.slug = a.slug
  on conflict (alias) do nothing;

commit;
