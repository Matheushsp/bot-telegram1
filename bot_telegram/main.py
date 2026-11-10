

import os

import logging

import threading

import time

import unicodedata

from datetime import datetime


import requests

from flask import Flask, request

from dotenv import load_dotenv


load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)


TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise SystemExit(
        "ERRO: configure TELEGRAM_TOKEN nas Environment Variables do Render."
    )


TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"


GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"

WEATHER_API = "https://api.open-meteo.com/v1/forecast"

WTTR_API = "https://wttr.in"


CACHE_TTL_SEGUNDOS = 30 * 60

cache_tempo = {}

cache_lock = threading.Lock()


sessao = requests.Session()

sessao.headers.update({"User-Agent": "BotPrevisaoTempo/1.0"})


app = Flask(__name__)


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



TRADUCOES_CONDICAO = {
    "patchy rain nearby": "Chuva irregular nas proximidades",
    "partly cloudy": "Parcialmente nublado",
    "mostly cloudy": "Predominantemente nublado",
    "cloudy": "Nublado",
    "overcast": "Encoberto",
    "sunny": "Ensolarado",
    "clear": "Céu limpo",
    "mist": "Neblina",
    "fog": "Nevoeiro",
    "light rain": "Chuva fraca",
    "moderate rain": "Chuva moderada",
    "heavy rain": "Chuva forte",
    "light drizzle": "Garoa leve",
    "thunderstorm": "Tempestade com trovoadas",
}

def traduzir_condicao(descricao):
    texto = str(descricao or "N/D").strip()
    return TRADUCOES_CONDICAO.get(texto.casefold(), texto)

def formatar_data_hora(horario):

    if not horario:
        return "N/D"

    formatos = (
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %H:%M %p",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",
    )
    for formato in formatos:
        try:
            data = datetime.strptime(horario, formato)
            return data.strftime("%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            pass
    return str(horario)


def enviar_mensagem(chat_id, texto):

    try:
        resposta = sessao.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": texto},
            timeout=20,
        )
        resposta.raise_for_status()
        dados = resposta.json()
        if not dados.get("ok"):
            logger.error("Telegram não confirmou o envio: %s", dados)
    except requests.RequestException:
        logger.exception("ERRO AO ENVIAR MENSAGEM AO TELEGRAM")


def obter_cache(nome_cidade):
    chave = nome_cidade.strip().casefold()
    agora = time.time()
    with cache_lock:
        item = cache_tempo.get(chave)
        if item and agora - item["horario"] < CACHE_TTL_SEGUNDOS:
            logger.info("Usando previsão em cache para %s", nome_cidade)
            return item["texto"]
        if item:
            cache_tempo.pop(chave, None)
    return None


def salvar_cache(nome_cidade, texto):
    chave = nome_cidade.strip().casefold()
    with cache_lock:
        cache_tempo[chave] = {"texto": texto, "horario": time.time()}


def normalizar_nome(nome):

    texto = unicodedata.normalize("NFKD", str(nome or ""))
    return "".join(
        caractere for caractere in texto
        if not unicodedata.combining(caractere)
    ).casefold().strip()


