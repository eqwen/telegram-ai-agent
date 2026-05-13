# Telegram AI Agent with Ollama

Production-ready Telegram bot on Python with `python-telegram-bot`, Ollama, SQLite memory, per-user context, `.env` config, logging, `/start`, `/reset`, and typing indicator.

## Project structure

```text
bot/
  __init__.py
  bot.py
  memory.py
  config.py
  prompts.py
requirements.txt
.env.example
telegram-ai-agent.service
README.md
```

## Ubuntu installation

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip sqlite3 curl
```

Install Ollama:

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull qwen3:4b
```

Create app user and deploy project:

```bash
sudo useradd --system --home /opt/telegram-ai-agent --shell /usr/sbin/nologin telegrambot
sudo mkdir -p /opt/telegram-ai-agent
sudo chown -R telegrambot:telegrambot /opt/telegram-ai-agent
```

Copy this project into `/opt/telegram-ai-agent`, then install dependencies:

```bash
cd /opt/telegram-ai-agent
sudo -u telegrambot python3 -m venv .venv
sudo -u telegrambot .venv/bin/pip install --upgrade pip
sudo -u telegrambot .venv/bin/pip install -r requirements.txt
sudo -u telegrambot mkdir -p data
```

Create environment file:

```bash
sudo -u telegrambot cp .env.example .env
sudo nano .env
```

Set your Telegram token:

```env
TELEGRAM_BOT_TOKEN=your_real_token
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=qwen3:4b
DATABASE_PATH=/opt/telegram-ai-agent/data/memory.sqlite3
MAX_CONTEXT_MESSAGES=12
MAX_PROMPT_CHARS=12000
REQUEST_TIMEOUT_SECONDS=90
LOG_LEVEL=INFO
```

## Run manually

```bash
cd /opt/telegram-ai-agent
sudo -u telegrambot .venv/bin/python -m bot.bot
```

## Run with systemd

```bash
sudo cp telegram-ai-agent.service /etc/systemd/system/telegram-ai-agent.service
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-ai-agent
sudo systemctl status telegram-ai-agent
```

View logs:

```bash
journalctl -u telegram-ai-agent -f
```

Restart after changes:

```bash
sudo systemctl restart telegram-ai-agent
```

## Bot commands

- `/start` - welcome message.
- `/reset` - clears memory for the current Telegram user.

## Production notes

- The bot uses long polling, which is simple and reliable for a VPS.
- SQLite stores the last `MAX_CONTEXT_MESSAGES` messages per Telegram user.
- `MAX_PROMPT_CHARS` protects Ollama from oversized prompts.
- The `systemd` unit restarts the bot after failures and restricts filesystem access to the app directory.
- Keep `.env` private and never commit a real Telegram token.
