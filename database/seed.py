"""
Seed script — vult de database met de standaard grootboekstructuur
zoals gedefinieerd in de specificatie.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from db import execute, query, init_db

DEFAULT_GROEPEN = [
    # Balans — Activa
    ("Vaste activa",                        "Balans",           "Activa",  10),
    ("Liquide middelen",                    "Balans",           "Activa",  20),
    # Balans — Passiva
    ("Eigen vermogen",                      "Balans",           "Passiva", 30),
    ("Schulden",                            "Balans",           "Passiva", 40),
    # Winst en Verlies
    ("Inkomsten",                           "Winst en Verlies", None,      10),
    ("Maandelijkse vaste lasten",           "Winst en Verlies", None,      20),
    ("Niet-maandelijkse vaste lasten",      "Winst en Verlies", None,      30),
    ("Variabele lasten",                    "Winst en Verlies", None,      40),
    ("Sparen / reserveringen",              "Winst en Verlies", None,      50),
    # Voormalige subgroepen — nu volwaardige W&V groepen
    ("Abonnementen",                        "Winst en Verlies", None,      60),
    ("Boodschappen",                        "Winst en Verlies", None,      70),
    ("Kinderopvang",                        "Winst en Verlies", None,      80),
    ("Leningen",                            "Winst en Verlies", None,      90),
    ("Nutsvoorzieningen",                   "Winst en Verlies", None,      100),
    ("Verzekeringen",                       "Winst en Verlies", None,      110),
]

def seed():
    init_db()

    # Controleer of al geseed is
    bestaand = query("SELECT COUNT(*) as n FROM grootboeken", one=True)
    if bestaand and bestaand['n'] > 0:
        print("Database bevat al grootboeken — seed overgeslagen.")
        return

    print("Groepen aanmaken...")
    for naam, type_, kant, volgorde in DEFAULT_GROEPEN:
        execute(
            "INSERT OR IGNORE INTO groepen (naam, type, kant, volgorde) VALUES (?, ?, ?, ?)",
            (naam, type_, kant, volgorde)
        )
    print(f"  {len(DEFAULT_GROEPEN)} groepen aangemaakt")

    print("Grootboeken aanmaken...")

    grootboeken = [
        # ── BALANS: ACTIVA ──────────────────────────────────────────
        # Vaste activa
        ("1000", "Woning Bezembinder 20",       "Balans", "Vaste activa",     None,            0, None, None),
        ("1010", "Auto",                         "Balans", "Vaste activa",     None,            0, None, None),
        ("1020", "Inventaris",                   "Balans", "Vaste activa",     None,            0, None, None),
        # Liquide middelen — bankrekeningen (placeholder, IBAN in te vullen)
        ("1100", "Betaalrekening gezin",         "Balans", "Liquide middelen", None,            1, None, "Betaalrekening gezin"),
        ("1101", "Betaalrekening Erik",          "Balans", "Liquide middelen", None,            1, None, "Betaalrekening Erik"),
        ("1102", "Betaalrekening 3",             "Balans", "Liquide middelen", None,            1, None, "Betaalrekening 3"),
        ("1110", "Spaarrekening 1",              "Balans", "Liquide middelen", None,            1, None, "Spaarrekening 1"),
        ("1111", "Spaarrekening 2",              "Balans", "Liquide middelen", None,            1, None, "Spaarrekening 2"),
        ("1120", "Waarde crypto's",              "Balans", "Liquide middelen", None,            0, None, None),

        # ── BALANS: PASSIVA ─────────────────────────────────────────
        # Eigen vermogen
        ("3000", "Eigen vermogen Erik",          "Balans", "Eigen vermogen",   None, 0, None, None),
        # Schulden
        ("4000", "Hypotheek",                    "Balans", "Schulden",         None, 0, None, None),
        ("4010", "Onderhandse lening papa",      "Balans", "Schulden",         None, 0, None, None),
        ("4020", "Persoonlijke lening Freo",     "Balans", "Schulden",         None, 0, None, None),

        # ── W&V: INKOMSTEN ──────────────────────────────────────────
        ("8000", "Salaris",                      "Winst en Verlies", "Inkomsten",                       None, 0, None, None),
        ("8010", "Toeslagen",                    "Winst en Verlies", "Inkomsten",                       None, 0, None, None),
        ("8020", "Overige inkomsten",            "Winst en Verlies", "Inkomsten",                       None, 0, None, None),

        # ── W&V: MAANDELIJKSE VASTE LASTEN ─────────────────────────
        ("6000", "Huur / hypotheeklasten",       "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6010", "Aflossing Freo",               "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6020", "Aflossing papa",               "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6030", "Kinderopvang",                 "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6040", "Gas / water / elektra",        "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6050", "Zorgverzekering",              "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6060", "Aansprakelijkheidsverzekering","Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6070", "Autoverzekering",              "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6080", "Netflix",                      "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6081", "Spotify",                      "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6082", "Overige abonnementen",         "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),
        ("6090", "Overige maandelijkse lasten",  "Winst en Verlies", "Maandelijkse vaste lasten",       None, 0, None, None),

        # ── W&V: NIET-MAANDELIJKSE VASTE LASTEN ────────────────────
        ("6200", "Wegenbelasting",               "Winst en Verlies", "Niet-maandelijkse vaste lasten",  None, 0, None, None),
        ("6210", "Gemeentelijke belastingen",    "Winst en Verlies", "Niet-maandelijkse vaste lasten",  None, 0, None, None),
        ("6220", "Waterschapsbelasting",         "Winst en Verlies", "Niet-maandelijkse vaste lasten",  None, 0, None, None),
        ("6230", "Inboedelverzekering",          "Winst en Verlies", "Niet-maandelijkse vaste lasten",  None, 0, None, None),
        ("6240", "Reisverzekering",              "Winst en Verlies", "Niet-maandelijkse vaste lasten",  None, 0, None, None),
        ("6250", "Overige niet-maandelijkse abonnementen", "Winst en Verlies", "Niet-maandelijkse vaste lasten", None, 0, None, None),
        ("6260", "Overige niet-maandelijkse lasten", "Winst en Verlies", "Niet-maandelijkse vaste lasten", None, 0, None, None),

        # ── W&V: VARIABELE LASTEN ───────────────────────────────────
        ("6400", "Boodschappen",                 "Winst en Verlies", "Variabele lasten",                "Boodschappen",    0, None, None),
        ("6410", "Tanken / brandstof",           "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6420", "Kleding",                      "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6430", "Uit eten / horeca",            "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6440", "Persoonlijke verzorging",      "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6450", "Huishoudelijke uitgaven",      "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6460", "Kinderen (diversen)",          "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6470", "Sport / hobby",                "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6480", "Vakantie / reizen",            "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6490", "Cadeaus / giften",             "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6500", "Gezondheid / apotheek",        "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6510", "Onderhoud woning",             "Winst en Verlies", "Variabele lasten",                None,              0, None, None),
        ("6520", "Overige variabele lasten",     "Winst en Verlies", "Variabele lasten",                None,              0, None, None),

        # ── W&V: SPAREN / RESERVERINGEN ────────────────────────────
        ("6700", "Spaarpot vakantie",            "Winst en Verlies", "Sparen / reserveringen",          None,              0, None, None),
        ("6710", "Spaarpot auto",                "Winst en Verlies", "Sparen / reserveringen",          None,              0, None, None),
        ("6720", "Spaarpot verbouwing",          "Winst en Verlies", "Sparen / reserveringen",          None,              0, None, None),
        ("6730", "Spaarpot kinderen",            "Winst en Verlies", "Sparen / reserveringen",          None,              0, None, None),
        ("6740", "Overige reserveringen",        "Winst en Verlies", "Sparen / reserveringen",          None,              0, None, None),
    ]

    for gb in grootboeken:
        nummer, omschr, cat, groep, subgroep, isbank, iban, reknaam = gb
        execute(
            """INSERT OR IGNORE INTO grootboeken
               (nummer, omschrijving, categorie, groep, subgroep, is_bankrekening, iban, rekening_naam)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (nummer, omschr, cat, groep, subgroep, isbank, iban, reknaam)
        )

    print(f"  {len(grootboeken)} grootboeken aangemaakt")

    # ── VOORBEELD MATCHREGELS ───────────────────────────────────
    print("Voorbeeld matchregels aanmaken...")

    # Haal grootboek ID's op
    def gb_id(nummer):
        r = query("SELECT id FROM grootboeken WHERE nummer = ?", (nummer,), one=True)
        return r['id'] if r else None

    matchregels = [
        ("Albert Heijn boodschappen",   "NAAM LIKE 'albert heijn'",                          "6400"),
        ("Jumbo boodschappen",          "NAAM LIKE 'jumbo'",                                 "6400"),
        ("Lidl boodschappen",           "NAAM LIKE 'lidl'",                                  "6400"),
        ("Salaris",                     "OMSCHRIJVING LIKE 'salaris'",                        "8000"),
        ("Netflix",                     "NAAM LIKE 'netflix'",                               "6080"),
        ("Spotify",                     "NAAM LIKE 'spotify'",                               "6081"),
        ("Tanken Shell",                "NAAM LIKE 'shell'",                                 "6410"),
        ("Tanken BP",                   "NAAM LIKE 'bp'",                                    "6410"),
    ]

    for naam, conditie, gb_nummer in matchregels:
        gid = gb_id(gb_nummer)
        if gid:
            execute(
                "INSERT OR IGNORE INTO matchregels (naam, conditie, grootboek_id) VALUES (?, ?, ?)",
                (naam, conditie, gid)
            )

    print(f"  {len(matchregels)} matchregels aangemaakt")
    print("\n✅ Seed voltooid!")

if __name__ == '__main__':
    seed()
