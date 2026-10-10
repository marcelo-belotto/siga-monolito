#!/usr/bin/env bash
#
# gerar-relatorios-pmd.sh
#
# Roda o relatório PMD (profile "pmd-report") em todos os microsserviços
# Maven encontrados recursivamente a partir do diretório onde este script
# é executado, e consolida os relatórios (pmd.xml + site HTML) numa pasta
# central única.
#
# Uso:
#   ./gerar-relatorios-pmd.sh
#
# Pré-requisitos:
#   - Rodar a partir da pasta pai que contém os microsserviços
#     (ex: siga-microsservicos/)
#   - JAVA_HOME apontando para um JDK compatível com o PMD (ex: JDK 21)
#   - Cada microsserviço já tem o profile "pmd-report" configurado no pom.xml
#
set -uo pipefail

# --- Configurações ---------------------------------------------------------

# Pasta central onde os relatórios consolidados serão salvos
OUTPUT_DIR="$(pwd)/relatorios-pmd-consolidado"

# Profile Maven que gera o relatório (o mesmo criado anteriormente no pom.xml)
MAVEN_PROFILE="pmd-report"

# Goal a ser executado (gera target/pmd.xml). Este é o mesmo comando confirmado
# como funcional: "mvn pmd:pmd -Ppmd-report"
MAVEN_GOAL="pmd:pmd"

# --- Preparação --------------------------------------------------------------

echo "==> Limpando/criando pasta de saída: ${OUTPUT_DIR}"
rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

# Timestamp para o resumo final
RESUMO="${OUTPUT_DIR}/RESUMO.txt"
echo "Relatório consolidado de complexidade (PMD) - $(date '+%Y-%m-%d %H:%M:%S')" > "${RESUMO}"
echo "==============================================================" >> "${RESUMO}"

# Contadores
TOTAL=0
SUCESSO=0
FALHA=0

# --- Descoberta dos módulos Maven -------------------------------------------
#
# Busca por qualquer pom.xml, mas ignora os que estão dentro de "target/"
# (evita pegar poms copiados/gerados por build) e ignora o pom.xml raiz
# caso o script seja executado dentro de um projeto multi-módulo agregador.

mapfile -t POM_FILES < <(find "$(pwd)" -mindepth 1 -maxdepth 3 -iname "pom.xml" -not -path "*/target/*" | sort)

if [ ${#POM_FILES[@]} -eq 0 ]; then
    echo "Nenhum pom.xml encontrado a partir de $(pwd). Verifique se você está na pasta correta."
    exit 1
fi

echo "==> Encontrados ${#POM_FILES[@]} módulo(s) Maven:"
for p in "${POM_FILES[@]}"; do
    echo "    - ${p}"
done
echo ""

# --- Execução por módulo -----------------------------------------------------

for POM in "${POM_FILES[@]}"; do
    MODULE_DIR="$(dirname "${POM}")"
    MODULE_NAME="$(basename "${MODULE_DIR}")"
    TOTAL=$((TOTAL + 1))

    echo "=============================================================="
    echo "==> [${MODULE_NAME}] Gerando relatório PMD..."
    echo "=============================================================="

    LOG_FILE="${OUTPUT_DIR}/${MODULE_NAME}-build.log"

    (
        cd "${MODULE_DIR}" || exit 1
        mvn -P"${MAVEN_PROFILE}" "${MAVEN_GOAL}" \
            > "${LOG_FILE}" 2>&1
    )
    BUILD_STATUS=$?

    DEST_DIR="${OUTPUT_DIR}/${MODULE_NAME}"
    mkdir -p "${DEST_DIR}"

    # Copia os artefatos relevantes, se existirem.
    # Com o goal "pmd:pmd", o artefato principal é target/pmd.xml.
    # A pasta target/site só existe se o goal "site" também tiver rodado
    # em algum momento anterior; se existir, copiamos como bônus.
    RELATORIO_GERADO=false

    if [ -f "${MODULE_DIR}/target/pmd.xml" ]; then
        cp "${MODULE_DIR}/target/pmd.xml" "${DEST_DIR}/pmd.xml"
        RELATORIO_GERADO=true
    fi

    if [ -d "${MODULE_DIR}/target/site" ]; then
        cp -r "${MODULE_DIR}/target/site" "${DEST_DIR}/site"
    fi

    if [ "${BUILD_STATUS}" -eq 0 ] && [ "${RELATORIO_GERADO}" = true ]; then
        SUCESSO=$((SUCESSO + 1))
        echo "OK] ${MODULE_NAME}: relatório copiado para ${DEST_DIR}"
        echo "[OK] ${MODULE_NAME}" >> "${RESUMO}"
    else
        FALHA=$((FALHA + 1))
        echo "FALHOU] ${MODULE_NAME}: veja ${LOG_FILE}"
        echo "[FALHOU] ${MODULE_NAME} - ver ${MODULE_NAME}-build.log" >> "${RESUMO}"
    fi

    echo ""
done

# --- Resumo final ------------------------------------------------------------

echo "==============================================================" >> "${RESUMO}"
echo "Total de módulos: ${TOTAL}" >> "${RESUMO}"
echo "Sucesso: ${SUCESSO}" >> "${RESUMO}"
echo "Falha: ${FALHA}" >> "${RESUMO}"

echo "=============================================================="
echo "Concluído."
echo "  Total:   ${TOTAL}"
echo "  Sucesso: ${SUCESSO}"
echo "  Falha:   ${FALHA}"
echo ""
echo "Relatórios consolidados em: ${OUTPUT_DIR}"
echo "Resumo:                     ${RESUMO}"
echo "=============================================================="

# --- Geração da página HTML única consolidada -------------------------------
#
# Requer o script consolidar-pmd.py na mesma pasta deste script (ou ajuste
# o caminho abaixo). Ele lê todos os pmd.xml copiados acima e monta uma
# única página HTML navegável, filtrável e ordenável.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONSOLIDAR_PY="${SCRIPT_DIR}/consolidar-pmd.py"

if [ -f "${CONSOLIDAR_PY}" ]; then
    echo ""
    echo "==> Gerando página HTML única consolidada..."
    if command -v python3 >/dev/null 2>&1; then
        python3 "${CONSOLIDAR_PY}" "${OUTPUT_DIR}" "${OUTPUT_DIR}/relatorio-consolidado.html"
    else
        echo "[AVISO] python3 não encontrado no PATH. Pulei a geração do HTML único."
        echo "        Instale o Python 3 ou rode manualmente:"
        echo "        python3 ${CONSOLIDAR_PY} ${OUTPUT_DIR} ${OUTPUT_DIR}/relatorio-consolidado.html"
    fi
else
    echo ""
    echo "[AVISO] consolidar-pmd.py não encontrado em ${SCRIPT_DIR}."
    echo "        Coloque-o na mesma pasta deste script para gerar o HTML único automaticamente."
fi