import logging
import re
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process
from unidecode import unidecode

logger = logging.getLogger(__name__)

LIMIAR_NOME = 65
LIMIAR_EMPATE = 5

_PROC_KEYWORDS: list[tuple[list[str], str]] = [
    (["eletrocardiograma", "eletroca"], "ELETROCARDIOGRAMA"),
    (["ultrassom", "ultrasso"], "ULTRASSOM ABDOMINAL"),
    (["espirometria", "espirome"], "ESPIROMETRIA"),
    (["raio"], "RAIO-X TORAX"),
    (["tomografia", "tomograf"], "TOMOGRAFIA COMPUTADORIZADA"),
    (["endoscopia", "endoscop"], "ENDOSCOPIA DIGESTIVA"),
    (["ecocardiograma", "ecocardi"], "ECOCARDIOGRAMA"),
    (["ressonancia", "ressonan"], "RESSONANCIA MAGNETICA"),
    (["examedes", "sangue"], "EXAME DE SANGUE COMPLETO"),
    (["consulta"], "CONSULTA CLINICA GERAL"),
]

_ABREV_PROC = re.compile(r"\b(ELE|ULT|ESP|RAI|TOM|END|ECO|RES|EXA|CON)\b")
_ABREV_PROC_MAP = {
    "ELE": "ELETROCARDIOGRAMA", "ULT": "ULTRASSOM ABDOMINAL", "ESP": "ESPIROMETRIA",
    "RAI": "RAIO-X TORAX", "TOM": "TOMOGRAFIA COMPUTADORIZADA", "END": "ENDOSCOPIA DIGESTIVA",
    "ECO": "ECOCARDIOGRAMA", "RES": "RESSONANCIA MAGNETICA", "EXA": "EXAME DE SANGUE COMPLETO",
    "CON": "CONSULTA CLINICA GERAL",
}
_RUIDO = re.compile(
    r"\b(laudo|resultado|final|rel|nov|nov24|112024|exame|exam|xto)\b", re.IGNORECASE
)
# Captura: DD.MM.AAAA, DD_MM, 112024, 20241101 e números soltos de 1-2 dígitos (dias/meses)
_DATA = re.compile(r"\b\d{1,2}[._]\d{1,2}([._]\d{2,4})?\b|\b\d{6,8}\b|\b\d{1,2}\b")
_SEPARADORES = re.compile(r"[_\-\.]+")
_NAO_ALFANUM = re.compile(r"[^A-Z0-9 ]")



def _normalizar(texto: str) -> str:
    """Funçao diferente de _normalizar_nome pois agora removemos vírgulas e outros caracteres"""
    t = unidecode(str(texto)).upper()
    t = _NAO_ALFANUM.sub(" ", t)
    return " ".join(t.split())


def _extrair_nome_candidato(nome_arquivo: str) -> str:
    """Remove procedimentos, datas e ruído do filename — deixa só o nome do paciente."""
    stem = Path(nome_arquivo).stem
    stem = _SEPARADORES.sub(" ", stem)  # primeiro: _ - . viram espaço para word boundaries funcionarem
    stem = _ABREV_PROC.sub(" ", stem)
    stem = _DATA.sub(" ", stem)
    stem = _RUIDO.sub(" ", stem)
    for keywords, _ in _PROC_KEYWORDS:
        for kw in keywords:
            stem = re.sub(rf"\b{re.escape(kw)}\b", " ", stem, flags=re.IGNORECASE)
    return _normalizar(stem)


def _identificar_procedimento(nome_arquivo: str) -> str | None:
    """Tenta extrair o procedimento do nome do arquivo."""
    # Abreviações de 3 letras têm precedência (ex: _ELE_, _TOM_)
    m = _ABREV_PROC.search(nome_arquivo)
    if m:
        return _ABREV_PROC_MAP.get(m.group(1))

    norm = _normalizar(nome_arquivo)
    for keywords, procedimento in _PROC_KEYWORDS:
        if any(_normalizar(kw) in norm for kw in keywords):
            return procedimento
    return None


