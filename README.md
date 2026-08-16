# Email → Kalendar

Django aplikacija koja prati email pretinac, pomoću velikog jezičnog
modela prepoznaje zadatke, rokove i osobe, te ih nakon korisničke
potvrde dodaje u Google kalendar uz pozivnice sudionicima.

Završni rad — Niko Grđan

## Pokretanje

    python -m venv venv
    source venv/Scripts/activate      # Windows Git Bash
    pip install -r requirements.txt
    cp .env.example .env              # popuniti vrijednosti
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver

Dodatno je potrebno preuzeti OAuth podatke iz Google Cloud konzole
(tip klijenta: Desktop app) i spremiti ih kao `credentials.json` u
korijen projekta.

## Naredbe

    python manage.py fetch_emails --limit 20
    python manage.py analyze_emails --limit 10 [--reanalyze]
    python manage.py sync_tasks [--dry-run]

Usporedba modela i verzija upita:

    python manage.py analyze_emails --model <naziv> --reanalyze
    python manage.py analyze_emails --prompt-version v2 --reanalyze

## Arhitektura

    apps/emails/         dohvat poruka (IMAP) i pohrana
    apps/extraction/     analiza jezičnim modelom, prepoznati zadaci
    apps/calendarsync/   OAuth 2.0 i Google Calendar
    apps/web/            sučelje za pregled, potvrdu i evaluaciju

Poslovna logika nalazi se u podmapama `services/`; pogledi i naredbe
sadrže isključivo orkestraciju.

## Pozivnice sudionicima

Aplikacija ne piše u tuđe kalendare. Adresa pretinca dodaje se u Cc
poruke, a potvrđeni zadaci nastaju kao događaji s ostalim sudionicima
kao gostima. Google im šalje standardnu pozivnicu koju prihvaćaju ili
odbijaju — prihvaćanje je njihov pristanak.

Slanje pozivnica nikada nije automatsko: zahtijeva izričitu potvrdu u
sučelju za svaki zadatak.

## Evaluacija

Ispravci u sučelju bilježe se u polja `was_edited` i `edited_fields`,
pa se točnost po pojedinom polju računa kao nuspojava korištenja
aplikacije. Rezultati su na `/evaluation/`.

Mjere se računaju samo nad pregledanim zadacima; zadaci koji čekaju
pregled i ručno uneseni zadaci isključeni su.

## Poznata ograničenja

- Jedan pretinac, bez prijave korisnika. Višekorisnički rad zahtijevao
  bi OAuth po korisniku i Googleovu provjeru aplikacije.
- Analiza se pokreće ručno; nema pozadinskog posla.
- Adrese u Bcc polju nisu vidljive pa se ne mogu pozvati.