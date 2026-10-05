-- 0006_barki-przedramiona.sql — barki i przedramiona
--
-- Katalog wcześniej nie miał ani barków, ani przedramion.
-- Bez hantli przedramiona idą uginaniem nachwytem na gryfie łamanym,
-- a barki wyciskaniem sztangi prostej na siedząco, zaraz po ławce (ta sama sztanga,
-- tylko zdejmuje się talerze).

begin;

insert into training.exercise
    (slug, name, equipment, body_part, default_bar_weight_kg, measure, notes)
values
    ('wyciskanie-nad-glowe-siedzac', 'Wyciskanie nad głowę — siedząc, sztanga',
     'sztanga prosta', 'barki', 20, 'reps',
     'Siedząc na ławce, plecy oparte albo proste. Sztanga 20 kg wliczana do obciążenia. ' ||
     'Idzie po ławce płaskiej na tej samej sztandze — zdejmuje się same piątki.'),

    ('uginanie-nachwytem-gryf-lamany', 'Uginanie nachwytem — gryf łamany',
     'gryf łamany', 'przedramiona', 7, 'reps',
     'Dłonie skierowane w dół. Pracuje głównie ramienno-promieniowy — grubość ' ||
     'przedramienia przy łokciu. Gryf 7 kg wliczany do obciążenia.')
  on conflict (slug) do nothing;

insert into training.exercise_alias (alias, exercise_id)
select a.alias, e.id
  from (values
        ('wyciskanie nad glowe',      'wyciskanie-nad-glowe-siedzac'),
        ('wyciskanie zolnierskie',    'wyciskanie-nad-glowe-siedzac'),
        ('ohp',                       'wyciskanie-nad-glowe-siedzac'),
        ('uginanie nachwytem',        'uginanie-nachwytem-gryf-lamany'),
        ('reverse curl',              'uginanie-nachwytem-gryf-lamany')
       ) as a(alias, slug)
  join training.exercise e on e.slug = a.slug
  on conflict (alias) do nothing;

commit;
