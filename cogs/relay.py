import asyncio
import json

# import cogs.utils.crashes as crashes
import re
import sys
import time
import traceback
from datetime import datetime, timedelta

import aiosqlite
import asyncpg
import config
import discord
import requests
import humanize
import io
import math
from PIL import Image
from aiohttp import ClientSession, web
from discord.ext import commands, tasks

import cogs.utils.utils as utils  # this is stupid


class Relay(commands.Cog):
    """Relay stuff."""

    def __init__(self, client):
        self.client = client
        self.client.current_log = None
        self.client.old = 0
        self.client.auth = {}
        errors = [
            asyncpg.PostgresConnectionError,
            discord.errors.NotFound,
            discord.errors.HTTPException,
            requests.exceptions.ConnectionError,
            AttributeError,
            json.decoder.JSONDecodeError,
        ]
        if not config.debug:
            for error in errors:
                self.update_stats.add_exception_type(error)
        self.client.playing = {}
        self.client.lazy_playing = {}
        self.client.online = {}
        for s in config.servers + config.tournament_servers:
            self.client.playing[s.name] = []
            self.client.lazy_playing[s.name] = []
            self.client.online[s.name] = False
        self.update_stats.start()
        self.app = web.Application()
        self.app.router.add_post("/post", self.recieve_relay_info)
        self.app.router.add_get("/get", self.tone_info)
        self.app.router.add_post("/leaderboard", self.get_leaderboard)
        self.app.router.add_get("/leaderboard-info", self.get_leaderboard_info)
        self.app.router.add_get("/is-whitelisted", self.is_whitelisted)
        self.app.router.add_get("/is-banned", self.is_banned)
        self.app.router.add_get("/stats", self.get_stats)
        self.app.router.add_get("/server-scoreboard", self.get_server_scoreboard)
        self.app.router.add_get("/server-history", self.get_scoreboard_history)
        self.app.router.add_get("/tournament-loadout", self.get_tournament_loadout)
        self.app.router.add_route("OPTIONS", "/leaderboard", self.handle_options)
        self.app.router.add_route("OPTIONS", "/leaderboard-info", self.handle_options)
        self.app.router.add_route("OPTIONS", "/get", self.handle_options)
        self.app.router.add_route("OPTIONS", "/post", self.handle_options)
        self.app.router.add_route("OPTIONS", "/is-whitelisted", self.handle_options)
        self.app.router.add_route("OPTIONS", "/stats", self.handle_options)
        self.app.router.add_route("OPTIONS", "/tournament-loadout", self.handle_options)
        self.app.router.add_route("OPTIONS", "/server-scoreboard", self.handle_options)
        self.app.router.add_route("OPTIONS", "/server-history", self.handle_options)
        self.runner = web.AppRunner(self.app)
        self.message_queue = {}
        for s in config.servers:
            self.message_queue[s.name] = ""
        self.client.tournament_loadout = {}
        self.client.tournament_should_track_kills = True
        self.client.tournament_should_sleep = True

    async def get_tournament_loadout(self, request):
        # with open("tourney/round1.json", "r") as f:
        #     return web.Response(text=f.read())
        return web.Response(text=json.dumps(self.client.tournament_loadout))

    async def add_to_message_queue(self, server, message):
        self.message_queue[server] += message + "\n"
        if len(self.message_queue[server]) > 1000:
            server = await utils.get_server(server)
            channel = self.client.get_channel(server.relay)
            await channel.send(self.message_queue[server])
            self.message_queue[server] = ""

    @tasks.loop(seconds=10)
    async def post_relay(self):
        for server in config.servers:
            if self.message_queue[server.name] != "":
                channel = self.client.get_channel(server.relay)
                await channel.send(self.message_queue[server])
                self.message_queue[server] = ""

    def cog_unload(self):
        self.update_stats.cancel()
        # self.lazy_playing_update.cancel()

    async def make_mentionable(self):
        await self.client.get_guild(929895874799226881).get_role(
            1000617424934154260
        ).edit(mentionable=True)

    async def get_leaderboard(self, request):
        corsheaders = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        try:
            data = await request.json()
        except json.decoder.JSONDecodeError:
            return web.Response(
                status=400, text="bad json dumbass", headers=corsheaders
            )
        server = data["server"]
        server = await utils.get_server(server)
        if server is None:
            return web.Response(
                status=404, text="server not found", headers=corsheaders
            )
        page = data["page"]
        if not isinstance(page, int):
            return web.Response(
                status=400, text="page must be an integer", headers=corsheaders
            )
        if page < 0:
            return web.Response(
                status=400, text="page must be greater than 0", headers=corsheaders
            )
        if server.name == "infection":
            valid_stats = [
                "survivor kills",
                "survivor deaths",
                "infected kills",
                "infected deaths",
                "playtime",
                "killstreak",
            ]
        else:
            valid_stats = ["kills", "playtime", "deaths", "killstreak"]
        stat = data["stat"]
        if stat not in valid_stats:
            return web.Response(status=400, text="invalid stat", headers=corsheaders)
        async with aiosqlite.connect(config.bank) as db:
            if stat == "kills":
                async with db.execute(
                    f"SELECT name, killsimc, killsmilitia FROM {server.name} ORDER BY killsimc + killsmilitia DESC LIMIT 10 OFFSET 10*{page-1}"
                ) as cursor:
                    fetched = await cursor.fetchall()
                    result = {"results": []}
                    for row in fetched:
                        result["results"].append(
                            {"name": row[0], "stat": row[1] + row[2]}
                        )
            elif stat == "deaths":
                async with db.execute(
                    f"SELECT name, deathsimc, deathsmilitia FROM {server.name} ORDER BY deathsimc + deathsmilitia DESC LIMIT 10 OFFSET 10*{page-1}"
                ) as cursor:
                    fetched = await cursor.fetchall()
                    result = {"results": []}
                    for row in fetched:
                        result["results"].append(
                            {"name": row[0], "stat": row[1] + row[2]}
                        )
            elif stat == "survivor kills":
                async with db.execute(
                    f"SELECT name, killsmilitia FROM {server.name} ORDER BY killsmilitia DESC LIMIT 10 OFFSET 10*{page-1}"
                ) as cursor:
                    fetched = await cursor.fetchall()
                    result = {"results": []}
                    for row in fetched:
                        result["results"].append({"name": row[0], "stat": row[1]})
            elif stat == "survivor deaths":
                async with db.execute(
                    f"SELECT name, deathsmilitia FROM {server.name} ORDER BY deathsmilitia DESC LIMIT 10 OFFSET 10*{page-1}"
                ) as cursor:
                    fetched = await cursor.fetchall()
                    result = {"results": []}
                    for row in fetched:
                        result["results"].append({"name": row[0], "stat": row[1]})
            elif stat == "infected kills":
                async with db.execute(
                    f"SELECT name, killsimc FROM {server.name} ORDER BY killsimc DESC LIMIT 10 OFFSET 10*{page-1}"
                ) as cursor:
                    fetched = await cursor.fetchall()
                    result = {"results": []}
                    for row in fetched:
                        result["results"].append({"name": row[0], "stat": row[1]})
            elif stat == "infected deaths":
                async with db.execute(
                    f"SELECT name, deathsimc FROM {server.name} ORDER BY deathsimc DESC LIMIT 10 OFFSET 10*{page-1}"
                ) as cursor:
                    fetched = await cursor.fetchall()
                    result = {"results": []}
                    for row in fetched:
                        result["results"].append({"name": row[0], "stat": row[1]})
            elif stat == "playtime":
                async with db.execute(
                    f"SELECT name, playtime FROM {server.name} ORDER BY playtime DESC LIMIT 10 OFFSET 10*{page-1}"
                ) as cursor:
                    fetched = await cursor.fetchall()
                    result = {"results": []}
                    for row in fetched:
                        result["results"].append(
                            {
                                "name": row[0],
                                "stat": await utils.human_time_duration(row[1]),
                            }
                        )
            else:
                async with db.execute(
                    f"SELECT name, {stat} FROM {server.name} ORDER BY {stat} DESC LIMIT 10 OFFSET 10*{page-1}"
                ) as cursor:
                    fetched = await cursor.fetchall()
                    result = {"results": []}
                    for row in fetched:
                        result["results"].append({"name": row[0], "stat": row[1]})
        return web.json_response(
            text=json.dumps(result), status=200, headers=corsheaders
        )

    async def get_leaderboard_info(self, request):
        corsheaders = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        result = {"servers": {}}
        async with aiosqlite.connect(config.bank) as db:
            # get amount of rows in all servers
            for server in config.servers:
                async with db.execute(f"SELECT COUNT(*) FROM {server.name}") as cursor:
                    response = await cursor.fetchone()
                    if server.name == "infection":
                        result["servers"][server.name] = {
                            "rows": response[0],
                            "stats": [
                                "survivor kills",
                                "infected kills",
                                "survivor deaths",
                                "infected deaths",
                                "playtime",
                                "killstreak",
                            ],
                        }
                    else:
                        result["servers"][server.name] = {
                            "rows": response[0],
                            "stats": ["kills", "deaths", "playtime", "killstreak"],
                        }
        return web.json_response(
            text=json.dumps(result), status=200, headers=corsheaders
        )

    async def is_whitelisted(self, request):
        # get uid from request
        uid = request.query.get("uid")

        # check if uid is whitelisted
        async with aiosqlite.connect(config.bank) as db:
            async with db.execute("SELECT uid FROM whitelist") as cursor:
                fetched = await cursor.fetchall()
                for row in fetched:
                    if str(row[0]) == str(uid):
                        return web.json_response(
                            text=json.dumps({"whitelisted": True}), status=200
                        )

        return web.json_response(text=json.dumps({"whitelisted": False}), status=200)

    async def is_banned(self, request):
        # get uid from request
        uid = request.query.get("uid")

        # check if uid is banned
        async with aiosqlite.connect(config.bank) as db:
            async with db.execute("SELECT * FROM banned WHERE uid=?", (uid,)) as cursor:
                # uid, reason, expires (datetime object)
                fetched = await cursor.fetchall()
                if fetched:
                    for row in fetched:
                        reason = row[2] if row[2] else "Not listed"
                        if row[3]:
                            expire_date = datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S")
                            now = datetime.now()
                            if expire_date < now:
                                continue
                            expires = (
                                humanize.naturaldate(expire_date)
                                + ", "
                                + humanize.naturaltime(expire_date)
                            )
                        else:
                            expires = "Never"
                        ban_message = f"You have been banned from all awesome servers.\nReason: {reason}\nExpires: {expires}\nPlease join discord.gg/awesometf to appeal"
                        return web.json_response(
                            text=json.dumps(
                                {"banned": "true", "ban_message": ban_message}
                            ),
                            status=200,
                        )

        return web.json_response(
            text=json.dumps({"banned": "false", "ban_message": ""}), status=200
        )

    async def handle_options(self, request):
        # do nothing, just respond with OK
        return web.Response(
            text="Options received",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if not message.content:
            return
        if not message.guild:
            return
        for role in message.role_mentions:
            if role.id == 1000617424934154260:
                await role.edit(mentionable=False)
                await self.discord_log(
                    f"looking to play is now unmentionable due to {message.author.name} {message.jump_url}"
                )
                await asyncio.sleep(3600)
                await role.edit(mentionable=True)
                await self.discord_log("looking to play is now mentionable")
        for s in config.servers:
            if message.channel.id == s.relay:

                if message.attachments:
                    async with io.BytesIO() as f:
                        f = await message.attachments[0].read(f)
                        f.seek(0)
                        f = Image.open(f)
                        f.convert("RGB")
                        resize_ratio = min(37 / f.width, 11 / f.height)
                        f = f.resize(
                            (
                                math.floor(f.width * resize_ratio),
                                math.floor(f.height * resize_ratio),
                            )
                        )
                        pixels = []
                        for x in range(f.width):
                            for y in range(f.height):
                                r, g, b = f.getpixel((x, y))
                                pixels.append(f"{r},{g},{b}")
                        await s.send_command(
                            f"sendimage {message.author.name} {f.width} {" ".join(pixels)}"
                        )
                        await self.discord_log(
                            f"from {message.author.name}: `sendimage {message.author.name} {f.width}`"
                        )
                        return

                remove_chars = "`;&|'\"\\"
                translation_table = str.maketrans("", "", remove_chars)
                cleaned_message = message.content.translate(translation_table)
                cleaned_message.replace("\n", " ").strip()
                cleaned_message = re.sub(
                    r"\s+", " ", cleaned_message
                )  # replace multiple spaces with a single space
                cleaned_message.strip()  # for good measure

                await s.send_command(
                    f"serversay {message.author.name} {cleaned_message}"
                )
                await self.discord_log(
                    f"from {message.author.name}: `serversay {message.author.name} {cleaned_message}`"
                )

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()
        await self.make_mentionable()
        print("Relay is ready. Starting web server...")
        await self.start_web_server()
        self.client.loop.create_task(self.track_servers())

    async def create_server_tracker_db(self):
        async with aiosqlite.connect(config.bank) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS server_tracker(num INTEGER PRIMARY KEY AUTOINCREMENT, server_name TEXT, score INTEGER)"
            )
            await db.execute(
                "CREATE TABLE IF NOT EXISTS players_tracker(num INTEGER PRIMARY KEY AUTOINCREMENT, server_name TEXT, playercount INTEGER, timestamp INTEGER)"
            )
            await db.commit()

    async def seconds_until_next_interval(wait_time):
        """Calculate seconds until the next exact interval (1:05, 1:10, etc.)."""
        now = datetime.now()
        next_minute = (now.minute // wait_time + 1) * wait_time  # Next multiple of 5
        if next_minute >= 60:
            next_minute = 0
            next_hour = now.hour + 1
        else:
            next_hour = now.hour

        next_run = now.replace(
            hour=next_hour, minute=next_minute, second=0, microsecond=0
        )
        if next_run <= now:
            next_run += timedelta(hours=1)

        return (next_run - now).total_seconds()

    async def track_servers(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            wait_time = await self.seconds_until_next_interval(5)
            print(f"Next server check in {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)
            await self.create_server_tracker_db()
            try:
                async with ClientSession() as session:
                    async with session.get(config.masterurl) as response:
                        servers = await response.json()
            except Exception as e:
                print("Error fetching servers " + e)
                await asyncio.sleep(10)
                continue
            async with aiosqlite.connect(config.bank) as db:
                async with db.cursor() as cursor:
                    for server in servers:
                        await cursor.execute(
                            "SELECT * FROM server_tracker WHERE server_name = ?",
                            (server["name"],),
                        )
                        result = await cursor.fetchone()
                        if result:
                            old_score = result[2]
                            await cursor.execute(
                                "UPDATE server_tracker SET score = ? WHERE server_name = ?",
                                (server["playerCount"] + old_score, server["name"]),
                            )
                        else:
                            await cursor.execute(
                                "INSERT INTO server_tracker (server_name, score) VALUES (?, ?)",
                                (server["name"], server["playerCount"]),
                            )
                        await cursor.execute(
                            "INSERT INTO players_tracker (server_name, playercount, timestamp) VALUES (?, ?, ?)",
                            (server["name"], server["playerCount"], int(time.time())),
                        )
                await db.commit()

    @commands.command()
    @commands.is_owner()
    async def resettracker(self, ctx):
        await ctx.send(
            "YOU ARE ABOUT TO RESET THE SERVER TRACKER AND ALL OF ITS HISTORY, ARE YOU SURE?"
        )
        msg = await self.client.wait_for(
            "message", check=lambda m: m.author == ctx.author
        )
        if msg.content.lower() == "yes":
            async with aiosqlite.connect(config.bank) as db:
                await db.execute("DROP TABLE server_tracker")
                await db.execute("DROP TABLE players_tracker")
                await db.commit()
            await self.create_server_tracker_db()
            await ctx.send("done")
        else:
            await ctx.send("cancelled")

    @commands.command()
    @commands.is_owner()
    async def scoretransfer(self, ctx, old, new):
        async with aiosqlite.connect(config.bank) as db:
            async with db.cursor() as cursor:
                await cursor.execute(
                    "SELECT score FROM server_tracker WHERE server_name = ?", (old,)
                )
                old_score = await cursor.fetchone()
                if not old_score:
                    await ctx.send(f"Server `{old}` not found.")
                    return
                await cursor.execute(
                    "SELECT score FROM server_tracker WHERE server_name = ?", (new,)
                )
                new_exists = await cursor.fetchone()
                if not new_exists:
                    await ctx.send(f"Server `{new}` not found.")
                    return
                await cursor.execute(
                    "UPDATE server_tracker SET score = score + ? WHERE server_name = ?",
                    (old_score[0], new),
                )
                await cursor.execute(
                    "DELETE FROM server_tracker WHERE server_name = ?", (old,)
                )
                await cursor.execute(
                    "UPDATE players_tracker SET server_name = ? WHERE server_name = ?",
                    (new, old),
                )
                await db.commit()
            await ctx.send(
                f"Transferred score ({old_score[0]}) from `{old}` to `{new}` successfully."
            )

    async def get_server_scoreboard(self, request):
        corsheaders = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        async with aiosqlite.connect(config.bank) as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT * FROM server_tracker ORDER BY score DESC")
            rows = await cursor.fetchall()
            result = {"rows": len(rows), "servers": []}
            for row in rows:
                result["servers"].append({"name": row[1], "score": row[2]})
        return web.json_response(result, headers=corsheaders, status=200)

    async def get_scoreboard_history(self, request):
        corsheaders = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        before = request.query.get("before")
        after = request.query.get("after")
        name_filter = request.query.get("filter")
        key = request.query.get("key")
        authorized = False
        if key:
            if key in config.keys:
                authorized = True
        if not before:
            before = int(time.time())
        if not after:
            after = 0
        if before - after > 60 * 60 * 24 * 30 and not name_filter and not authorized:
            return web.Response(
                status=403,
                text="Time range too large, provide a filter or reduce range to 30 days or less.",
                headers=corsheaders,
            )
        if after > before:
            return web.Response(
                status=400,
                text="After time is greater than before time. You likely want to swap them.",
                headers=corsheaders,
            )
        async with aiosqlite.connect(config.bank) as db:
            async with db.cursor() as cursor:
                servers = []
                await cursor.execute("SELECT server_name FROM server_tracker")
                server_names = await cursor.fetchall()
                for name in server_names:
                    if name_filter:
                        if name_filter in name[0]:
                            servers.append(name[0])
                    else:
                        servers.append(name[0])
                if name_filter:
                    if len(servers) == 0:
                        return web.Response(
                            status=404,
                            headers=corsheaders,
                            text="No servers found matching filter",
                        )
                    if len(servers) > 10:
                        return web.Response(
                            status=403,
                            headers=corsheaders,
                            text="Too many servers found matching filter, max is 10",
                        )
                result = {"servers": {}}
                for server in servers:
                    await cursor.execute(
                        "SELECT * FROM players_tracker WHERE server_name = ? AND timestamp < ? AND timestamp > ? ORDER BY timestamp DESC",
                        (server, before, after),
                    )
                    rows = await cursor.fetchall()
                    result["servers"][server] = {}
                    for row in rows:
                        result["servers"][server][row[3]] = row[2]

        return web.json_response(result, headers=corsheaders, status=200)

    async def start_web_server(self):
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", 2585)
        await site.start()

    # events
    @tasks.loop(seconds=30)
    async def update_stats(self):
        channel = self.client.get_channel(config.stats_channel)
        fetch_message = None
        async for message in channel.history(limit=200):
            if message.author.id == self.client.user.id:
                fetch_message = message
                break

        if fetch_message is not None:
            message_id = fetch_message.id
            msg = await channel.fetch_message(message_id)
        else:
            msg = None

        async with ClientSession() as session:
            async with session.get(config.masterurl) as response:
                servers = await response.json()

        query_results = []
        total_players = 0

        for server in servers:
            total_players += server["playerCount"]

        for s in config.servers + config.tournament_servers:
            for server in servers:
                if s.display_name in server["name"]:
                    query_results.append(server)
                    if not self.client.online[s.name]:
                        self.client.online[s.name] = True
                        adminrelay = self.client.get_channel(config.admin_relay)
                        await adminrelay.send(f"{s.display_name} just came online")
                    break
            else:
                if self.client.online[s.name]:
                    self.client.online[s.name] = False
                    adminrelay = self.client.get_channel(config.admin_relay)
                    await adminrelay.send(
                        f"{s.display_name} just went offline, did it crash?"
                    )

        if query_results:
            sdescription = f"Total Northstar Players: {total_players}"
        else:
            sdescription = "All servers down. Uh oh."

        embed = discord.Embed(
            title="Server Stats",
            description=sdescription,
            color=discord.Color.blue(),
        )

        table = []
        for server in query_results:
            table.append(
                [
                    server["name"],
                    str(server["playerCount"]) + "/" + str(server["maxPlayers"]),
                    server["playlist"],
                    server["map"],
                ]
            )
            if table:
                embed.add_field(
                    name="Name:",
                    value=server["name"],
                    inline=False,
                )
                embed.add_field(
                    name="Playercount:",
                    value=str(server["playerCount"]) + "/" + str(server["maxPlayers"]),
                    inline=True,
                )
                embed.add_field(name="Gamemode:", value=server["playlist"], inline=True)
                embed.add_field(name="Map:", value=server["map"], inline=True)
            embed.set_footer(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        if msg is None:
            await channel.send(embed=embed)
        else:
            await msg.edit(embed=embed)

    async def register_server(self, server_identifier):
        async with aiosqlite.connect(config.bank) as db:
            await db.execute(
                f"""CREATE TABLE IF NOT EXISTS {server_identifier}(
num INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT NOT NULL,
uid INT NOT NULL,
killsimc INT NOT NULL,
killsmilitia INT NOT NULL,
deathsimc INT NOT NULL,
deathsmilitia INT NOT NULL,
first_join TEXT NOT NULL,
last_join TEXT NOT NULL,
playtime INT NOT NULL,
killstreak INT NOT NULL,
gamesplayed INT NOT NULL
)
"""
            )
            await db.execute(
                f"""CREATE TABLE IF NOT EXISTS {server_identifier}_kill_log(
num INTEGER PRIMARY KEY AUTOINCREMENT,
killer INT NOT NULL,
action INT NOT NULL,
victim INT NOT NULL,
timestamp INT NOT NULL
)
"""
            )
            await db.execute(
                """CREATE TABLE IF NOT EXISTS whitelist(
num INTEGER PRIMARY KEY AUTOINCREMENT,
uid INT NOT NULL
)
"""
            )
            await db.execute(
                """CREATE TABLE IF NOT EXISTS banned(
num INTEGER PRIMARY KEY AUTOINCREMENT,
uid INT NOT NULL,
reason TEXT,
expire_date TEXT
)
"""
            )

            await db.commit()

    async def tone_info(self, request):
        player = request.query.get("player")
        if player is None:
            return web.Response(status=400, text="No player")
        try:
            player = int(player)
        except ValueError:
            return web.Response(status=400, text="No player")
        kills = 0
        deaths = 0
        async with aiosqlite.connect(config.bank) as db:
            cursor = await db.cursor()
            for server in config.servers:
                if server.name == "infection":
                    continue
                await cursor.execute(
                    f"SELECT * FROM {server.name} WHERE uid = ?", (player,)
                )
                result = await cursor.fetchone()
                if result is not None:
                    results = list(result)
                    kills += results[3] + results[4]
                    deaths += results[5] + results[6]
                    username = results[1]
                else:
                    return web.Response(status=404, text="Player not found")
        return web.json_response(
            text=json.dumps({"user": username, "kills": kills, "deaths": deaths})
        )

    async def get_stats(self, request):
        player = request.query.get("player")
        server = request.query.get("server")
        if player is None:
            return web.Response(status=400, text="No player")
        player = int(player)
        kills = 0
        deaths = 1
        async with aiosqlite.connect(config.bank) as db:
            cursor = await db.cursor()
            await cursor.execute(f"SELECT * FROM {server} WHERE name = ?", (player,))
            results = await cursor.fetchone()
            kills = results[3] + results[4]
            deaths = results[5] + results[6]
            playtime = results[9]
            killstreak = results[10]
            username = player
            return web.json_response(
                text=json.dumps(
                    {
                        "user": username,
                        "kills": kills,
                        "deaths": deaths,
                        "playtime": playtime,
                        "killstreak": killstreak,
                    }
                )
            )

    async def recieve_relay_info(self, request):
        data = await request.text()
        done = False
        while not done:  # clean stupid ass color
            if "" in data:
                start_esc = data.find("")
                end_esc = data[start_esc:].find("m")
                data = data[:start_esc] + data[end_esc + start_esc + 1 :]
            else:
                done = True
        try:
            data = data.replace("\n", "|")
            data = json.loads(data)  # convert to fucking json
        except Exception as e:
            print("i could not convert the following line to json:")
            print(data)
            await self.discord_log(
                "i could not convert the following line to json:\n" + data
            )
            await self.discord_log(f"{e}")
            return web.Response(status=400, text="Bad JSON")
        try:  # how is json in python THIS BAD
            player = data["subject"]["name"]
            uid = data["subject"]["uid"]
            team = data["subject"]["teamId"]
        except (KeyError, TypeError):
            pass
        try:
            message = data["object"]["message"]
        except (KeyError, TypeError):
            pass
        server_identifier = data["server_identifier"]
        ip = request.headers.get("X-Forwarded-For")
        if ip:
            ip = ip.split(",")[0]
        else:
            ip = request.remote
        if not await utils.is_valid_server(server_identifier):
            print(
                f"Warning! Invalid server identifier for {server_identifier}. Provided data was {data}. IP of request was {ip}."
            )
            return web.Response(status=401, text="Bad identifier")
        auth_header = request.headers.get("authentication")
        if not await utils.check_server_auth(server_identifier, auth_header):
            print(
                f"Warning! Invalid auth header for {server_identifier}. Provided auth was {auth_header}. IP of request was {ip}."
            )
            return web.Response(status=401, text="Bad auth")
        if not await utils.check_server_ip(server_identifier, ip):
            print(f"Warning! Invalid ip for {server_identifier}. Provided ip was {ip}.")
            return web.Response(status=401, text="Bad IP")
        if await utils.is_tournament_server(server_identifier):
            await self.handle_tournament(data, server_identifier)
            return web.Response(status=200, text="OK")
        await self.register_server(server_identifier)
        try:
            custom = data["custom"]
        except (KeyError, TypeError):
            custom = False
        if custom:
            match custom:
                case "killstreak":
                    bits = data["args"].split("|")
                    attacker = bits[0]
                    kills = int(bits[1])
                    if kills == 5:
                        await self.send_relay_misc(
                            f"**<< {attacker} is on a KILLING SPREE {kills} >>**",
                            server_identifier,
                        )
                    elif kills == 10:
                        await self.send_relay_misc(
                            f"**<< {attacker} is UNSTOPPABLE {kills} >>**",
                            server_identifier,
                        )
                    elif kills == 15:
                        await self.send_relay_misc(
                            f"**<< {attacker} is on a RAMPAGE {kills} >>**",
                            server_identifier,
                        )
                    elif kills == 20:
                        await self.send_relay_misc(
                            f"**<< {attacker} is GOD-LIKE {kills} >>**",
                            server_identifier,
                        )
                    elif kills % 5 == 0 and kills < 96:
                        await self.send_relay_misc(
                            f"**<< {attacker} is still GOD-LIKE {kills} >>**",
                            server_identifier,
                        )
                    elif kills == 100:
                        await self.send_relay_misc(
                            f"**<< {attacker} is FUCKING CHEATING {kills} >>**",
                            server_identifier,
                        )
                    elif kills % 5 == 0 and int(kills) > 101:
                        await self.send_relay_misc(
                            f"**<< {attacker} is still FUCKING CHEATING {kills} >>**",
                            server_identifier,
                        )
                case "killend":
                    bits = data["args"].split("|")
                    attacker = bits[0]
                    kills = int(bits[1])
                    victim = bits[2]
                    if server_identifier != "infection":
                        await self.log_killstreak(victim, int(kills), server_identifier)
                    if kills > 9:
                        await self.send_relay_misc(
                            f"**<< {attacker} ended {victim}'s killstreak {kills} >>**",
                            server_identifier,
                        )
                case "killstreakwin":
                    bits = data["args"].split("|")
                    killer = bits[0]
                    kills = int(bits[1])
                    await self.log_killstreak(killer, int(kills), server_identifier)
                    if kills > 9:
                        await self.send_relay_misc(
                            f"**<< {killer} has ended the round with {kills} kills >>**",
                            server_identifier,
                        )
                case "command":
                    print(f"Command {data['args']}|{server_identifier}.")
                    await self.big_brother(
                        f"Command `{data['args']}|{server_identifier}`."
                    )
                case _:
                    print(f"Warning! Unknown custom message {custom}.")
        else:
            match data["verb"]:
                case "sent":
                    # if line["object"]["team_chat"] == False:
                    await self.send_relay_msg(
                        player, message, team, uid, server_identifier
                    )
                    if self.client.auth != {}:
                        try:
                            auth = int(message)
                        except ValueError:
                            auth = 0
                        if (
                            auth in self.client.auth
                            and self.client.auth[auth]["name"] == player
                        ):
                            self.client.auth[auth]["confirmed"] = True
                case "winnerDetermined":
                    await self.send_relay_misc(
                        "**The round has ended.**", server_identifier
                    )
                    await self.award_games_to_online(server_identifier)
                    await self.clear_playing(server_identifier)
                case "waitingForPlayers":
                    await self.send_relay_misc(
                        "**The game is loading.**", server_identifier
                    )
                case "playing":
                    await self.send_relay_misc(
                        "**The game has started.**", server_identifier
                    )
                case "connected":
                    await self.send_relay_misc(
                        f"**{player} just connected.**", server_identifier
                    )
                    await self.log_join(player, uid, server_identifier)
                    await self.check_for_changed_name(uid, player)
                    await self.add_playing(uid, server_identifier)
                case "respawned":
                    await self.add_playing(
                        uid, server_identifier
                    )  # sometimes connected will just not be sent
                case "disconnected":
                    await self.send_relay_misc(
                        f"**{player} just disconnected.**", server_identifier
                    )
                    await self.remove_playing(uid, server_identifier)
                case "killed":
                    victim = data["object"]["name"]
                    kteam = data["subject"]["teamId"]
                    iteam = data["object"]["teamId"]
                    await self.log_kill(data, server_identifier)
                    await self.send_relay_kill(
                        player, victim, kteam, iteam, server_identifier
                    )
                case _:
                    print("unknown verb: " + data["verb"])
        return web.Response(status=200, text="OK")

    async def handle_tournament(self, data, server_identifier):
        if data["verb"] == "killed":
            killer_uid = data["subject"]["uid"]
            victim_uid = data["object"]["uid"]
            print(f"killer uid: {killer_uid}")
        else:
            print("unknown tournament verb: " + data["verb"])
            return

        if self.client.tournament_should_track_kills:
            for key, _ in self.client.tournament_players.items():
                if str(key) == str(killer_uid) and str(key) != str(victim_uid):
                    print("found killer, adding to kill count")
                    self.client.tournament_players[key]["kills"] += 1
                    print(self.client.tournament_players[key]["kills"])
                    self.client.tournament_should_track_kills = False
                    if self.client.tournament_should_sleep:
                        await asyncio.sleep(5)
                    self.client.tournament_should_track_kills = True
                elif str(key) == str(killer_uid) and str(key) == str(victim_uid):
                    print("found suicide")
                    for key, _ in self.client.tournament_players.items():
                        if str(key) != str(killer_uid):
                            self.client.tournament_players[key]["kills"] += 1
                    self.client.tournament_should_track_kills = False
                    if self.client.tournament_should_sleep:
                        await asyncio.sleep(5)
                    self.client.tournament_should_track_kills = True

    async def add_playing(self, player, server_identifier):
        unix = int(time.time())
        if any(player == uid[0] for uid in self.client.playing[server_identifier]):
            # print(f"duplicate found! {player}")
            return
        self.client.playing[server_identifier].append([player, unix])

    async def remove_playing(self, player, server_identifier):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()

            # Using reversed enumeration to ensure list consistency when popping elements
            for i, uid in reversed(
                list(enumerate(self.client.playing[server_identifier]))
            ):
                if player == uid[0]:
                    unix = int(time.time())
                    time_diff = unix - uid[1]
                    if len(self.client.lazy_playing) > 1:
                        await cursor.execute(
                            f"UPDATE {server_identifier} SET playtime = playtime + {time_diff} WHERE uid = {player}"
                        )
                    self.client.playing[server_identifier].pop(i)

            await db.commit()

    async def clear_playing(self, server_identifier):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()

            self.client.lazy_playing[server_identifier] = self.client.playing[
                server_identifier
            ]

            # Using a copy to iterate
            for uid in self.client.playing[server_identifier][:]:
                unix = int(time.time())
                time_diff = unix - uid[1]
                if len(self.client.lazy_playing) > 1:
                    await cursor.execute(
                        f"UPDATE {server_identifier} SET playtime = playtime + {time_diff} WHERE uid = {uid[0]}"
                    )
                self.client.playing[server_identifier].remove(uid)

            await db.commit()

    async def award_games_to_online(self, server_identifier):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            playing = (
                self.client.playing[server_identifier]
                if self.client.playing[server_identifier]
                > self.client.lazy_playing[server_identifier]
                else self.client.lazy_playing[server_identifier]
            )
            if len(playing) > 1:
                for uid in playing:
                    await cursor.execute(
                        f"UPDATE {server_identifier} SET gamesplayed = gamesplayed + 1 WHERE uid = {uid[0]}"
                    )
            await db.commit()

    async def send_relay_msg(self, player, message, team, uid, server_identifier):
        server = await utils.get_server(server_identifier)
        channel = self.client.get_channel(server.relay)
        if server_identifier == "infection":
            if team == 3:
                team = "S"
            elif team == 2:
                team = "I"
            else:
                team = "?"
            if message[0] == "!":
                return
        else:
            team = "M" if team == 3 else "I"
        output = f"{message}"
        output = discord.utils.escape_mentions(output)
        output = discord.utils.escape_markdown(output)
        sent = await channel.send(f"[**__{team}__**] **{player}**: " + output)
        print(output)
        await self.check_for_bad(player, message, uid, sent)

    async def send_relay_misc(self, msg, server_identifier):
        server = await utils.get_server(server_identifier)
        channel = self.client.get_channel(server.relay)
        await channel.send(msg)
        print(msg)

    async def send_relay_kill(
        self, killer, victim, killer_team, victim_team, server_identifier
    ):
        if server_identifier == "infection" and killer_team == 2 and killer != victim:
            await self.log_kill_db(killer, 1, victim, server_identifier)

        # if killer_team == 2 and victim_team == 2:
        #     # team will be switched before titanfall can say someone actually died
        #     if server_identifier == "infection":
        #         action = "**infected**"
        #     else:
        #         action = "killed"
        # else:
        # action = "killed"
        if killer == victim:
            await self.log_kill_db(killer, 2, victim, server_identifier)
            # server = await utils.get_server(server_identifier)
            # channel = self.client.get_channel(server.relay)
            # await channel.send(f"{killer} bid farewell, cruel world!")
        else:
            await self.log_kill_db(killer, 0, victim, server_identifier)
        # else:
        #     killer = discord.utils.escape_markdown(killer)
        #     victim = discord.utils.escape_markdown(victim)
        # output = f"{killer} {action} {victim}."
        # server = await utils.get_server(server_identifier)
        # channel = self.client.get_channel(server.relay)
        # await channel.send(output)

    async def log_kill_db(self, killer, action, victim, server_identifier):
        # 0 = s kills i, 1 = i kills s, 2, suicide
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute(
                f"SELECT uid FROM {server_identifier} WHERE name=?", (killer,)
            )
            killerid = await cursor.fetchone()
            if killerid is None:
                print(f"{killer} does not have a uid!!!")
                await self.discord_log(f"{killer} does not have a uid!!!")
                return
            killerid = killerid[0]
            await cursor.execute(
                f"SELECT uid FROM {server_identifier} WHERE name=?", (victim,)
            )
            victimid = await cursor.fetchone()
            if victimid is None:
                print(f"{victim} does not have a uid!!!")
                await self.discord_log(f"{victim} does not have a uid!!!")
                return
            victimid = victimid[0]
            await cursor.execute(
                f"INSERT INTO {server_identifier}_kill_log(killer, action, victim, timestamp) values(?, ?, ?, ?)",
                (killerid, action, victimid, int(time.time())),
            )
            await db.commit()

    async def check_for_changed_name(self, uid, name):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            changed = False
            for server in config.servers:
                await cursor.execute(
                    f"SELECT name FROM {server.name} WHERE uid = ?", (uid,)
                )
                result = await cursor.fetchone()
                if not result:
                    continue
                if result[0] != name:
                    changed = True
                    break
            if changed:
                for server in config.servers:
                    await cursor.execute(
                        f"UPDATE {server.name} SET name = ? WHERE uid = ?", (name, uid)
                    )
                    await db.commit()
                adminrelay = self.client.get_channel(config.admin_relay)
                await adminrelay.send(
                    f"Name change detected.\n`{result[0]}` -> `{name}`\nUID: `{uid}`"
                )
                discord_id = await utils.get_discord_id_user_from_connection(uid)
                if discord_id is not None:
                    discord_user = await self.client.fetch_user(discord_id)
                    if discord_user is not None:
                        try:
                            await discord_user.send(
                                f"Warning! Your name on titanfall has been changed from `{result[0]}` to `{name}`. If this was not you, your EA/Origin account has been compromised. Please change your password immediately. If this was in fact you, you can safely ignore this message."
                            )
                        except discord.errors.Forbidden:
                            await adminrelay.send(
                                f"Could not send message to {discord_user.name} about name change."
                            )

    async def new_account(self, user, uid, server_identifier):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if server_identifier == "infection":
                await cursor.execute(
                    f"INSERT INTO {server_identifier}(name, uid, killsimc, killsmilitia, deathsimc, deathsmilitia, first_join, last_join, playtime, killstreak, gamesplayed, firstinfected) values(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (user, uid, 0, 0, 0, 0, current_time, current_time, 0, 0, 0, 0),
                )
            else:
                await cursor.execute(
                    f"INSERT INTO {server_identifier}(name, uid, killsimc, killsmilitia, deathsimc, deathsmilitia, first_join, last_join, playtime, killstreak, gamesplayed) values(?,?,?,?,?,?,?,?,?,?,?)",
                    (user, uid, 0, 0, 0, 0, current_time, current_time, 0, 0, 0),
                )
            await self.discord_log(
                f"New account created for {user} with uid {uid} in {server_identifier}"
            )
            await db.commit()

    async def log_firstinfected(self, name):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute(
                "UPDATE infection SET firstinfected = firstinfected + 1 WHERE name=?",
                (name,),
            )
            await db.commit()

    async def log_killstreak(self, name, kills, server_identifier):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute(
                f"SELECT killstreak FROM {server_identifier} WHERE name = ?", (name,)
            )
            real = await cursor.fetchone()
            real = real[0] if real else 0
            if kills > real:
                await cursor.execute(
                    f"UPDATE {server_identifier} SET killstreak = ? WHERE name=?",
                    (kills, name),
                )
                await db.commit()

    async def log_join(self, player, uid, server_identifier):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute(
                f'SELECT "first_join" FROM {server_identifier} WHERE uid=?', (uid,)
            )
            result_userid = await cursor.fetchone()
            if not result_userid:
                await self.new_account(player, uid, server_identifier)
            await cursor.execute(
                f"UPDATE {server_identifier} SET last_join = ? WHERE uid=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), uid),
            )
            await db.commit()

    async def discord_log(self, msg):
        channel = await self.client.fetch_channel(config.log_channel)
        await channel.send(msg)

    async def big_brother(self, msg):
        channel = await self.client.fetch_channel(config.bigbrother)
        await channel.send(msg)

    async def log_kill(self, line, server_identifier):
        player = line["subject"]["name"]
        team = line["subject"]["teamId"]
        uid = line["subject"]["uid"]
        victim = line["object"]["name"]
        vuid = line["object"]["uid"]
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            if player == victim:
                if team == 2:
                    await db.execute(
                        f"UPDATE {server_identifier} SET deathsimc = deathsimc + 1 WHERE uid=?",
                        (uid,),
                    )
                if team == 3:
                    await db.execute(
                        f"UPDATE {server_identifier} SET deathsmilitia = deathsmilitia + 1 WHERE uid=?",
                        (uid,),
                    )
                return
            elif team == 2:
                await db.execute(
                    f"UPDATE {server_identifier} SET killsimc = killsimc + 1 WHERE uid=?",
                    (uid,),
                )
                await db.execute(
                    f"UPDATE {server_identifier} SET deathsmilitia = deathsmilitia + 1 WHERE uid=?",
                    (vuid,),
                )
            elif team == 3:
                await db.execute(
                    f"UPDATE {server_identifier} SET killsmilitia = killsmilitia + 1 WHERE uid=?",
                    (uid,),
                )
                await db.execute(
                    f"UPDATE {server_identifier} SET deathsimc = deathsimc + 1 WHERE uid=?",
                    (vuid,),
                )
            await db.commit()

    async def check_for_bad(self, player, message, uid, sent):
        for word in config.ban_words:
            # Search for the pattern in the text
            if re.search(word, message, re.IGNORECASE):
                await utils.ban_user(
                    uid,
                    reason="AUTO BAN: Rule breaking language",
                    expires=utils.human_time_to_seconds("1w"),
                )
                adminrelay = self.client.get_channel(config.admin_relay)
                await adminrelay.send(
                    f"`{player}` has been automatically banned due to a rule breaking message:\n`{message}`\nMatches pattern:`{word}`\nUID: `{uid}`\nPlease review: {sent.jump_url}"
                )
                banlog = self.client.get_channel(config.ban_log)
                await banlog.send(
                    f"{player} has been automatically banned.\nReason: Rule breaking language\nContext: {sent.jump_url}"
                )
                for server in config.servers:
                    await server.send_command("checkbans")
                return

        for word in config.bad_words:
            if re.search(word, message, re.IGNORECASE):
                adminrelay = self.client.get_channel(config.admin_relay)
                await adminrelay.send(
                    f"Message from `{player}`: `{message}` matches pattern `{word}`\nUID: `{uid}`\nPlease review: {sent.jump_url}"
                )
                break

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                f"This command is on cooldown, you can use it "
                f"<t:{int(time.time()) + int(error.retry_after) + 3}:R>"
            )
        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.reply(
                "Too many people are using this command! Please try again later."
            )
        elif isinstance(error, commands.NSFWChannelRequired):
            await ctx.reply("<:weirdchamp:1037242286439931974>")
        elif isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.UserNotFound):
            await ctx.reply(
                "The specified user was not found. Did you type the name correctly? Try pinging them or pasting their ID."
            )
            ctx.command.reset_cooldown(ctx)
        elif isinstance(error, commands.NotOwner):
            return
        elif isinstance(error, commands.UserNotFound) or isinstance(
            error, commands.MemberNotFound
        ):
            await ctx.reply("The person you specified was not found! Try pinging them.")
            ctx.command.reset_cooldown(ctx)
        elif isinstance(error, commands.BadArgument):
            ctx.command.reset_cooldown(ctx)
            await ctx.reply("One of the arguments you specified was not valid.")
        else:
            ctx.command.reset_cooldown(ctx)
            channel = await self.client.fetch_channel(1096272472204115968)
            embed = discord.Embed(
                title="An Error has occurred",
                description=f"Error: \n `{error}`\nCommand: `{ctx.command}`",
                timestamp=ctx.message.created_at,
                color=242424,
            )
            await channel.send(embed=embed)
            print(error)
            traceback.print_exception(
                type(error), error, error.__traceback__, file=sys.stderr
            )
            print("-" * 20)
            await ctx.reply("An unexpected error occurred! Please try again.")


async def setup(client):
    await client.add_cog(Relay(client))
