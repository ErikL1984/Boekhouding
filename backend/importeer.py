"""
Rabobank CSV import module
Verwerkt standaard Rabobank CSV-export
"""
import csv
import io
from typing import List, Dict, Tuple
from db import query, execute, get_db
from matchengine import zoek_match

# Rabobank CSV kolomnamen (standaard export)
RABOBANK_KOLOMMEN = {
    'IBAN/BBAN':                'iban',
    'Volgnr':                   'volgnummer',
    'Datum':                    'datum',
    'Bedrag':                   'bedrag',
    'Valutacode':               'valutacode',
    'BIC':                      None,
    'Volgnr tegenrekening':     None,
    'Tegenrekening IBAN/BBAN':  'tegenrekening_iban',
    'Naam tegenpartij':         'naam_tegenpartij',
    'Naam uiteindelijke partij': None,
    'Naam initiërende partij':  None,
    'BIC tegenpartij':          None,
    'Omschrijving-1':           'omschrijving_1',
    'Omschrijving-2':           None,
    'Omschrijving-3':           None,
    'Reden retour':             None,
    'Oorspr bedrag':            None,
    'SEPA batch id':            None,
    'SEPA Machtiging id':       None,
    'SEPA Incassant id':        None,
    'Type batch':               None,
    'Saldo na trn':             'saldo_na',
}

def parse_bedrag(s: str) -> float:
    """Verwerk Rabobank bedragnotatie naar float"""
    if not s:
        return 0.0
    s = s.strip().replace(',', '.')
    # Rabobank gebruikt soms punt als duizendscheider
    parts = s.split('.')
    if len(parts) > 2:
        s = ''.join(parts[:-1]) + '.' + parts[-1]
    try:
        return float(s)
    except ValueError:
        return 0.0

def parse_datum(s: str) -> str:
    """Normaliseer datum naar YYYY-MM-DD"""
    if not s:
        return ''
    s = s.strip()
    # Rabobank: YYYY-MM-DD
    if len(s) == 10 and s[4] == '-':
        return s
    # DD-MM-YYYY
    if len(s) == 10 and s[2] == '-':
        d, m, y = s.split('-')
        return f"{y}-{m}-{d}"
    return s

def haal_eigen_ibans() -> set:
    """Haal alle eigen IBAN's op uit bankrekeningen tabel"""
    rows = query("SELECT iban FROM bankrekeningen WHERE actief = 1")
    return {r['iban'].replace(' ', '').upper() for r in rows}

def haal_matchregels() -> list:
    rows = query(
        "SELECT m.id, m.naam, m.conditie, m.grootboek_id, g.nummer as gb_nummer, g.omschrijving as gb_omschrijving "
        "FROM matchregels m JOIN grootboeken g ON g.id = m.grootboek_id "
        "WHERE m.actief = 1"
    )
    return [dict(r) for r in rows]

def haal_bank_grootboek(iban: str) -> int:
    """Zoek het grootboek_id voor een bankrekening op IBAN"""
    row = query(
        "SELECT grootboek_id FROM bankrekeningen WHERE REPLACE(iban,' ','') = ?",
        (iban.replace(' ', '').upper(),), one=True
    )
    return row['grootboek_id'] if row else None

def importeer_csv(csv_inhoud: str, gebruiker_id: int) -> Dict:
    """
    Importeer Rabobank CSV.
    Returns: { 'nieuw': int, 'overgeslagen': int, 'auto_geboekt': int, 'handmatig': int, 'fouten': list }
    """
    resultaat = {'nieuw': 0, 'overgeslagen': 0, 'auto_geboekt': 0, 'handmatig': 0, 'fouten': []}

    eigen_ibans = haal_eigen_ibans()
    matchregels = haal_matchregels()

    # Detecteer delimiter
    eerste_regel = csv_inhoud.split('\n')[0]
    delimiter = ',' if csv_inhoud.count(',') > csv_inhoud.count(';') else ';'

    reader = csv.DictReader(io.StringIO(csv_inhoud), delimiter=delimiter)

    for rijnr, rij in enumerate(reader, start=2):
        try:
            # Normaliseer kolomnamen
            transactie = {}
            for kolom, veld in RABOBANK_KOLOMMEN.items():
                waarde = rij.get(kolom, '').strip()
                if veld:
                    transactie[veld] = waarde

            iban = transactie.get('iban', '').replace(' ', '').upper()
            volgnummer = transactie.get('volgnummer', '').strip()
            datum = parse_datum(transactie.get('datum', ''))
            bedrag = parse_bedrag(transactie.get('bedrag', '0'))
            tegenrekening = transactie.get('tegenrekening_iban', '').replace(' ', '').upper()

            if not iban or not volgnummer:
                resultaat['fouten'].append(f"Rij {rijnr}: ontbrekend IBAN of volgnummer")
                continue

            # Duplicaatcontrole
            bestaand = query(
                "SELECT id FROM banktransacties WHERE iban = ? AND volgnummer = ?",
                (iban, volgnummer), one=True
            )
            if bestaand:
                resultaat['overgeslagen'] += 1
                continue

            # Sla transactie op
            trans_id = execute(
                """INSERT INTO banktransacties
                   (iban, volgnummer, datum, bedrag, tegenrekening_iban, naam_tegenpartij,
                    omschrijving_1, valutacode, saldo_na, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'nieuw')""",
                (iban, volgnummer, datum, bedrag,
                 tegenrekening or None,
                 transactie.get('naam_tegenpartij') or None,
                 transactie.get('omschrijving_1') or None,
                 transactie.get('valutacode', 'EUR'),
                 parse_bedrag(transactie.get('saldo_na', '0')) or None)
            )
            resultaat['nieuw'] += 1

            # Interne overboeking?
            if tegenrekening and tegenrekening in eigen_ibans:
                gb_van = haal_bank_grootboek(iban)
                gb_naar = haal_bank_grootboek(tegenrekening)
                if gb_van and gb_naar:
                    boek_intern(trans_id, datum, bedrag, gb_van, gb_naar, gebruiker_id)
                    resultaat['auto_geboekt'] += 1
                    continue

            # Matchregel toepassen
            trans_dict = dict(transactie)
            trans_dict['bedrag'] = bedrag
            match = zoek_match(trans_dict, matchregels)
            if match:
                gb_bank = haal_bank_grootboek(iban)
                if gb_bank:
                    boek_automatisch(trans_id, datum, bedrag, gb_bank, match['grootboek_id'],
                                     match['gb_omschrijving'], gebruiker_id)
                    resultaat['auto_geboekt'] += 1
                    continue

            # Handmatig te boeken
            resultaat['handmatig'] += 1

        except Exception as e:
            resultaat['fouten'].append(f"Rij {rijnr}: {str(e)}")

    return resultaat

