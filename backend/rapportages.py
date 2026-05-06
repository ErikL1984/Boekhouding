"""
Rapportage module — balans, W&V, maandoverzicht, budgetvergelijking
"""
from db import query

def haal_saldo(grootboek_id: int, tot_datum: str = None) -> float:
    """Bereken het saldo van een grootboek tot een bepaalde datum"""
    if tot_datum:
        row = query(
            """SELECT COALESCE(SUM(br.debet - br.credit), 0) as saldo
               FROM boekingsregels br
               JOIN boekingen b ON b.id = br.boeking_id
               WHERE br.grootboek_id = ? AND b.datum <= ?""",
            (grootboek_id, tot_datum), one=True
        )
    else:
        row = query(
            """SELECT COALESCE(SUM(br.debet - br.credit), 0) as saldo
               FROM boekingsregels br
               WHERE br.grootboek_id = ?""",
            (grootboek_id,), one=True
        )
    return round(float(row['saldo']), 2) if row else 0.0

def balans(peildatum: str) -> dict:
    """Genereer een balans op peildatum"""
    gb_rows = query(
        "SELECT id, nummer, omschrijving, categorie, groep, subgroep FROM grootboeken WHERE categorie = 'Balans' AND actief = 1 ORDER BY nummer"
    )

    activa = {}
    passiva = {}

    for gb in gb_rows:
        saldo = haal_saldo(gb['id'], peildatum)
        if saldo == 0:
            continue
        groep = gb['groep']
        item = {
            'id': gb['id'],
            'nummer': gb['nummer'],
            'omschrijving': gb['omschrijving'],
            'subgroep': gb['subgroep'],
            'saldo': saldo
        }
        # Activa-groepen
        if groep in ('Vaste activa', 'Liquide middelen'):
            activa.setdefault(groep, []).append(item)
        # Passiva-groepen
        elif groep in ('Eigen vermogen', 'Schulden'):
            passiva.setdefault(groep, []).append(item)

    totaal_activa = sum(i['saldo'] for groep in activa.values() for i in groep)
    totaal_passiva = sum(i['saldo'] for groep in passiva.values() for i in groep)

    return {
        'peildatum': peildatum,
        'activa': activa,
        'passiva': passiva,
        'totaal_activa': round(totaal_activa, 2),
        'totaal_passiva': round(totaal_passiva, 2),
        'in_balans': abs(totaal_activa - totaal_passiva) < 0.01
    }

def winst_verlies(jaar: int) -> dict:
    """Genereer een W&V-rekening voor een heel jaar"""
    datum_van = f"{jaar}-01-01"
    datum_tot = f"{jaar}-12-31"

    gb_rows = query(
        """SELECT id, nummer, omschrijving, groep, subgroep FROM grootboeken
           WHERE categorie = 'Winst en Verlies' AND actief = 1 ORDER BY groep, subgroep, nummer"""
    )

    GROEP_VOLGORDE = [
        'Inkomsten',
        'Maandelijkse vaste lasten',
        'Niet-maandelijkse vaste lasten',
        'Variabele lasten',
        'Sparen / reserveringen'
    ]

    resultaat = {}
    for gb in gb_rows:
        row = query(
            """SELECT COALESCE(SUM(br.credit - br.debet), 0) as totaal
               FROM boekingsregels br
               JOIN boekingen b ON b.id = br.boeking_id
               WHERE br.grootboek_id = ? AND b.datum BETWEEN ? AND ?""",
            (gb['id'], datum_van, datum_tot), one=True
        )
        totaal = round(float(row['totaal']), 2) if row else 0.0

        budget_row = query(
            """SELECT COALESCE(SUM(bedrag), 0) as budget
               FROM budgetten WHERE grootboek_id = ? AND jaar = ?""",
            (gb['id'], jaar), one=True
        )
        budget = round(float(budget_row['budget']), 2) if budget_row else 0.0

        groep = gb['groep']
        if groep not in resultaat:
            resultaat[groep] = []
        resultaat[groep].append({
            'id': gb['id'],
            'nummer': gb['nummer'],
            'omschrijving': gb['omschrijving'],
            'subgroep': gb['subgroep'],
            'gerealiseerd': totaal,
            'budget': budget,
            'afwijking': round(totaal - budget, 2)
        })

    # Sorteer op volgorde
    gesorteerd = {g: resultaat.get(g, []) for g in GROEP_VOLGORDE if g in resultaat}
    totaal_inkomsten = sum(i['gerealiseerd'] for i in gesorteerd.get('Inkomsten', []))
    totaal_lasten = sum(
        i['gerealiseerd']
        for g in ('Maandelijkse vaste lasten', 'Niet-maandelijkse vaste lasten', 'Variabele lasten', 'Sparen / reserveringen')
        for i in gesorteerd.get(g, [])
    )

    return {
        'jaar': jaar,
        'groepen': gesorteerd,
        'totaal_inkomsten': round(totaal_inkomsten, 2),
        'totaal_lasten': round(totaal_lasten, 2),
        'netto': round(totaal_inkomsten - totaal_lasten, 2)
    }

