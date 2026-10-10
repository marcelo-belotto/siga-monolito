#!/usr/bin/env python3
"""
consolidar-pmd.py

Lê todos os arquivos pmd.xml gerados para cada microsserviço (já copiados
pelo gerar-relatorios-pmd.sh para a pasta relatorios-pmd-consolidado/<servico>/pmd.xml)
e monta uma ÚNICA página HTML navegável com:
  - Resumo geral (total de serviços, classes, métodos, complexidade média)
  - Gráfico de distribuição por serviço
  - Tabela detalhada por serviço > classe > método, ordenável e filtrável

Uso:
    python3 consolidar-pmd.py [pasta_consolidado] [arquivo_saida.html]

Padrões:
    pasta_consolidado = ./relatorios-pmd-consolidado
    arquivo_saida.html = ./relatorios-pmd-consolidado/relatorio-consolidado.html

Requer apenas biblioteca padrão do Python 3 (xml.etree, re, os, sys).
"""

import os
import re
import sys
import html
import glob
import json
from xml.etree import ElementTree as ET

NS = {"pmd": "http://pmd.sourceforge.net/report/2.0.0"}


def find_pmd_xml_files(base_dir):
    """Encontra todos os pmd.xml dentro das subpastas de cada serviço."""
    pattern = os.path.join(base_dir, "*", "pmd.xml")
    return sorted(glob.glob(pattern))


def parse_complexity_from_text(text):
    """
    Extrai o valor numérico de complexidade do texto da violação, ex:
    "The method 'foo()' has a cyclomatic complexity of 12." -> 12
    "The class 'Bar' has a total cyclomatic complexity of 145 ..." -> 145
    Retorna None se não encontrar.
    """
    if not text:
        return None
    match = re.search(r"complexity of (\d+)", text)
    if match:
        return int(match.group(1))
    return None


def parse_pmd_xml(filepath, service_name):
    """
    Faz o parse de um pmd.xml e retorna uma lista de dicts, um por violação:
    {
        "service": ..., "file": ..., "package": ..., "class": ...,
        "method": ..., "complexity": ..., "priority": ..., "message": ...
    }
    Tenta lidar tanto com o XML tendo namespace declarado quanto sem.
    """
    results = []
    try:
        tree = ET.parse(filepath)
    except ET.ParseError as e:
        print(f"  [AVISO] Não foi possível parsear {filepath}: {e}")
        return results

    root = tree.getroot()

    # O PMD 7 às vezes gera XML sem namespace explícito, então tentamos
    # localizar as tags "file" e "violation" com ou sem prefixo de namespace.
    def findall(elem, tag):
        found = elem.findall(f"pmd:{tag}", NS)
        if found:
            return found
        return elem.findall(tag)

    for file_elem in findall(root, "file"):
        file_name = file_elem.get("name", "")
        for viol in findall(file_elem, "violation"):
            message = (viol.text or "").strip()
            complexity = parse_complexity_from_text(message)
            results.append({
                "service": service_name,
                "file": file_name,
                "package": viol.get("package", ""),
                "class": viol.get("class", ""),
                "method": viol.get("method", ""),
                "rule": viol.get("rule", ""),
                "priority": viol.get("priority", ""),
                "complexity": complexity,
                "message": message,
            })

    return results


