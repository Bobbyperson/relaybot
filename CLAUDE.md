# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Relaybot is a Python Discord bot that provides two-way Discord <-> Northstar (Titanfall 2) game server relay, stat tracking, leaderboards, and tournament management. It is highly specialized for the author's server infrastructure.

## Commands

```bash
uv sync                    # Install dependencies
python main.py             # Run the bot
ruff check .               # Lint
```

The bot requires a `config.toml` file (not in git). Copy `example.config.toml` and fill in Discord token, server definitions, channel IDs, and admin lists. Config is loaded in the `Bot` subclass in `main.py` and accessible as `bot.config` (a dict). Server objects are on `bot.servers` and `bot.tournament_servers`.

## Architecture

**Entry point:** `main.py` — subclasses `commands.Bot` to load `config.toml` via `tomllib`, constructs `Server` objects, dynamically loads all cogs from `./cogs/`, and starts the event loop.

**Cogs (modular command groups):**
- `relay.py` — Core relay logic and aiohttp web server. Handles bidirectional Discord <-> game server messaging, exposes HTTP endpoints (`/post`, `/get`, `/leaderboard`, `/stats`, `/is-whitelisted`, `/is-banned`, etc.) for game servers to interact with.
- `stats.py` — Player statistics, playtime tracking, online status, raid mode (auto-timeout during attacks).
- `admin.py` — Owner/admin commands: lookup, sync, whitelist/ban management, RCON server commands.
- `tournament.py` — Challonge-integrated tournament system with loadout management. Loadout configs in `tourney/loadout*.json`.
- `parkour.py` — Parkour event tracking via external API.

**Utilities:**
- `cogs/utils/utils.py` — Database helpers, user linking (Discord ID <-> Northstar UID), server validation, ban/unban, admin checks. Most functions take `bot` as the first parameter to access config.
- `cogs/utils/crashes.py` — `CrashHandler` for server crash tracking and whitelist recommendations.

**Other directories:**
- `leaderboard/` — Static HTML/CSS/JS frontend for leaderboard display.
- `tourney/` — Tournament loadout JSON configs.
- `mods/` — Custom Northstar game server mods.
- `server.py` — `Server` class wrapping RCON connections to game servers.

## Key Patterns

- **Async throughout:** aiosqlite for DB, aiohttp for HTTP, discord.py async commands. Database is SQLite (`database.sqlite`).
- **Multi-server:** Bot manages multiple parallel game servers, each with their own DB tables and relay channels. Server definitions come from `config.toml`.
- **Web server inside a cog:** The Relay cog starts an aiohttp server on bot ready, serving JSON APIs and the leaderboard frontend.
- **RCON:** Direct game server control via Source RCON protocol (`rcon` library).

## Tech Stack

- Python 3.14+, discord.py 2.7+, uv for package management
- Ruff for linting (config in `pyproject.toml` — selected rules: A004, RUF, UP, I, ASYNC, F, FURB, PLC)
- CI runs `ruff check` on push/PR to main