def localizar_cidade(nome_cidade):

    logger.info("Consultando geolocalização: %s", nome_cidade)
    resposta = sessao.get(
        GEOCODING_API,
        params={
            "name": nome_cidade,
            "count": 10,
            "language": "pt",
            "format": "json",
            "countryCode": "BR",
        },
        timeout=15,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    resultados = dados.get("results") or []

    if not resultados:
        return None

    nome_pedido = normalizar_nome(nome_cidade)


    correspondencias = [
        cidade for cidade in resultados
        if normalizar_nome(cidade.get("name", "")) == nome_pedido
    ]


    if not correspondencias:
        correspondencias = [
            cidade for cidade in resultados
            if nome_pedido in normalizar_nome(cidade.get("name", ""))
        ]


    cidade = correspondencias[0] if correspondencias else resultados[0]

    logger.info(
        "Cidade selecionada: %s, %s, %s (%.5f, %.5f)",
        cidade.get("name"),
        cidade.get("admin1", ""),
        cidade.get("country", ""),
        cidade.get("latitude"),
        cidade.get("longitude"),
    )
    return cidade


def montar_resposta(
    local, horario, temperatura, sensacao, descricao,
    umidade, vento, precipitacao, fonte
):
    return (
        "🌦️ PREVISÃO DO TEMPO\n\n"
        f"📍 Cidade: {local}\n"
        f"🕒 Horário local: {formatar_data_hora(horario)}\n\n"
        f"🌡️ Temperatura: {temperatura} °C\n"
        f"🤔 Sensação térmica: {sensacao} °C\n"
        f"☁️ Condição: {descricao}\n"
        f"💧 Umidade: {umidade}%\n"
        f"💨 Vento: {vento} km/h\n"
        f"🌧️ Precipitação: {precipitacao} mm\n\n"
        f"Fonte: {fonte}"
    )


def consultar_open_meteo(nome_cidade, cidade=None):

    if cidade is None:
        cidade = localizar_cidade(nome_cidade)
    if cidade is None:
        raise LookupError(f"Cidade não encontrada: {nome_cidade}")

    resposta = sessao.get(
        WEATHER_API,
        params={
            "latitude": cidade["latitude"],
            "longitude": cidade["longitude"],
            "current": (
                "temperature_2m,relative_humidity_2m,"
                "apparent_temperature,precipitation,weather_code,wind_speed_10m"
            ),
            "timezone": "auto",
        },
        timeout=20,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    atual = dados.get("current")
    if not isinstance(atual, dict):
        raise ValueError("Resposta da Open-Meteo sem dados meteorológicos.")

    codigo = atual.get("weather_code")
    descricao = DESCRICOES_TEMPO.get(codigo, "Condição não identificada")
    local = ", ".join(
        str(parte)
        for parte in (
            cidade.get("name", nome_cidade),
            cidade.get("admin1", ""),
            cidade.get("country", ""),
        )
        if parte
    )

    return montar_resposta(
        local=local,
        horario=atual.get("time"),
        temperatura=atual.get("temperature_2m", "N/D"),
        sensacao=atual.get("apparent_temperature", "N/D"),
        descricao=descricao,
        umidade=atual.get("relative_humidity_2m", "N/D"),
        vento=atual.get("wind_speed_10m", "N/D"),
        precipitacao=atual.get("precipitation", "N/D"),
        fonte="Open-Meteo",
    )


def consultar_wttr(nome_cidade, cidade=None):

    logger.info("Tentando fonte alternativa WTTR.IN para %s", nome_cidade)


    if cidade and cidade.get("latitude") is not None and cidade.get("longitude") is not None:
        local_consulta = (
            f"{cidade['latitude']},{cidade['longitude']}"
        )
    else:

        local_consulta = nome_cidade

    resposta = sessao.get(
        f"{WTTR_API}/{requests.utils.quote(local_consulta, safe=',.-')}",
        params={"format": "j1", "lang": "pt"},
        headers={"Accept": "application/json"},
        timeout=25,
    )
    resposta.raise_for_status()
    dados = resposta.json()

    condicoes = dados.get("current_condition") or []
    if not condicoes:
        raise ValueError("WTTR.IN não retornou as condições atuais.")

    atual = condicoes[0]
    areas = dados.get("nearest_area") or []
    area = areas[0] if areas else {}

    def primeiro_texto(lista):
        if isinstance(lista, list) and lista:
            return lista[0].get("value", "N/D")
        return "N/D"

    nome = primeiro_texto(area.get("areaName"))
    regiao = primeiro_texto(area.get("region"))
    pais = primeiro_texto(area.get("country"))


    if cidade:
        nome = cidade.get("name") or nome
        regiao = cidade.get("admin1") or regiao
        pais = cidade.get("country") or pais

    local = ", ".join(parte for parte in (nome, regiao, pais) if parte)
    if not local:
        local = nome_cidade


    horario = atual.get("localObsDateTime")


    if not horario:
        fusos = dados.get("time_zone") or []
        if fusos and isinstance(fusos[0], dict):
            horario = fusos[0].get("localtime")


    if not horario:
        hora_observacao = atual.get("observation_time")
        previsoes_diarias = dados.get("weather") or []
        data_previsao = (
            previsoes_diarias[0].get("date")
            if previsoes_diarias and isinstance(previsoes_diarias[0], dict)
            else None
        )

        if data_previsao and hora_observacao:
            horario = f"{data_previsao} {hora_observacao}"
        elif data_previsao:
            horario = data_previsao
        elif hora_observacao:
            horario = f"{datetime.now().strftime('%Y-%m-%d')} {hora_observacao}"


    if not horario:
        horario = datetime.now().strftime("%Y-%m-%d %H:%M")

    return montar_resposta(
        local=local,
        horario=horario,
        temperatura=atual.get("temp_C", "N/D"),
        sensacao=atual.get("FeelsLikeC", "N/D"),
        descricao=traduzir_condicao(primeiro_texto(atual.get("weatherDesc"))),
        umidade=atual.get("humidity", "N/D"),
        vento=atual.get("windspeedKmph", "N/D"),
        precipitacao=atual.get("precipMM", "N/D"),
        fonte="WTTR.IN (fonte alternativa)",
    )


def consultar_tempo(nome_cidade):

    texto_cache = obter_cache(nome_cidade)
    if texto_cache:
        return texto_cache

    cidade = None


    try:
        cidade = localizar_cidade(nome_cidade)
        if cidade is None:
            raise LookupError(f"Cidade não encontrada: {nome_cidade}")

    except requests.RequestException as erro:
        logger.warning(
            "Geolocalização Open-Meteo indisponível (%s). "
            "A alternativa tentará localizar pelo nome.",
            erro,
        )


    if cidade is not None:
        try:
            resultado = consultar_open_meteo(nome_cidade, cidade=cidade)
            salvar_cache(nome_cidade, resultado)
            logger.info("Previsão recebida pela Open-Meteo para %s", nome_cidade)
            return resultado

        except requests.HTTPError as erro:
            status = erro.response.status_code if erro.response is not None else None
            logger.warning("Open-Meteo retornou HTTP %s", status)
            if status != 429:
                raise
            logger.warning("Limite da Open-Meteo atingido. Acionando WTTR.IN.")

        except (requests.Timeout, requests.ConnectionError) as erro:
            logger.warning("Open-Meteo indisponível (%s). Tentando WTTR.IN.", erro)

        except requests.RequestException as erro:
            logger.warning("Falha na Open-Meteo (%s). Tentando WTTR.IN.", erro)


    resultado = consultar_wttr(nome_cidade, cidade=cidade)
    salvar_cache(nome_cidade, resultado)
    logger.info("Previsão recebida pela WTTR.IN para %s", nome_cidade)
    return resultado


def processar_mensagem(mensagem):

    chat_id = mensagem.get("chat", {}).get("id")
    texto = mensagem.get("text", "")

    if not chat_id or not texto:
        return

    texto = texto.strip()
    logger.info("Mensagem recebida. Chat ID: %s", chat_id)

    if texto == "/start" or texto.startswith("/start "):
        enviar_mensagem(
            chat_id,
            "Olá! 🌤️ Sou o Bot de Previsão do Tempo!\n\n"
            "Envie o nome de uma cidade para consultar o clima.\n\n"
            "Exemplo: Campinas\n\n"
            "Comandos disponíveis:\n"
            "/start - Iniciar o bot\n"
            "/help - Mostrar ajuda\n"
            "/tempo Campinas - Consultar uma cidade",
        )
        return

    if texto == "/help" or texto.startswith("/help "):
        enviar_mensagem(
            chat_id,
            "📘 COMANDOS DO BOT\n\n"
            "/start - Iniciar o bot\n"
            "/help - Mostrar esta ajuda\n"
            "/tempo Campinas - Consultar uma cidade\n\n"
            "Você também pode enviar apenas o nome da cidade.",
        )
        return

    if texto.startswith("/tempo"):
        partes = texto.split(maxsplit=1)
        if len(partes) < 2 or not partes[1].strip():
            enviar_mensagem(
                chat_id,
                "Informe uma cidade.\n\nExemplo: /tempo Campinas",
            )
            return
        nome_cidade = partes[1].strip()

    elif texto.startswith("/"):
        enviar_mensagem(chat_id, "Comando desconhecido. Digite /help.")
        return
    else:
        nome_cidade = texto

    enviar_mensagem(chat_id, f"🔎 Consultando o tempo em {nome_cidade}...")

    try:
        resultado = consultar_tempo(nome_cidade)
        enviar_mensagem(chat_id, resultado)

    except LookupError:
        logger.exception("CIDADE NÃO ENCONTRADA")
        enviar_mensagem(
            chat_id,
            f"Não encontrei a cidade '{nome_cidade}'. Confira o nome e tente novamente.",
        )

    except requests.HTTPError as erro:
        status = erro.response.status_code if erro.response is not None else "desconhecido"
        logger.exception("ERRO HTTP NAS FONTES METEOROLÓGICAS: %s", status)
        enviar_mensagem(
            chat_id,
            "Não consegui consultar a previsão neste momento. "
            "As fontes meteorológicas estão temporariamente indisponíveis. "
            "Tente novamente mais tarde.",
        )

    except requests.Timeout:
        logger.exception("TEMPO ESGOTADO")
        enviar_mensagem(chat_id, "A consulta demorou demais. Tente novamente.")

    except requests.RequestException:
        logger.exception("ERRO DE CONEXÃO/REQUISIÇÃO NAS FONTES METEOROLÓGICAS")
        enviar_mensagem(
            chat_id,
            "Não consegui conectar às fontes de previsão do tempo. Tente novamente mais tarde.",
        )

    except (ValueError, KeyError, TypeError):
        logger.exception("ERRO AO PROCESSAR OS DADOS")
        enviar_mensagem(
            chat_id,
            "Recebi dados que não consegui interpretar. Tente novamente mais tarde.",
        )

    except Exception:
        logger.exception("ERRO INESPERADO")
        enviar_mensagem(chat_id, "Ocorreu um erro inesperado. Confira os Logs do Render.")


@app.route("/", methods=["GET"])
def inicio():
    return "Bot de Previsão do Tempo está funcionando!", 200


@app.route("/telegram", methods=["POST"])
def webhook_telegram():
    mensagem_recebida = request.get_json(silent=True)
    if not isinstance(mensagem_recebida, dict):
        return "Requisição inválida", 400

    mensagem = mensagem_recebida.get("message")
    if mensagem:
        try:
            processar_mensagem(mensagem)
        except Exception:
            logger.exception("ERRO AO PROCESSAR ATUALIZAÇÃO")

    return "OK", 200


def configurar_webhook():

    url_render = os.getenv("RENDER_EXTERNAL_URL")
    if not url_render:
        logger.error("RENDER_EXTERNAL_URL não está disponível.")
        return

    url_webhook = f"{url_render.rstrip('/')}/telegram"
    logger.info("Configurando webhook do Telegram.")

    try:
        resposta = sessao.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": url_webhook},
            timeout=20,
        )
        resposta.raise_for_status()
        dados = resposta.json()

        if dados.get("ok"):
            logger.info("Webhook configurado com sucesso: %s", url_webhook)
        else:
            logger.error("Telegram recusou o webhook: %s", dados)

    except requests.RequestException:
        logger.exception("ERRO AO CONFIGURAR WEBHOOK")


if __name__ == "__main__":
    threading.Thread(target=configurar_webhook, daemon=True).start()

    porta = int(os.environ.get("PORT", "10000"))
    logger.info("Iniciando o bot na porta %s", porta)
    app.run(host="0.0.0.0", port=porta)
