import re

def parse_sql():
    with open('./siga-monolito/backup_inserts.sql', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Parse Aluno
    # Columns: id, ra, nome, data_nascimento, cpf, email, nome_responsavel, cpf_responsavel, ativo
    alunos = {}
    # Handles "SELECT * FROM (VALUES" or just "(VALUES" depending on how it's formatted. It seems to be "SELECT * FROM (VALUES"
    aluno_match = re.search(r'INSERT INTO public\.aluno \([^\)]+\)\s+SELECT \* FROM \(VALUES(.*?)\) AS', content, re.DOTALL)
    if aluno_match:
        aluno_data = aluno_match.group(1)
        tuples = re.findall(r'\((.*?)\)(?:,\n|\n)', aluno_data)
        for t in tuples:
            parts = re.split(r",\s*(?=(?:[^']*'[^']*')*[^']*$)", t)
            if len(parts) >= 3:
                a_id = parts[0].strip()
                a_ra = parts[1].strip().strip("'")
                a_nome = parts[2].strip().strip("'")
                alunos[a_id] = {'ra': a_ra, 'nome': a_nome}
    
    # 2. Parse Turma
    # Columns: ano_letivo, ativo, aulas_por_dia, id, modelo_grade_id, professor_regente_id, serie, codigo, nome, turno
    turmas = {}
    # We find all blocks of INSERT INTO public.turma ... VALUES ...;
    turma_blocks = re.findall(r'INSERT INTO public\.turma \([^\)]+\) VALUES\s+(.*?);', content, re.DOTALL)
    for block in turma_blocks:
        tuples = re.findall(r'\((.*?)\)', block)
        for t in tuples:
            parts = re.split(r",\s*(?=(?:[^']*'[^']*')*[^']*$)", t)
            if len(parts) == 10:
                t_ano_letivo = parts[0].strip()
                t_id = parts[3].strip()
                t_serie = parts[6].strip()
                t_codigo = parts[7].strip().strip("'")
                t_turno = parts[9].strip().strip("'")
                turmas[t_id] = {
                    'ano_letivo': t_ano_letivo,
                    'serie': t_serie,
                    'codigo': t_codigo,
                    'turno': t_turno
                }

    # 3. Parse Matricula
    # Columns: aluno_id, ano_letivo, data_cancelamento, data_matricula, id, serie, turma_id, motivo_cancelamento, numero, situacao, turno
    matriculas = []
    matricula_blocks = re.findall(r'INSERT INTO public\.matricula \([^\)]+\) VALUES\s+(.*?);', content, re.DOTALL)
    for block in matricula_blocks:
        tuples = re.findall(r'\((.*?)\)', block)
        for t in tuples:
            parts = re.split(r",\s*(?=(?:[^']*'[^']*')*[^']*$)", t)
            if len(parts) == 11:
                aluno_id = parts[0].strip()
                ano_letivo = parts[1].strip()
                data_cancelamento = parts[2].strip()
                data_matricula = parts[3].strip().strip("'")
                m_id = parts[4].strip()
                serie = parts[5].strip()
                turma_id = parts[6].strip()
                motivo_cancelamento = parts[7].strip()
                numero = parts[8].strip().strip("'")
                situacao = parts[9].strip().strip("'")
                turno = parts[10].strip().strip("'")
                
                matriculas.append({
                    'id': m_id,
                    'numero': numero,
                    'aluno_id': aluno_id,
                    'turma_id': turma_id,
                    'ano_letivo': ano_letivo,
                    'serie': serie,
                    'turno': turno,
                    'data_matricula': data_matricula,
                    'situacao': situacao
                })

    print(f"Parsed {len(alunos)} alunos")
    print(f"Parsed {len(turmas)} turmas")
    print(f"Parsed {len(matriculas)} matriculas")

    # Constructing new SQL for seed_matricula.sql
    sql_lines = [
        "BEGIN;",
        "",
        "SET client_encoding = 'UTF8';",
        "SET standard_conforming_strings = on;",
        "",
        f"-- Matrículas ({len(matriculas)} no total)",
        "INSERT INTO matricula (id, numero, aluno_id, aluno_nome, aluno_ra, turma_id, turma_identificacao,",
        "                       ano_letivo, serie, turno, data_matricula, situacao)",
        "SELECT * FROM (VALUES"
    ]

    values_lines = []
    for m in matriculas:
        a_id = m['aluno_id']
        t_id = m['turma_id']
        aluno = alunos.get(a_id, {'nome': 'Desconhecido', 'ra': 'Desconhecido'})
        turma = turmas.get(t_id, {'codigo': 'Desconhecido'})
        
        v_line = (
            f"    ({m['id']}, '{m['numero']}', {a_id}, '{aluno['nome']}', '{aluno['ra']}', "
            f"{t_id}, '{turma['codigo']}', {m['ano_letivo']}, {m['serie']}, "
            f"'{m['turno']}', DATE '{m['data_matricula']}', '{m['situacao']}')"
        )
        values_lines.append(v_line)
    
    sql_lines.append(",\n".join(values_lines))
    sql_lines.append(
        ") AS v(id, numero, aluno_id, aluno_nome, aluno_ra, turma_id, turma_identificacao,\n"
        "       ano_letivo, serie, turno, data_matricula, situacao)\n"
        "WHERE NOT EXISTS (SELECT 1 FROM matricula);\n"
        "SELECT setval('matricula_id_seq', (SELECT COALESCE(MAX(id), 1) FROM matricula));\n\n"
        "COMMIT;"
    )

    with open('./siga-microsservicos/init-scripts/seed_matricula.sql', 'w', encoding='utf-8') as f:
        f.write("\n".join(sql_lines))

if __name__ == "__main__":
    parse_sql()