def maandoverzicht(jaar: int) -> dict:
    """Genereer een maandoverzicht met gerealiseerd + budget per grootboek per maand"""
    gb_rows = query(
        """SELECT id, nummer, omschrijving, groep, subgroep FROM grootboeken
           WHERE categorie = 'Winst en Verlies' AND actief = 1 ORDER BY groep, subgroep, nummer"""
    )

    GROEP_VOLGORDE = [
        'Inkomsten',
        'Maandelijkse vaste lasten',
        'Niet-maandelijkse vaste lasten',
        'Variabele lasten',
        'Sparen / reserveringen'
    ]

    data = {}
    for gb in gb_rows:
        maanden = {}
        for maand in range(1, 13):
            datum_van = f"{jaar}-{maand:02d}-01"
            import calendar
            laatste_dag = calendar.monthrange(jaar, maand)[1]
            datum_tot = f"{jaar}-{maand:02d}-{laatste_dag:02d}"

            real_row = query(
                """SELECT COALESCE(SUM(br.credit - br.debet), 0) as totaal
                   FROM boekingsregels br
                   JOIN boekingen b ON b.id = br.boeking_id
                   WHERE br.grootboek_id = ? AND b.datum BETWEEN ? AND ?""",
                (gb['id'], datum_van, datum_tot), one=True
            )
            gerealiseerd = round(float(real_row['totaal']), 2) if real_row else 0.0

            bud_row = query(
                "SELECT bedrag FROM budgetten WHERE grootboek_id = ? AND jaar = ? AND maand = ?",
                (gb['id'], jaar, maand), one=True
            )
            budget = round(float(bud_row['bedrag']), 2) if bud_row else 0.0

            maanden[maand] = {'gerealiseerd': gerealiseerd, 'budget': budget}

        totaal_gerealiseerd = sum(m['gerealiseerd'] for m in maanden.values())
        totaal_budget = sum(m['budget'] for m in maanden.values())
        groep = gb['groep']

        if groep not in data:
            data[groep] = []
        data[groep].append({
            'id': gb['id'],
            'nummer': gb['nummer'],
            'omschrijving': gb['omschrijving'],
            'subgroep': gb['subgroep'],
            'maanden': maanden,
            'totaal_gerealiseerd': round(totaal_gerealiseerd, 2),
            'totaal_budget': round(totaal_budget, 2),
        })

    gesorteerd = {g: data.get(g, []) for g in GROEP_VOLGORDE if g in data}
    return {'jaar': jaar, 'groepen': gesorteerd}

def grootboek_saldi(datum: str = None) -> list:
    """Haal alle grootboeknummers op met saldo"""
    rows = query(
        "SELECT id, nummer, omschrijving, categorie, groep, subgroep, is_bankrekening, rekening_naam FROM grootboeken WHERE actief = 1 ORDER BY nummer"
    )
    result = []
    for gb in rows:
        saldo = haal_saldo(gb['id'], datum)
        result.append({**dict(gb), 'saldo': saldo})
    return result
