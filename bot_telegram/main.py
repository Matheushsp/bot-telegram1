
import os
import requests
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise SystemExit(
        "Token não encontrado! Configure TELEGRAM_TOKEN nas "
        "Environment Variables do Render."
    )

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

GEOCODING_API = (
    "https://geocoding-api.open-meteo.com/v1/search"
)
WEATHER_API = "https://api.open-meteo.com/v1/forecast"

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
    61: "Chuva leve",
    63: "Chuva moderada",
    65: "Chuva forte",
    71: "Neve leve",
    73: "Neve moderada",
    75: "Neve forte",
    80: "Pancadas de chuva leves",
    81: "Pancadas de chuva moderadas",
    82: "Pancadas de chuva fortes",
    95: "Trovoadas",
    96: "Trovoadas com granizo",
    99: "Trovoadas fortes com granizo",
}


def enviar_mensagem(chat_id, texto):
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

    except requests.RequestException as erro:
        print("Erro ao enviar mensagem:", erro)


def localizar_cidade(nome_cidade):
    resposta = requests.get(
        GEOCODING_API,
        params={
            "name": nome_cidade,
            "count": 1,
            "language": "pt",
            "format": "json"
        },
        timeout=15
    )
    resposta.raise_for_status()

    resultados = resposta.json().get("results", [])

    if not resultados:
        return None

    return resultados[0]


def consultar_tempo(nome_cidade):
    cidade = localizar_cidade(nome_cidade)

    if not cidade:
        return (
            f"Não encontrei a cidade '{nome_cidade}'. "
            "Confira o nome e tente novamente."
        )

    resposta = requests.get(
        WEATHER_API,
        params={
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
        },
        timeout=15
    )
    resposta.raise_for_status()

    atual = resposta.json()["current"]

    codigo = atual.get("weather_code")
    descricao = DESCRICOES_TEMPO.get(
        codigo, "Condição não identificada"
    )

    local = ", ".join(
        parte for parte in [
            cidade.get("name", nome_cidade),
            cidade.get("admin1", ""),
            cidade.get("country", "")
        ] if parte
    )

    return (
        "🌦️ PREVISÃO DO TEMPO\n"
        f"📍 Cidade: {local}\n"
        f"🕒 Horário: {atual.get('time', 'N/D')}\n\n"
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


def processar_mensagem(mensagem):
    chat_id = mensagem.get("chat", {}).get("id")
    texto = mensagem.get("text", "")

    if not chat_id or not texto:
        return

    texto = texto.strip()

    if texto.startswith("/start"):
        enviar_mensagem(
            chat_id,
            "Olá! 🌤️ Sou o Bot de Previsão do Tempo!\n\n"
            "Envie o nome de uma cidade para consultar o clima.\n\n"
            "Exemplo: Campinas\n\n"
            "Use /tempo Campinas ou digite /help "
            "para ver os comandos."
        )
        return

    if texto.startswith("/help"):
        enviar_mensagem(
            chat_id,
            "📘 COMANDOS DO BOT\n\n"
            "/start - Iniciar o bot\n"
            "/help - Mostrar esta ajuda\n"
            "/tempo Campinas - Consultar uma cidade\n\n"
            "Você também pode enviar apenas o nome da cidade."
        )
        return

    if texto.startswith("/tempo"):
        partes = texto.split(maxsplit=1)

        if len(partes) < 2:
            enviar_mensagem(
                chat_id,
                "Informe a cidade. Exemplo: /tempo Campinas"
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
        enviar_mensagem(chat_id, resultado)

    except requests.RequestException as erro:
        print("Erro ao consultar previsão:", erro)
        enviar_mensagem(
            chat_id,
            "Não consegui acessar a API agora. "
            "Tente novamente mais tarde."
        )

    except (KeyError, ValueError) as erro:
        print("Erro nos dados meteorológicos:", erro)
        enviar_mensagem(
            chat_id,
            "Não consegui interpretar os dados do tempo. "
            "Tente novamente."
        )


@app.route("/", methods=["GET"])
def inicio():
    return "Bot de Previsão do Tempo está funcionando!", 200


@app.route("/telegram", methods=["POST"])
def webhook_telegram():
    mensagem_recebida = request.get_json(silent=True) or {}

    if not isinstance(mensagem_recebida, dict):
        return "Requisição inválida", 400

    mensagem = mensagem_recebida.get("message")

    if mensagem:
        try:
            processar_mensagem(mensagem)
        except Exception as erro:
            print("Erro ao processar mensagem:", erro)

    return "OK", 200


def configurar_webhook():
    url_render = os.getenv("RENDER_EXTERNAL_URL")

    if not url_render:
        print("RENDER_EXTERNAL_URL não configurada.")
        return

    url_webhook = f"{url_render.rstrip('/')}/telegram"

    try:
        resposta = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": url_webhook},
            timeout=20
        )
        resposta.raise_for_status()

        dados = resposta.json()
        print("Resultado da configuração do webhook:", dados)

        if not dados.get("ok"):
            print("O Telegram não aceitou o webhook.")

    except requests.RequestException as erro:
        print("Erro ao configurar webhook:", erro)


if __name__ == "__main__":
    import threading

    threading.Thread(
        target=configurar_webhook,
        daemon=True
    ).start()

    porta = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=porta
    )
