
import os
import logging
import threading
from datetime import datetime

import requests
from flask import Flask, request
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Configuração dos logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

# Token do Telegram
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise SystemExit(
        "ERRO: configure TELEGRAM_TOKEN nas "
        "Environment Variables do Render."
    )

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

# APIs Open-Meteo
GEOCODING_API = (
    "https://geocoding-api.open-meteo.com/v1/search"
)

WEATHER_API = (
    "https://api.open-meteo.com/v1/forecast"
)

# Aplicação Flask
app = Flask(__name__)

# Descrições meteorológicas
DESCRICOES_TEMPO = {
    0: "Céu limpo",
    1: "Predominantemente limpo",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Neblina",
    48: "Neblina com geada",
    51: "Garoa leve",
    53: "Garoa moderada",
    55: "Garoa intensa",
    56: "Garoa congelante leve",
    57: "Garoa congelante intensa",
    61: "Chuva leve",
    63: "Chuva moderada",
    65: "Chuva forte",
    66: "Chuva congelante leve",
    67: "Chuva congelante forte",
    71: "Neve leve",
    73: "Neve moderada",
    75: "Neve forte",
    77: "Grãos de neve",
    80: "Pancadas de chuva leves",
    81: "Pancadas de chuva moderadas",
    82: "Pancadas de chuva fortes",
    85: "Pancadas de neve leves",
    86: "Pancadas de neve fortes",
    95: "Trovoadas",
    96: "Trovoadas com granizo leve",
    99: "Trovoadas com granizo forte",
}


def formatar_data_hora(horario):
    """Converte a data para o formato brasileiro."""

    try:
        data = datetime.strptime(
            horario,
            "%Y-%m-%dT%H:%M"
        )

        return data.strftime("%d/%m/%Y %H:%M")

    except (ValueError, TypeError):
        return horario or "N/D"


def enviar_mensagem(chat_id, texto):
    """Envia mensagem pelo Telegram."""

    try:
        resposta = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": texto
            },
            timeout=20
        )

        resposta.raise_for_status()

        dados = resposta.json()

        if not dados.get("ok"):
            logger.error(
                "Telegram não confirmou o envio: %s",
                dados
            )

    except requests.RequestException:
        logger.exception(
            "ERRO AO ENVIAR MENSAGEM AO TELEGRAM"
        )


def localizar_cidade(nome_cidade):
    """Busca as coordenadas geográficas."""

    logger.info(
        "Consultando geolocalização: %s",
        nome_cidade
    )

    try:
        resposta = requests.get(
            GEOCODING_API,
            params={
                "name": nome_cidade,
                "count": 1,
                "language": "pt",
                "format": "json",
                "countryCode": "BR"
            },
            timeout=20
        )

        resposta.raise_for_status()

        dados = resposta.json()

        resultados = dados.get("results") or []

        if not resultados:
            logger.warning(
                "Cidade não encontrada: %s",
                nome_cidade
            )
            return None

        cidade = resultados[0]

        logger.info(
            "Cidade encontrada: %s, %s, %s",
            cidade.get("name"),
            cidade.get("admin1", ""),
            cidade.get("country", "")
        )

        return cidade

    except requests.RequestException:
        logger.exception(
            "ERRO NA API DE GEOLOCALIZAÇÃO"
        )
        raise

    except ValueError:
        logger.exception(
            "ERRO AO INTERPRETAR JSON DA GEOLOCALIZAÇÃO"
        )
        raise


def consultar_tempo(nome_cidade):
    """Consulta as condições meteorológicas."""

    cidade = localizar_cidade(nome_cidade)

    if cidade is None:
        return (
            f"Não encontrei a cidade '{nome_cidade}'.\n\n"
            "Confira o nome e tente novamente."
        )

    parametros = {
        "latitude": cidade["latitude"],
        "longitude": cidade["longitude"],
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "weather_code,"
            "wind_speed_10m"
        ),
        "timezone": "auto"
    }

    try:
        resposta = requests.get(
            WEATHER_API,
            params=parametros,
            timeout=25
        )

        resposta.raise_for_status()

        dados = resposta.json()

        atual = dados.get("current")

        if not isinstance(atual, dict):
            raise ValueError(
                "Resposta da API sem dados meteorológicos."
            )

        codigo = atual.get("weather_code")

        descricao = DESCRICOES_TEMPO.get(
            codigo,
            "Condição não identificada"
        )

        local = ", ".join(
            str(parte)
            for parte in [
                cidade.get("name", nome_cidade),
                cidade.get("admin1", ""),
                cidade.get("country", "")
            ]
            if parte
        )

        # Formata a data para DD/MM/AAAA
        horario = formatar_data_hora(
            atual.get("time")
        )

        logger.info(
            "Previsão recebida com sucesso para %s",
            local
        )

        return (
            "🌦️ PREVISÃO DO TEMPO\n\n"
            f"📍 Cidade: {local}\n"
            f"🕒 Horário local: {horario}\n\n"
            f"🌡️ Temperatura: "
            f"{atual.get('temperature_2m', 'N/D')} °C\n"
            f"🤔 Sensação térmica: "
            f"{atual.get('apparent_temperature', 'N/D')} °C\n"
            f"☁️ Condição: {descricao}\n"
            f"💧 Umidade: "
            f"{atual.get('relative_humidity_2m', 'N/D')}%\n"
            f"💨 Vento: "
            f"{atual.get('wind_speed_10m', 'N/D')} km/h\n"
            f"🌧️ Precipitação: "
            f"{atual.get('precipitation', 'N/D')} mm\n\n"
            "Fonte: Open-Meteo"
        )

    except requests.RequestException:
        logger.exception(
            "ERRO NA REQUISIÇÃO METEOROLÓGICA"
        )
        raise

    except ValueError:
        logger.exception(
            "ERRO AO INTERPRETAR DADOS METEOROLÓGICOS"
        )
        raise


