# Bot Calculadora no Telegram

Projeto em Python para executar no VS Code no Windows. O bot responde aos comandos `/start` e `/help` e calcula expressões matemáticas simples.

## 1. Pré-requisitos

- Python 3.11 ou mais recente
- VS Code
- Extensão Python da Microsoft no VS Code
- Conta no Telegram

## 2. Criar o bot no Telegram

1. Abra [@BotFather](https://t.me/BotFather) no Telegram.
2. Envie `/newbot`.
3. Escolha o nome e o username do bot (o username deve terminar em `bot`).
4. Copie o token fornecido. **Não compartilhe esse token com ninguém.**

## 3. Abrir o projeto

1. Extraia o ZIP para uma pasta, por exemplo `C:\Projetos\bot_telegram`.
2. Abra essa pasta no VS Code: **File > Open Folder**.
3. Abra o terminal integrado: **Terminal > New Terminal**.

## 4. Criar o ambiente virtual

No terminal PowerShell do VS Code, execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação, você pode instalar e executar usando o Python do ambiente virtual diretamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 5. Configurar o token

Na pasta do projeto, copie `.env.example` e renomeie a cópia para `.env`.

Abra `.env` e substitua o texto de exemplo pelo token real:

```env
TELEGRAM_TOKEN=123456789:SEU_TOKEN_REAL
```

Não coloque aspas e não envie esse arquivo a outras pessoas. O `.gitignore` já exclui o arquivo `.env` do Git.

## 6. Executar

Com o ambiente virtual ativado:

```powershell
python main.py
```

O terminal deve mostrar:

```text
Bot iniciado. Pressione Ctrl+C para parar.
```

Abra o bot pelo link que o BotFather forneceu ou pesquise seu username no Telegram, pressione **Iniciar** e teste:

- `/start`
- `/help`
- `10 + 5`
- `(8 * 3) / 2`
- `2 ** 3`

Para encerrar, volte ao terminal e pressione `Ctrl+C`. O bot só responde enquanto o programa estiver em execução.

## 7. Como funciona

- `getUpdates`: recebe as mensagens enviadas ao bot.
- `sendMessage`: envia respostas ao usuário.
- `python-dotenv`: carrega o token do arquivo `.env`.
- A calculadora usa uma análise restrita de expressões matemáticas; ela não executa código arbitrário com `eval()`.

## Solução de problemas

- **Token não encontrado:** confira se o arquivo se chama exatamente `.env` e está na mesma pasta que `main.py`.
- **Módulo não encontrado:** ative `.venv` e execute `pip install -r requirements.txt`.
- **Bot não responde:** confira se o programa continua rodando e se iniciou a conversa com o bot no Telegram.
- **Outra aplicação está usando `getUpdates`:** pare outros programas que consultem atualizações do mesmo bot e tente novamente.
- **Token exposto:** gere outro token pelo BotFather e atualize o arquivo `.env`.
