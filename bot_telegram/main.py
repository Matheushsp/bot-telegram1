import ast
import operator
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else None

# Operadores permitidos na calculadora. Não usamos eval().
OPERADORES = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calcular(expressao):
    """Calcula apenas expressões matemáticas com números e operadores permitidos."""
    if len(expressao) > 100:
        raise ValueError("A expressão é muito longa.")

    arvore = ast.parse(expressao, mode="eval")

    def avaliar(no):
        if isinstance(no, ast.Expression):
            return avaliar(no.body)

        if isinstance(no, ast.Constant) and type(no.value) in (int, float):
            return no.value

        if isinstance(no, ast.BinOp) and type(no.op) in OPERADORES:
            esquerda = avaliar(no.left)
            direita = avaliar(no.right)

            # Limites simples para evitar cálculos excessivos.
            if isinstance(no.op, ast.Pow) and abs(direita) > 100:
                raise ValueError("O expoente deve estar entre -100 e 100.")

            resultado = OPERADORES[type(no.op)](esquerda, direita)
            if isinstance(resultado, (int, float)) and abs(resultado) > 1e100:
                raise ValueError("O resultado é grande demais.")
            return resultado

        if isinstance(no, ast.UnaryOp) and type(no.op) in OPERADORES:
            return OPERADORES[type(no.op)](avaliar(no.operand))

        raise ValueError("Use apenas números, parênteses e operadores matemáticos.")

    return avaliar(arvore)


def enviar_mensagem(chat_id, texto):
    """Envia uma mensagem ao chat do Telegram."""
    try:
        resposta = requests.post(
            f"{API_URL}/sendMessage",
            data={"chat_id": chat_id, "text": texto},
            timeout=15,
        )
        resposta.raise_for_status()
        dados = resposta.json()
        if not dados.get("ok"):
            print("Telegram retornou um erro:", dados)
    except requests.RequestException as erro:
        print("Erro ao enviar mensagem:", erro)


def processar_mensagem(mensagem):
    chat = mensagem.get("chat", {})
    chat_id = chat.get("id")
    texto = mensagem.get("text", "")

    if not chat_id or not texto:
        return

    texto = texto.strip()

    if texto.startswith("/start"):
        enviar_mensagem(
            chat_id,
            "Olá! 👋 Sou sua Calculadora Bot.\n\n"
            "Envie uma conta, por exemplo:\n"
            "10 + 5\n"
            "(8 * 3) / 2\n"
            "2 ** 3\n\n"
            "Digite /help para ver os comandos.",
        )
        return

    if texto.startswith("/help"):
        enviar_mensagem(
            chat_id,
            "📘 COMO USAR A CALCULADORA\n\n"
            "/start — iniciar o bot\n"
            "/help — mostrar esta ajuda\n\n"
            "Operadores aceitos:\n"
            "+ adição\n"
            "- subtração\n"
            "* multiplicação\n"
            "/ divisão\n"
            "// divisão inteira\n"
            "% resto da divisão\n"
            "** potência\n\n"
            "Exemplos: 12 + 8, 9 / 3, (4 + 2) * 5",
        )
        return

    if texto.startswith("/"):
        enviar_mensagem(chat_id, "Comando não reconhecido. Digite /help para ver os comandos.")
        return

    try:
        resultado = calcular(texto)
        enviar_mensagem(chat_id, f"🧮 Resultado: {resultado}")
    except ZeroDivisionError:
        enviar_mensagem(chat_id, "Não é possível dividir por zero.")
    except (ValueError, SyntaxError, TypeError, OverflowError):
        enviar_mensagem(
            chat_id,
            "Não consegui calcular essa expressão.\n"
            "Envie uma conta como: (10 + 5) * 2",
        )


def main():
    if not TOKEN:
        raise SystemExit(
            "Token não encontrado. Crie o arquivo .env e configure TELEGRAM_TOKEN."
        )

    print("Bot iniciado. Pressione Ctrl+C para parar.")
    offset = None

    while True:
        try:
            parametros = {"timeout": 30}
            if offset is not None:
                parametros["offset"] = offset

            resposta = requests.get(
                f"{API_URL}/getUpdates",
                params=parametros,
                timeout=35,
            )
            resposta.raise_for_status()
            dados = resposta.json()

            if not dados.get("ok"):
                print("Erro retornado pelo Telegram:", dados)
                time.sleep(3)
                continue

            for atualizacao in dados.get("result", []):
                offset = atualizacao["update_id"] + 1
                mensagem = atualizacao.get("message")
                if mensagem:
                    processar_mensagem(mensagem)

        except requests.RequestException as erro:
            print(f"Falha de conexão: {erro}. Tentando novamente em 5 segundos...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nBot encerrado.")
            break


if __name__ == "__main__":
    main()
