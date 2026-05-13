import logging
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz
from unidecode import unidecode

logger = logging.getLogger(__name__)

COLUNAS_XLSX = ["id_cobranca", "paciente", "registro_ans", "procedimento", "data_atendimento", "valor"]
COLUNAS_CSV = [
    "num_guia", "nome_beneficiario", "cpf_beneficiario", "ans", "nome_operadora",
    "descricao_servico", "cod_tuss", "dt_realizacao", "dt_lancamento",
    "vl_servico", "vl_glosa", "vl_liquido",
]

# Score mínimo de similaridade (0-100) para considerar nomes equivalentes com erros de escrita
LIMIAR_SIMILARIDADE_NOME = 80

"""
Código para solução do desafio 1, contendo todas as funções necessárias para:
-Ler os arquivos solicitados
-Anotar diferenças de valores
-Anotar diferenças de nomes (erros de digitação)
-Anotar diferenças no código de convênio
"""

def _parse_brl(valor: str) -> float:
    """Converte '1.234,56' para 1234.56."""
    return float(str(valor).strip().replace(".", "").replace(",", "."))


def _normalizar_nome(nome: str) -> str:
    """Remove acentos, coloca em maiúsculas e normaliza espaços."""
    return " ".join(unidecode(str(nome)).upper().split())


def _csv_para_natural(nome_csv: str) -> str:
    """TRANSFORMA DE 'SOBRENOME, NOME' PARA 'NOME SOBRENOME'."""
    partes = [p.strip() for p in nome_csv.split(",", 1)]
    if len(partes) == 2:
        return f"{partes[1]} {partes[0]}"
    return nome_csv


def _carregar_csv(caminho: str) -> pd.DataFrame:
    """Lê o CSV do convênio e converte colunas de valor para float."""
    path = Path(caminho)
    if not path.exists():
        raise FileNotFoundError(f"CSV não encontrado: {caminho}")

    df = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8")

    colunas_faltando = set(COLUNAS_CSV) - set(df.columns)
    if colunas_faltando:
        raise ValueError(f"CSV com colunas faltando: {colunas_faltando}")

    for col in ("vl_servico", "vl_glosa", "vl_liquido"):
        try:
            df[col] = df[col].apply(_parse_brl)
        except (ValueError, AttributeError) as e:
            logger.warning("Valor inválido em '%s', linha será marcada como nula: %s", col, e)
            df[col] = pd.to_numeric(
                df[col].str.replace(",", ".").str.replace(r"[^\d.]", "", regex=True),
                errors="coerce",
            )

    df["dt_realizacao"] = pd.to_datetime(df["dt_realizacao"], format="%Y-%m-%d", errors="coerce")
    df["dt_lancamento"] = pd.to_datetime(df["dt_lancamento"], format="%Y-%m-%d", errors="coerce")
    df["ans"] = df["ans"].str.strip()

    logger.info("CSV carregado: %d registros", len(df))
    return df


def _carregar_xlsx(caminho: str) -> pd.DataFrame:
    """Lê a planilha interna e normaliza tipos."""
    path = Path(caminho)
    if not path.exists():
        raise FileNotFoundError(f"XLSX não encontrado: {caminho}")

    df = pd.read_excel(caminho, dtype={"registro_ans": str})

    colunas_faltando = set(COLUNAS_XLSX) - set(df.columns)
    if colunas_faltando:
        raise ValueError(f"XLSX com colunas faltando: {colunas_faltando}")

    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["data_atendimento"] = pd.to_datetime(df["data_atendimento"], dayfirst=True, errors="coerce")
    df["registro_ans"] = df["registro_ans"].str.strip()

    logger.info("XLSX carregado: %d registros", len(df))
    return df


def _detectar_divergencias(row: pd.Series) -> list[str]:
    """Retorna lista de descrições de divergências para uma linha consolidada."""
    problemas = []

    # Cobrança presente apenas no CSV (equipe interna ainda não lançou)
    if row.get("_apenas_csv"):
        problemas.append("apenas_csv: registro não encontrado no XLSX")
        return problemas

    # Diferença de valor: compara o bruto do XLSX com o líquido do CSV (referência autoritativa)
    valor_xlsx = row.get("valor")
    vl_liquido = row.get("vl_liquido")
    if pd.notna(valor_xlsx) and pd.notna(vl_liquido):
        if abs(float(valor_xlsx) - float(vl_liquido)) > 0.01:
            problemas.append(
                f"divergencia_valor: XLSX={valor_xlsx:.2f} | CSV vl_liquido={vl_liquido:.2f}"
            )

    # Diferença de nome entre as fontes: qualquer diferença é flagrada
    # Algoritmo Fuzz para matching de nomes: Score >= limiar = provavelmente erro, score baixo = possível paciente errado
    nome_xlsx_norm = _normalizar_nome(str(row.get("paciente", "")))
    nome_csv_natural = _normalizar_nome(_csv_para_natural(str(row.get("nome_beneficiario", ""))))
    if nome_xlsx_norm != nome_csv_natural:
        score = fuzz.token_sort_ratio(nome_xlsx_norm, nome_csv_natural)
        tipo = "possivel_typo_nome" if score >= LIMIAR_SIMILARIDADE_NOME else "divergencia_nome"
        problemas.append(
            f"{tipo}: XLSX='{row.get('paciente')}' | "
            f"CSV='{row.get('nome_beneficiario')}' (similaridade={score})"
        )

    # Diferença no código de convênio
    ans_xlsx = str(row.get("registro_ans", "")).strip()
    ans_csv = str(row.get("ans", "")).strip()
    if ans_xlsx and ans_csv and ans_xlsx != ans_csv:
        problemas.append(f"divergencia_ans: XLSX={ans_xlsx} | CSV={ans_csv}")

    return problemas


