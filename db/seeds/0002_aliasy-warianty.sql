-- 0002_aliasy-warianty.sql — warianty nazw tych samych ćwiczeń
--
-- Te same ćwiczenia bywały zapisywane w dwóch konwencjach:
-- „Wyciskanie sztangi na ławce płaskiej" oraz „Wyciskanie sztangi — ławka płaska".
-- Bez tych aliasów backfill historii nie dopasowałby połowy pozycji.
--
-- Aliasy trzymamy w formie znormalizowanej: małe litery, myślniki zamienione
-- na spacje, pojedyncze odstępy. Importer normalizuje tak samo obie strony.

begin;

insert into training.exercise_alias (alias, exercise_id)
select a.alias, e.id
  from (values
        ('wyciskanie sztangi lawka plaska',   'wyciskanie-lawka-plaska'),
        ('wyciskanie sztangi lawka skosna',    'wyciskanie-lawka-skosna'),
        ('uginanie ramion gryf lamany',        'uginanie-gryf-lamany'),
        ('uginanie ramion gryfem lamanym',     'uginanie-gryf-lamany'),
        ('uginanie sztanga lamana',            'uginanie-gryf-lamany'),
        ('wyciskanie na lawce plaskiej',       'wyciskanie-lawka-plaska'),
        ('wyciskanie sztangi na lawce plaskiej','wyciskanie-lawka-plaska'),
        ('wyciskanie na lawce skosnej',        'wyciskanie-lawka-skosna'),
        ('wyciskanie sztangi na lawce skosnej','wyciskanie-lawka-skosna'),
        ('goblet squat',                       'goblet-squat'),
        ('pullover',                           'pullover-hantlem'),
        ('pullover hantlem',                   'pullover-hantlem'),
        ('plank',                              'plank'),
        ('bird dog',                           'bird-dog')
       ) as a(alias, slug)
  join training.exercise e on e.slug = a.slug
  on conflict (alias) do nothing;

commit;
