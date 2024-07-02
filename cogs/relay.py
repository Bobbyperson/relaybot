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
        self.runner = web.AppRunner(self.app)

    def cog_unload(self):
        self.update_stats.cancel()
        # self.lazy_playing_update.cancel()

    async def make_mentionable(self):
        await self.client.get_guild(929895874799226881).get_role(
            1000617424934154260
        ).edit(mentionable=True)

    async def send_test_message(self, request):
        await self.client.get_channel(745410408482865267).send("test")

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

    @commands.Cog.listener()
    async def on_ready(self):
        await self.make_mentionable()
        print("Relay is ready. Starting web server...")
        await self.start_web_server()

    async def start_web_server(self):
        await self.runner.setup()
        site = web.TCPSite(self.runner, "localhost", 2585)
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
        highest = 0
        for term in config.query:
            for server in servers:
                if server["playerCount"] > highest:
                    highest = server["playerCount"]
                if term in server["name"]:
                    query_results.append(server)

        if query_results:
            if highest == query_results[0]["playerCount"]:
                sdescription = "We currently have the most players on any server!!!!!"
            else:
                sdescription = "Server is up!"
        else:
            sdescription = "Server is down! :("

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
        async with aiosqlite.connect(config.relay) as db:
            await db.execute(
                f"""CREATE TABLE IF NOT EXISTS {server_identifier}
num INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT NOT NULL,
uid INT NOT NULL,
killsimc INT NOT NULL,
killsmilitia INT NOT NULL,
deathsimc INT NOT NULL,
deathsmilitia INT NOT NULL,
firstjoin TEXT NOT NULL,
lastjoin TEXT NOT NULL,
playtime INT NOT NULL,
killstreak INT NOT NULL,
gamesplayed INT NOT NULL
"""
            )
            await db.execute(
                f"""CREATE TABLE IF NOT EXISTS {server_identifier}_kill_log
num INTEGER PRIMARY KEY AUTOINCREMENT,
killer INT NOT NULL,
action INT NOT NULL,
victim INT NOT NULL,
timestamp INT NOT NULL
"""
            )
            await db.commit()

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
        except KeyError:
            pass
        try:
            message = data["object"]["message"]
        except KeyError:
            pass
        server_identifier = data["server_identifier"]
        if not await utils.is_valid_server(server_identifier):
            print(
                f"Warning! Invalid server identifier for {server_identifier}. Provided data was {data}. IP of request was {request.remote_addr}."
            )
            return web.Response(status=401, text="Bad identifier")
        auth_header = request.headers.get("authentication")
        if not await utils.check_server_auth(server_identifier, auth_header):
            print(
                f"Warning! Invalid auth header for {server_identifier}. Provided auth was {auth_header}. IP of request was {request.remote_addr}."
            )
            return web.Response(status=401, text="Bad auth")
        ip = request.remote_addr
        if not await utils.check_server_ip(server_identifier, ip):
            print(
                f"Warning! Invalid ip for {server_identifier}. Provided ip was {ip}."
            )
            return web.Response(status=401, text="Bad IP")
        await self.register_server(server_identifier)
        match data["verb"]:
            case "sent":
                # if line["object"]["team_chat"] == False:
                await self.send_relay_msg(player, message, team, uid, server_identifier)
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
                await self.send_relay_misc("**The round has ended.**", server_identifier)
                await self.award_games_to_online(server_identifier)
                await self.clear_playing(server_identifier)
            case "waitingForPlayers":
                await self.send_relay_misc("**The game is loading.**", server_identifier)
            case "playing":
                await self.send_relay_misc("**The game has started.**", server_identifier)
            case "connected":
                await self.send_relay_misc(f"**{player} just connected.**", server_identifier)
                await self.log_join(player, uid, server_identifier)
                await self.check_for_changed_name(uid, player, server_identifier)
                await self.add_playing(uid, server_identifier)
            case "respawned":
                await self.add_playing(uid, server_identifier)  # sometimes connected will just not be sent
            case "disconnected":
                await self.send_relay_misc(f"**{player} just disconnected.**", server_identifier)
                await self.remove_playing(uid, server_identifier)
            case "killed":
                victim = data["object"]["name"]
                kteam = data["subject"]["teamId"]
                iteam = data["object"]["teamId"]
                await self.log_kill(data, server_identifier)
                await self.send_relay_kill(player, victim, kteam, iteam, server_identifier)
            case _:
                print("unknown verb: " + data["verb"])
        return web.Response(status=200, text="OK")

    async def add_playing(self, player, server_identifier):
        unix = int(time.time())
        if any(player == uid[0] for uid in self.client.playing):
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
            for uid in self.client.playing[:]:
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
            if message == "!hardmode":
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
        if killer_team == 2 and victim_team == 2 and server_identifier == "infection":
            # team will be switched before titanfall can say someone actually died
            action = "**infected**"
            await self.log_kill_db(killer, 1, victim)
        else:
            action = "killed"
            await self.log_kill_db(killer, 0, victim)
        if killer == victim:
            await self.log_kill_db(killer, 2, victim)
            channel = self.client.get_channel(config.relay)
            await channel.send(f"{killer} bid farewell, cruel world!")
        else:
            killer = discord.utils.escape_markdown(killer)
            victim = discord.utils.escape_markdown(victim)
            output = f"{killer} {action} {victim}."
            channel = self.client.get_channel(config.relay)
            await channel.send(output)

    async def log_kill_db(self, killer, action, victim, server_identifier):
        # 0 = s kills i, 1 = i kills s, 2, suicide
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute(f"SELECT uid FROM {server_identifier} WHERE name=?", (killer,))
            killerid = await cursor.fetchone()
            if killerid is None:
                print(f"{killer} does not have a uid!!!")
                await self.discord_log(f"{killer} does not have a uid!!!")
                return
            killerid = killerid[0]
            await cursor.execute(f"SELECT uid FROM {server_identifier} WHERE name=?", (victim,))
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
                await cursor.execute(f"SELECT name FROM {server.name} WHERE uid = ?", (uid,))
                result = await cursor.fetchone()
                if result[0] != name:
                    changed = True
                    break
            if changed:
                for server in config.server:
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
            await cursor.execute(
                f"INSERT INTO {server_identifier}(name, uid, killsimc, killsmilitia, deathsimc, deathsmilitia, first_join, last_join, playtime, killstreak, firstinfected, gamesplayed) values(?,?,?,?,?,?,?,?,?,?,?,?)",
                (user, uid, 0, 0, 0, 0, current_time, current_time, 0, 0, 0, 0),
            )
            await self.discord_log(f"New account created for {user} with uid {uid} in {server_identifier}")
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
            await cursor.execute(f"SELECT killstreak FROM {server_identifier} WHERE name = ?", (name,))
            real = await cursor.fetchone()
            real = real[0]
            if kills > real:
                await cursor.execute(
                    f"UPDATE {server_identifier} SET killstreak = ? WHERE name=?", (kills, name)
                )
                await db.commit()

    async def log_join(self, player, uid, server_identifier):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute(f'SELECT "first_join" FROM {server_identifier} WHERE uid=?', (uid,))
            result_userID = await cursor.fetchone()
            if not result_userID:
                await self.new_account(player, uid)
            await cursor.execute(f'UPDATE {server_identifier} SET last_join = ? WHERE uid=?', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), uid))
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
                    await db.execute(f"UPDATE {server_identifier} SET deathsimc = deathsimc + 1 WHERE uid=?", (uid,))
                if team == 3:
                    await db.execute(f"UPDATE {server_identifier} SET deathsmilitia = deathsmilitia + 1 WHERE uid=?", (uid,))
                return
            elif team == 2:
                await db.execute(f"UPDATE {server_identifier} SET killsimc = killsimc + 1 WHERE uid=?", (uid,))
                await db.execute(f"UPDATE {server_identifier} SET deathsmilitia = deathsmilitia + 1 WHERE uid=?", (vuid,))
            elif team == 3:
                await db.execute(f"UPDATE {server_identifier} SET killsmilitia = killsmilitia + 1 WHERE uid=?", (uid,))
                await db.execute(f"UPDATE {server_identifier} SET deathsimc = deathsimc + 1 WHERE uid=?", (vuid,))
            await db.commit()

    async def check_for_bad(self, player, message, uid, sent):
        for word in config.bad_words:
            if re.search(word, message, re.IGNORECASE):
                adminrelay = self.client.get_channel(config.admin_relay)
                await adminrelay.send(
                    f"Message from `{player}`: `{message}` matches pattern `{word}`\nUID: `{uid}`\nPlease review: {sent.jump_url}"
                )
                break
        for word in config.ban_words:
            # Search for the pattern in the text
            if re.search(word, message, re.IGNORECASE):
                # with open(
                #     "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\banlist.txt",
                #     "r",
                # ) as f:
                #     file_lines = [line.rstrip() for line in f.readlines()]
                #     for line in file_lines:
                #         if uid in line:
                #             return
                for server in config.servers:
                    await server.send_command(f"bban {uid}")
                adminrelay = self.client.get_channel(config.admin_relay)
                await adminrelay.send(
                    f"{player} has been automatically banned due to a rule breaking message:\n{message}\nMatches pattern:`{word}`\nUID: `{uid}`\nPlease review"
                )
                banlog = self.client.get_channel(config.ban_log)
                await banlog.send(
                    f"{player} has been automatically banned.\nReason: Rule breaking language"
                )
                break


async def setup(client):
    await client.add_cog(Relay(client))
