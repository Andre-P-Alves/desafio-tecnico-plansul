import logging
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "src"))

from consolidar_cobrancas import consolidar
from enviar_email_relatorio import enviar
from gerar_relatorio import gerar
from renomear_laudos import renomear

DATA_DIR = BASE_DIR / "data"
CSV_PATH = str(DATA_DIR / "cobrancas_convenio.csv")
XLSX_PATH = str(DATA_DIR / "cobrancas_internas.xlsx")
LAUDOS_DIR = str(DATA_DIR / "laudos")
LAUDOS_SAIDA_DIR = str(DATA_DIR / "laudos_renomeados")
LOG_DIR = BASE_DIR / "logs"


def _setup_logging() -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"pipeline_{ts}.log"
    fmt = "[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s"

    # Garante UTF-8 no stdout (necessário no Windows com cp1252)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file


def main() -> int:
    log_file = _setup_logging()
    logger = logging.getLogger("main")
    logger.info("=== Pipeline de faturamento iniciado ===")

    try:
        import pandas as pd

        # Etapa 1 — Consolidar cobranças
        logger.info("--- Etapa 1: Consolidando cobrancas ---")
        df, alertas = consolidar(CSV_PATH, XLSX_PATH)

        mes_ref = ""
        if not df.empty and df["dt_realizacao"].notna().any():
            mes_ref = pd.Timestamp(df["dt_realizacao"].dropna().iloc[0]).strftime("%m/%Y")

        # Etapa 2 — Renomear laudos
        logger.info("--- Etapa 2: Renomeando laudos ---")
        res_laudos = renomear(df, LAUDOS_DIR, LAUDOS_SAIDA_DIR)

        # Etapa 3 — Gerar relatório Excel
        logger.info("--- Etapa 3: Gerando relatorio Excel ---")
        mes_arquivo = mes_ref.replace("/", "") if mes_ref else datetime.now().strftime("%m%Y")
        caminho_relatorio = str(BASE_DIR / f"relatorio_faturamento_{mes_arquivo}.xlsx")
        gerar(df, alertas, res_laudos, mes_ref, caminho_relatorio)

        # Etapa 4 — Enviar por e-mail (não bloqueia o pipeline em caso de falha)
        logger.info("--- Etapa 4: Enviando e-mail ---")
        resumo = {
            "mes_ref": mes_ref,
            "total_cobrancas": len(df),
            "total_divergencias": len(alertas),
            "vl_liquido_total": round(float(df["vl_liquido"].sum()), 2),
            "vl_glosa_total": round(float(df["vl_glosa"].sum()), 2),
            "pdfs_renomeados": sum(1 for r in res_laudos if r["status"] == "renomeado"),
            "pdfs_total": len(res_laudos),
            "alertas": alertas[:20],
        }
        try:
            enviar(caminho_relatorio, resumo)
        except EnvironmentError as e:
            logger.warning("E-mail nao enviado (configuracao ausente): %s", e)
        except Exception as e:
            logger.warning("Falha no envio do e-mail (pipeline continua): %s", e)

        logger.info("=== Pipeline concluido com sucesso. Log: %s ===", log_file)
        return 0

    except Exception:
        logging.getLogger("main").exception("Falha critica no pipeline")
        return 1


if __name__ == "__main__":
    sys.exit(main())
