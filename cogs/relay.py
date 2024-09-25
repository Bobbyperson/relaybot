import discord
import time
from discord.ext import commands
from discord.ext import tasks
import config
import aiosqlite
import asyncpg
import requests
import json
import asyncio
import sys
import traceback
from datetime import datetime
import cogs.utils.utils as utils  # this is stupid

# import cogs.utils.crashes as crashes
import re
from aiohttp import web, ClientSession


class Relay(commands.Cog):
    """Relay stuff."""

    def __init__(self, client):
        self.client = client
        self.client.current_log = None
        self.client.old = 0
        self.client.auth = {}
        if not config.debug:
            # if there is a common exception occuring, add it here.
            self.update_stats.add_exception_type(
                asyncpg.PostgresConnectionError
            )  # internet dropping
            self.update_stats.add_exception_type(
                discord.errors.NotFound
            )  # 404, unsure when this occurs
            self.update_stats.add_exception_type(
                discord.errors.HTTPException
            )  # discord 524
            self.update_stats.add_exception_type(
                requests.exceptions.ConnectionError
            )  # northstar 524
            self.update_stats.add_exception_type(
                AttributeError
            )  # very rare, sometimes the channel will not be fetched properly
            self.update_stats.add_exception_type(
                json.decoder.JSONDecodeError
            )  # sometimes northstar server will return nothing
        self.client.playing = {}
        self.client.lazy_playing = {}
        for s in config.servers:
            self.client.playing[s.name] = []
            self.client.lazy_playing[s.name] = []
        self.update_stats.start()
        self.app = web.Application()
        self.app.router.add_post("/post", self.recieve_relay_info)
        self.app.router.add_get("/get", self.tone_info)
        self.app.router.add_post("/leaderboard", self.get_leaderboard)
        self.app.router.add_get("/leaderboard-info", self.get_leaderboard_info)
        self.app.router.add_get("/is-whitelisted", self.is_whitelisted)
        self.app.router.add_get("/stats", self.get_stats)
        self.app.router.add_get("/tournament-loadout", self.get_tournament_loadout)
        self.app.router.add_route("OPTIONS", "/leaderboard", self.handle_options)
        self.app.router.add_route("OPTIONS", "/leaderboard-info", self.handle_options)
        self.app.router.add_route("OPTIONS", "/get", self.handle_options)
        self.app.router.add_route("OPTIONS", "/post", self.handle_options)
        self.app.router.add_route("OPTIONS", "/is-whitelisted", self.handle_options)
        self.app.router.add_route("OPTIONS", "/stats", self.handle_options)
        self.app.router.add_route("OPTIONS", "/tournament-loadout", self.handle_options)
        self.runner = web.AppRunner(self.app)
        self.message_queue = {}
        for s in config.servers:
            self.message_queue[s.name] = ""
        self.client.ban_list = {}
        for s in config.servers:
            self.client.ban_list[s.name] = []
        self.client.tournament_loadout = {}
        self.client.tournament_should_track_kills = True

    async def get_tournament_loadout(self, request):
        with open("tourney/round1.json", "r") as f:
            return web.Response(text=f.read())
        # return web.Response(text=json.dumps(self.client.tournament_loadout))

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

    async def send_test_message(self, request):
        await self.client.get_channel(745410408482865267).send("test")

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
                cleaned_message = (
                    message.content.strip("'")
                    .strip('"')
                    .strip("`;&|")
                    .replace("\n", " ")
                )

                await s.send_command(
                    f"serversay {message.author.name} {cleaned_message}"
                )
                await self.discord_log(f"from {message.author.name}: `serversay {message.author.name} {cleaned_message}`")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.make_mentionable()
        print("Relay is ready. Starting web server...")
        await self.start_web_server()

    async def start_web_server(self):
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", 2585)
        await site.start()

    # events
    @tasks.loop(seconds=30)
    async def update_stats(self):
        channel = self.client.get_channel(config.stats_channel)
        fetchMessage = None
        async for message in channel.history(limit=200):
            if message.author.id == self.client.user.id:
                fetchMessage = message
                break

        if fetchMessage is not None:
            message_id = fetchMessage.id
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

        for term in config.query:
            for server in servers:
                if term in server["name"]:
                    query_results.append(server)

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
                startEsc = data.find("")
                endEsc = data[startEsc:].find("m")
                data = data[:startEsc] + data[endEsc + startEsc + 1 :]
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
            return
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
                case "banlist":
                    bans = data["args"].split("|")
                    self.client.ban_list[server_identifier] = bans
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
            print(f"killer uid: {killer_uid}")
        else:
            print("unknown tournament verb: " + data["verb"])
            return

        if self.client.tournament_should_track_kills:
            for key, _ in self.client.tournament_players.items():
                if str(key) == str(killer_uid):
                    print("found killer, adding to kill count")
                    self.client.tournament_players[key]["kills"] += 1
                    print(self.client.tournament_players[key]["kills"])
                    self.client.tournament_should_track_kills = False
                    await asyncio.sleep(10)
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
            result_userID = await cursor.fetchone()
            if not result_userID:
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
                for server in config.servers:
                    await server.send_command(f"cbbanuid {uid}")
                adminrelay = self.client.get_channel(config.admin_relay)
                await adminrelay.send(
                    f"`{player}` has been automatically banned due to a rule breaking message:\n`{message}`\nMatches pattern:`{word}`\nUID: `{uid}`\nPlease review: {sent.jump_url}"
                )
                banlog = self.client.get_channel(config.ban_log)
                await banlog.send(
                    f"{player} has been automatically banned.\nReason: Rule breaking language\nContext: {sent.jump_url}"
                )
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
        elif isinstance(error, commands.UserNotFound):
            await ctx.reply("The person you specified was not found! Try pinging them.")
            ctx.command.reset_cooldown(ctx)
        elif isinstance(error, commands.MemberNotFound):
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
