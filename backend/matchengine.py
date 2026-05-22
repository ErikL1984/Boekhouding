"""
Matchregel engine — parseren en evalueren van matchregels
Syntax: BEDRAG < -50 AND NAAM LIKE 'jumbo'
        NAAM = 'BCK*Jumbo v.Daalhuizen'
        BEDRAG = -50.99 OR OMSCHRIJVING LIKE 'sparen auto'
"""
import re
from typing import Optional

VELD_MAP = {
    'BEDRAG': 'bedrag',
    'NAAM': 'naam_tegenpartij',
    'OMSCHRIJVING': 'omschrijving_1',
}

TEKSTVELDEN = {'NAAM', 'OMSCHRIJVING'}
OPERATOREN = ['<=', '>=', '<', '>', '=', 'LIKE']

def parse_conditie(conditie_str: str) -> dict:
    conditie_str = conditie_str.strip()
    for op in OPERATOREN:
        pat = rf"^(BEDRAG|NAAM|OMSCHRIJVING)\s+{re.escape(op)}\s+(.+)$"
        m = re.match(pat, conditie_str, re.IGNORECASE)
        if m:
            veld = m.group(1).upper()
            waarde_raw = m.group(2).strip()
            if waarde_raw.startswith("'") and waarde_raw.endswith("'"):
                waarde = waarde_raw[1:-1]
            else:
                try:
                    waarde = float(waarde_raw)
                except ValueError:
                    waarde = waarde_raw
            return {'veld': veld, 'operator': op.upper(), 'waarde': waarde}
    raise ValueError(f"Ongeldige conditie: {conditie_str}")

def parse_regel(regel_str: str) -> dict:
    regel_str = regel_str.strip()
    split = re.split(r'\s+(AND|OR)\s+', regel_str, maxsplit=1, flags=re.IGNORECASE)
    if len(split) == 3:
        c1_str, logisch, c2_str = split
        return {
            'conditie1': parse_conditie(c1_str),
            'logisch': logisch.upper(),
            'conditie2': parse_conditie(c2_str),
        }
    else:
        return {
            'conditie1': parse_conditie(regel_str),
            'logisch': None,
            'conditie2': None,
        }

def evalueer_conditie(conditie: dict, transactie: dict) -> bool:
    veld = VELD_MAP[conditie['veld']]
    waarde_trans = transactie.get(veld)
    operator = conditie['operator']
    waarde_regel = conditie['waarde']
    is_tekstveld = conditie['veld'] in TEKSTVELDEN

    # LIKE: altijd tekstueel, % wildcards worden genegeerd (alles is 'bevat')
    if operator == 'LIKE':
        if not waarde_trans:
            return False
        zoekterm = str(waarde_regel).replace('%', '').strip().lower()
        return zoekterm in str(waarde_trans).strip().lower()

    # = op tekstveld: tekstuele vergelijking (niet hoofdlettergevoelig)
    if operator == '=' and is_tekstveld:
        if waarde_trans is None:
            return False
        return str(waarde_regel).strip().lower() == str(waarde_trans).strip().lower()

    # Numerieke vergelijking (BEDRAG, of getallen)
    try:
        trans_num = float(waarde_trans) if waarde_trans is not None else None
        regel_num = float(waarde_regel)
    except (TypeError, ValueError):
        return False
    if trans_num is None:
        return False
    if operator == '=':  return abs(trans_num - regel_num) < 0.005
    if operator == '<':  return trans_num < regel_num
    if operator == '>':  return trans_num > regel_num
    if operator == '<=': return trans_num <= regel_num
    if operator == '>=': return trans_num >= regel_num
    return False

def evalueer_regel(regel_str: str, transactie: dict) -> bool:
    try:
        parsed = parse_regel(regel_str)
        r1 = evalueer_conditie(parsed['conditie1'], transactie)
        if parsed['logisch'] is None:
            return r1
        r2 = evalueer_conditie(parsed['conditie2'], transactie)
        if parsed['logisch'] == 'AND':
            return r1 and r2
        else:
            return r1 or r2
    except Exception:
        return False

def valideer_conditie_syntax(conditie_str: str) -> tuple[bool, str]:
    try:
        parse_regel(conditie_str)
        return True, ""
    except ValueError as e:
        return False, str(e)

def zoek_match(transactie: dict, matchregels: list) -> Optional[dict]:
    """
    0 matches  → None (handmatig)
    1 match    → return die matchregel
    2+ matches → None (handmatig, want ambigu)
    """
    matches = []
    for regel in matchregels:
        if evalueer_regel(regel['conditie'], transactie):
            matches.append(regel)
    if len(matches) == 1:
        return matches[0]
    return None