def consolidar(caminho_csv: str, caminho_xlsx: str) -> tuple[pd.DataFrame, list[dict]]:
    """
    Cruza as duas fontes de cobrança e retorna:
      - DataFrame consolidado com campos enriquecidos e coluna 'divergencias'
      - Lista de alertas (dicts) para uso no relatório

    O CSV é a fonte principal. Quando há divergência de valor, vl_liquido do CSV prevalece.
    Registros presentes apenas no CSV são incluídos e sinalizados.
    """
    csv = _carregar_csv(caminho_csv)
    xlsx = _carregar_xlsx(caminho_xlsx)

    ids_csv = set(csv["num_guia"])
    ids_xlsx = set(xlsx["id_cobranca"])

    apenas_csv = ids_csv - ids_xlsx
    apenas_xlsx = ids_xlsx - ids_csv

    if apenas_xlsx:
        logger.warning(
            "Cobranças no XLSX sem correspondente no CSV (%d): %s",
            len(apenas_xlsx), sorted(apenas_xlsx),
        )
    if apenas_csv:
        logger.info(
            "Cobranças apenas no CSV — não lançadas internamente (%d): %s",
            len(apenas_csv), sorted(apenas_csv),
        )

    # Left join no CSV para preservar registros que só existem no CSV
    merged = csv.merge(
        xlsx,
        left_on="num_guia",
        right_on="id_cobranca",
        how="left",
        suffixes=("", "_xlsx"),
    )

    merged["_apenas_csv"] = merged["id_cobranca"].isna()

    # Detectar divergências linha a linha e acumular alertas
    alertas: list[dict] = []
    lista_divergencias: list[str] = []

    for _, row in merged.iterrows():
        problemas = _detectar_divergencias(row)
        texto = " | ".join(problemas) if problemas else ""
        lista_divergencias.append(texto)

        if problemas:
            alertas.append({
                "id_cobranca": row["num_guia"],
                "divergencias": texto,
                "paciente_xlsx": row.get("paciente"),
                "nome_beneficiario_csv": row.get("nome_beneficiario"),
                "valor_xlsx": row.get("valor"),
                "vl_liquido_csv": row.get("vl_liquido"),
                "registro_ans_xlsx": row.get("registro_ans"),
                "ans_csv": row.get("ans"),
            })
            logger.warning("[%s] %s", row["num_guia"], texto)

    merged["divergencias"] = lista_divergencias
    merged.drop(columns=["_apenas_csv"], inplace=True)

    # Reordenar colunas: ID e campos CSV primeiro, depois complementos do XLSX
    colunas_saida = [
        "num_guia", "nome_beneficiario", "cpf_beneficiario",
        "ans", "nome_operadora", "descricao_servico", "cod_tuss",
        "dt_realizacao", "dt_lancamento", "vl_servico", "vl_glosa", "vl_liquido",
        "paciente", "registro_ans", "procedimento", "data_atendimento", "valor",
        "divergencias",
    ]
    colunas_saida = [c for c in colunas_saida if c in merged.columns]
    merged = merged[colunas_saida]

    logger.info(
        "Consolidação concluída: %d registros | %d com divergências | %d apenas no CSV",
        len(merged), len(alertas), len(apenas_csv),
    )

    return merged, alertas


""""Caso queira rodar o arquivo individualmente, printa no terminal o resultado"""
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    _BASE = Path(__file__).parent.parent
    _DATA = _BASE / "data"

    _df, _alertas = consolidar(
        str(_DATA / "cobrancas_convenio.csv"),
        str(_DATA / "cobrancas_internas.xlsx"),
    )

    print(f"\nRegistros consolidados : {len(_df)}")
    print(f"Alertas / divergencias : {len(_alertas)}")
    print(f"\nAmostra (5 linhas):")
    print(_df[["num_guia", "nome_beneficiario", "vl_liquido", "divergencias"]].head().to_string())