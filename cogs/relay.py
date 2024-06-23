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
import os
import cogs.utils.utils as utils  # this is stupid
import cogs.utils.crashes as crashes
import re
import aiohttp


class Relay(commands.Cog):
    """Relay stuff."""
    def __init__(self, client):
        self.client = client
        self.client.current_log = None
        self.client.old = 0
        self.client.auth = {}
        self.check_server.add_exception_type(
            discord.errors.HTTPException
        )  # discord will timeout more frequently than you think...
        self.check_server.add_exception_type(UnicodeDecodeError)
        self.check_server.start()
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
        self.client.playing = []
        self.client.whitelist = 5
        self.client.lazy_playing = []
        self.update_stats.start()
        self.lazy_playing_update.start()
        self.client.crash_handler = crashes.Crash_Handler()
        

    def cog_unload(self):
        self.update_stats.cancel()
        self.check_server.cancel()
        self.lazy_playing_update.cancel()
        
    async def make_mentionable(self):
        await self.client.get_guild(929895874799226881).get_role(1000617424934154260).edit(mentionable=True)
        
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        for role in message.role_mentions:
            if role.id == 1000617424934154260:
                await role.edit(mentionable=False)
                await self.discord_log(f"looking to play is now unmentionable due to {message.author.name} {message.jump_url}")
                await asyncio.sleep(3600)
                await role.edit(mentionable=True)
                await self.discord_log("looking to play is now mentionable")
    # events
    @tasks.loop(seconds=30)
    async def update_stats(self):
        channel = self.client.get_channel(config.channel_id)
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
        
        async with aiohttp.ClientSession() as session:
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
            if self.client.whitelist != 5:
                sdescription = "Server is in whitelist mode. Use `/amiwhitelisted`."
            elif highest == query_results[0]["playerCount"]:
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
                embed.add_field(name="Playercount:", value=str(server["playerCount"]) + "/" + str(server["maxPlayers"]), inline=True)
                embed.add_field(name="Gamemode:", value=server["playlist"], inline=True)
                embed.add_field(name="Map:", value=server["map"], inline=True)
            embed.set_footer(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        if msg is None:
            await channel.send(embed=embed)
        else:
            await msg.edit(embed=embed)

        # # dm notifs logic
        # print(1)
        # if table != []:
        #     playercount = table[0][1]
        #     peopleToMessage = await get_notifs(playercount)
        #     print(2)
        #     print(peopleToMessage)
        #     if peopleToMessage:
        #         print(3)
        #         await discordLog(peopleToMessage)
        #         for i in range(len(peopleToMessage)):
        #             user = await client.fetch_user(peopleToMessage[i][1])
        #             await user.send(
        #                 f"the awesome infection server has reached **{playercount} players**. i am messaging you as per the notification you set\n",
        #                 f"i will be messaging you again after {peopleToMessage[i][3]} hours have passed and at least {peopleToMessage[i][2]} people are on the server",
        #             )
        #             await set_cooldown(peopleToMessage[i][1])
        #         await discordLog(f"server reached {playercount} players and i annoyed {len(peopleToMessage)} people about it")
        
    @tasks.loop(seconds=15)
    async def lazy_playing_update(self):
        self.client.lazy_playing = self.client.playing[:]

    @tasks.loop(seconds=5)
    async def check_server(self):
        loge = await self.get_log()
        if loge is None:
            print("loge is none!!!!")
            return
        if self.client.old != 0:
            print(str(len(self.client.old)) + " == old")
        else:
            print("old == None")
        print(str(len(loge)) + " == new")
        # new_lines = []
        if self.client.old != 0:
            if len(loge) < len(self.client.old):
                await self.send_relay_misc(
                    "__**New log file detected! The server appears to have crashed.\nIt should restart within 30 seconds.**__"
                )
                await self.client.crash_handler.log_crash()
                message = "Server crashed! The following players were playing:\n```"
                adminrelay = self.client.get_channel(config.admin_relay)
                if await self.client.crash_handler.recommend_whitelist(self.client.whitelist):
                    self.client.whitelist -= 1
                    await adminrelay.send(f"Warning! Fuckery detected! The server has crashed {len(self.client.crash_handler.crashes) if len(self.client.crash_handler.crashes) < 5 else '4+'} times in the past 10 minutes. Whitelist mode has been set to {self.client.whitelist}.")
                    await crashes.whitelist_set(self.client.whitelist)
                playing = self.client.playing if self.client.playing > self.client.lazy_playing else self.client.lazy_playing
                if len(playing) == 0:
                    message += "nobody"
                for uid in playing:
                    db = await aiosqlite.connect(config.bank, timeout=10)
                    cursor = await db.cursor()
                    await cursor.execute("SELECT name FROM main WHERE uid = ?", (uid[0],))
                    result = await cursor.fetchone()
                    message += result[0] + "\n" if result is not None else "USER NOT FOUND" + "\n"
                    await cursor.close()
                    await db.close()
                message += f"```\nTotal: {len(playing)} players"
                await self.discord_log(message + "\nPlease note: if someone joined the server and crashed the server instantly, they will likely not be seen here! Check logs if needed!")
                try:
                    logchnl = await self.client.fetch_channel(config.log_channel)
                    logdir = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\logs"
                    newest = sorted([f for f in os.listdir(logdir) if f.startswith("nslog")])
                    await logchnl.send(file=discord.File(f"{logdir}\\{newest[-2]}"), content="Please note that this log is private information, and **should not be shared** with anyone outside of this channel. Additionally, **if a crash is due to a player, please ensure that is was intentional**, just because a crash was caused by a player does not mean it was!")
                except Exception as e:
                    await self.discord_log(f"Could not post last log!: `{e}`")
                await self.clear_playing()
                await self.set_old(loge)
                print("Server crashed!!!!")
                return
            if len(loge) != len(self.client.old):
                loopable_lines = len(loge) - len(self.client.old)
                print(f"Looping through {str(loopable_lines)} lines")
                startTime = int(round(time.time() * 1000))
                line_count = 0
                for i in range(
                    len(self.client.old) - 1, len(loge) - 1
                ):  # instead of popping hundreds of thousands of elements from an array, this just loops through the new bits. in other words, the obvious solution
                    line = loge[i]
                    line_count += 1
                    if "command|" in line:
                        start = line.find("command|")
                        line = line[start:]
                        print(line)
                        await self.big_brother(discord.utils.escape_mentions(line))
                    elif "killstreak|" in line:
                        start = line.find("killstreak|")
                        line = line[start:]
                        bits = line.split("|")  # 1 = name, 2 = streak
                        if len(bits) != 3:
                            await self.set_old(loge)
                            print("too many killstreak bits! returning!")
                            return
                        try:
                            int(bits[2])
                        except:
                            await self.set_old(loge)
                            print("not int! returning!")
                            return
                        if int(bits[2]) == 5:
                            await self.send_relay_misc(
                                "<< "
                                + bits[1]
                                + " is on a KILLING SPREE "
                                + (bits[2])
                                + " >>"
                            )
                        elif int(bits[2]) == 10:
                            await self.send_relay_misc(
                                "<< " + bits[1] + " is UNSTOPPABLE " + (bits[2]) + " >>"
                            )
                        elif int(bits[2]) == 15:
                            await self.send_relay_misc(
                                "<< "
                                + bits[1]
                                + " is on a RAMPAGE "
                                + (bits[2])
                                + " >>"
                            )
                        elif int(bits[2]) == 20:
                            await self.send_relay_misc(
                                "<< " + bits[1] + " is GOD-LIKE " + (bits[2]) + " >>"
                            )
                        elif (int(bits[2]) % 5) == 0 and int(bits[2]) < 96:
                            await self.send_relay_misc(
                                "<< "
                                + bits[1]
                                + " is still GOD-LIKE "
                                + (bits[2])
                                + " >>"
                            )
                        elif (int(bits[2]) % 5) == 0 and int(bits[2]) > 99:
                            await self.send_relay_misc(
                                "<< "
                                + bits[1]
                                + " is FUCKING CHEATING "
                                + (bits[2])
                                + " >>"
                            )
                    elif "killstreakend|" in line:
                        start = line.find("killstreakend|")
                        line = line[start:]
                        bits = line.split("|")  # 1 = name, 2 = streak
                        if len(bits) != 3:
                            await self.set_old(loge)
                            print("fucked up killstreakend!")
                            return
                        try:
                            int(bits[2])
                        except:
                            await self.set_old(loge)
                            print("not int! returning!")
                            return
                        await self.log_killstreak(bits[1], int(bits[2]))
                        print(line)
                    elif "firstinfected|" in line:
                        start = line.find("firstinfected|")
                        line = line[start:]
                        bits = line.split("|")  # 1 = name
                        if len(bits) != 2:
                            await self.set_old(loge)
                            return
                        await self.log_firstinfected(bits[1])
                    elif "boomer|" in line:
                        start = line.find("boomer|")
                        line = line[start:]
                        bits = line.split("|")  # 1 = name, 2 = streak
                        if len(bits) != 2:
                            await self.set_old(loge)
                            return
                        boomerName = line[1]
                        # remove one death from boomer
                        db = await aiosqlite.connect(config.bank, timeout=10)
                        cursor = await db.cursor()
                        await cursor.execute(
                            "UPDATE main SET deaths_as_inf = deaths_as_inf - 1 WHERE name=?",
                            (boomerName,),
                        )
                        await db.commit()
                        await cursor.close()
                        await db.close()
                    elif "[ParseableLog]" in line:
                        start = line.find("[ParseableLog]")
                        line = line[start+15:]
                        if len(line) == 0:
                            await self.set_old(loge)
                            return
                        if line[0] == " ":
                            line = line[
                                1:
                            ]  # ooh look at me im gonna make inconsistencies in my mod just to fuck with you heeeheee
                        done = False
                        while not done:  # clean stupid ass color
                            if "" in line:
                                startEsc = line.find("")
                                endEsc = line[startEsc:].find("m")
                                line = line[:startEsc] + line[endEsc + startEsc + 1 :]
                            else:
                                done = True
                        try:
                            line = json.loads(line)  # convert to fucking json
                        except Exception as e:
                            print("i could not convert the following line to json:")
                            print(line)
                            await self.discord_log(
                                "i could not convert the following line to json:\n"
                                + line
                            )
                            await self.discord_log(f"{e}")
                            await self.set_old(loge)
                            return
                        try:  # how is json in python THIS BAD
                            player = line["subject"]["name"]
                            uid = line["subject"]["uid"]
                            team = line["subject"]["teamId"]
                        except:
                            pass
                        try:
                            message = line["object"]["message"]
                        except:
                            pass
                        match line["verb"]:
                            case "sent":
                                # if line["object"]["team_chat"] == False:
                                await self.send_relay_msg(player, message, team, uid)
                                if self.client.auth != {}:
                                    try:
                                        auth = int(message)
                                    except:
                                        auth = 0
                                    if auth in self.client.auth and self.client.auth[auth]["name"] == player:
                                        self.client.auth[auth]["confirmed"] = True
                            case "winnerDetermined":
                                await self.send_relay_misc("**The round has ended.**")
                                await self.award_games_to_online()
                                await self.clear_playing()
                            case "waitingForPlayers":
                                await self.send_relay_misc("**The game is loading.**")
                            case "playing":
                                await self.send_relay_misc("**The game has started.**")
                            case "connected":
                                await self.send_relay_misc(f"**{player} just connected.**")
                                await self.log_join(player, uid)
                                await self.check_for_changed_name(uid, player)
                                await self.add_playing(uid)
                            case "respawned":
                                await self.add_playing(uid) # sometimes connected will just not be sent
                            case "disconnected":
                                await self.send_relay_misc(
                                    f"**{player} just disconnected.**"
                                )
                                await self.remove_playing(uid)
                            case "killed":
                                victim = line["object"]["name"]
                                kteam = line["subject"]["teamId"]
                                iteam = line["object"]["teamId"]
                                await self.log_kill(line)
                                await self.send_relay_kill(player, victim, kteam, iteam)
                            case _:
                                print("unknown verb: " + line["verb"])
                endTime = int(round(time.time() * 1000))
                print(
                    f"It took {endTime - startTime} ms to loop through {loopable_lines} lines."
                )
        await self.set_old(loge)

    async def add_playing(self, player):
        unix = int(time.time())
        if any(player == uid[0] for uid in self.client.playing):
            #print(f"duplicate found! {player}")
            return
        self.client.playing.append([player, unix])

    async def remove_playing(self, player):
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()

        # Using reversed enumeration to ensure list consistency when popping elements
        for i, uid in reversed(list(enumerate(self.client.playing))):
            if player == uid[0]:
                unix = int(time.time())
                time_diff = unix - uid[1]
                if len(self.client.lazy_playing) > 1:
                    await cursor.execute(
                        f"UPDATE main SET playtime = playtime + {time_diff} WHERE uid = {player}"
                    )
                self.client.playing.pop(i)

        await db.commit()
        await cursor.close()
        await db.close()

    async def clear_playing(self):
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()

        self.client.lazy_playing = self.client.playing
        
        # Using a copy to iterate
        for uid in self.client.playing[:]:
            unix = int(time.time())
            time_diff = unix - uid[1]
            if len(self.client.lazy_playing) > 1:
                await cursor.execute(
                    f"UPDATE main SET playtime = playtime + {time_diff} WHERE uid = {uid[0]}"
                )
            self.client.playing.remove(uid)

        await db.commit()
        await cursor.close()
        await db.close()
        
    async def award_games_to_online(self):
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        playing = self.client.playing if self.client.playing > self.client.lazy_playing else self.client.lazy_playing
        if len(playing) > 1:
            for uid in playing:
                await cursor.execute(
                    f"UPDATE main SET gamesplayed = gamesplayed + 1 WHERE uid = {uid[0]}"
                )
        await db.commit()
        await cursor.close()
        await db.close()

    async def send_relay_msg(self, player, message, team, uid):
        channel = self.client.get_channel(config.relay)
        if team == 3:
            team = "S"
        elif team == 2:
            team = "I"
        else:
            team = "?"
        if message == "!hardmode":
            return
        output = f"{message}"
        output = discord.utils.escape_mentions(output)
        output = discord.utils.escape_markdown(output)
        sent = await channel.send(f"[**__{team}__**] **{player}**: " + output)
        print(output)
        await self.check_for_bad(player, message, uid, sent)

    async def send_relay_misc(self, msg):
        channel = self.client.get_channel(config.relay)
        await channel.send(msg)
        print(msg)

    async def send_relay_kill(self, killer, victim, killer_team, victim_team):
        channel = self.client.get_channel(config.relay)
        if (
            killer_team == 2 and victim_team == 2
        ):  # team will be switched before titanfall can say someone actually died
            action = "**infected**"
            await self.log_kill_db(killer, 1, victim)
        else:
            action = "killed"
            await self.log_kill_db(killer, 0, victim)
        if killer == victim:
            await channel.send(f"{killer} bid farewell, cruel world!")
            await self.log_kill_db(killer, 2, victim)
        else:
            killer = discord.utils.escape_markdown(killer)
            victim = discord.utils.escape_markdown(victim)
            output = f"{killer} {action} {victim}."
            await channel.send(output)

    async def log_kill_db(
        self, killer, action, victim
    ):  # 0 = s kills i, 1 = i kills s, 2, suicide
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        await cursor.execute('SELECT uid FROM main WHERE name=?', (killer,))
        killerid = await cursor.fetchone()
        if killerid is None:
            print(f"{killer} does not have a uid!!!")
            await self.discord_log(f"{killer} does not have a uid!!!")
            return
        killerid = killerid[0]
        await cursor.execute('SELECT uid FROM main WHERE name=?', (victim,))
        victimid = await cursor.fetchone()
        if victimid is None:
            print(f"{victim} does not have a uid!!!")
            await self.discord_log(f"{victim} does not have a uid!!!")
            return
        victimid = victimid[0]
        await cursor.execute(
            "INSERT INTO killLog(killer, action, victim, timestamp) values(?, ?, ?, ?)",
            (killerid, action, victimid, int(time.time()))
        )
        await db.commit()
        await cursor.close()
        await db.close()
        return

    async def check_for_changed_name(self, uid, name):
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        await cursor.execute("SELECT name FROM main WHERE uid = ?", (uid,))
        result = await cursor.fetchone()
        if result[0] != name:
            await cursor.execute('UPDATE main SET name = ? WHERE uid = ?', (name, uid))
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
                        await discord_user.send(f"Warning! Your name on titanfall has been changed from `{result[0]}` to `{name}`. If this was not you, your EA/Origin account has been compromised. Please change your password immediately. If this was in fact you, you can safely ignore this message.")
                    except discord.errors.Forbidden:
                        await adminrelay.send(f"Could not send message to {discord_user.name} about name change.")
        await cursor.close()
        await db.close()

    async def new_account(self, user, uid):
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await cursor.execute(
            'INSERT INTO main(name, uid, kills_as_inf, kills_as_sur, deaths_as_inf, deaths_as_sur, first_join, last_join, playtime, killstreak, slevel, ilevel) values(?,?,?,?,?,?,?,?,?,?,?,?)',
            (user, uid, 0, 0, 0, 0, current_time, current_time, 0, 0, 0, 0)
        )
        await self.discord_log(f"New account created for {user} with uid {uid}")
        await db.commit()
        await db.close()

    async def new_notif(self, userid, threshhold, cooldown):
        unix = int(time.time())
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        await cursor.execute(
            "INSERT INTO notifs(id, threshold, cooldown, nextPing) values(?, ?, ?, ?)",
            (userid, threshhold, cooldown, unix)
        )
        await db.commit()
        await db.close()

    async def delete_notif(self, userid):
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        await cursor.execute("DELETE FROM notifs WHERE id=?", (userid,))
        await db.commit()
        await db.close()

    async def check_notif(self, userid):
        unix = int(time.time())
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        await cursor.execute(
            "SELECT * FROM notifs WHERE id=? AND nextPing>=?",
            (userid, unix)
        )
        bruh = await cursor.fetchone()[0]
        await db.commit()
        await db.close()
        return bruh

    async def get_notifs(self, threshold):
        unix = int(time.time())
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        await cursor.execute(
            f"SELECT * FROM notifs WHERE threshold>='{threshold}' AND nextPing<'{unix}'"
        )
        bruh = await cursor.fetchall()
        await db.commit()
        await db.close()
        return bruh

    async def set_cooldown(self, userid):
        unix = int(time.time())
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        await cursor.execute("SELECT cooldown FROM notifs WHERE id=?", (userid,))
        hours = await cursor.fetchone()
        hours = hours[0]
        await cursor.execute(
            "UPDATE notifs SET nextPing=? WHERE id=?",
            (unix + (hours * 60 * 60), userid)
        )
        await db.commit()
        await db.close()

    async def log_firstinfected(self, name):
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        await cursor.execute(
            'UPDATE main SET firstinfected = firstinfected + 1 WHERE name=?',
            (name,)
        )
        await db.commit()
        await cursor.close()
        await db.close()

    async def get_element(self, element, user, uid):
        result_userBal = None
        while not result_userBal:
            db = await aiosqlite.connect(config.bank, timeout=10)
            cursor = await db.cursor()

            # Construct the query with the column name
            query = f"SELECT {element} FROM main WHERE uid=?"

            await cursor.execute(query, (uid,))
            result_userID = await cursor.fetchone()

            if not result_userID:
                await self.new_account(user, uid)
            else:
                await cursor.execute(query, (uid,))
                result_userBal = await cursor.fetchone()
                await cursor.close()
                await db.close()

                return result_userBal[0] if result_userBal else None


    async def log_killstreak(self, name, kills):
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        await cursor.execute('SELECT killstreak FROM main WHERE name = ?', (name,))
        real = await cursor.fetchone()
        real = real[0]
        if kills > real:
            await cursor.execute(
                'UPDATE main SET killstreak = ? WHERE name=?',
                (kills, name)
            )
            await db.commit()
        await cursor.close()
        await db.close()

    async def update_element(self, element, user, new, uid):
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        column_name = element  # Make sure this is safe and not directly from user input
        sql_query = f'UPDATE main SET {column_name} = ? WHERE uid=?'
        await cursor.execute(sql_query, (new, uid))
        await db.commit()
        await cursor.close()
        await db.close()

    async def add_element(self, element, user, addition, uid):
        db = await aiosqlite.connect(config.bank, timeout=10)
        change = await self.get_element(element, user, uid)
        cursor = await db.cursor()
        column_name = element  # Make sure this is safe and not directly from user input
        sql_query = f'UPDATE main SET {column_name} = ? WHERE uid=?'
        await cursor.execute(sql_query, (int(change) + addition, uid))
        await db.commit()
        await cursor.close()
        await db.close()

    async def log_join(self, player, uid):
        db = await aiosqlite.connect(config.bank, timeout=10)
        cursor = await db.cursor()
        await cursor.execute('SELECT "first_join" FROM main WHERE uid=?', (uid,))
        result_userID = await cursor.fetchone()
        if not result_userID:
            await self.new_account(player, uid)
        await self.update_element(
            "last_join", player, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), uid
        )

    async def discord_log(self, msg):
        channel = await self.client.fetch_channel(config.log_channel)
        await channel.send(msg)

    async def big_brother(self, msg):
        channel = await self.client.fetch_channel(config.bigbrother)
        await channel.send(msg)

    async def log_kill(self, line):
        player = line["subject"]["name"]
        team = line["subject"]["teamId"]
        uid = line["subject"]["uid"]
        victim = line["object"]["name"]
        vuid = line["object"]["uid"]
        if player == victim:
            if team == 2:
                await self.add_element("deaths_as_sur", victim, 1, uid)
            if team == 3:
                await self.add_element("deaths_as_inf", victim, 1, uid)
            return
        if team == 2:
            await self.add_element("kills_as_inf", player, 1, uid)
            await self.add_element("deaths_as_sur", victim, 1, vuid)
        if team == 3:
            await self.add_element("kills_as_sur", player, 1, uid)
            await self.add_element("deaths_as_inf", victim, 1, vuid)

    async def get_log(self):
        startTime = int(round(time.time() * 1000))
        logdir = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\logs"
        newest = sorted([f for f in os.listdir(logdir) if f.startswith("nslog")])
        with open(logdir + "\\" + newest[-1], "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
            for pp in lines:
                if "-dedicated" in pp:
                    endTime = int(round(time.time() * 1000))
                    print(
                        f"It took {endTime - startTime} ms to get the log, which is {len(lines)} lines long."
                    )
                    return lines
            return None

    async def init_playing(self):
        self.client.playing = []
        self.client.lazy_playing = []

    async def set_old(self, new):
        self.client.old = new

    async def init_old(self):
        self.client.current_log = None
        self.client.old = 0

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
                with open(
                    "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\banlist.txt",
                    "r",
                ) as f:
                    file_lines = [line.rstrip() for line in f.readlines()]
                    for line in file_lines:
                        if uid in line:
                            return
                await utils.ban(player, uid, f"message containing: {word}")
                adminrelay = self.client.get_channel(config.admin_relay)
                await adminrelay.send(
                    f"{player} has been automatically banned due to a rule breaking message:\n{message}\nMatches pattern:`{word}`\nUID: `{uid}`\nPlease review: {sent.jump_url}"
                )
                banlog = self.client.get_channel(config.ban_log)
                await banlog.send(
                    f"{player} has been automatically banned.\nReason: Rule breaking language\n{sent.jump_url}"
                )
                break


async def setup(client):
    await client.add_cog(Relay(client))
