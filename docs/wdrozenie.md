# Wdrożenie

## Lokalnie, do popróbowania

Opisane w [README](../README.md). Krótko: `docker compose up -d --build`,
potem `sh db/zaloz.sh`, potem wsad planu.

## Na własnym serwerze w domu

Aplikacja chodzi na **Raspberry Pi 4** i obraz jest pod to zbudowany:
`python:3.12-slim`, wszystkie zależności mają koła `aarch64`, więc kontener
nie potrzebuje kompilatora. Na zwykłym x86 zbuduje się tak samo.

Skopiuj repozytorium na serwer i uruchom tam to samo:

```sh
scp -r aplikacja-treningowa/ uzytkownik@serwer.local:~/
ssh uzytkownik@serwer.local
cd ~/aplikacja-treningowa
mkdir -p sekrety && head -c 24 /dev/urandom | base64 > sekrety/haslo-bazy
chmod 600 sekrety/haslo-bazy
docker compose up -d --build
sh db/zaloz.sh
```

Aplikacja odpowiada wtedy pod `http://serwer.local:8002` z każdego urządzenia
w sieci domowej. Dodaj ten adres do ekranu głównego telefonu.

**Adres z DHCP nie jest gwarancją.** Jeśli łapiesz się na wpisywaniu
`http://192.168.x.x:8002`, ustaw na routerze stałą dzierżawę albo polegaj
na nazwie `.local`.

**Rozpoznawanie nazw `.local` potrafi chwilowo paść** w trakcie sesji SSH.
Polecenie wywala się na „Name or service not known", mimo że serwer działa.
Powtórzenie zwykle pomaga — to nie jest awaria.

## Aktualizacja kodu na serwerze

```sh
cd ~/aplikacja-treningowa
git pull          # albo scp nowych plików
docker compose build && docker compose up -d
```

Migracje **nie wjeżdżają same**. Nową migrację wgrywasz świadomie:

```sh
docker compose exec -T postgres psql -U trening -d trening -v ON_ERROR_STOP=1 \
  < db/migrations/0008_cokolwiek.sql
```

Migracje są w transakcji — przy błędzie nie zostaje nic w połowie.

## Dostęp z zewnątrz — przeczytaj, zanim wystawisz

**Aplikacja nie ma logowania.** Wystawiona wprost na internet jest otwarta
dla każdego, kto trafi na adres. Potrzebna jest bramka przed nią.

Sprawdzone rozwiązanie to **Cloudflare Tunnel + Cloudflare Access**: tunel wypuszcza
`http://localhost:8002` pod własną domeną, a Access wymaga zalogowania mailem
(sesja 24 h). Żadnego portu nie trzeba otwierać na routerze.

**Kolejność jest wiążąca: najpierw Access, potem DNS.** Odwrotna zostawia okno,
w którym Twój adres odpowiada całemu internetowi bez żadnej ochrony. To nie jest
teoretyczne — to się zdarzyło i było wychwycone po fakcie.

Drobiazg z panelu: nowy Cloudflare One trzyma regułę `Include` **wewnątrz
polityki**, nie na ekranie tworzenia aplikacji. Łatwo wyklikać aplikację
bez żadnej reguły i myśleć, że jest chroniona.

Alternatywy równie dobre: WireGuard albo Tailscale do sieci domowej i wtedy
nic nie wystawiasz w ogóle. Najprostsze, jeśli tylko Ty masz z tego korzystać.

## Pokazanie komuś kopii bez ryzyka

Zmienna `HEALTH_PREVIEW_READONLY=1` blokuje wszystkie metody poza `GET` i `HEAD`.
Kontener pokazuje wtedy realne dane, ale nie może ich zmienić:

```yaml
    environment:
      HEALTH_PREVIEW_READONLY: "1"
```

## Kopia bazy

Compose trzyma dane w wolumenie `dane-bazy`. Zrzut:

```sh
docker compose exec -T postgres pg_dump -U trening -d trening \
  > kopia-$(date +%F).sql
```

Odtworzenie do pustej bazy:

```sh
docker compose exec -T postgres psql -U trening -d trening < kopia-2026-01-15.sql
```

Rób to. Historia treningu odtwarza się wyłącznie z bazy — w plikach jej nie ma.

## Monitoring

`GET /zdrowie` sprawdza aplikację **razem z połączeniem do bazy**. Podepnij go
pod cokolwiek, co pinguje usługi (Uptime Kuma, Healthchecks). Odpowiedź
`{"status": "ok"}` znaczy, że baza też odpowiada.

## Czego brakuje i wypadałoby dopisać

- **Testów automatycznych.** Sprawdzenie było ręcznym przebiegiem przez HTTP
  na osobnej bazie. Nie ma zestawu w pytest.
- **Logowania.** Patrz wyżej — całość zakłada bramkę przed aplikacją.
- **Migracji „w dół".** Nie ma rollbacku; wycofanie zmiany to napisanie
  kolejnej migracji.