def processar_mensagem(mensagem):
    """Processa os comandos do Telegram."""

    chat_id = mensagem.get("chat", {}).get("id")
    texto = mensagem.get("text", "")

    if not chat_id or not texto:
        return

    texto = texto.strip()

    logger.info(
        "Mensagem recebida. Chat ID: %s",
        chat_id
    )

    if texto == "/start" or texto.startswith("/start "):
        enviar_mensagem(
            chat_id,
            "Olá! 🌤️ Sou o Bot de Previsão do Tempo!\n\n"
            "Envie o nome de uma cidade para consultar o clima.\n\n"
            "Exemplo: Campinas\n\n"
            "Comandos disponíveis:\n"
            "/start - Iniciar o bot\n"
            "/help - Mostrar ajuda\n"
            "/tempo Campinas - Consultar uma cidade"
        )
        return

    if texto == "/help" or texto.startswith("/help "):
        enviar_mensagem(
            chat_id,
            "📘 COMANDOS DO BOT\n\n"
            "/start - Iniciar o bot\n"
            "/help - Mostrar esta ajuda\n"
            "/tempo Campinas - Consultar uma cidade\n\n"
            "Você também pode enviar apenas "
            "o nome da cidade."
        )
        return

    if texto.startswith("/tempo"):
        partes = texto.split(maxsplit=1)

        if len(partes) < 2 or not partes[1].strip():
            enviar_mensagem(
                chat_id,
                "Informe uma cidade.\n\n"
                "Exemplo: /tempo Campinas"
            )
            return

        nome_cidade = partes[1].strip()

    elif texto.startswith("/"):
        enviar_mensagem(
            chat_id,
            "Comando desconhecido. Digite /help."
        )
        return

    else:
        nome_cidade = texto

    enviar_mensagem(
        chat_id,
        f"🔎 Consultando o tempo em {nome_cidade}..."
    )

    try:
        resultado = consultar_tempo(nome_cidade)

        enviar_mensagem(
            chat_id,
            resultado
        )

    except requests.HTTPError as erro:
        logger.error("ERRO HTTP: %r", erro)

        if erro.response is not None:
            logger.error(
                "STATUS: %s | RESPOSTA: %s",
                erro.response.status_code,
                erro.response.text[:2000]
            )

        enviar_mensagem(
            chat_id,
            "A API retornou um erro HTTP. "
            "Confira os Logs do Render."
        )

    except requests.Timeout:
        logger.exception("TEMPO ESGOTADO")

        enviar_mensagem(
            chat_id,
            "A consulta demorou demais. "
            "Tente novamente."
        )

    except requests.ConnectionError:
        logger.exception("ERRO DE CONEXÃO")

        enviar_mensagem(
            chat_id,
            "Não consegui conectar à API. "
            "Tente novamente mais tarde."
        )

    except requests.RequestException:
        logger.exception("ERRO DE REQUISIÇÃO")

        enviar_mensagem(
            chat_id,
            "Erro de comunicação com a API. "
            "Confira os Logs do Render."
        )

    except (ValueError, KeyError, TypeError):
        logger.exception("ERRO AO PROCESSAR OS DADOS")

        enviar_mensagem(
            chat_id,
            "Recebi dados que não consegui interpretar. "
            "Confira os Logs do Render."
        )

    except Exception:
        logger.exception("ERRO INESPERADO")

        enviar_mensagem(
            chat_id,
            "Ocorreu um erro inesperado. "
            "Confira os Logs do Render."
        )


@app.route("/", methods=["GET"])
def inicio():
    """Verifica se o serviço está funcionando."""

    return (
        "Bot de Previsão do Tempo está funcionando!",
        200
    )


@app.route("/telegram", methods=["POST"])
def webhook_telegram():
    """Recebe atualizações do Telegram."""

    mensagem_recebida = request.get_json(
        silent=True
    )

    if not isinstance(mensagem_recebida, dict):
        return "Requisição inválida", 400

    mensagem = mensagem_recebida.get("message")

    if mensagem:
        try:
            processar_mensagem(mensagem)

        except Exception:
            logger.exception(
                "ERRO AO PROCESSAR ATUALIZAÇÃO"
            )

    return "OK", 200


def configurar_webhook():
    """Registra o webhook no Telegram."""

    url_render = os.getenv("RENDER_EXTERNAL_URL")

    if not url_render:
        logger.error(
            "RENDER_EXTERNAL_URL não está disponível."
        )
        return

    url_webhook = (
        f"{url_render.rstrip('/')}/telegram"
    )

    logger.info("Configurando webhook do Telegram.")

    try:
        resposta = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={
                "url": url_webhook
            },
            timeout=20
        )

        resposta.raise_for_status()

        dados = resposta.json()

        if dados.get("ok"):
            logger.info(
                "Webhook configurado com sucesso."
            )
        else:
            logger.error(
                "Telegram recusou o webhook: %s",
                dados
            )

    except requests.RequestException:
        logger.exception(
            "ERRO AO CONFIGURAR WEBHOOK"
        )


if __name__ == "__main__":

    threading.Thread(
        target=configurar_webhook,
        daemon=True
    ).start()

    porta = int(
        os.environ.get("PORT", "10000")
    )

    logger.info(
        "Iniciando o bot na porta %s",
        porta
    )

    app.run(
        host="0.0.0.0",
        port=porta
    )
