"""
Privé Boekhoudprogramma — Flask API
"""
import os, sys, json
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, g

sys.path.insert(0, os.path.dirname(__file__))
import db as database
import auth as auth_module
from matchengine import valideer_conditie_syntax
from importeer import importeer_csv, boek_handmatig

app = Flask(__name__, static_folder='../frontend', static_url_path='')

# ─── HELPERS ─────────────────────────────────────────────────

def json_response(data, status=200):
    return jsonify(data), status

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Session-Token') or request.cookies.get('session_token')
        gebruiker = auth_module.verifieer_sessie(token)
        if not gebruiker:
            return json_response({'error': 'Niet ingelogd'}, 401)
        g.gebruiker = gebruiker
        return f(*args, **kwargs)
    return decorated

def beheerder_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Session-Token') or request.cookies.get('session_token')
        gebruiker = auth_module.verifieer_sessie(token)
        if not gebruiker:
            return json_response({'error': 'Niet ingelogd'}, 401)
        if gebruiker['rol'] != 'beheerder':
            return json_response({'error': 'Geen toegang'}, 403)
        g.gebruiker = gebruiker
        return f(*args, **kwargs)
    return decorated

# ─── STATIC / SPA ────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_proxy(path):
    try:
        return send_from_directory(app.static_folder, path)
    except Exception:
        return send_from_directory(app.static_folder, 'index.html')

# ─── AUTH ROUTES ─────────────────────────────────────────────

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    token, fout = auth_module.login(data.get('gebruikersnaam', ''), data.get('wachtwoord', ''))
    if fout:
        return json_response({'error': fout}, 401)
    return json_response({'token': token, 'bericht': 'Ingelogd'})

@app.route('/api/logout', methods=['POST'])
@auth_required
def api_logout():
    token = request.headers.get('X-Session-Token') or request.cookies.get('session_token')
    auth_module.verwijder_sessie(token)
    return json_response({'bericht': 'Uitgelogd'})

@app.route('/api/profiel', methods=['GET'])
@auth_required
def api_profiel():
    return json_response(g.gebruiker)

# ─── GEBRUIKERSBEHEER ────────────────────────────────────────

@app.route('/api/gebruikers', methods=['GET'])
@beheerder_required
def api_gebruikers_lijst():
    return json_response(auth_module.alle_gebruikers())

@app.route('/api/gebruikers', methods=['POST'])
@beheerder_required
def api_gebruiker_aanmaken():
    data = request.json or {}
    uid, fout = auth_module.maak_gebruiker(
        data.get('gebruikersnaam', ''),
        data.get('wachtwoord', ''),
        data.get('rol', 'gebruiker')
    )
    if fout:
        return json_response({'error': fout}, 400)
    return json_response({'id': uid, 'bericht': 'Gebruiker aangemaakt'}, 201)

@app.route('/api/gebruikers/<int:uid>', methods=['PUT'])
@beheerder_required
def api_gebruiker_update(uid):
    data = request.json or {}
    auth_module.update_gebruiker(
        uid,
        rol=data.get('rol'),
        actief=data.get('actief'),
        nieuw_wachtwoord=data.get('wachtwoord')
    )
    return json_response({'bericht': 'Bijgewerkt'})

@app.route('/api/gebruikers/<int:uid>', methods=['DELETE'])
@beheerder_required
def api_gebruiker_verwijderen(uid):
    auth_module.verwijder_gebruiker(uid)
    return json_response({'bericht': 'Verwijderd'})

# ─── GROOTBOEKEN ─────────────────────────────────────────────

@app.route('/api/grootboeken', methods=['GET'])
@auth_required
def api_grootboeken():
    rows = database.query(
        "SELECT * FROM grootboeken WHERE actief = 1 ORDER BY nummer"
    )
    return json_response([dict(r) for r in rows])