def boek_intern(trans_id, datum, bedrag, gb_van_id, gb_naar_id, gebruiker_id):
    """Boek interne overboeking tussen twee eigen rekeningen"""
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO boekingen (transactie_id, omschrijving, datum, gebruiker_id, type) VALUES (?, ?, ?, ?, 'intern')",
            (trans_id, 'Interne overboeking', datum, gebruiker_id)
        )
        boeking_id = cur.lastrowid
        if bedrag < 0:
            # Geld weg van eigen rekening
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, ?)",
                (boeking_id, gb_naar_id, 0, abs(bedrag))
            )
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, ?)",
                (boeking_id, gb_van_id, abs(bedrag), 0)
            )
        else:
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, ?)",
                (boeking_id, gb_van_id, bedrag, 0)
            )
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, ?)",
                (boeking_id, gb_naar_id, 0, bedrag)
            )
        conn.execute("UPDATE banktransacties SET status = 'geboekt' WHERE id = ?", (trans_id,))
        conn.commit()
    finally:
        conn.close()

def boek_automatisch(trans_id, datum, bedrag, gb_bank_id, gb_tegen_id, omschrijving, gebruiker_id):
    """Boek een transactie automatisch op basis van matchregel"""
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO boekingen (transactie_id, omschrijving, datum, gebruiker_id, type) VALUES (?, ?, ?, ?, 'normaal')",
            (trans_id, omschrijving, datum, gebruiker_id)
        )
        boeking_id = cur.lastrowid
        if bedrag < 0:
            # Uitgave: debet tegenkant, credit bank
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, ?)",
                (boeking_id, gb_tegen_id, abs(bedrag), 0)
            )
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, ?)",
                (boeking_id, gb_bank_id, 0, abs(bedrag))
            )
        else:
            # Inkomst: debet bank, credit tegenkant
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, ?)",
                (boeking_id, gb_bank_id, bedrag, 0)
            )
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, ?)",
                (boeking_id, gb_tegen_id, 0, bedrag)
            )
        conn.execute("UPDATE banktransacties SET status = 'geboekt' WHERE id = ?", (trans_id,))
        conn.commit()
    finally:
        conn.close()

def boek_handmatig(trans_id: int, regels: list, gebruiker_id: int, omschrijving: str = None) -> tuple:
    """
    Boek een transactie handmatig.
    regels: [{ 'grootboek_id': int, 'bedrag': float }, ...]
    Totaal van regels moet gelijk zijn aan transactiebedrag.
    """
    trans = query("SELECT * FROM banktransacties WHERE id = ?", (trans_id,), one=True)
    if not trans:
        return False, "Transactie niet gevonden"

    trans = dict(trans)
    totaal_regels = sum(r['bedrag'] for r in regels)
    if abs(abs(totaal_regels) - abs(trans['bedrag'])) > 0.005:
        return False, f"Totaal regels (€{totaal_regels:.2f}) komt niet overeen met transactiebedrag (€{trans['bedrag']:.2f})"

    gb_bank = haal_bank_grootboek(trans['iban'])
    if not gb_bank:
        return False, "Bankrekening niet gekoppeld aan grootboek"

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO boekingen (transactie_id, omschrijving, datum, gebruiker_id, type) VALUES (?, ?, ?, ?, 'normaal')",
            (trans_id, omschrijving or 'Handmatige boeking', trans['datum'], gebruiker_id)
        )
        boeking_id = cur.lastrowid

        bedrag = trans['bedrag']
        if bedrag < 0:
            # Uitgave: bank credit, categorieën debet
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, 0, ?)",
                (boeking_id, gb_bank, abs(bedrag))
            )
            for regel in regels:
                conn.execute(
                    "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, 0)",
                    (boeking_id, regel['grootboek_id'], abs(regel['bedrag']))
                )
        else:
            # Inkomst: bank debet, categorieën credit
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, 0)",
                (boeking_id, gb_bank, bedrag)
            )
            for regel in regels:
                conn.execute(
                    "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, 0, ?)",
                    (boeking_id, regel['grootboek_id'], abs(regel['bedrag']))
                )

        conn.execute("UPDATE banktransacties SET status = 'handmatig' WHERE id = ?", (trans_id,))
        conn.commit()
        return True, "Geboekt"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()
