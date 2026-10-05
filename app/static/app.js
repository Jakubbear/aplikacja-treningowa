/* Zapis w tle dla pól, które już istnieją w bazie.
 *
 * To jest wyłącznie ulepszenie: każdy formularz ma swój przycisk „zapisz" i działa
 * bez tego pliku. Skrypt chowa przycisk dopiero wtedy, gdy sam wstanie — więc telefon
 * z zablokowanym JS-em dostaje pełną aplikacją, tylko z dodatkowym kliknięciem.
 *
 * Świadomie NIE obejmuje formularzy tworzących serię. Tam zapis zmienia stronę
 * (dochodzi wiersz, przesuwa się numeracja), więc potwierdzenie haczykiem
 * i przeładowanie są uczciwsze niż ciche dopisanie czegoś do bazy.
 */

(function () {
  "use strict";

  var OPOZNIENIE_ZNIKNIECIA = 1500;

  function oznacz(form, stan) {
    var wiersz = form.closest("li, section") || form;
    wiersz.classList.remove("zapisano", "blad-zapisu");
    if (stan) {
      wiersz.classList.add(stan);
      if (stan === "zapisano") {
        setTimeout(function () {
          wiersz.classList.remove("zapisano");
        }, OPOZNIENIE_ZNIKNIECIA);
      }
    }
  }

  function wyslij(form) {
    var przycisk = form.querySelector(".zapisz");
    form.classList.add("w-locie");

    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "fetch" },
      redirect: "follow",
    })
      .then(function (odp) {
        if (!odp.ok) throw new Error("HTTP " + odp.status);
        oznacz(form, "zapisano");
      })
      .catch(function () {
        // Sieć padła w połowie treningu: pokazujemy przycisk z powrotem,
        // żeby dało się ponowić ręcznie, i nie udajemy, że zapis przeszedł.
        oznacz(form, "blad-zapisu");
        if (przycisk) przycisk.hidden = false;
      })
      .then(function () {
        form.classList.remove("w-locie");
      });
  }

  document.querySelectorAll("form[data-autozapis]").forEach(function (form) {
    var przycisk = form.querySelector(".zapisz");
    if (przycisk) przycisk.hidden = true;

    form.addEventListener("change", function (zdarzenie) {
      // Pola bez `name` nic nie wysyłają — a takim jest przełącznik „boli / nie boli".
      // Bez tego samo rozwinięcie pytania strzelało zapisem do bazy.
      var cel = zdarzenie.target;
      if (cel && !cel.name) return;
      wyslij(form);
    });

    // Enter w polu tekstowym ma zapisać, a nie przeładować strony.
    form.addEventListener("submit", function (zdarzenie) {
      zdarzenie.preventDefault();
      wyslij(form);
    });
  });
})();

/* Zapis nowej serii odporny na zacięcie sieci.
 *
 * 4.10 trzy zapisy w ogóle nie doszły do serwera: serwer odpowiadał w ułamku
 * sekundy na wszystko, co do niego dotarło, a telefon kręcił się bez końca.
 * Zwykły formularz nie ma wtedy wyjścia — zostaje odświeżenie, a odświeżenie
 * kasuje wpisane liczby. Stąd trzy rzeczy:
 *
 * 1. Szkic: każda wpisana liczba ląduje w pamięci telefonu i wraca po odświeżeniu.
 * 2. Limit czasu: po LIMIT_CZASU ms zapis jest przerywany, wiersz robi się czerwony,
 *    a liczby zostają na miejscu — wystarczy ponownie kliknąć haczyk.
 * 3. Identyfikator zapisu: ponowienie niesie ten sam `zapis_id`, więc gdy pierwsza
 *    próba jednak doszła, serwer nie dopisze serii drugi raz.
 *
 * Bez JS formularz nadal działa po staremu — z przeładowaniem strony.
 */
