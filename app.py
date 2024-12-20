import logging
import sqlite3
import re
import warnings
from flask import Flask, render_template, abort, g, jsonify

# Suppress FutureWarnings
warnings.filterwarnings('ignore', category=FutureWarning)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Flask app setup
APP = Flask(__name__)

# Database connection
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('AlunosMatriculados.db', check_same_thread=False)
        g.db.row_factory = sqlite3.Row
        logging.info('Connected to database')
    return g.db

def close_db(exception=None):
    db = g.pop('db', None)
    if db:
        db.close()
        logging.info('Closed database connection')

APP.teardown_appcontext(close_db)

def execute(sql, args=None):
    sql = re.sub('\s+', ' ', sql)
    logging.info('SQL: {} Args: {}'.format(sql, args))
    cur = get_db().cursor()
    return cur.execute(sql, args) if args else cur.execute(sql)

# Jinja2 filters for dynamic content
@APP.template_filter('startswith')
def startswith_filter(s, prefix):
    return str(s).lower().startswith(prefix)

@APP.template_filter('endswith')
def endswith_filter(s, suffix):
    return str(s).lower().endswith(suffix)

@APP.route('/')
def index():
    try:
        # Perform individual queries for each table count
        stats = {}
        stats['n_entidades'] = execute('SELECT COUNT(*) FROM Entidade').fetchone()[0]
        stats['n_anos'] = execute('SELECT COUNT(*) FROM AnoLetivo').fetchone()[0]
        stats['n_cursos'] = execute('SELECT COUNT(*) FROM Cursos').fetchone()[0]
        stats['n_ofertas'] = execute('SELECT COUNT(*) FROM Oferta').fetchone()[0]
        stats['n_organizacoes'] = execute('SELECT COUNT(*) FROM Organizacao').fetchone()[0]
        stats['n_niveis'] = execute('SELECT COUNT(*) FROM NivelEnsino').fetchone()[0]
        stats['n_orientacoes'] = execute('SELECT COUNT(*) FROM Orientacao').fetchone()[0]
        stats['n_ciclos'] = execute('SELECT COUNT(*) FROM CicloEstudos').fetchone()[0]
        stats['n_sexos'] = execute('SELECT COUNT(*) FROM Sexo').fetchone()[0]
        stats['n_concelhos'] = execute('SELECT COUNT(*) FROM Concelho').fetchone()[0]
        stats['n_distritos'] = execute('SELECT COUNT(*) FROM Distrito').fetchone()[0]
        stats['n_nutsii'] = execute('SELECT COUNT(*) FROM NUTSII').fetchone()[0]
        stats['n_nutsiii'] = execute('SELECT COUNT(*) FROM NUTSIII').fetchone()[0]
        stats['n_anoEscolaridade'] = execute('SELECT COUNT(*) FROM AnoEscolaridade').fetchone()[0]
        stats['n_inscricoes'] = execute('SELECT sum(NumeroAlunosMatriculados) FROM Inscricoes').fetchone()[0]
        stats['n_localizacao'] = execute('SELECT COUNT(*) FROM Localizacao').fetchone()[0]
        stats['n_escola'] = execute('SELECT COUNT(*) FROM Escola').fetchone()[0]
        stats['n_agrupamento'] = execute('SELECT COUNT(*) FROM Agrupamento').fetchone()[0]
        stats['n_EscolaSede'] = execute('SELECT COUNT(*) FROM EscolaSede').fetchone()[0]

        logging.info(stats)
        return render_template('index.html', stats=stats)

    except Exception as e:
        logging.error(f"Error retrieving stats: {e}")
        return "An error occurred while fetching the statistics.", 500

# List table route
@APP.route('/list/<table_name>/')
def list_table(table_name):
    allowed_tables = [row[0] for row in execute("SELECT name FROM sqlite_master WHERE type='table'")]
    if table_name not in allowed_tables:
        return "Invalid table name", 400
    query = f'SELECT * FROM {table_name}'
    try:
        table_data = execute(query).fetchall()
    except Exception as e:
        logging.error(f"Error retrieving table {table_name}: {e}")
        return "An error occurred while fetching the table.", 500
    return render_template('list_tables.html', table_name=table_name, table_data=table_data)

