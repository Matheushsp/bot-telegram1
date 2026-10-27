
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise SystemExit(
        "Token não encontrado! Configure o arquivo .env."
    )

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

GEOCODING_API = (
    "https://geocoding-api.open-meteo.com/v1/search"
)
WEATHER_API = "https://api.open-meteo.com/v1/forecast"

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
            data={
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
        f"🌡️ Temperatura: {atual.get('temperature_2m', 'N/D')} °C\n"
        f"🤔 Sensação térmica: {atual.get('apparent_temperature', 'N/D')} °C\n"
        f"☁️ Condição: {descricao}\n"
        f"💧 Umidade: {atual.get('relative_humidity_2m', 'N/D')}%\n"
        f"💨 Vento: {atual.get('wind_speed_10m', 'N/D')} km/h\n"
        f"🌧️ Precipitação: {atual.get('precipitation', 'N/D')} mm\n\n"
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

    except requests.RequestException:
        enviar_mensagem(
            chat_id,
            "Não consegui acessar a API agora. "
            "Verifique a internet e tente novamente."
        )


def main():
    print(
        "Bot de Previsão do Tempo iniciado. "
        "Pressione Ctrl+C para parar."
    )

    offset = None

    while True:
        try:
            parametros = {"timeout": 30}

            if offset is not None:
                parametros["offset"] = offset

            resposta = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params=parametros,
                timeout=35
            )

            resposta.raise_for_status()
            dados = resposta.json()

            for atualizacao in dados.get("result", []):
                offset = atualizacao["update_id"] + 1

                mensagem = atualizacao.get("message")

                if mensagem:
                    processar_mensagem(mensagem)

        except requests.HTTPError as erro:
            status = (
                erro.response.status_code
                if erro.response is not None else 0
            )

            if status == 409:
                print(
                    "Erro 409: feche outras instâncias "
                    "do mesmo bot."
                )
                time.sleep(5)
            else:
                print("Erro HTTP:", erro)
                time.sleep(5)

        except requests.RequestException as erro:
            print("Erro de conexão:", erro)
            time.sleep(5)

        except KeyboardInterrupt:
            print("\nBot encerrado.")
            break


if __name__ == "__main__":
    main()
