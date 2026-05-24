# 08 — DISCORD BOT + AI ASSISTANT

---

## Arsitektur

```
User (Discord) → Discord Bot → AI Client → OpenAI-compatible API
                      ↓
               Bot State / Logs / Trade Data
```

Discord bot = UI layer. AI = brain yang bisa baca semua data bot.
Semua provider yang pakai OpenAI base URL format diterima (OpenAI, Anthropic via proxy, Groq, Together, local Ollama, dll).

---

## Dependencies Tambahan

```
discord.py>=2.3.0     # Discord bot framework
httpx>=0.27.0         # async HTTP client untuk AI API calls
```

---

## discord_ui/bot.py (~50 lines)

```python
import discord
from discord.ext import commands

def createBot() -> commands.Bot:
    """
    Create Discord bot instance.
    Intents: message_content, guilds.
    Prefix: tidak ada — pakai slash commands saja.
    """

async def startBot(token: str) -> None:
    """Start bot, load commands cog."""
```

---

## discord_ui/commands.py (~100 lines)

Slash commands:

```python
@bot.tree.command(name="status")
async def statusCommand(interaction: discord.Interaction) -> None:
    """
    Show: open positions, uptime, last cycle time, balance.
    Source: botState (shared reference) + position/tracker.py
    """

@bot.tree.command(name="positions")
async def positionsCommand(interaction: discord.Interaction) -> None:
    """
    Show detail semua open positions:
    symbol, side, entry FR, entry time, unrealized PnL, SL/TP status.
    """

@bot.tree.command(name="metrics")
async def metricsCommand(interaction: discord.Interaction) -> None:
    """
    Parse trades.jsonl, hitung:
    - Total net $, APY estimate
    - Fill rate, max drawdown
    - Avg actual cost vs 0.12%
    - Trade count, win/loss
    """

@bot.tree.command(name="trades")
async def tradesCommand(interaction: discord.Interaction, limit: int = 10) -> None:
    """Show last N trades dari trade log."""

@bot.tree.command(name="ask")
async def askCommand(interaction: discord.Interaction, question: str) -> None:
    """
    Kirim pertanyaan ke AI assistant.
    AI punya akses ke: bot state, trade log, cost cache, recent logs.
    Response di-format dan dikirim ke Discord.
    """

@bot.tree.command(name="health")
async def healthCommand(interaction: discord.Interaction) -> None:
    """
    Quick health check:
    - Bot running? Last cycle timestamp?
    - Unprotected positions?
    - Orphan orders?
    - Downtime?
    """
```

---

## discord_ui/formatter.py (~40 lines)

```python
def formatPositionsEmbed(positions: list[dict]) -> discord.Embed:
    """Format positions ke Discord embed."""

def formatMetricsEmbed(metrics: dict) -> discord.Embed:
    """Format metrics summary ke Discord embed."""

def formatTradesEmbed(trades: list[dict]) -> discord.Embed:
    """Format recent trades ke Discord embed."""

def formatStatusEmbed(status: dict) -> discord.Embed:
    """Format bot status ke Discord embed."""
```

---

## ai/client.py (~60 lines)

```python
class AiClient:
    """
    OpenAI-compatible API client.
    Accepts any provider with OpenAI base URL format:
    - OpenAI, Groq, Together, Ollama, LM Studio, etc.
    """

    def __init__(self, baseUrl: str, apiKey: str, model: str):
        """
        baseUrl: e.g. "https://api.openai.com/v1"
                      "https://api.groq.com/openai/v1"
                      "http://localhost:11434/v1"
        """

    async def chat(self, messages: list[dict], 
                   maxTokens: int = 1024) -> str:
        """
        POST {baseUrl}/chat/completions
        Standard OpenAI chat format.
        Return: assistant message content.
        """
```

---

## ai/context_builder.py (~70 lines)

```python
def buildContext(botState: dict, query: str) -> list[dict]:
    """
    Build messages array untuk AI:
    1. System prompt (dari ai/prompts/system.md)
    2. Context data (auto-selected based on query):
       - Current positions
       - Recent trades (last 20)
       - Bot status (uptime, balance, cycle count)
       - Cost cache summary
       - Recent log entries (last 50 lines)
       - Performance metrics
    3. User query
    
    Return: [{"role": "system", ...}, {"role": "user", ...}]
    """

def summarizePositions(positions: list[dict]) -> str:
    """Compact text summary of open positions."""

def summarizeMetrics(trades: list[dict]) -> str:
    """Compact text summary of performance metrics."""

def summarizeRecentLogs(logPath: str, lines: int = 50) -> str:
    """Last N lines dari bot.log."""

def summarizeCostCache(costCache: CostCache) -> str:
    """Top coins by cost, avg cost across universe."""
```

---

## ai/prompts/system.md

File terpisah, loaded at runtime. Isi:

```markdown
# System Prompt

Kamu adalah AI assistant untuk Funding Rate Arbitrage Bot.

## Konteks Bot
- Strategy: delta-neutral (long spot + short futures) saat |FR| >= 0.05%
- Exit: |FR| < 0.02% atau FR flip sign
- Capital: $3,000, 6 max pairs, $300/pair
- Phase: Paper trading validation (Phase 4)

## Yang Kamu Bisa
- Analisa performance (APY, fill rate, drawdown)
- Jelaskan kenapa trade tertentu profit/loss
- Identifikasi pattern di trade history
- Suggest apakah parameter tunable perlu diubah
- Diagnosa masalah (orphan orders, high cost, low fill rate)
- Jawab pertanyaan tentang strategy logic

## Yang Kamu TIDAK Boleh
- Suggest ubah LOCKED parameters (entry/exit threshold, max pairs, buffer)
- Suggest deploy ke mainnet sebelum 4 minggu + pass metrics
- Suggest expand universe ke 4h coins
- Buat keputusan trading — kamu hanya analisa

## Data Yang Tersedia
- Open positions (real-time)
- Trade history (semua closed trades)
- Cost cache (rolling avg per coin)
- Bot logs (recent entries)
- Performance metrics (computed)

## Response Style
- Concise, data-driven
- Pakai angka spesifik, bukan generalisasi
- Kalau data tidak cukup untuk jawab, bilang
```

---

## ai/prompts/tools.md

Reserved untuk future tool-use / function calling. Kosong dulu di Phase 4.

---

## Secrets Tambahan (.env)

```env
# Discord
DISCORD_BOT_TOKEN=

# AI (OpenAI-compatible)
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=
AI_MODEL=gpt-4o-mini
```

---

## Running Architecture

Dua process terpisah (atau satu process, dua async tasks):

**Option A — Dua process (recommended untuk Phase 4):**
```bash
# Terminal 1: trading bot
python -m bot.main

# Terminal 2: discord bot
python -m discord_ui.bot
```

Discord bot baca state dari:
- `logs/trades.jsonl` (file)
- `logs/bot.log` (file)
- `logs/cost_cache.json` (file)
- Live API calls (positions, balance) — via exchange instances sendiri

**Option B — Single process (Phase 5):**
Bot + Discord dalam satu async event loop. Lebih complex, tidak perlu sekarang.

---

## Critical Notes

- Discord bot READONLY terhadap trading — tidak bisa trigger entry/exit
- AI assistant READONLY — analisa saja, tidak bisa modify bot state
- AI context window: trim data kalau terlalu besar (max ~4000 tokens context)
- Rate limit Discord: 50 requests/second global — tidak masalah untuk monitoring
- Kalau AI provider down → command tetap jalan (status/metrics/positions langsung dari data)
- `/ask` command: defer reply dulu (AI bisa lambat), lalu edit dengan response
