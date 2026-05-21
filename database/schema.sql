-- ============================================================
-- Privé Boekhoudprogramma — Database Schema
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ─── GEBRUIKERS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gebruikers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gebruikersnaam TEXT NOT NULL UNIQUE,
    wachtwoord_hash TEXT NOT NULL,
    rol         TEXT NOT NULL DEFAULT 'gebruiker' CHECK(rol IN ('gebruiker', 'beheerder')),
    actief      INTEGER NOT NULL DEFAULT 1,
    aangemaakt  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── SESSIONS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessies (
    token       TEXT PRIMARY KEY,
    gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
    vervalt     TEXT NOT NULL,
    aangemaakt  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── GROEPEN ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS groepen (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    naam        TEXT NOT NULL UNIQUE,
    type        TEXT NOT NULL CHECK(type IN ('Balans', 'Winst en Verlies')),
    kant        TEXT CHECK(kant IS NULL OR kant IN ('Activa', 'Passiva')),
    volgorde    INTEGER NOT NULL DEFAULT 0,
    actief      INTEGER NOT NULL DEFAULT 1,
    aangemaakt  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── GROOTBOEKREKENINGEN ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS grootboeken (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer      TEXT NOT NULL UNIQUE,   -- 4-cijferig
    omschrijving TEXT NOT NULL,
    categorie   TEXT NOT NULL CHECK(categorie IN ('Balans', 'Winst en Verlies')),
    groep       TEXT NOT NULL,
    subgroep    TEXT,
    is_bankrekening INTEGER NOT NULL DEFAULT 0,
    iban        TEXT,                   -- alleen voor bankrekeningen
    rekening_naam TEXT,                 -- bijv. 'Betaalrekening gezin'
    actief      INTEGER NOT NULL DEFAULT 1,
    aangemaakt  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── BANKREKENINGEN (eigen rekeningen) ───────────────────────
CREATE TABLE IF NOT EXISTS bankrekeningen (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    naam        TEXT NOT NULL,
    iban        TEXT NOT NULL UNIQUE,
    grootboek_id INTEGER REFERENCES grootboeken(id),
    actief      INTEGER NOT NULL DEFAULT 1
);

-- ─── BANKTRANSACTIES (ruwe import) ───────────────────────────
CREATE TABLE IF NOT EXISTS banktransacties (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    iban            TEXT NOT NULL,
    volgnummer      TEXT NOT NULL,
    datum           TEXT NOT NULL,
    bedrag          REAL NOT NULL,
    tegenrekening_iban TEXT,
    naam_tegenpartij TEXT,
    omschrijving_1  TEXT,
    valutacode      TEXT DEFAULT 'EUR',
    saldo_na        REAL,
    raw_csv         TEXT,
    import_datum    TEXT NOT NULL DEFAULT (datetime('now')),
    status          TEXT NOT NULL DEFAULT 'nieuw' CHECK(status IN ('nieuw','geboekt','handmatig')),
    UNIQUE(iban, volgnummer)
);

-- ─── BOEKINGEN ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS boekingen (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transactie_id   INTEGER REFERENCES banktransacties(id),
    omschrijving    TEXT,
    datum           TEXT NOT NULL,
    aangemaakt      TEXT NOT NULL DEFAULT (datetime('now')),
    gebruiker_id    INTEGER REFERENCES gebruikers(id),
    type            TEXT NOT NULL DEFAULT 'normaal' CHECK(type IN ('normaal','opening','intern'))
);

-- ─── BOEKINGSREGELS (debet/credit) ───────────────────────────
CREATE TABLE IF NOT EXISTS boekingsregels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    boeking_id      INTEGER NOT NULL REFERENCES boekingen(id) ON DELETE CASCADE,
    grootboek_id    INTEGER NOT NULL REFERENCES grootboeken(id),
    debet           REAL NOT NULL DEFAULT 0,
    credit          REAL NOT NULL DEFAULT 0,
    omschrijving    TEXT
);

-- ─── MATCHREGELS ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS matchregels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    naam            TEXT NOT NULL,
    conditie        TEXT NOT NULL,  -- bijv. "BEDRAG < -50 AND NAAM LIKE 'jumbo'"
    grootboek_id    INTEGER NOT NULL REFERENCES grootboeken(id),
    actief          INTEGER NOT NULL DEFAULT 1,
    aangemaakt      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── BUDGETTEN ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budgetten (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    grootboek_id    INTEGER NOT NULL REFERENCES grootboeken(id),
    jaar            INTEGER NOT NULL,
    maand           INTEGER NOT NULL CHECK(maand BETWEEN 1 AND 12),
    bedrag          REAL NOT NULL DEFAULT 0,
    UNIQUE(grootboek_id, jaar, maand)
);

-- ─── INDEXES ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_transacties_iban_volg ON banktransacties(iban, volgnummer);
CREATE INDEX IF NOT EXISTS idx_transacties_datum ON banktransacties(datum);
CREATE INDEX IF NOT EXISTS idx_transacties_status ON banktransacties(status);
CREATE INDEX IF NOT EXISTS idx_boekingsregels_gb ON boekingsregels(grootboek_id);
CREATE INDEX IF NOT EXISTS idx_boekingen_datum ON boekingen(datum);
CREATE INDEX IF NOT EXISTS idx_budgetten_gb ON budgetten(grootboek_id, jaar, maand);
