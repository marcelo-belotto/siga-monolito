#!/bin/bash
#
# docker-stats-exporter.sh
#
# Coleta periodicamente o "docker stats" de todos os containers rodando
# e grava em um único CSV estruturado, pronto para ser lido pelo
# script Python (gerar_relatorio_docker.py), que monta uma página HTML
# navegável com gráficos de CPU/Memória/Rede ao longo do tempo.
#
# Uso:
#   ./docker-stats-exporter.sh
#   (Ctrl+C para parar a coleta)
#
# Ajuste o INTERVALO_SEGUNDOS abaixo conforme a granularidade desejada.
#

CSV_FILE="monitoramento_docker.csv"
INTERVALO_SEGUNDOS=5

# Nome/caminho do script Python que gera a página HTML consolidada.
# Por padrão, assume que ele está na mesma pasta deste script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/gerar_relatorio_docker.py"
HTML_OUTPUT="relatorio-docker.html"

# Cria o cabeçalho apenas se o arquivo ainda não existir, para permitir
# retomar a coleta sem perder o histórico já gravado.
if [ ! -f "${CSV_FILE}" ]; then
    echo "Data_Hora,Container,CPU_Porcentagem,Memoria_Uso,Memoria_Limite,Memoria_Porcentagem,Net_In,Net_Out,Bloco_In,Bloco_Out" > "${CSV_FILE}"
fi

# --- Gera o relatório HTML ao encerrar a coleta (Ctrl+C / SIGINT / SIGTERM) --
#
# O "trap" intercepta o sinal antes do bash matar o processo, roda o Python
# para gerar a página, e só então finaliza o script (exit 0).
gerar_relatorio_e_sair() {
    echo ""
    echo "Coleta interrompida. Gerando relatório HTML..."

    if [ -f "${PYTHON_SCRIPT}" ]; then
        if command -v python3 >/dev/null 2>&1; then
            python3 "${PYTHON_SCRIPT}" "${CSV_FILE}" "${HTML_OUTPUT}"
        else
            echo "[AVISO] python3 não encontrado no PATH. Rode manualmente depois:"
            echo "        python3 ${PYTHON_SCRIPT} ${CSV_FILE} ${HTML_OUTPUT}"
        fi
    else
        echo "[AVISO] ${PYTHON_SCRIPT} não encontrado. Coloque-o na mesma pasta deste script."
    fi

    exit 0
}

trap gerar_relatorio_e_sair SIGINT SIGTERM

echo "Coletando docker stats a cada ${INTERVALO_SEGUNDOS}s em ${CSV_FILE}. Pressione Ctrl+C para parar e gerar o relatório."

while true; do
    TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

    # --format usando delimitador ";" para evitar conflito com a vírgula que
    # já aparece nativamente nos valores de memória/rede do docker stats
    # (ex: "12.3MiB / 1GiB"). Cada linha vira um registro CSV completo.
    docker stats --no-stream --format \
        "{{.Name}};{{.CPUPerc}};{{.MemUsage}};{{.MemPerc}};{{.NetIO}};{{.BlockIO}}" \
    | while IFS=';' read -r NOME CPU MEM_USAGE MEM_PERC NET_IO BLOCK_IO; do

        # Separa "12.3MiB / 1GiB" em USO e LIMITE
        MEM_USO="$(echo "${MEM_USAGE}" | awk -F' / ' '{print $1}' | xargs)"
        MEM_LIMITE="$(echo "${MEM_USAGE}" | awk -F' / ' '{print $2}' | xargs)"

        # Separa "1.2MB / 3.4MB" em NET_IN e NET_OUT
        NET_IN="$(echo "${NET_IO}" | awk -F' / ' '{print $1}' | xargs)"
        NET_OUT="$(echo "${NET_IO}" | awk -F' / ' '{print $2}' | xargs)"

        # Separa "1.2MB / 3.4MB" em BLOCO_IN e BLOCO_OUT
        BLOCO_IN="$(echo "${BLOCK_IO}" | awk -F' / ' '{print $1}' | xargs)"
        BLOCO_OUT="$(echo "${BLOCK_IO}" | awk -F' / ' '{print $2}' | xargs)"

        echo "${TIMESTAMP},${NOME},${CPU},${MEM_USO},${MEM_LIMITE},${MEM_PERC},${NET_IN},${NET_OUT},${BLOCO_IN},${BLOCO_OUT}" >> "${CSV_FILE}"
    done

    # "sleep &" em segundo plano + "wait" permite que o trap SIGINT
    # interrompa a espera imediatamente, em vez de aguardar o sleep terminar.
    sleep "${INTERVALO_SEGUNDOS}" &
    wait $!
done
