#!/usr/bin/env sh
# Zakłada schemat treningowy w bazie, która już stoi.
#
#   docker compose up -d
#   sh db/zaloz.sh
#
# Kolejność jest wiążąca i nie jest alfabetyczna:
#
#   1. migrations/0001_training.sql   — schemat, triggery, widoki
#   2. seeds/*.sql                    — katalog ćwiczeń
#   3. migrations/0002 i dalsze       — poprawki, z których część
#                                       AKTUALIZUJE wiersze z seeda
#
# Migracja 0002 poprawia wagę gryfu w katalogu, więc musi wejść PO seedzie.
#
# Seed nie jest idempotentny: drugie uruchomienie wywali się na `slug unique`.
# Tak ma być — to sygnał, że baza nie była pusta.

set -e
KONTENER="${KONTENER:-postgres}"
BAZA="${BAZA:-trening}"
UZYTKOWNIK="${UZYTKOWNIK:-trening}"
KATALOG="$(cd "$(dirname "$0")" && pwd)"
# `docker compose` musi widzieć docker-compose.yml, więc stajemy w korzeniu repo
# niezależnie od tego, skąd skrypt został odpalony.
cd "$KATALOG/.."

wgraj() {
  echo "→ $1"
  docker compose exec -T "$KONTENER" \
    psql -U "$UZYTKOWNIK" -d "$BAZA" -v ON_ERROR_STOP=1 -q < "$1"
}

wgraj "$KATALOG/migrations/0001_training.sql"

for plik in "$KATALOG"/seeds/*.sql; do
  wgraj "$plik"
done

for plik in "$KATALOG"/migrations/*.sql; do
  case "$plik" in */0001_*) continue ;; esac
  wgraj "$plik"
done

echo
echo "Gotowe. Sprawdzenie:"
docker compose exec -T "$KONTENER" psql -U "$UZYTKOWNIK" -d "$BAZA" -c \
  "select count(*) as cwiczen from training.exercise"
