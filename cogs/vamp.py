"""VAMP duel tracking.

Self-contained module: own aiohttp app, own port, own tables, own static site.
Ingests events from the vaxta.VAMP Northstar mod and serves the stats site.

Everything the site shows is derived from the `vamp_duels` table at query time
rather than from running totals, so windowed views (24h/7d/30d/all) and cycles
stay correct without a rebuild step.
"""

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite
import discord
from aiohttp import web
from discord.ext import commands

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,authentication",
}

WINDOWS = {"24h": 86400, "7d": 604800, "30d": 2592000, "all": None}
SORTS = {"wins", "losses", "winrate", "duels", "acc", "streak"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS vamp_duels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              INTEGER NOT NULL,
    server          TEXT,
    winner_uid      TEXT NOT NULL,
    winner_name     TEXT NOT NULL,
    winner_acc      REAL NOT NULL DEFAULT 0,
    winner_hp       INTEGER,
    winner_handicap REAL NOT NULL DEFAULT 1.0,
    loser_uid       TEXT NOT NULL,
    loser_name      TEXT NOT NULL,
    loser_acc       REAL NOT NULL DEFAULT 0,
    loser_handicap  REAL NOT NULL DEFAULT 1.0,
    duration        REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS vamp_duels_ts      ON vamp_duels (ts);
CREATE INDEX IF NOT EXISTS vamp_duels_winner  ON vamp_duels (winner_uid);
CREATE INDEX IF NOT EXISTS vamp_duels_loser   ON vamp_duels (loser_uid);

CREATE TABLE IF NOT EXISTS vamp_players (
    uid       TEXT PRIMARY KEY,
    name      TEXT,
    online    INTEGER NOT NULL DEFAULT 0,
    handicap  REAL NOT NULL DEFAULT 1.0,
    redaction INTEGER NOT NULL DEFAULT 0,
    last_seen INTEGER
);
"""


def _cycle_code(ts: int) -> str:
    """Cycles are ISO weeks; ranks reset weekly."""
    y, w, _ = datetime.fromtimestamp(ts, UTC).isocalendar()
    return f"{y}-W{w:02d}"


def _cycle_bounds(code: str) -> tuple[int, int]:
    year, week = code.split("-W")
    start = datetime.fromisocalendar(int(year), int(week), 1).replace(tzinfo=UTC)
    return int(start.timestamp()), int((start + timedelta(days=7)).timestamp())


def _since(window: str) -> int:
    span = WINDOWS.get(window, 604800)
    return 0 if span is None else int(time.time()) - span


def _json(payload, status: int = 200) -> web.Response:
    return web.json_response(payload, status=status, headers=CORS, dumps=json.dumps)


def _int_arg(request, name: str, default: int, lo: int, hi: int) -> int:
    """Query params come off a public endpoint, so bad input is a 400, not a 500."""
    raw = request.query.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as e:
        raise web.HTTPBadRequest(text=f"invalid {name}", headers=CORS) from e
    return max(lo, min(value, hi))


def _cycle_arg(request) -> str:
    code = request.query.get("cycle") or _cycle_code(int(time.time()))
    try:
        _cycle_bounds(code)
    except (ValueError, TypeError) as e:
        raise web.HTTPBadRequest(text="invalid cycle", headers=CORS) from e
    return code


class Vamp(commands.Cog):
    """VAMP duel stats."""

    def __init__(self, client):
        self.client = client
        cfg = client.config.get("vamp", {})
        self.enabled = bool(cfg.get("enabled", False))
        self.key = cfg.get("key", "")
        self.port = int(cfg.get("port", 2586))
        self.relay_channel = int(cfg.get("relay_channel", 0))
        self.db_path = client.config["bot"]["bank"]
        self.site_root = Path(__file__).resolve().parent.parent / "vampsite"
        self.runner = None

        self.app = web.Application()
        api = [
            ("/api/leaderboard", self.api_leaderboard),
            ("/api/recent_duels", self.api_recent_duels),
            ("/api/top_players", self.api_top_players),
            ("/api/streaks", self.api_streaks),
            ("/api/heatmap", self.api_heatmap),
            ("/api/online_players", self.api_online_players),
            ("/api/player_search", self.api_player_search),
            ("/api/versus", self.api_versus),
            ("/api/cycles", self.api_cycles),
            ("/api/cycle_status", self.api_cycle_status),
            ("/api/live_insights", self.api_live_insights),
        ]
        for path, handler in api:
            self.app.router.add_get(path, handler)
            self.app.router.add_route("OPTIONS", path, self.handle_options)
        self.app.router.add_post("/vamp", self.ingest)
        self.app.router.add_route("OPTIONS", "/vamp", self.handle_options)
        if self.site_root.is_dir():
            self.app.router.add_static("/static/", self.site_root, name="static")
            self.app.router.add_get("/", self.serve_index)

    # ---------------------------------------------------------------- plumbing

    async def handle_options(self, request):
        return web.Response(text="OK", headers=CORS)

    async def serve_index(self, request):
        return web.FileResponse(self.site_root / "index.html")

    async def connect(self):
        return aiosqlite.connect(self.db_path, timeout=10)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.enabled:
            print("VAMP disabled (no [vamp] section in config.toml), skipping")
            return
        if self.runner is not None:
            return
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            await db.executescript(SCHEMA)
            await db.commit()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        await web.TCPSite(self.runner, "0.0.0.0", self.port).start()
        print(f"VAMP ready on :{self.port}")

    async def cog_unload(self):
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None

    # ----------------------------------------------------------------- ingest

    async def ingest(self, request):
        if request.headers.get("authentication") != self.key or not self.key:
            return web.Response(status=401, text="Bad auth", headers=CORS)
        try:
            data = await request.json()
        except (json.JSONDecodeError, ValueError):
            return web.Response(status=400, text="Bad JSON", headers=CORS)

        event = data.get("event")
        handlers = {
            "duel": self.on_duel,
            "status": self.on_status,
            "handicap": self.on_handicap,
            "redact": self.on_redact,
            "test": self.on_test,
        }
        handler = handlers.get(event)
        if handler is None:
            return web.Response(status=400, text=f"Unknown event {event!r}", headers=CORS)
        try:
            await handler(data)
        except (KeyError, TypeError, ValueError) as e:
            print(f"VAMP: malformed {event} payload {data}: {e}")
            return web.Response(status=400, text="Malformed payload", headers=CORS)
        return _json({"ok": True})

    async def on_duel(self, data):
        w, s = data["winner"], data["loser"]
        now = int(time.time())
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            await db.execute(
                "INSERT INTO vamp_duels (ts, server, winner_uid, winner_name, winner_acc,"
                " winner_hp, winner_handicap, loser_uid, loser_name, loser_acc,"
                " loser_handicap, duration) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    now,
                    data.get("server_identifier", "vamp"),
                    str(w["uid"]),
                    w.get("name", "?"),
                    float(w.get("acc", 0)),
                    int(w.get("hp", 0)),
                    float(w.get("handicap", 1.0)),
                    str(s["uid"]),
                    s.get("name", "?"),
                    float(s.get("acc", 0)),
                    float(s.get("handicap", 1.0)),
                    float(data.get("duration", 0)),
                ),
            )
            for p in (w, s):
                await db.execute(
                    "INSERT INTO vamp_players (uid, name, last_seen) VALUES (?,?,?)"
                    " ON CONFLICT(uid) DO UPDATE SET name=excluded.name, last_seen=excluded.last_seen",
                    (str(p["uid"]), p.get("name", "?"), now),
                )
            await db.commit()
        # The duel is already saved; a Discord failure must not tell the mod otherwise.
        try:
            await self.announce_duel(w, s, float(data.get("duration", 0)))
        except discord.DiscordException as e:
            print(f"VAMP: duel saved but announce failed: {e}")

    async def on_status(self, data):
        now = int(time.time())
        online = 1 if data.get("status") == "online" else 0
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            await db.execute(
                "INSERT INTO vamp_players (uid, name, online, last_seen) VALUES (?,?,?,?)"
                " ON CONFLICT(uid) DO UPDATE SET online=excluded.online,"
                " last_seen=excluded.last_seen, name=COALESCE(excluded.name, vamp_players.name)",
                (str(data["uid"]), data.get("name"), online, now),
            )
            await db.commit()

    async def on_handicap(self, data):
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            await db.execute(
                "INSERT INTO vamp_players (uid, name, handicap, last_seen) VALUES (?,?,?,?)"
                " ON CONFLICT(uid) DO UPDATE SET handicap=excluded.handicap,"
                " name=COALESCE(excluded.name, vamp_players.name)",
                (str(data["uid"]), data.get("name"), float(data["handicap"]), int(time.time())),
            )
            await db.commit()

    async def on_redact(self, data):
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            await db.execute(
                "INSERT INTO vamp_players (uid, redaction) VALUES (?,?)"
                " ON CONFLICT(uid) DO UPDATE SET redaction=excluded.redaction",
                (str(data["uid"]), int(data["level"])),
            )
            await db.commit()

    async def on_test(self, data):
        print(f"VAMP: test event from {data.get('tester')}")

    async def announce_duel(self, winner, loser, duration):
        if not self.relay_channel:
            return
        channel = self.client.get_channel(self.relay_channel)
        if channel is None:
            return
        embed = discord.Embed(color=0xEA6A0F, timestamp=datetime.now(UTC))
        embed.add_field(
            name="VICTOR",
            value=f"**{discord.utils.escape_markdown(str(winner.get('name', '?')))}**\n"
            f"`{float(winner.get('acc', 0)):.1f}%` acc · `{int(winner.get('hp', 0))}` hp",
        )
        embed.add_field(
            name="VICTIM",
            value=f"{discord.utils.escape_markdown(str(loser.get('name', '?')))}\n"
            f"`{float(loser.get('acc', 0)):.1f}%` acc",
        )
        embed.set_footer(text=f"{duration:.1f}s")
        await channel.send(embed=embed)

    # -------------------------------------------------------------------- api

    async def api_leaderboard(self, request):
        window = request.query.get("window", "7d")
        sort = request.query.get("sort", "wins")
        search = request.query.get("search", "").strip()
        if sort not in SORTS:
            return web.Response(status=400, text="invalid sort", headers=CORS)
        rows = await self.standings(_since(window), search)
        key = {
            "wins": lambda r: (r["wins"], r["winrate"]),
            "losses": lambda r: r["losses"],
            "winrate": lambda r: (r["winrate"], r["duels"]),
            "duels": lambda r: r["duels"],
            "acc": lambda r: r["acc"],
            "streak": lambda r: r["streak"],
        }[sort]
        rows.sort(key=key, reverse=True)
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        return _json({"window": window, "sort": sort, "results": rows})

    async def standings(self, since: int, search: str = "", until: int | None = None):
        """Per-player W/L/accuracy/streak over a time range, computed from duels."""
        clause = "WHERE ts >= ?"
        params: list = [since]
        if until is not None:
            clause += " AND ts < ?"
            params.append(until)
        agg: dict[str, dict] = {}

        def slot(uid, name):
            r = agg.setdefault(
                uid,
                {"uid": uid, "name": name, "wins": 0, "losses": 0, "acc_sum": 0.0,
                 "duels": 0, "streak": 0, "handicap": 1.0},
            )
            r["name"] = name or r["name"]
            return r

        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            async with db.execute(
                "SELECT winner_uid, winner_name, winner_acc, loser_uid, loser_name,"
                f" loser_acc FROM vamp_duels {clause} ORDER BY ts ASC",
                params,
            ) as cur:
                async for wu, wn, wa, lu, ln, la in cur:
                    w = slot(wu, wn)
                    w["wins"] += 1
                    w["duels"] += 1
                    w["acc_sum"] += wa
                    w["streak"] = w["streak"] + 1 if w["streak"] >= 0 else 1
                    lo = slot(lu, ln)
                    lo["losses"] += 1
                    lo["duels"] += 1
                    lo["acc_sum"] += la
                    lo["streak"] = lo["streak"] - 1 if lo["streak"] <= 0 else -1
            async with db.execute("SELECT uid, handicap FROM vamp_players") as cur:
                async for uid, hc in cur:
                    if uid in agg:
                        agg[uid]["handicap"] = hc

        out = []
        needle = search.lower()
        for r in agg.values():
            if needle and needle not in (r["name"] or "").lower():
                continue
            r["acc"] = round(r.pop("acc_sum") / r["duels"], 1) if r["duels"] else 0.0
            r["winrate"] = round(r["wins"] / r["duels"] * 100, 1) if r["duels"] else 0.0
            out.append(r)
        return out

    async def api_recent_duels(self, request):
        limit = _int_arg(request, "limit", 25, 1, 200)
        window = request.query.get("window", "7d")
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM vamp_duels WHERE ts >= ? ORDER BY ts DESC, id DESC LIMIT ?",
                (_since(window), limit),
            ) as cur:
                rows = [dict(r) for r in await cur.fetchall()]
        return _json({"window": window, "results": rows})

    async def api_top_players(self, request):
        limit = _int_arg(request, "limit", 5, 1, 50)
        cycle = _cycle_arg(request)
        start, end = _cycle_bounds(cycle)
        rows = await self.standings(start, until=end)
        rows.sort(key=lambda r: (r["wins"], r["winrate"]), reverse=True)
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        return _json({"cycle": cycle, "results": rows[:limit]})

    async def api_streaks(self, request):
        window = request.query.get("window", "7d")
        rows = await self.standings(_since(window))
        hot = sorted((r for r in rows if r["streak"] > 0), key=lambda r: -r["streak"])
        cold = sorted((r for r in rows if r["streak"] < 0), key=lambda r: r["streak"])
        return _json({"window": window, "hot": hot[:10], "cold": cold[:10]})

    async def api_heatmap(self, request):
        window = request.query.get("window", "7d")
        buckets = [0] * 24
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            async with db.execute(
                "SELECT ts FROM vamp_duels WHERE ts >= ?", (_since(window),)
            ) as cur:
                async for (ts,) in cur:
                    buckets[datetime.fromtimestamp(ts, UTC).hour] += 1
        return _json({"window": window, "hours": list(range(24)), "counts": buckets})

    async def api_online_players(self, request):
        cutoff = int(time.time()) - 3600
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT uid, name, handicap, last_seen FROM vamp_players"
                " WHERE online = 1 AND last_seen >= ? ORDER BY name COLLATE NOCASE",
                (cutoff,),
            ) as cur:
                rows = [dict(r) for r in await cur.fetchall()]
        return _json({"count": len(rows), "results": rows})

    async def api_player_search(self, request):
        q = request.query.get("q", "").strip()
        limit = _int_arg(request, "limit", 6, 1, 25)
        if not q:
            return _json({"results": []})
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT uid, name FROM vamp_players WHERE name LIKE ?"
                " ORDER BY name COLLATE NOCASE LIMIT ?",
                (f"%{q}%", limit),
            ) as cur:
                rows = [dict(r) for r in await cur.fetchall()]
        return _json({"results": rows})

    async def api_versus(self, request):
        a = request.query.get("a", "").strip()
        b = request.query.get("b", "").strip()
        if not a or not b:
            return web.Response(status=400, text="need a and b", headers=CORS)
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM vamp_duels WHERE (winner_name = ? AND loser_name = ?)"
                " OR (winner_name = ? AND loser_name = ?) ORDER BY ts DESC LIMIT 100",
                (a, b, b, a),
            ) as cur:
                rows = [dict(r) for r in await cur.fetchall()]
        a_wins = sum(1 for r in rows if r["winner_name"] == a)
        return _json(
            {
                "a": a,
                "b": b,
                "a_wins": a_wins,
                "b_wins": len(rows) - a_wins,
                "total": len(rows),
                "duels": rows[:25],
            }
        )

    async def api_cycles(self, request):
        async with aiosqlite.connect(self.db_path, timeout=10) as db:
            async with db.execute("SELECT MIN(ts), MAX(ts) FROM vamp_duels") as cur:
                lo, hi = await cur.fetchone()
        if lo is None:
            return _json({"results": [_cycle_code(int(time.time()))]})
        seen, t = [], lo
        while t <= hi:
            code = _cycle_code(t)
            if code not in seen:
                seen.append(code)
            t += 604800
        current = _cycle_code(int(time.time()))
        if current not in seen:
            seen.append(current)
        return _json({"results": list(reversed(seen))})

    async def api_cycle_status(self, request):
        code = _cycle_arg(request)
        start, end = _cycle_bounds(code)
        return _json(
            {
                "cycle": code,
                "start": start,
                "end": end,
                "seconds_remaining": max(0, end - int(time.time())),
                "active": start <= int(time.time()) < end,
            }
        )

    async def api_live_insights(self, request):
        limit = _int_arg(request, "limit", 5, 1, 25)
        min_duels = _int_arg(request, "min_duels", 1, 0, 10000)
        window = request.query.get("window", "cycle")
        if window == "cycle":
            start, end = _cycle_bounds(_cycle_code(int(time.time())))
            rows = await self.standings(start, until=end)
        else:
            rows = await self.standings(_since(window))
        rows = [r for r in rows if r["duels"] >= min_duels]
        eliminators = sorted(rows, key=lambda r: -r["wins"])[:limit]
        eliminated = sorted(rows, key=lambda r: -r["losses"])[:limit]
        momentum = sorted(rows, key=lambda r: -r["streak"])[:limit]
        return _json(
            {
                "window": window,
                "top_eliminators": eliminators,
                "most_eliminated": eliminated,
                "recent_gains": momentum,
            }
        )

    # --------------------------------------------------------------- commands

    @commands.command()
    async def vamp(self, ctx, *, player: str | None = None):
        """VAMP standings, or one player's record."""
        rows = await self.standings(_since("all"), player or "")
        if not rows:
            await ctx.reply("No VAMP duels recorded yet.")
            return
        rows.sort(key=lambda r: (r["wins"], r["winrate"]), reverse=True)
        embed = discord.Embed(title="VAMP // STANDINGS", color=0xEA6A0F)
        for i, r in enumerate(rows[:10], 1):
            embed.add_field(
                name=f"{i}. {r['name']}",
                value=f"`{r['wins']}W {r['losses']}L` · {r['winrate']}% · acc {r['acc']}%",
                inline=False,
            )
        await ctx.reply(embed=embed)


async def setup(client):
    await client.add_cog(Vamp(client))
