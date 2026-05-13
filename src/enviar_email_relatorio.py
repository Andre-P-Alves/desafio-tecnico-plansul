import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _carregar_config() -> dict:
    load_dotenv()
    campos = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO", "EMAIL_FROM"]
    config = {k: os.getenv(k) for k in campos}
    faltando = [k for k, v in config.items() if not v]
    if faltando:
        raise EnvironmentError(f"Variáveis de ambiente ausentes no .env: {faltando}")
    return config


def _renderizar_html(resumo: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)
    tmpl = env.get_template("email.html")
    return tmpl.render(**resumo)


def enviar(caminho_relatorio: str, resumo: dict) -> None:
    """
    Envia o relatório por e-mail: corpo HTML via Jinja2 + XLSX como anexo.
    Configuração lida do arquivo .env (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    EMAIL_FROM, EMAIL_TO).
    """
    config = _carregar_config()
    html_body = _renderizar_html(resumo)

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Relatório de Faturamento — {resumo.get('mes_ref', '')}"
    msg["From"] = config["EMAIL_FROM"]
    msg["To"] = config["EMAIL_TO"]
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    caminho = Path(caminho_relatorio)
    if not caminho.exists():
        raise FileNotFoundError(f"Relatório não encontrado: {caminho_relatorio}")

    with open(caminho, "rb") as f:
        anexo = MIMEApplication(
            f.read(),
            _subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        anexo.add_header("Content-Disposition", "attachment", filename=caminho.name)
        msg.attach(anexo)

    host = config["SMTP_HOST"]
    port = int(config["SMTP_PORT"])

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
        server.sendmail(config["EMAIL_FROM"], config["EMAIL_TO"], msg.as_string())

    logger.info("E-mail enviado para %s | anexo: %s", config["EMAIL_TO"], caminho.name)

"""Caso queira rodar o arquivo individualmente, printa no terminal o resultado"""

if __name__ == "__main__":
    import logging
    import sys

    import pandas as pd

    sys.path.insert(0, str(Path(__file__).parent))
    from consolidar_cobrancas import consolidar
    from renomear_laudos import renomear

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    _BASE = Path(__file__).parent.parent
    _DATA_DIR = _BASE / "data"

    # Usa o relatório mais recente gerado na raiz do projeto
    _relatorios = sorted(_BASE.glob("relatorio_faturamento_*.xlsx"), reverse=True)
    if not _relatorios:
        print("Nenhum relatório encontrado. Execute gerar_relatorio.py primeiro.")
        raise SystemExit(1)

    # Reconstrói o resumo a partir dos dados reais
    _df, _alertas = consolidar(
        str(_DATA_DIR / "cobrancas_convenio.csv"),
        str(_DATA_DIR / "cobrancas_internas.xlsx"),
    )
    _res_laudos = renomear(_df, str(_DATA_DIR / "laudos"), str(_DATA_DIR / "laudos_renomeados"))

    _mes_ref = ""
    if not _df.empty and _df["dt_realizacao"].notna().any():
        _mes_ref = pd.Timestamp(_df["dt_realizacao"].dropna().iloc[0]).strftime("%m/%Y")

    _resumo = {
        "mes_ref": _mes_ref,
        "total_cobrancas": len(_df),
        "total_divergencias": len(_alertas),
        "vl_liquido_total": round(float(_df["vl_liquido"].sum()), 2),
        "vl_glosa_total": round(float(_df["vl_glosa"].sum()), 2),
        "pdfs_renomeados": sum(1 for r in _res_laudos if r["status"] == "renomeado"),
        "pdfs_total": len(_res_laudos),
        "alertas": _alertas[:20],
    }
    enviar(str(_relatorios[0]), _resumo)
    print("E-mail enviado com sucesso.")
