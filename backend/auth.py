"""
Authenticatie — gebruikersbeheer, sessies, wachtwoord hashing
"""
import hashlib
import secrets
import os
from datetime import datetime, timedelta
from db import query, execute

def hash_wachtwoord(wachtwoord: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', wachtwoord.encode(), salt, 310000)
    return salt.hex() + ':' + key.hex()

def verifieer_wachtwoord(wachtwoord: str, opgeslagen_hash: str) -> bool:
    try:
        salt_hex, key_hex = opgeslagen_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac('sha256', wachtwoord.encode(), salt, 310000)
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False

def maak_sessie(gebruiker_id: int) -> str:
    token = secrets.token_urlsafe(32)
    vervalt = (datetime.now() + timedelta(days=7)).isoformat()
    execute(
        "INSERT INTO sessies (token, gebruiker_id, vervalt) VALUES (?, ?, ?)",
        (token, gebruiker_id, vervalt)
    )
    return token

def verifieer_sessie(token: str):
    if not token:
        return None
    row = query(
        """SELECT g.id, g.gebruikersnaam, g.rol
           FROM sessies s
           JOIN gebruikers g ON g.id = s.gebruiker_id
           WHERE s.token = ? AND s.vervalt > datetime('now') AND g.actief = 1""",
        (token,), one=True
    )
    return dict(row) if row else None

def verwijder_sessie(token: str):
    execute("DELETE FROM sessies WHERE token = ?", (token,))

def login(gebruikersnaam: str, wachtwoord: str):
    row = query(
        "SELECT id, gebruikersnaam, wachtwoord_hash, rol FROM gebruikers WHERE gebruikersnaam = ? AND actief = 1",
        (gebruikersnaam,), one=True
    )
    if not row:
        return None, "Gebruikersnaam of wachtwoord onjuist"
    if not verifieer_wachtwoord(wachtwoord, row['wachtwoord_hash']):
        return None, "Gebruikersnaam of wachtwoord onjuist"
    token = maak_sessie(row['id'])
    return token, None

def maak_gebruiker(gebruikersnaam: str, wachtwoord: str, rol: str = 'gebruiker'):
    bestaand = query("SELECT id FROM gebruikers WHERE gebruikersnaam = ?", (gebruikersnaam,), one=True)
    if bestaand:
        return None, "Gebruikersnaam bestaat al"
    wh = hash_wachtwoord(wachtwoord)
    uid = execute(
        "INSERT INTO gebruikers (gebruikersnaam, wachtwoord_hash, rol) VALUES (?, ?, ?)",
        (gebruikersnaam, wh, rol)
    )
    return uid, None

def alle_gebruikers():
    rows = query("SELECT id, gebruikersnaam, rol, actief, aangemaakt FROM gebruikers ORDER BY gebruikersnaam")
    return [dict(r) for r in rows]

def update_gebruiker(uid: int, rol: str = None, actief: int = None, nieuw_wachtwoord: str = None):
    if rol:
        execute("UPDATE gebruikers SET rol = ? WHERE id = ?", (rol, uid))
    if actief is not None:
        execute("UPDATE gebruikers SET actief = ? WHERE id = ?", (actief, uid))
    if nieuw_wachtwoord:
        wh = hash_wachtwoord(nieuw_wachtwoord)
        execute("UPDATE gebruikers SET wachtwoord_hash = ? WHERE id = ?", (wh, uid))

def verwijder_gebruiker(uid: int):
    execute("UPDATE gebruikers SET actief = 0 WHERE id = ?", (uid,))
