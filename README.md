# Privé Boekhoudprogramma

Webgebaseerd privé boekhoudprogramma met dubbel boekhouden, Rabobank CSV-import,
automatische matchregels, budgetten en rapportages.

---

## Systeemvereisten

- Linux server (Ubuntu 20.04+ / Debian 11+)
- Python 3.9 of hoger
- ~50 MB schijfruimte
- Optioneel: Nginx (voor productiegebruik)

---

## Installatie

### Stap 1 — Bestanden plaatsen

```bash
sudo mkdir -p /opt/boekhouding
sudo cp -r . /opt/boekhouding/
cd /opt/boekhouding
```

### Stap 2 — Setup uitvoeren

```bash
bash setup.sh
```

Dit doet het volgende:
- Maakt een Python virtual environment aan
- Installeert Flask
- Initialiseert de database
- Laadt de standaard grootboekstructuur
- Maakt de standaard beheerder aan

### Stap 3 — Starten (test)

```bash
bash start.sh
```

Open een browser op `http://<server-ip>:5000`

Standaard inloggegevens:
- Gebruikersnaam: `beheerder`
- Wachtwoord: `Wijzig_dit_wachtwoord!`

**Wijzig het wachtwoord direct na de eerste login via Gebruikersbeheer.**

---

## Productie-installatie (als systemd service)

### Stap 4 — Service installeren

```bash
# Pas het pad in het service-bestand aan als je niet /opt/boekhouding gebruikt
sudo cp boekhouding.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable boekhouding
sudo systemctl start boekhouding

# Status controleren
sudo systemctl status boekhouding

# Logbestanden bekijken
sudo journalctl -u boekhouding -f
```

### Stap 5 — Nginx instellen (optioneel maar aanbevolen)

```bash
sudo apt install nginx -y
sudo cp nginx.conf /etc/nginx/sites-available/boekhouding
sudo ln -s /etc/nginx/sites-available/boekhouding /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

De applicatie is nu bereikbaar op poort 80.

### Stap 6 — HTTPS met Let's Encrypt (sterk aanbevolen)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d jouwdomein.nl
```

---

## Configuratie via omgevingsvariabelen

| Variabele | Standaard                      | Omschrijving                    |
|-----------|--------------------------------|---------------------------------|
| `PORT`    | `5000`                         | Poort waarop de server luistert |
| `DEBUG`   | `false`                        | Debugmodus (niet in productie!) |
| `DB_PATH` | `./data/boekhouding.db`        | Pad naar de SQLite database     |

Voorbeeld in het service-bestand:
```ini
Environment=PORT=8080
Environment=DB_PATH=/mnt/data/boekhouding.db
```

---

## PostgreSQL (toekomstige upgrade)

De applicatie is gebouwd met standaard SQL en is eenvoudig te migreren naar PostgreSQL:

1. Installeer `psycopg2`: `pip install psycopg2-binary`
2. Pas `backend/db.py` aan om `psycopg2` te gebruiken in plaats van `sqlite3`
3. Vervang `?` placeholders door `%s` in alle queries
4. Verwijder SQLite-specifieke `PRAGMA` statements

---

## Back-up

De volledige administratie staat in één bestand: `data/boekhouding.db`

Automatische dagelijkse back-up instellen:
```bash
# Voeg toe aan crontab (crontab -e)
0 2 * * * cp /opt/boekhouding/data/boekhouding.db /opt/boekhouding/data/backup_$(date +\%Y\%m\%d).db
```

---

## Projectstructuur

```
boekhouding/
├── backend/
│   ├── app.py          — Flask API (alle routes)
│   ├── db.py           — Database module
│   ├── auth.py         — Authenticatie & gebruikersbeheer
│   ├── importeer.py    — Rabobank CSV import & boekingslogica
│   ├── matchengine.py  — Matchregel parser & evaluator
│   └── rapportages.py  — Balans, W&V, maandoverzicht
├── frontend/
│   └── index.html      — Volledige single-page applicatie
├── database/
│   ├── schema.sql      — Database schema
│   └── seed.py         — Standaard grootboekstructuur
├── data/               — Database opslag (aangemaakt bij setup)
├── setup.sh            — Installatie script
├── start.sh            — Start script
├── boekhouding.service — Systemd service definitie
├── nginx.conf          — Nginx reverse proxy configuratie
└── README.md           — Deze documentatie
```

---

## Functies

### Grootboekbeheer
- 4-cijferige nummering (1000–8999)
- Categorie: Balans of Winst en Verlies
- Groepen en subgroepen conform specificatie
- Bankrekeningen als grootboek

### Import
- Rabobank standaard CSV-export
- Automatische duplicaatdetectie (IBAN + volgnummer)
- Interne overboekingen automatisch herkend
- Matchregels voor automatisch boeken

### Matchregels
- Syntax: `BEDRAG < -50 AND NAAM LIKE 'jumbo'`
- Velden: BEDRAG, NAAM, OMSCHRIJVING
- Operatoren: `=`, `<`, `>`, `<=`, `>=`, `LIKE`
- Logisch: `AND` / `OR`
- Bij meerdere matches → handmatig boeken

### Handmatig boeken
- Knop per grootboek (volledig bedrag)
- Knop "Afwijkend" voor gesplitste boekingen
- Validatie: totaal moet overeenkomen

### Rapportages
- Balans op peildatum
- W&V-rekening per jaar
- Maandoverzicht (5 weergavemodi)
- Budgetten per grootboek per maand

### Beveiliging
- Wachtwoord hashing (PBKDF2-SHA256, 310.000 iteraties)
- Sessietokens (32 bytes, 7 dagen geldig)
- Rolgebaseerde toegang (gebruiker / beheerder)