def build_html(all_rows, services):
    """Gera o HTML final, com os dados embutidos como JSON para filtragem via JS."""

    total_violations = len(all_rows)
    complexities = [r["complexity"] for r in all_rows if r["complexity"] is not None]
    avg_complexity = round(sum(complexities) / len(complexities), 2) if complexities else 0
    max_complexity = max(complexities) if complexities else 0

    # Distribuição por serviço (contagem de métodos analisados)
    per_service_count = {}
    per_service_avg = {}
    for s in services:
        rows_s = [r for r in all_rows if r["service"] == s]
        comps_s = [r["complexity"] for r in rows_s if r["complexity"] is not None]
        per_service_count[s] = len(rows_s)
        per_service_avg[s] = round(sum(comps_s) / len(comps_s), 2) if comps_s else 0

    data_json = json.dumps(all_rows, ensure_ascii=False)
    services_json = json.dumps(services, ensure_ascii=False)
    per_service_count_json = json.dumps(per_service_count, ensure_ascii=False)
    per_service_avg_json = json.dumps(per_service_avg, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Relatório Consolidado de Complexidade Ciclomática</title>
<style>
  :root {{
    --bg: #0f1115;
    --panel: #171a21;
    --panel-2: #1e222b;
    --border: #2a2f3a;
    --text: #e6e8ec;
    --muted: #9aa3b2;
    --accent: #5b8cff;
    --low: #4caf50;
    --mid: #ffb020;
    --high: #ff5252;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
  }}
  header {{
    padding: 24px 32px;
    border-bottom: 1px solid var(--border);
    background: var(--panel);
  }}
  header h1 {{
    margin: 0 0 4px 0;
    font-size: 22px;
  }}
  header p {{
    margin: 0;
    color: var(--muted);
    font-size: 13px;
  }}
  .container {{
    padding: 24px 32px;
    max-width: 1400px;
    margin: 0 auto;
  }}
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 28px;
  }}
  .card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 18px;
  }}
  .card .label {{
    color: var(--muted);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
  }}
  .card .value {{
    font-size: 26px;
    font-weight: 600;
  }}
  .service-bars {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 28px;
  }}
  .service-bars h2 {{
    margin-top: 0;
    font-size: 16px;
  }}
  .bar-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 10px 0;
  }}
  .bar-label {{
    width: 200px;
    font-size: 13px;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .bar-track {{
    flex: 1;
    background: var(--panel-2);
    border-radius: 6px;
    height: 20px;
    overflow: hidden;
    position: relative;
  }}
  .bar-fill {{
    height: 100%;
    background: linear-gradient(90deg, var(--accent), #7aa2ff);
    border-radius: 6px 0 0 6px;
  }}
  .bar-value {{
    width: 90px;
    font-size: 12px;
    color: var(--muted);
    text-align: right;
  }}
  .filters {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 16px;
  }}
  .filters input, .filters select {{
    background: var(--panel-2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 10px;
    border-radius: 6px;
    font-size: 13px;
  }}
  .filters input {{
    flex: 1;
    min-width: 200px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    font-size: 13px;
  }}
  thead th {{
    background: var(--panel-2);
    text-align: left;
    padding: 10px 12px;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
    color: var(--muted);
    font-weight: 600;
    border-bottom: 1px solid var(--border);
  }}
  thead th:hover {{ color: var(--text); }}
  tbody td {{
    padding: 9px 12px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }}
  tbody tr:hover {{ background: var(--panel-2); }}
  .pill {{
    display: inline-block;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
  }}
  .pill.low {{ background: rgba(76,175,80,0.15); color: var(--low); }}
  .pill.mid {{ background: rgba(255,176,32,0.15); color: var(--mid); }}
  .pill.high {{ background: rgba(255,82,82,0.15); color: var(--high); }}
  .file-path {{
    color: var(--muted);
    font-size: 11px;
  }}
  .count-info {{
    color: var(--muted);
    font-size: 12px;
    margin-bottom: 8px;
  }}
</style>
</head>
<body>

<header>
  <h1>Relatório Consolidado de Complexidade Ciclomática</h1>
  <p>Gerado automaticamente a partir dos relatórios PMD do monolito</p>
</header>

<div class="container">

  <div class="summary-grid">
    <div class="card">
      <div class="label">Monolito</div>
      <div class="value">{len(services)}</div>
    </div>
    <div class="card">
      <div class="label">Métodos/Classes analisados</div>
      <div class="value">{total_violations}</div>
    </div>
    <div class="card">
      <div class="label">Complexidade média</div>
      <div class="value">{avg_complexity}</div>
    </div>
    <div class="card">
      <div class="label">Complexidade máxima</div>
      <div class="value">{max_complexity}</div>
    </div>
  </div>

  <div class="service-bars">
    <h2>Complexidade média</h2>
    <div id="serviceBars"></div>
  </div>

  <div class="filters">
    <input type="text" id="searchInput" placeholder="Buscar por classe, método, arquivo ou pacote...">
    <select id="serviceFilter">
      <option value="">Todos as classes</option>
    </select>
    <select id="levelFilter">
      <option value="">Todos os níveis</option>
      <option value="low">Baixa (&lt; 10)</option>
      <option value="mid">Moderada (10–20)</option>
      <option value="high">Alta (&gt; 20)</option>
    </select>
  </div>

  <div class="count-info" id="countInfo"></div>

  <table>
    <thead>
      <tr>
        <th data-key="service">Serviço</th>
        <th data-key="package">Pacote</th>
        <th data-key="class">Classe</th>
        <th data-key="method">Método</th>
        <th data-key="complexity">Complexidade</th>
        <th data-key="priority">Prioridade PMD</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>

</div>

<script>
  const DATA = {data_json};
  const SERVICES = {services_json};
  const PER_SERVICE_COUNT = {per_service_count_json};
  const PER_SERVICE_AVG = {per_service_avg_json};

  // --- Popular gráfico de barras por serviço ---
  const barsContainer = document.getElementById('serviceBars');
  const maxAvg = Math.max(1, ...Object.values(PER_SERVICE_AVG));
  SERVICES.forEach(s => {{
    const avg = PER_SERVICE_AVG[s] || 0;
    const count = PER_SERVICE_COUNT[s] || 0;
    const pct = Math.max(4, (avg / maxAvg) * 100);
    const row = document.createElement('div');
    row.className = 'bar-row';
    row.innerHTML = `
      <div class="bar-label" title="${{s}}">${{s}}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${{pct}}%"></div></div>
      <div class="bar-value">${{avg}} (${{count}} itens)</div>
    `;
    barsContainer.appendChild(row);
  }});

  // --- Popular filtro de serviços ---
  const serviceFilter = document.getElementById('serviceFilter');
  SERVICES.forEach(s => {{
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    serviceFilter.appendChild(opt);
  }});

  // --- Renderização da tabela ---
  const tableBody = document.getElementById('tableBody');
  const countInfo = document.getElementById('countInfo');
  let sortKey = 'complexity';
  let sortAsc = false;

  function levelClass(c) {{
    if (c === null || c === undefined) return '';
    if (c < 10) return 'low';
    if (c <= 20) return 'mid';
    return 'high';
  }}

  function levelLabel(c) {{
    if (c === null || c === undefined) return 'N/D';
    return String(c);
  }}

  function render() {{
    const search = document.getElementById('searchInput').value.toLowerCase();
    const serviceVal = serviceFilter.value;
    const levelVal = document.getElementById('levelFilter').value;

    let rows = DATA.filter(r => {{
      const matchesSearch = !search || [r.service, r.package, r.class, r.method, r.file]
        .join(' ').toLowerCase().includes(search);
      const matchesService = !serviceVal || r.service === serviceVal;
      const lvl = levelClass(r.complexity);
      const matchesLevel = !levelVal || lvl === levelVal;
      return matchesSearch && matchesService && matchesLevel;
    }});

    rows.sort((a, b) => {{
      let va = a[sortKey];
      let vb = b[sortKey];
      if (va === null || va === undefined) va = -1;
      if (vb === null || vb === undefined) vb = -1;
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    }});

    countInfo.textContent = `Exibindo ${{rows.length}} de ${{DATA.length}} itens`;

    tableBody.innerHTML = rows.map(r => `
      <tr>
        <td>${{r.service}}</td>
        <td>${{r.package || ''}}</td>
        <td>${{r.class || ''}}<div class="file-path">${{(r.file || '').split('/').pop()}}</div></td>
        <td>${{r.method || ''}}</td>
        <td><span class="pill ${{levelClass(r.complexity)}}">${{levelLabel(r.complexity)}}</span></td>
        <td>${{r.priority || ''}}</td>
      </tr>
    `).join('');
  }}

  document.getElementById('searchInput').addEventListener('input', render);
  serviceFilter.addEventListener('change', render);
  document.getElementById('levelFilter').addEventListener('change', render);

  document.querySelectorAll('thead th').forEach(th => {{
    th.addEventListener('click', () => {{
      const key = th.getAttribute('data-key');
      if (sortKey === key) {{
        sortAsc = !sortAsc;
      }} else {{
        sortKey = key;
        sortAsc = true;
      }}
      render();
    }});
  }});

  render();
</script>

</body>
</html>
"""
    return html_content


def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "./relatorios-pmd-consolidado"
    output_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(base_dir, "relatorio-consolidado.html")

    if not os.path.isdir(base_dir):
        print(f"Pasta não encontrada: {base_dir}")
        sys.exit(1)

    pmd_files = find_pmd_xml_files(base_dir)
    if not pmd_files:
        print(f"Nenhum pmd.xml encontrado em {base_dir}/*/pmd.xml")
        sys.exit(1)

    print(f"Encontrados {len(pmd_files)} arquivo(s) pmd.xml:")
    all_rows = []
    services = []
    for f in pmd_files:
        service_name = os.path.basename(os.path.dirname(f))
        print(f"  - {service_name}: {f}")
        rows = parse_pmd_xml(f, service_name)
        all_rows.extend(rows)
        if service_name not in services:
            services.append(service_name)

    print(f"\nTotal de violações/métodos coletados: {len(all_rows)}")

    html_out = build_html(all_rows, services)
    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write(html_out)

    print(f"\nRelatório consolidado gerado em: {output_file}")


if __name__ == "__main__":
    main()