@app.route('/api/grootboeken', methods=['POST'])
@beheerder_required
def api_grootboek_aanmaken():
    data = request.json or {}
    # Valideer uniek nummer
    bestaand = database.query("SELECT id FROM grootboeken WHERE nummer = ? AND actief = 1", (data.get('nummer'),), one=True)
    if bestaand:
        return json_response({'error': 'Nummer bestaat al'}, 400)
    gid = database.execute(
        """INSERT INTO grootboeken (nummer, omschrijving, categorie, groep, subgroep, is_bankrekening, iban, rekening_naam, snelboeken)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data.get('nummer'), data.get('omschrijving'), data.get('categorie'),
         data.get('groep'), data.get('subgroep'), data.get('is_bankrekening', 0),
         data.get('iban'), data.get('rekening_naam'), data.get('snelboeken', 0))
    )
    return json_response({'id': gid, 'bericht': 'Grootboek aangemaakt'}, 201)

@app.route('/api/grootboeken/<int:gid>', methods=['PUT'])
@beheerder_required
def api_grootboek_update(gid):
    data = request.json or {}
    database.execute(
        """UPDATE grootboeken SET omschrijving=?, categorie=?, groep=?, subgroep=?,
           is_bankrekening=?, iban=?, rekening_naam=?, snelboeken=? WHERE id=?""",
        (data.get('omschrijving'), data.get('categorie'), data.get('groep'),
         data.get('subgroep'), data.get('is_bankrekening', 0),
         data.get('iban'), data.get('rekening_naam'), data.get('snelboeken', 0), gid)
    )
    return json_response({'bericht': 'Bijgewerkt'})

@app.route('/api/grootboeken/<int:gid>', methods=['DELETE'])
@beheerder_required
def api_grootboek_verwijderen(gid):
    # Check op boekingen
    boekingen = database.query("SELECT COUNT(*) as n FROM boekingsregels WHERE grootboek_id = ?", (gid,), one=True)
    if boekingen and boekingen['n'] > 0:
        return json_response({'error': 'Grootboek heeft boekingen en kan niet worden verwijderd'}, 400)
    database.execute("UPDATE grootboeken SET actief = 0 WHERE id = ?", (gid,))
    return json_response({'bericht': 'Verwijderd'})

# ─── BANKREKENINGEN ──────────────────────────────────────────

@app.route('/api/bankrekeningen', methods=['GET'])
@auth_required
def api_bankrekeningen():
    rows = database.query(
        """SELECT b.*, g.omschrijving as gb_omschrijving, g.nummer as gb_nummer
           FROM bankrekeningen b LEFT JOIN grootboeken g ON g.id = b.grootboek_id
           WHERE b.actief = 1"""
    )
    return json_response([dict(r) for r in rows])

@app.route('/api/bankrekeningen', methods=['POST'])
@beheerder_required
def api_bankrekening_aanmaken():
    data = request.json or {}
    rid = database.execute(
        "INSERT INTO bankrekeningen (naam, iban, grootboek_id) VALUES (?, ?, ?)",
        (data.get('naam'), data.get('iban', '').replace(' ', '').upper(), data.get('grootboek_id'))
    )
    return json_response({'id': rid, 'bericht': 'Bankrekening aangemaakt'}, 201)

@app.route('/api/bankrekeningen/<int:rid>', methods=['PUT'])
@beheerder_required
def api_bankrekening_update(rid):
    data = request.json or {}
    database.execute(
        "UPDATE bankrekeningen SET naam=?, iban=?, grootboek_id=? WHERE id=?",
        (data.get('naam'), data.get('iban', '').replace(' ', '').upper(), data.get('grootboek_id'), rid)
    )
    return json_response({'bericht': 'Bijgewerkt'})

# ─── IMPORT ──────────────────────────────────────────────────

@app.route('/api/import', methods=['POST'])
@auth_required
def api_import():
    if 'bestand' not in request.files:
        return json_response({'error': 'Geen bestand meegestuurd'}, 400)
    bestand = request.files['bestand']
    inhoud = bestand.read().decode('utf-8-sig', errors='replace')
    resultaat = importeer_csv(inhoud, g.gebruiker['id'])
    return json_response(resultaat)

# ─── TRANSACTIES ─────────────────────────────────────────────

@app.route('/api/transacties', methods=['GET'])
@auth_required
def api_transacties():
    status = request.args.get('status', 'nieuw')
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))
    rows = database.query(
        """SELECT t.*, b.naam as rekening_naam
           FROM banktransacties t
           LEFT JOIN bankrekeningen b ON REPLACE(b.iban,' ','') = t.iban
           WHERE t.status = ? ORDER BY t.datum DESC, t.id DESC LIMIT ? OFFSET ?""",
        (status, limit, offset)
    )
    return json_response([dict(r) for r in rows])

@app.route('/api/transacties/count', methods=['GET'])
@auth_required
def api_transacties_count():
    status = request.args.get('status', 'nieuw')
    row = database.query(
        "SELECT COUNT(*) as count FROM banktransacties WHERE status = ?",
        (status,), one=True
    )
    return json_response({'count': row['count'] if row else 0})

@app.route('/api/transacties/alle/count', methods=['GET'])
@auth_required
def api_transacties_alle_count():
    datum_van = request.args.get('van', '')
    datum_tot = request.args.get('tot', '')
    status = request.args.get('status', '')
    rekening_id = request.args.get('rekening_id', '')

    sql = """SELECT COUNT(*) as count
             FROM banktransacties t
             LEFT JOIN bankrekeningen b ON REPLACE(b.iban,' ','') = t.iban
             WHERE 1=1"""
    params = []
    if datum_van:
        sql += " AND t.datum >= ?"
        params.append(datum_van)
    if datum_tot:
        sql += " AND t.datum <= ?"
        params.append(datum_tot)
    if status:
        sql += " AND t.status = ?"
        params.append(status)
    if rekening_id:
        sql += " AND b.id = ?"
        params.append(int(rekening_id))
    row = database.query(sql, params, one=True)
    return json_response({'count': row['count'] if row else 0})

@app.route('/api/transacties/alle', methods=['GET'])
@auth_required
def api_transacties_alle():
    limit = min(int(request.args.get('limit', 50)), 500)
    offset = int(request.args.get('offset', 0))
    datum_van = request.args.get('van', '')
    datum_tot = request.args.get('tot', '')
    status = request.args.get('status', '')
    rekening_id = request.args.get('rekening_id', '')
    sorteer = request.args.get('sorteer', 'datum')
    volgorde = request.args.get('volgorde', 'desc')

    sorteer_velden = {
        'datum': 't.datum',
        'naam_tegenpartij': 't.naam_tegenpartij',
        'omschrijving_1': 't.omschrijving_1',
        'bedrag': 't.bedrag'
    }
    sorteer_col = sorteer_velden.get(sorteer, 't.datum')
    volgorde_sql = 'ASC' if volgorde == 'asc' else 'DESC'

    sql = """SELECT t.*, b.naam as rekening_naam
             FROM banktransacties t
             LEFT JOIN bankrekeningen b ON REPLACE(b.iban,' ','') = t.iban
             WHERE 1=1"""
    params = []
    if datum_van:
        sql += " AND t.datum >= ?"
        params.append(datum_van)
    if datum_tot:
        sql += " AND t.datum <= ?"
        params.append(datum_tot)
    if status:
        sql += " AND t.status = ?"
        params.append(status)
    if rekening_id:
        sql += " AND b.id = ?"
        params.append(int(rekening_id))
    sql += f" ORDER BY {sorteer_col} {volgorde_sql}, t.id {volgorde_sql} LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = database.query(sql, params)
    return json_response([dict(r) for r in rows])

@app.route('/api/transacties/hermatchen', methods=['POST'])
@auth_required
def api_hermatchen():
    from importeer import haal_matchregels, haal_bank_grootboek, boek_automatisch, haal_eigen_ibans, boek_intern
    from matchengine import zoek_match

    matchregels = haal_matchregels()
    eigen_ibans = haal_eigen_ibans()

    transacties = database.query("SELECT * FROM banktransacties WHERE status = 'nieuw'")
    auto_geboekt = 0

    for trans in transacties:
        trans = dict(trans)
        iban = trans['iban']
        tegenrekening = (trans.get('tegenrekening_iban') or '').replace(' ', '').upper()

        if tegenrekening and tegenrekening in eigen_ibans:
            gb_van = haal_bank_grootboek(iban)
            gb_naar = haal_bank_grootboek(tegenrekening)
            if gb_van and gb_naar:
                boek_intern(trans['id'], trans['datum'], trans['bedrag'], gb_van, gb_naar, g.gebruiker['id'])
                auto_geboekt += 1
                continue

        match = zoek_match(trans, matchregels)
        if match:
            gb_bank = haal_bank_grootboek(iban)
            if gb_bank:
                boek_automatisch(trans['id'], trans['datum'], trans['bedrag'], gb_bank,
                                 match['grootboek_id'], match['gb_omschrijving'], g.gebruiker['id'])
                auto_geboekt += 1

    return json_response({'auto_geboekt': auto_geboekt})

@app.route('/api/transacties/<int:tid>/boek', methods=['POST'])
@auth_required
def api_boek_transactie(tid):
    data = request.json or {}
    regels = data.get('regels', [])
    omschrijving = data.get('omschrijving', '')
    ok, bericht = boek_handmatig(tid, regels, g.gebruiker['id'], omschrijving)
    if not ok:
        return json_response({'error': bericht}, 400)
    return json_response({'bericht': bericht})

# ─── BOEKINGEN ───────────────────────────────────────────────

def _boekingen_where(args):
    """Bouw WHERE-clausule voor boekingen op basis van querystring parameters."""
    sql = """SELECT b.id, b.datum, b.omschrijving, b.type, b.transactie_id,
                    (SELECT COALESCE(SUM(br2.debet),0) FROM boekingsregels br2 WHERE br2.boeking_id=b.id) as totaal_bedrag,
                    t.naam_tegenpartij
             FROM boekingen b
             LEFT JOIN banktransacties t ON t.id = b.transactie_id
             WHERE 1=1"""
    params = []
    datum_van = args.get('van', '')
    datum_tot = args.get('tot', '')
    gb_id = args.get('grootboek_id', '')
    omschrijving = args.get('omschrijving', '')
    bedrag_van = args.get('bedrag_van', '')
    bedrag_tot = args.get('bedrag_tot', '')
    rekening = args.get('rekening', '')
    tegenrekening = args.get('tegenrekening', '')

    if datum_van:
        sql += " AND b.datum >= ?"; params.append(datum_van)
    if datum_tot:
        sql += " AND b.datum <= ?"; params.append(datum_tot)
    if gb_id:
        sql += " AND EXISTS (SELECT 1 FROM boekingsregels br WHERE br.boeking_id=b.id AND br.grootboek_id=?)"
        params.append(gb_id)
    if omschrijving:
        sql += " AND (b.omschrijving LIKE ? OR t.omschrijving_1 LIKE ?)"
        params.extend([f'%{omschrijving}%', f'%{omschrijving}%'])
    if bedrag_van:
        sql += " AND (SELECT COALESCE(SUM(br2.debet),0) FROM boekingsregels br2 WHERE br2.boeking_id=b.id) >= ?"
        params.append(float(bedrag_van))
    if bedrag_tot:
        sql += " AND (SELECT COALESCE(SUM(br2.debet),0) FROM boekingsregels br2 WHERE br2.boeking_id=b.id) <= ?"
        params.append(float(bedrag_tot))
    if rekening:
        sql += """ AND EXISTS (SELECT 1 FROM boekingsregels br JOIN grootboeken g ON g.id=br.grootboek_id
                               WHERE br.boeking_id=b.id AND (g.nummer LIKE ? OR g.omschrijving LIKE ?))"""
        params.extend([f'%{rekening}%', f'%{rekening}%'])
    if tegenrekening:
        sql += """ AND EXISTS (SELECT 1 FROM boekingsregels br JOIN grootboeken g ON g.id=br.grootboek_id
                               WHERE br.boeking_id=b.id AND (g.nummer LIKE ? OR g.omschrijving LIKE ?))"""
        params.extend([f'%{tegenrekening}%', f'%{tegenrekening}%'])
    return sql, params


@app.route('/api/boekingen', methods=['GET'])
@auth_required
def api_boekingen():
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    sql, params = _boekingen_where(request.args)
    sql += " ORDER BY b.datum DESC, b.id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = database.query(sql, params)
    return json_response([dict(r) for r in rows])


@app.route('/api/boekingen/count', methods=['GET'])
@auth_required
def api_boekingen_count():
    sql, params = _boekingen_where(request.args)
    count_sql = f"SELECT COUNT(*) as count FROM ({sql}) sub"
    row = database.query(count_sql, params, one=True)
    return json_response({'count': row['count'] if row else 0})


@app.route('/api/boekingen', methods=['POST'])
@auth_required
def api_boeking_aanmaken():
    data = request.json or {}
    datum = data.get('datum', '')
    omschrijving = data.get('omschrijving', '')
    regels = data.get('regels', [])

    if not datum:
        return json_response({'error': 'Datum is verplicht'}, 400)
    if len(regels) < 2:
        return json_response({'error': 'Minimaal 2 boekingsregels vereist'}, 400)

    totaal_debet = sum(float(r.get('debet', 0)) for r in regels)
    totaal_credit = sum(float(r.get('credit', 0)) for r in regels)
    if abs(totaal_debet - totaal_credit) > 0.005:
        return json_response({'error': f'Debet ({totaal_debet:.2f}) en credit ({totaal_credit:.2f}) zijn niet in balans'}, 400)

    from db import get_db
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO boekingen (omschrijving, datum, gebruiker_id, type) VALUES (?, ?, ?, 'normaal')",
            (omschrijving, datum, g.gebruiker['id'])
        )
        bid = cur.lastrowid
        for regel in regels:
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit, omschrijving) VALUES (?, ?, ?, ?, ?)",
                (bid, regel['grootboek_id'], float(regel.get('debet', 0)), float(regel.get('credit', 0)), regel.get('omschrijving'))
            )
        conn.commit()
        return json_response({'id': bid, 'bericht': 'Grootboekmutatie aangemaakt'}, 201)
    except Exception as e:
        conn.rollback()
        return json_response({'error': str(e)}, 500)
    finally:
        conn.close()


@app.route('/api/boekingen/<int:bid>', methods=['GET'])
@auth_required
def api_boeking_detail(bid):
    boeking = database.query("SELECT * FROM boekingen WHERE id = ?", (bid,), one=True)
    if not boeking:
        return json_response({'error': 'Niet gevonden'}, 404)
    regels = database.query(
        """SELECT br.*, g.nummer, g.omschrijving as gb_omschrijving
           FROM boekingsregels br JOIN grootboeken g ON g.id = br.grootboek_id
           WHERE br.boeking_id = ?""", (bid,)
    )
    return json_response({**dict(boeking), 'regels': [dict(r) for r in regels]})


@app.route('/api/boekingen/<int:bid>', methods=['PUT'])
@auth_required
def api_boeking_update(bid):
    boeking = database.query("SELECT * FROM boekingen WHERE id = ?", (bid,), one=True)
    if not boeking:
        return json_response({'error': 'Niet gevonden'}, 404)

    data = request.json or {}
    datum = data.get('datum', '')
    omschrijving = data.get('omschrijving', '')
    regels = data.get('regels', [])

    if not datum:
        return json_response({'error': 'Datum is verplicht'}, 400)
    if len(regels) < 2:
        return json_response({'error': 'Minimaal 2 boekingsregels vereist'}, 400)

    totaal_debet = sum(float(r.get('debet', 0)) for r in regels)
    totaal_credit = sum(float(r.get('credit', 0)) for r in regels)
    if abs(totaal_debet - totaal_credit) > 0.005:
        return json_response({'error': f'Debet ({totaal_debet:.2f}) en credit ({totaal_credit:.2f}) zijn niet in balans'}, 400)

    from db import get_db
    conn = get_db()
    try:
        conn.execute("UPDATE boekingen SET datum=?, omschrijving=? WHERE id=?", (datum, omschrijving, bid))
        conn.execute("DELETE FROM boekingsregels WHERE boeking_id=?", (bid,))
        for regel in regels:
            conn.execute(
                "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit, omschrijving) VALUES (?, ?, ?, ?, ?)",
                (bid, regel['grootboek_id'], float(regel.get('debet', 0)), float(regel.get('credit', 0)), regel.get('omschrijving'))
            )
        conn.commit()
        return json_response({'bericht': 'Bijgewerkt'})
    except Exception as e:
        conn.rollback()
        return json_response({'error': str(e)}, 500)
    finally:
        conn.close()


@app.route('/api/boekingen/<int:bid>', methods=['DELETE'])
@auth_required
def api_boeking_verwijderen(bid):
    boeking = database.query("SELECT * FROM boekingen WHERE id = ?", (bid,), one=True)
    if not boeking:
        return json_response({'error': 'Niet gevonden'}, 404)
    if boeking['transactie_id']:
        database.execute("UPDATE banktransacties SET status='nieuw' WHERE id=?", (boeking['transactie_id'],))
    database.execute("DELETE FROM boekingen WHERE id=?", (bid,))
    return json_response({'bericht': 'Verwijderd'})

# Openingsbalans
@app.route('/api/openingsbalans', methods=['POST'])
@beheerder_required
def api_openingsbalans():
    data = request.json or {}
    datum = data.get('datum', '2025-07-01')
    posten = data.get('posten', [])  # [{grootboek_id, saldo}]

    from db import get_db
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO boekingen (omschrijving, datum, gebruiker_id, type) VALUES ('Openingsbalans', ?, ?, 'opening')",
            (datum, g.gebruiker['id'])
        )
        bid = cur.lastrowid
        for post in posten:
            saldo = float(post.get('saldo', 0))
            if saldo == 0:
                continue
            if saldo > 0:
                conn.execute(
                    "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, ?, 0)",
                    (bid, post['grootboek_id'], saldo)
                )
            else:
                conn.execute(
                    "INSERT INTO boekingsregels (boeking_id, grootboek_id, debet, credit) VALUES (?, ?, 0, ?)",
                    (bid, post['grootboek_id'], abs(saldo))
                )
        conn.commit()
        return json_response({'bericht': 'Openingsbalans geboekt', 'boeking_id': bid})
    except Exception as e:
        conn.rollback()
        return json_response({'error': str(e)}, 500)
    finally:
        conn.close()

# ─── MATCHREGELS ─────────────────────────────────────────────

@app.route('/api/matchregels', methods=['GET'])
@auth_required
def api_matchregels():
    rows = database.query(
        """SELECT m.*, g.nummer as gb_nummer, g.omschrijving as gb_omschrijving
           FROM matchregels m JOIN grootboeken g ON g.id = m.grootboek_id
           WHERE m.actief = 1 ORDER BY m.naam"""
    )
    return json_response([dict(r) for r in rows])

@app.route('/api/matchregels', methods=['POST'])
@beheerder_required
def api_matchregel_aanmaken():
    data = request.json or {}
    conditie = data.get('conditie', '')
    geldig, fout = valideer_conditie_syntax(conditie)
    if not geldig:
        return json_response({'error': f'Ongeldige conditie: {fout}'}, 400)
    mid = database.execute(
        "INSERT INTO matchregels (naam, conditie, grootboek_id) VALUES (?, ?, ?)",
        (data.get('naam'), conditie, data.get('grootboek_id'))
    )
    return json_response({'id': mid, 'bericht': 'Matchregel aangemaakt'}, 201)

@app.route('/api/matchregels/<int:mid>', methods=['PUT'])
@beheerder_required
def api_matchregel_update(mid):
    data = request.json or {}
    conditie = data.get('conditie', '')
    geldig, fout = valideer_conditie_syntax(conditie)
    if not geldig:
        return json_response({'error': f'Ongeldige conditie: {fout}'}, 400)
    database.execute(
        "UPDATE matchregels SET naam=?, conditie=?, grootboek_id=? WHERE id=?",
        (data.get('naam'), conditie, data.get('grootboek_id'), mid)
    )
    return json_response({'bericht': 'Bijgewerkt'})

@app.route('/api/matchregels/<int:mid>', methods=['DELETE'])
@beheerder_required
def api_matchregel_verwijderen(mid):
    database.execute("UPDATE matchregels SET actief = 0 WHERE id = ?", (mid,))
    return json_response({'bericht': 'Verwijderd'})

@app.route('/api/matchregels/test', methods=['POST'])
@beheerder_required
def api_matchregel_test():
    data = request.json or {}
    conditie = data.get('conditie', '')
    geldig, fout = valideer_conditie_syntax(conditie)
    return json_response({'geldig': geldig, 'fout': fout})

# ─── BUDGETTEN ───────────────────────────────────────────────

@app.route('/api/budgetten', methods=['GET'])
@auth_required
def api_budgetten():
    jaar = request.args.get('jaar', '')
    gb_id = request.args.get('grootboek_id', '')
    sql = "SELECT * FROM budgetten WHERE 1=1"
    params = []
    if jaar:
        sql += " AND jaar = ?"; params.append(jaar)
    if gb_id:
        sql += " AND grootboek_id = ?"; params.append(gb_id)
    rows = database.query(sql, params)
    return json_response([dict(r) for r in rows])

@app.route('/api/budgetten', methods=['POST'])
@beheerder_required
def api_budget_instellen():
    data = request.json or {}
    posten = data.get('posten', [])  # [{grootboek_id, jaar, maand, bedrag}]
    for post in posten:
        database.execute(
            """INSERT INTO budgetten (grootboek_id, jaar, maand, bedrag)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(grootboek_id, jaar, maand) DO UPDATE SET bedrag = excluded.bedrag""",
            (post['grootboek_id'], post['jaar'], post['maand'], post['bedrag'])
        )
    return json_response({'bericht': f'{len(posten)} budget(ten) opgeslagen'})

# ─── RAPPORTAGES ─────────────────────────────────────────────

@app.route('/api/rapportages/balans', methods=['GET'])
@auth_required
def api_balans():
    from rapportages import balans
    peildatum = request.args.get('datum', '')
    if not peildatum:
        from datetime import date
        peildatum = date.today().isoformat()
    return json_response(balans(peildatum))

@app.route('/api/rapportages/wenv', methods=['GET'])
@auth_required
def api_wenv():
    from rapportages import winst_verlies
    from datetime import date
    jaar = int(request.args.get('jaar', date.today().year))
    return json_response(winst_verlies(jaar))

@app.route('/api/rapportages/maand', methods=['GET'])
@auth_required
def api_maandoverzicht():
    from rapportages import maandoverzicht
    from datetime import date
    jaar = int(request.args.get('jaar', date.today().year))
    return json_response(maandoverzicht(jaar))

@app.route('/api/rapportages/saldi', methods=['GET'])
@auth_required
def api_saldi():
    from rapportages import grootboek_saldi
    datum = request.args.get('datum', None)
    return json_response(grootboek_saldi(datum))

# ─── STARTUP ─────────────────────────────────────────────────

def initialiseer():
    database.init_db()
    # Maak standaard beheerder aan als geen gebruikers bestaan
    gebruikers = database.query("SELECT COUNT(*) as n FROM gebruikers", one=True)
    if gebruikers and gebruikers['n'] == 0:
        uid, _ = auth_module.maak_gebruiker('beheerder', 'Wijzig_dit_wachtwoord!', 'beheerder')
        print(f"⚠️  Standaard beheerder aangemaakt (id={uid}). Wijzig het wachtwoord direct na eerste login!")
    print("✅ Database geïnitialiseerd")

if __name__ == '__main__':
    initialiseer()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    print(f"🚀 Server gestart op http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