@APP.route('/list/<table_name>/<int:id>')
def dynamic_table_details(table_name, id):
    try:
        # Get the list of valid table names to validate the input
        allowed_tables = [row[0] for row in execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if table_name not in allowed_tables:
            return "Invalid table name", 400

        # Get the primary key column for the specified table
        pk_query = f"PRAGMA table_info({table_name})"
        table_info = execute(pk_query).fetchall()
        primary_key = None
        for column in table_info:
            if column['pk'] == 1:  # Check if this column is the primary key
                primary_key = column['name']
                break

        if not primary_key:
            return f"No primary key found for table {table_name}", 500

        # Construct the query dynamically using the primary key
        query = f"SELECT * FROM {table_name} WHERE {primary_key} = ?"
        record = execute(query, (id,)).fetchone()

        # Handle the case where no record is found
        if not record:
            return f"{table_name} with {primary_key} = {id} not found", 404

        # Render the record details
        return render_template('dynamic_table.html', table_name=table_name, record=dict(record))

    except Exception as e:
        logging.error(f"Error fetching record from {table_name}: {e}")
        return "An error occurred while fetching the record.", 500

#@APP.route('/queries')
#def queries():
#    return render_template('queries.html')

@APP.route('/tabelas')
def tabelas():
    return render_template('tabelas.html')

@APP.route('/queries')
def queries():
    try:
        stats = {}
        stats['n_query1'] = [row['Curso'] for row in execute('SELECT Curso FROM Cursos').fetchall()]
        stats['n_query2'] = [
            {'Curso': row['Curso'], 'NumeroMatriculas': row['NumeroMatriculas']}
            for row in execute(
                'SELECT Curso, COUNT(*) AS NumeroMatriculas '
                'FROM Inscricoes I '
                'JOIN Cursos C ON I.CODCurso = C.CODCurso '
                'GROUP BY C.CODCurso'
            ).fetchall()
        ]
        stats['n_query3'] = [
            {'Entidade': row['Entidade'], 'TotalAlunos': row['TotalAlunos']}
            for row in execute(
                'SELECT E.Entidade, SUM(I.NumeroAlunosMatriculados) AS TotalAlunos '
                'FROM Inscricoes I '
                'JOIN Entidade E ON I.CODEntidade = E.CODEntidade '
                'GROUP BY E.CODEntidade '
                'ORDER BY TotalAlunos DESC'
            ).fetchall()
        ]
        stats['n_query4'] = [
            {'CODEntidade': row['CODEntidade'], 'Escola': row['Escola'], 'TotalAlunos': row['TotalAlunos']}
            for row in execute(
                'SELECT DISTINCT I.CODEntidade, Es.Escola, SUM(I.NumeroAlunosMatriculados) AS TotalAlunos '
                'FROM Inscricoes I '
                'JOIN Entidade E ON E.CODEntidade = I.CODEntidade '
                'JOIN Escola Es ON E.CODEscola = Es.CODEscola '
                'GROUP BY I.CODEntidade '
                'HAVING E.Natureza LIKE "%privado%"'
            ).fetchall()
        ]
        stats['n_query5'] = [
            {'Distrito': row['distrito'], 'TotalPrivadas': row['total_privadas'], 'TotalPublicas': row['total_publicas']}
            for row in execute(
                'SELECT D.distrito, '
                'count(CASE WHEN E.Natureza LIKE "%Privado%" THEN E.CODEscola END) AS total_privadas, '
                'count(CASE WHEN E.Natureza LIKE "%Público%" THEN E.CODEscola END) AS total_publicas '
                'FROM Distrito D '
                'JOIN Concelho C ON D.CODDistrito = C.CODDistrito '
                'JOIN Localizacao L ON L.CODConcelho = C.CODConcelho '
                'JOIN Entidade E ON L.CODEntidade = E.CODEntidade '
                'GROUP BY D.distrito'
            ).fetchall()
        ]
        stats['n_query6'] = [
            {'Concelho': row['Concelho'], 'MaxAlunos': row['MAX(TotalAlunos)']}
            for row in execute(
                'WITH nrinscritosconcelho AS ('
                'SELECT C.Concelho, SUM(NumeroAlunosMatriculados) AS TotalAlunos '
                'FROM Localizacao L '
                'JOIN Inscricoes I ON L.CODEntidade = I.CODEntidade '
                'JOIN Concelho C ON L.CODConcelho = C.CODConcelho '
                'GROUP BY L.CODConcelho) '
                'SELECT Concelho, MAX(TotalAlunos) FROM nrinscritosconcelho'
            ).fetchall()
        ]
        stats['n_query7'] = [
            {'NUTSII': row['NUTSII'], 'TotalEscolas': row['total_escolas']}
            for row in execute(
                'SELECT COUNT(E.CODEscola) AS total_escolas, NII.NUTSII '
                'FROM Entidade E '
                'JOIN Localizacao L ON L.CODEntidade = E.CODEntidade '
                'JOIN Concelho C ON L.CODConcelho = C.CODConcelho '
                'JOIN NUTSIII NIII ON C.CODNUTSIII = NIII.CODNUTSIII '
                'JOIN NUTSII NII ON NIII.CODNUTSII = NII.CODNUTSII '
                'GROUP BY NII.NUTSII '
                'ORDER BY total_escolas DESC'
            ).fetchall()
        ]
        stats['n_query8'] = [
            {'NivelEnsino': row['NivelEnsino'], 'TotalAlunos': row['TotalAlunos']}
            for row in execute(
                'SELECT N.NivelEnsino, SUM(NumeroAlunosMatriculados) AS TotalAlunos '
                'FROM Inscricoes I '
                'JOIN Nivelensino N ON I.CODNivelEnsino = N.CODNivelEnsino '
                'GROUP BY N.CODNivelEnsino'
            ).fetchall()
        ]
        stats['n_query9'] = [
            {'Concelho': row['Concelho'], 'Sexo': row['Sexo'], 'TotalAlunos': row['TotalAlunos']}
            for row in execute(
                'SELECT C.Concelho, S.Sexo, SUM(NumeroAlunosMatriculados) AS TotalAlunos '
                'FROM Localizacao L '
                'JOIN Inscricoes I ON L.CODEntidade = I.CODEntidade '
                'JOIN Sexo S ON I.CODSexo = S.CODSexo '
                'JOIN Concelho C ON L.CODConcelho = C.CODConcelho '
                'GROUP BY L.CODConcelho, S.CODSexo'
            ).fetchall()
        ]
        stats['n_query10'] = [
            {'Distrito': row['Distrito'], 'Natureza': row['Natureza'], 'PCTPublico': row['PCTPublico']}
            for row in execute(
                'WITH NrAlunos AS ('
                'SELECT D.CODDistrito, SUM(I.NumeroAlunosMatriculados) AS NumeroAlunosMatriculados '
                'FROM Inscricoes I '
                'JOIN Entidade E ON I.CODEntidade = E.CODEntidade '
                'JOIN Concelho C ON L.CODConcelho = C.CODConcelho '
                'JOIN Distrito D ON C.CODDistrito = D.CODDistrito '
                'JOIN Localizacao L ON E.CODEntidade = L.CODEntidade '
                'GROUP BY D.CODDistrito) '
                'SELECT D.Distrito, E.Natureza, 100 * SUM(I.NumeroAlunosMatriculados) / NA.NumeroAlunosMatriculados as PCTPublico '
                'FROM Inscricoes I '
                'JOIN Entidade E ON I.CODEntidade = E.CODEntidade '
                'JOIN Concelho C ON L.CODConcelho = C.CODConcelho '
                'JOIN Distrito D ON C.CODDistrito = D.CODDistrito '
                'JOIN Localizacao L ON E.CODEntidade = L.CODEntidade '
                'JOIN NrAlunos NA ON D.CODDistrito = NA.CODDistrito '
                'WHERE E.Natureza LIKE "%Público%" '
                'GROUP BY D.CODDistrito, E.Natureza '
                'ORDER BY D.CODDistrito, E.Natureza'
            ).fetchall()
        ]
        stats['n_query11'] = [
            {'Curso': row['curso'], 'Diferenca': row['diferenca']}
            for row in execute(
                'WITH alunos_por_sexo AS ('
                'SELECT C.curso, '
                'sum(CASE WHEN S.Sexo = "Homens" THEN I.NumeroAlunosMatriculados ELSE 0 END) AS total_masculino, '
                'sum(CASE WHEN S.Sexo = "Mulheres" THEN I.NumeroAlunosMatriculados ELSE 0 END) AS total_feminino '
                'FROM inscricoes I '
                'JOIN Cursos C ON I.CODCurso = C.CODCurso '
                'JOIN Sexo S ON I.CODSexo = S.CODSexo '
                'GROUP BY C.Curso), '
                'diferencas AS ('
                'SELECT curso, abs(total_masculino - total_feminino) AS diferenca '
                'FROM alunos_por_sexo) '
                'SELECT curso, diferenca '
                'FROM diferencas '
                'WHERE diferenca = (SELECT max(diferenca) FROM diferencas)'
            ).fetchall()
        ]
        stats['n_query12'] = [
            {'Concelho': row['Concelho'], 'Entidade': row['Entidade'], 'MaxAlunos': row['MAXAlunos']}
            for row in execute(
                'WITH NrAlunosEntidade AS ('
                'SELECT C.concelho, E.entidade, SUM(I.NumeroAlunosMatriculados) AS nr_alunos '
                'FROM Inscricoes I '
                'JOIN Entidade E ON I.CODEntidade = E.CODEntidade '
                'JOIN Localizacao L ON E.CODEntidade = L.CODEntidade '
                'JOIN Concelho C ON L.CODConcelho = C.CODConcelho '
                'GROUP BY C.CODConcelho, I.CODEntidade) '
                'SELECT Concelho, Entidade, MAX(nr_alunos) as MAXAlunos '
                'FROM NrAlunosEntidade '
                'GROUP BY Concelho '
                'ORDER BY MAXAlunos DESC'
            ).fetchall()
        ]
        
        logging.info(stats)
        return render_template('queries.html', stats=stats)

    except Exception as e:
        logging.error(f"Error retrieving stats: {e}")
        return "An error occurred while fetching the statistics.", 500

@APP.route('/data')
def get_data():

    # Connect to the database
    db = sqlite3.connect("AlunosMatriculados.db")
    cursor = db.cursor()

    # Execute the query
    query = """
    SELECT N.NivelEnsino, SUM(NumeroAlunosMatriculados) AS TotalAlunos
    FROM Inscricoes I
    JOIN Nivelensino N ON I.CODNivelEnsino = N.CODNivelEnsino
    GROUP BY N.CODNivelEnsino
    """
    cursor.execute(query)
    results = cursor.fetchall()

    print(results)

    data = [{'NivelEnsino': row[0], 'TotalAlunos': row[1]} for row in results]
    db.close()
    return jsonify(data)

@APP.route('/sexo')
def get_sexo():

    # Connect to the database
    db = sqlite3.connect("AlunosMatriculados.db")
    cursor = db.cursor()

    # Execute the query
    query = """
    select sexo.sexo, sum(inscricoes.NumeroAlunosMatriculados) as total_inscritos from sexo
    join inscricoes on inscricoes.codsexo = sexo.codsexo
    group by sexo.codsexo
    """
    cursor.execute(query)
    results = cursor.fetchall()

    print(results)

    data = [{'Sexo': row[0], 'TotalAlunos': row[1]} for row in results]
    db.close()
    return jsonify(data)

@APP.route('/natureza')
def get_natureza():

    # Connect to the database
    db = sqlite3.connect("AlunosMatriculados.db")
    cursor = db.cursor()

    # Execute the query
    query = """
    select entidade.Natureza, count(entidade.CODEntidade) as TotalEntidades from entidade
    group by entidade.natureza
    """
    cursor.execute(query)
    results = cursor.fetchall()

    print(results)

    data = [{'Natureza': row[0], 'TotalEntidades': row[1]} for row in results]
    db.close()
    return jsonify(data)

# Main server start-up
if __name__ == '__main__':
    APP.run(host='0.0.0.0', port=9001)