def _formatar_cpf(cpf: str) -> str:
    return re.sub(r"[^\d]", "", str(cpf))


def _formatar_nome_saida(nome_csv: str) -> str:
    """'OLIVEIRA, MARIA' → 'MARIAOLIVEIRA'"""
    partes = [p.strip() for p in nome_csv.split(",", 1)]
    nome = f"{partes[1]} {partes[0]}" if len(partes) == 2 else nome_csv
    return _normalizar(nome).replace(" ", "")


def _indexar_pacientes(df: pd.DataFrame) -> dict[str, list[dict]]:
    """Agrupa cobranças por nome normalizado (ordem natural: NOME SOBRENOME)."""
    pacientes: dict[str, list[dict]] = {}
    for _, row in df.iterrows():
        raw = str(row.get("nome_beneficiario", ""))
        partes = [p.strip() for p in raw.split(",", 1)]
        nome_natural = _normalizar(f"{partes[1]} {partes[0]}" if len(partes) == 2 else raw)
        pacientes.setdefault(nome_natural, []).append(row.to_dict())
    return pacientes


def renomear(df: pd.DataFrame, pasta_laudos: str, pasta_destino: str | None = None) -> list[dict]:
    """
    Vincula cada PDF ao paciente/cobrança por similaridade de nome e renomeia para
    CPF-NOMEPACIENTE-IDCOBRANCA-MMYYYY.pdf. Nunca sobrescreve arquivos existentes.

    Se pasta_destino for informada, os PDFs são movidos para lá; caso contrário
    são renomeados na própria pasta_laudos.

    Retorna lista de dicts: {arquivo_original, arquivo_destino, status, motivo}.
    """
    pasta = Path(pasta_laudos)
    if not pasta.exists():
        raise FileNotFoundError(f"Pasta de laudos não encontrada: {pasta_laudos}")

    pasta_saida = Path(pasta_destino) if pasta_destino else pasta
    pasta_saida.mkdir(parents=True, exist_ok=True)

    pacientes = _indexar_pacientes(df)
    nomes_lista = list(pacientes.keys())
    pdfs = sorted(pasta.glob("*.pdf"))
    resultados: list[dict] = []

    for pdf in pdfs:
        candidato = _extrair_nome_candidato(pdf.name)

        if not candidato.strip():
            logger.warning("Nome candidato vazio após limpeza: %s", pdf.name)
            resultados.append({
                "arquivo_original": pdf.name, "arquivo_destino": None,
                "status": "pulado", "motivo": "nome candidato vazio após limpeza",
            })
            continue

        matches = process.extract(candidato, nomes_lista, scorer=fuzz.token_set_ratio, limit=2)

        if not matches or matches[0][1] < LIMIAR_NOME:
            best = matches[0][1] if matches else 0
            logger.warning("Sem correspondência (score=%d): %s", best, pdf.name)
            resultados.append({
                "arquivo_original": pdf.name, "arquivo_destino": None,
                "status": "pulado", "motivo": f"score abaixo do limiar ({best} < {LIMIAR_NOME})",
            })
            continue

        # Empate: dois candidatos muito próximos — não é seguro escolher
        if len(matches) >= 2 and (matches[0][1] - matches[1][1]) <= LIMIAR_EMPATE:
            logger.warning(
                "Empate entre '%s'(%d) e '%s'(%d): %s",
                matches[0][0], matches[0][1], matches[1][0], matches[1][1], pdf.name,
            )
            resultados.append({
                "arquivo_original": pdf.name, "arquivo_destino": None,
                "status": "pulado",
                "motivo": f"empate: '{matches[0][0]}'({matches[0][1]}) vs '{matches[1][0]}'({matches[1][1]})",
            })
            continue

        nome_paciente = matches[0][0]
        cobranças_paciente = pacientes[nome_paciente]
        proc_pdf = _identificar_procedimento(pdf.name)
        cobranca_escolhida = None

        if proc_pdf:
            candidatas = [
                c for c in cobranças_paciente
                if proc_pdf in str(c.get("descricao_servico", "")).upper()
            ]
            if len(candidatas) == 1:
                cobranca_escolhida = candidatas[0]
            elif candidatas:
                # Múltiplas cobranças para o mesmo proc — usar a mais antiga
                cobranca_escolhida = sorted(
                    candidatas, key=lambda x: x.get("dt_realizacao") or pd.Timestamp.max
                )[0]
                logger.info(
                    "Múltiplas cobranças para '%s'/%s, usando a mais antiga: %s",
                    nome_paciente, proc_pdf, cobranca_escolhida["num_guia"],
                )

        if cobranca_escolhida is None:
            # Sem procedimento identificável: usar a mais antiga do paciente
            cobranca_escolhida = sorted(
                cobranças_paciente, key=lambda x: x.get("dt_realizacao") or pd.Timestamp.max
            )[0]
            if proc_pdf is None and len(cobranças_paciente) > 1:
                logger.info(
                    "Procedimento não identificado para '%s', usando %s",
                    pdf.name, cobranca_escolhida["num_guia"],
                )

        cpf = _formatar_cpf(str(cobranca_escolhida.get("cpf_beneficiario", "")))
        nome_saida = _formatar_nome_saida(str(cobranca_escolhida.get("nome_beneficiario", "")))
        id_cob = str(cobranca_escolhida["num_guia"])
        dt = cobranca_escolhida.get("dt_realizacao")
        mmyyyy = pd.Timestamp(dt).strftime("%m%Y") if pd.notna(dt) else "000000"

        destino_nome = f"{cpf}-{nome_saida}-{id_cob}-{mmyyyy}.pdf"
        destino_path = pasta_saida / destino_nome

        if destino_path.exists():
            logger.info("Destino já existe, pulando: %s", destino_nome)
            resultados.append({
                "arquivo_original": pdf.name, "arquivo_destino": destino_nome,
                "status": "pulado", "motivo": "arquivo de destino já existe",
            })
            continue

        try:
            pdf.rename(destino_path)
            logger.info("Renomeado: %s -> %s", pdf.name, destino_nome)
            resultados.append({
                "arquivo_original": pdf.name, "arquivo_destino": destino_nome,
                "status": "renomeado",
                "motivo": f"paciente='{nome_paciente}' score={matches[0][1]} cob={id_cob}",
            })
        except OSError as e:
            logger.error("Erro ao renomear %s: %s", pdf.name, e)
            resultados.append({
                "arquivo_original": pdf.name, "arquivo_destino": destino_nome,
                "status": "erro", "motivo": str(e),
            })

    renomeados = sum(1 for r in resultados if r["status"] == "renomeado")
    pulados = sum(1 for r in resultados if r["status"] == "pulado")
    erros = sum(1 for r in resultados if r["status"] == "erro")
    logger.info(
        "Renomeação concluída: %d renomeados | %d pulados | %d erros",
        renomeados, pulados, erros,
    )
    return resultados

"""Caso queira rodar o arquivo individualmente, printa no terminal o resultado"""

if __name__ == "__main__":
    import logging
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from consolidar_cobrancas import consolidar

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    _BASE = Path(__file__).parent.parent
    _DATA_DIR = _BASE / "data"

    _df, _ = consolidar(
        str(_DATA_DIR / "cobrancas_convenio.csv"),
        str(_DATA_DIR / "cobrancas_internas.xlsx"),
    )
    _resultados = renomear(_df, str(_DATA_DIR / "laudos"), str(_DATA_DIR / "laudos_renomeados"))

    _renomeados = sum(1 for r in _resultados if r["status"] == "renomeado")
    _pulados    = sum(1 for r in _resultados if r["status"] == "pulado")
    _erros      = sum(1 for r in _resultados if r["status"] == "erro")
    print(f"\nRenomeados : {_renomeados}")
    print(f"Pulados    : {_pulados}")
    print(f"Erros      : {_erros}")
