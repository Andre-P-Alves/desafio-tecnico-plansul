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

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    _BASE = Path(__file__).parent.parent

    # Usa o relatório mais recente gerado na raiz do projeto
    _relatorios = sorted(_BASE.glob("relatorio_faturamento_*.xlsx"), reverse=True)
    if not _relatorios:
        print("Nenhum relatório encontrado. Execute gerar_relatorio.py primeiro.")
        raise SystemExit(1)

    _resumo = {
        "mes_ref": _relatorios[0].stem.split("_")[-1],
        "total_cobrancas": 0,
        "total_divergencias": 0,
        "vl_liquido_total": 0.0,
        "vl_glosa_total": 0.0,
        "pdfs_renomeados": 0,
        "pdfs_total": 0,
        "alertas": [],
    }
    enviar(str(_relatorios[0]), _resumo)
    print("E-mail enviado com sucesso.")
