-- 0002_ciezar-gryfu.sql — naprawa wagi gryfu w katalogu ćwiczeń
--
-- Zasada przyjęta w tym projekcie: KAŻDY zapisany ciężar jest łączny, razem z gryfem.
-- 35 kg na ławce to sztanga 20 kg + 15 kg talerzy, a 17 kg w goblecie i w uginaniu to
-- gryf łamany 7 kg + 10 kg talerzy.
--
-- W seedzie `0001_exercises.sql` ławka płaska i skośna mają `default_bar_weight_kg = 0`,
-- a goblet squat stoi jako 'hantel'. Aplikacja odejmuje tę wartość od ciężaru z planu,
-- żeby w formularzu podstawić to, co faktycznie nakładasz na gryf — więc przy zerze
-- kazałaby założyć 35 kg blachy zamiast 15 kg.
--
-- To NIE zmienia historii: `weight_total_kg` jest kolumną wyliczaną z wartości już
-- zapisanych, a ta migracja rusza wyłącznie katalog. Zapisane serie zostają takie,
-- jakie były.

begin;

update training.exercise
   set default_bar_weight_kg = 20,
       notes = coalesce(notes || ' ', '') ||
               'Sztanga prosta 20 kg. Zapis ciężaru jest łączny, razem z gryfem ' ||
               'razem z gryfem.'
 where slug in ('wyciskanie-lawka-plaska', 'wyciskanie-lawka-skosna');

-- Goblet squat robiony gryfem łamanym, nie hantlem: hantle odpadły, bo talerze 5 kg
-- obcinają zakres ruchu. 17 kg = 7 kg gryfu + 10 kg talerzy.
update training.exercise
   set default_bar_weight_kg = 7,
       equipment = 'gryf łamany',
       notes = coalesce(notes || ' ', '') ||
               'Trzymany gryfem łamanym — hantle odpadają, bo talerze 5 kg ' ||
               'ograniczają zakres ruchu.'
 where slug = 'goblet-squat';

commit;