(function () {
  "use strict";

  var LIMIT_CZASU = 12000;
  var KLUCZ = "szkic:" + location.pathname;

  function wczytaj() {
    try {
      return JSON.parse(localStorage.getItem(KLUCZ)) || {};
    } catch (e) {
      return {};
    }
  }

  function zachowaj(szkic) {
    try {
      localStorage.setItem(KLUCZ, JSON.stringify(szkic));
    } catch (e) {
      // Brak pamięci (tryb prywatny) — aplikacja działa dalej, tylko bez szkicu.
    }
  }

  function kluczPola(pole) {
    if (pole.id) return pole.id;
    // Panel podmiany nie ma identyfikatorów pól, a takich paneli jest tyle, ile ćwiczeń.
    var form = pole.form;
    var pozycja = form && form.elements.planned_item_id ? form.elements.planned_item_id.value : "";
    return (form ? form.getAttribute("action") : "") + "|" + pozycja + "|" + pole.name;
  }

  // Szkic obejmuje wszystko poza polami zapisywanymi w tle — te są już w bazie.
  function polaSzkicu() {
    return Array.prototype.filter.call(
      document.querySelectorAll("form:not([data-autozapis]) input[type=text], " +
        "form:not([data-autozapis]) input[type=number], form:not([data-autozapis]) select"),
      function (pole) { return pole.name; }
    );
  }

  var szkic = wczytaj();
  polaSzkicu().forEach(function (pole) {
    var klucz = kluczPola(pole);
    if (Object.prototype.hasOwnProperty.call(szkic, klucz)) pole.value = szkic[klucz];
    pole.addEventListener("input", function () {
      var s = wczytaj();
      s[klucz] = pole.value;
      zachowaj(s);
    });
    pole.addEventListener("change", function () {
      var s = wczytaj();
      s[klucz] = pole.value;
      zachowaj(s);
    });
  });

  function wyczyscSzkic(form) {
    var s = wczytaj();
    Array.prototype.forEach.call(form.elements, function (pole) {
      if (pole.name) delete s[kluczPola(pole)];
    });
    zachowaj(s);
  }

  function nowyId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return Date.now().toString(36) + Math.random().toString(36).slice(2);
  }

  function pokazBlad(form, tekst) {
    var wiersz = form.closest("li, .panel-zamiany, details, section") || form;
    wiersz.classList.add("blad-zapisu");
    // Pod formularzem, nie w nim: wiersz serii jest flexem w jednej linii.
    var notka = form.nextElementSibling;
    if (!notka || !notka.classList.contains("notka-sieci")) {
      notka = document.createElement("p");
      notka.className = "notka notka-sieci";
      form.insertAdjacentElement("afterend", notka);
    }
    notka.textContent = tekst;
  }

  // Zamknięcie treningu też zapamiętuje szkic, ale wysyła się zwyczajnie:
  // po nim i tak przechodzi się na podsumowanie.
  var zamkniecie = document.querySelector("form.zamkniecie");
  if (zamkniecie) {
    zamkniecie.addEventListener("submit", function () {
      try { localStorage.removeItem(KLUCZ); } catch (e) {}
    });
  }

  document.querySelectorAll("form[action$='/seria']").forEach(function (form) {
    form.addEventListener("submit", function (zdarzenie) {
      zdarzenie.preventDefault();
      if (form.classList.contains("w-locie")) return;

      var pole = form.querySelector("input[name=zapis_id]");
      if (!pole) {
        pole = document.createElement("input");
        pole.type = "hidden";
        pole.name = "zapis_id";
        pole.value = nowyId();
        form.appendChild(pole);
      }

      var przycisk = form.querySelector("button[type=submit]");
      if (przycisk) przycisk.disabled = true;
      form.classList.add("w-locie");

      var przerwij = window.AbortController ? new AbortController() : null;
      var zegar = setTimeout(function () { if (przerwij) przerwij.abort(); }, LIMIT_CZASU);

      fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        redirect: "follow",
        signal: przerwij ? przerwij.signal : undefined,
      })
        .then(function (odp) {
          clearTimeout(zegar);
          if (!odp.ok) throw new Error("HTTP " + odp.status);
          wyczyscSzkic(form);
          if (odp.url && odp.url.indexOf("/podsumowanie") !== -1) {
            location.replace(odp.url);
          } else {
            location.reload();
          }
        })
        .catch(function () {
          clearTimeout(zegar);
          form.classList.remove("w-locie");
          if (przycisk) przycisk.disabled = false;
          pokazBlad(form, "Nie doszło do serwera. Liczby zostają — kliknij ✓ jeszcze raz.");
        });
    });
  });
})();
