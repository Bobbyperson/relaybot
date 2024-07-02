import discord
import time
from discord.ext import commands
import aiosqlite
import config
import secrets
import cogs.utils.utils as utils # this is stupid
import asyncio
# import cogs.utils.crashes as crashes



class Stats(commands.Cog):
    """Main group of commands for stat tracking."""
    def __init__(self, client):
        self.client = client

    # events
    @commands.Cog.listener()
    async def on_ready(self):
        print("Stats ready")
        
    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            await member.send("Welcome to the awesome titanfall server! I am a stat tracking bot you can use to see all of your kills, deaths, games played, etc, but you need to link your titanfall and discord accounts first. Run `,.link <your titanfall name>` in the server to get started! My prefix is `,.` and my commands can be seen with `,.help`.")
            # if self.client.whitelist != 5:
                # await member.send("The server is currently being affected by a targeted attack, and thus is temporarily whitelist only. If you wish to be whitelisted, please contact an admin. Sorry for the inconvenience, and thank you for your patience")
        except discord.Forbidden:
            pass
        
    @commands.hybrid_command()
    async def playtime(self, ctx, name: str = None):
        """Get a user's playtime."""
        name = await utils.get_name_from_connection(ctx.author.id) if name is None else name
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            message = f"{name}'s playtime:\n"
            for s in config.servers:
                await cursor.execute(f"SELECT playtime FROM {s.name} WHERE name = ?", (name,))
                playtime = await cursor.fetchone()
                if playtime is None:
                    await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
                    return
                playtime = playtime[0]
                message += f"{s.name}: {await utils.human_time_duration(playtime)}\n"
        await ctx.send(message)


    @commands.hybrid_command()
    async def online(self, ctx, server: str = None):
        """See who's online."""
        if not server or not await utils.is_valid_server(server):
            return await ctx.send("Invalid server.")
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            message = "this is in BETA and might not be accurate! please check #server-stats for a 100% accurate player count.\n```\n"
            playing = self.client.playing[server] if self.client.playing[server] > self.client.lazy_playing[server] else self.client.lazy_playing[server]
            if len(playing) == 0:
                message += "nobody```"
                await ctx.send(message)
                return
            for uid in playing:
                await cursor.execute(f"SELECT name FROM {server} WHERE uid = ?", (uid[0],))
                result = await cursor.fetchone()
                message += result[0] + "\n" if result is not None else "USER NOT FOUND" + "\n"
            message += f"```\nTotal: {len(playing)} players"
            await ctx.send(message)


    @commands.hybrid_command()
    async def playtimeboard(self, ctx, server: str = None):
        """See who has the most playtime."""
        if not server or not await utils.is_valid_server(server):
            return await ctx.send("Invalid server.")
        amount = 10
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute(f"SELECT * FROM {server} ORDER BY playtime DESC")
            users = await cursor.fetchall()
            em = discord.Embed(title=f"Top {amount} Playtime", color=ctx.author.color)
            index = 0
            for user in users:
                if index == amount:
                    break
                index += 1
                username = user[1]
                playtime = user[9]
                em.add_field(
                    name=f"{index}. {username}",
                    value=f"{await utils.human_time_duration(playtime)}",
                    inline=False,
                )
            await ctx.send(embed=em)
        
    @commands.hybrid_command()
    async def firstinfectedboard(self, ctx):
        """See the leaderboard based on the ratio of first infected to games played."""
        amount = 10
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()

            # Filter out users with one or two games played and order results by the division of firstinfected by gamesplayed and by gamesplayed desc, handle division by zero.
            await cursor.execute("""
            SELECT *, CASE WHEN gamesplayed = 0 THEN 0 ELSE firstinfected * 1.0 / gamesplayed END AS ratio 
            FROM main 
            WHERE gamesplayed > 9
            ORDER BY ratio DESC, gamesplayed DESC
            """)
            users = await cursor.fetchall()

            em = discord.Embed(title=f"Top {amount} First Infected Chances", color=ctx.author.color)
            index = 0
            for user in users:
                if index == amount:
                    break
                index += 1
                username = user[1]
                ratio = user[-1]  # Assuming the ratio is the last column after our addition.
                em.add_field(
                    name=f"{index}. {username}",
                    value=f"{(ratio * 100):.2f}% {user[13]}/{user[14]}",  # Display ratio up to two decimal places.
                    inline=False,
                )

            await ctx.send(embed=em)


    @commands.hybrid_command()
    async def info(self, ctx):
        """See general server info."""
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT COUNT(*) FROM main")
            users = await cursor.fetchone()
            users = users[0]
            await cursor.execute("SELECT sum(kills_as_inf) FROM main")
            total_kills = await cursor.fetchone()
            total_kills = total_kills[0]
            await cursor.execute("SELECT sum(kills_as_sur) FROM main")
            survivor_kills = await cursor.fetchone()
            total_kills += survivor_kills[0]
            await ctx.send(
                f"A total of {await utils.commafy(users)} players have joined the server as of September 26th, 2022\nThere have been a combined total of {await utils.commafy(total_kills)} kills amongst all players."
            )

        
    @commands.command(hidden=True)
    @commands.is_owner()
    async def checkdifference(self, ctx):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT sum(kills_as_inf) FROM main")
            total_kills = await cursor.fetchone()
            total_kills = total_kills[0]
            await cursor.execute("SELECT sum(kills_as_sur) FROM main")
            survivor_kills = await cursor.fetchone()
            total_kills += survivor_kills[0]
            await cursor.execute("SELECT COUNT(*) AS total_rows FROM killLog WHERE action <> 2 AND killer <> victim")
            total_logged_kills = await cursor.fetchone()
            total_logged_kills = total_logged_kills[0]
            total_suicides = await cursor.execute("SELECT COUNT(*) AS total_rows FROM killLog WHERE action = 2 OR killer = victim")
            await ctx.send(f"Total kills in main: {total_kills}\nTotal kills in killLog: {total_logged_kills}\nTotal suicides: {total_suicides}\nUnlogged kills: {total_kills - total_logged_kills - total_suicides}")
            await cursor.execute(f"SELECT * FROM killLog WHERE num = {1000000 - total_logged_kills}")
            theinfo = await cursor.fetchall()
            await ctx.send(theinfo[0])
        
    @commands.command()
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def killnumber(self, ctx, number: int = 0, server: str = None):
        if server is None or not await utils.is_valid_server(server):
            return await ctx.send("Please provide a valid server.")
        if server == "infection":
            if number < 1:
                await ctx.send("Please provide a number greater than 0.")
                return
            if number < 151090:
                await ctx.send("Unfortunately, we did not start logging individual kills until kill number 151090. Please try a number greater than 151090.")
                return
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute(f"SELECT sum(kills_as_inf) FROM {server}")
            total_kills = await cursor.fetchone()
            total_kills = total_kills[0]
            await cursor.execute(f"SELECT sum(kills_as_sur) FROM {server}")
            survivor_kills = await cursor.fetchone()
            total_kills += survivor_kills[0]
            await cursor.execute(f"SELECT COUNT(*) AS total_rows FROM {server}_kill_log WHERE action <> 2 AND killer <> victim")
            total_killLog_kills = await cursor.fetchone()
            total_killLog_kills = total_killLog_kills[0]
            await cursor.execute(f"SELECT COUNT(*) AS total_rows FROM {server}_kill_log WHERE action = 2 OR killer = victim")
            total_suicides = await cursor.fetchone()
            total_suicides = total_suicides[0]
            missing_kills = total_kills - total_killLog_kills
            offset = number - missing_kills - 1
            if offset < 0:
                await ctx.send("This kill number is not logged. Either it hasn't happened yet, or happened before we started logging individual kills.")
                return
            await cursor.execute(f"SELECT * FROM {server}_kill_log WHERE action <> 2 AND killer <> victim ORDER BY num ASC LIMIT 1 OFFSET {offset}")
            onemilkill = await cursor.fetchall()
            if onemilkill is not None:
                onemilkill = onemilkill[0]
                action = "killed" if onemilkill[2] == 0 else "infected"
                await cursor.execute(f"SELECT name FROM {server} WHERE uid = ?", (onemilkill[1],))
                fetched = await cursor.fetchone()
                killer_name = fetched[0]
                await cursor.execute(f"SELECT name FROM {server} WHERE uid = ?", (onemilkill[3],))
                fetched = await cursor.fetchone()
                victim_name = fetched[0]
                timestamp = onemilkill[4]
                await ctx.send(f"Kill number {number}:\n{killer_name} {action} {victim_name} at <t:{timestamp}:f>")
            else:
                await ctx.send("This kill number is not logged. Either it hasn't happened yet, or happened before we started logging individual kills.")        


    @commands.hybrid_command()
    async def kd(self, ctx, name: str = None, server = None):
        """Get a user's KD."""
        name = await utils.get_name_from_connection(ctx.author.id) if name is None else name
        valid_servers = await utils.get_valid_server_names()
        if server not in valid_servers:
            return await ctx.send(f"Please specify a valid server. Valid servers are {', '.join(valid_servers)}")
        try:
            killsmilitia = await utils.get_row("killsmilitia", "name", name, server)

            killsimc = await utils.get_row("killsimc", "name", name, server)

            deathsimc = await utils.get_row("deathsimc", "name", name, server)

            deathsmilitia = await utils.get_row("deathsmilitia", "name", name, server)

        except aiosqlite.OperationalError:
            await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
            return

        # Handle zero deaths case
        deathsimc = deathsimc if deathsimc != 0 else 1
        deathsmilitia = deathsmilitia if deathsmilitia != 0 else 1
        
        if server == "infection":
            await ctx.reply(
                f"{name}:\nSurvivor: `{killsmilitia/deathsmilitia:.2f} ({killsmilitia}:{deathsmilitia})`\nInfected: `{killsimc/deathsimc:.2f} ({killsimc}:{deathsimc})`"
            )
        else:
            await ctx.reply(
                f"{name}: {(killsmilitia + killsimc)/(deathsmilitia + deathsimc):.2f} ({killsmilitia + killsimc}:{deathsmilitia + deathsimc})"
            )

    @commands.hybrid_command()
    async def killed(self, ctx, user1, user2, server = None):
        """See how many times two people have killed each other."""
        if not user1 or not user2:
            return await ctx.send("Please specify two users.")
        if not server or await utils.get_valid_server_names() is None:
            return await ctx.send("Please specify a valid server.")
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()

            await cursor.execute(f"SELECT uid FROM {server} WHERE name=?", (user1,))
            killer = await cursor.fetchone()
            killer = killer[0]

            await cursor.execute(f"SELECT uid FROM {server} WHERE name=?", (user2,))
            victim = await cursor.fetchone()
            victim = victim[0]

            if killer is None or victim is None:
                await ctx.send("One or neither of these people exist!")
                return

            await cursor.execute(
                "SELECT count(*) FROM killLog WHERE killer=? AND victim=? AND action=0",
                (killer, victim),
            )
            user1KillsAsSurvivor = await cursor.fetchone()
            user1KillsAsSurvivor = user1KillsAsSurvivor[0]

            await cursor.execute(
                "SELECT count(*) FROM killLog WHERE killer=? AND victim=? AND action=1",
                (killer, victim),
            )
            user1KillsAsInfected = await cursor.fetchone()
            user1KillsAsInfected = user1KillsAsInfected[0]

            await cursor.execute(
                "SELECT count(*) FROM killLog WHERE killer=? AND victim=? AND action=0",
                (victim, killer),
            )
            user2KillsAsSurvivor = await cursor.fetchone()
            user2KillsAsSurvivor = user2KillsAsSurvivor[0]

            await cursor.execute(
                "SELECT count(*) FROM killLog WHERE killer=? AND victim=? AND action=1",
                (victim, killer),
            )
            user2KillsAsInfected = await cursor.fetchone()
            user2KillsAsInfected = user2KillsAsInfected[0]

            await ctx.send(
                f"{user1} has killed {user2} {user1KillsAsSurvivor} times as a survivor.\n{user2} has killed {user1} {user2KillsAsSurvivor} times as a survivor.\n{user1} has killed {user2} {user1KillsAsInfected} times as an infected.\n{user2} has killed {user1} {user2KillsAsInfected} times as an infected."
            )


    @commands.hybrid_command()
    async def killboard(self, ctx, server: str = None, team: str = None):
        """See who has the most kills on a team."""
        if team != "survivor" and team != "infected" and server == "infection":
            await ctx.send("Error! Please specify team.")
            return
        showteam = team
        if team == "survivor":
            team = "militia"
        if team == "infected":
            team = "imc"
        amount = 10
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            if server == "infection":
                await cursor.execute(f"SELECT * FROM {server} ORDER BY kills{team} DESC")
            else:
                await cursor.execute(f"SELECT * FROM {server} ORDER BY kills{team} DESC")
            users = await cursor.fetchall()
            if server == "infection":
                em = discord.Embed(
                    title=f"Top {amount} Kills as {showteam}", color=ctx.author.color
                )
            else:
                em = discord.Embed(
                    title=f"Top {amount} Kills", color=ctx.author.color
                )
            index = 0
            for user in users:
                if index == amount:
                    break
                index += 1
                username = user[1]
                if server == "infection":
                    if team == "inf":
                        kills = user[3]
                    if team == "sur":
                        kills = user[4]
                else:
                    kills = user[3] + user[4]
                em.add_field(name=f"{index}. {username}", value=f"{kills}", inline=False)
            await ctx.send(embed=em)

    @commands.hybrid_command()
    async def killstreakboard(self, ctx, server: str = None):
        """See who has the highest killstreak."""
        if not server or not await utils.is_valid_server(server):
            return await ctx.send("Error! Please specify server.")
        amount = 10
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute(f"SELECT * FROM {server} ORDER BY killstreak DESC")
            users = await cursor.fetchall()
            em = discord.Embed(title=f"Top {amount} Killstreaks", color=ctx.author.color)
            index = 0
            for user in users:
                if index == amount:
                    break
                index += 1
                username = user[1]
                kills = user[10]
                em.add_field(name=f"{index}. {username}", value=f"{kills}", inline=False)
            await ctx.send(embed=em)

    # rarely used, needs update
    # @commands.hybrid_command()
    # async def deathboard(self, ctx, team: str = None):
    #     """See who has the most deaths on a team."""
    #     if team.lower() != "survivor" and team.lower() != "infected":
    #         await ctx.send("Error! Please specify team. `survivor` or `infected`")
    #         return
    #     team = team.lower()
    #     showteam = team
    #     if team == "survivor":
    #         team = "sur"
    #     elif team == "infected":
    #         team = "inf"
    #     amount = 10
    #     async with aiosqlite.connect(config.bank, timeout=10) as db:
    #         cursor = await db.cursor()
    #         await cursor.execute(f"SELECT * FROM main ORDER BY deaths_as_{team} DESC")
    #         users = await cursor.fetchall()
    #         em = discord.Embed(
    #             title=f"Top {amount} Deaths as {showteam}", color=ctx.author.color
    #         )
    #         index = 0
    #         for user in users:
    #             if index == amount:
    #                 break
    #             index += 1
    #             username = user[1]
    #             if team == "inf":
    #                 kills = user[5]
    #             elif team == "sur":
    #                 kills = user[6]
    #             em.add_field(name=f"{index}. {username}", value=f"{kills}", inline=False)
    #         await ctx.send(embed=em)


    @commands.hybrid_command(aliases=["ks", "kys", "killstreak"])
    async def highestkillstreak(self, ctx, name: str = None, server: str = None):
        """See someone's highest killstreak."""
        if not server or not await utils.is_valid_server(server):
            return await ctx.send("Error! Please specify server.")
        name = await utils.get_name_from_connection(ctx.author.id) if name is None else name
        if name is None:
            await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
            return

        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()

            # Use a parameterized query for the SELECT statements
            await cursor.execute(f'SELECT "killstreak" FROM {server.name} WHERE name=?', (name,))
            killstreak = await cursor.fetchone()
            if killstreak is None:
                await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
                return
            await ctx.reply(f"{name}: {killstreak[0]}")
        
    @commands.hybrid_command()
    async def firstinfected(self, ctx, name: str = None):
        """See how many times someone has been first infected."""
        name = await utils.get_name_from_connection(ctx.author.id) if name is None else name
        if name is None:
            await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
            return

        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()

            # Use a parameterized query for the SELECT statements
            await cursor.execute('SELECT "firstinfected" FROM infection WHERE name=?', (name,))
            killstreak = await cursor.fetchone()
            if killstreak is None:
                await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
                return
            await ctx.reply(f"{name}: {killstreak[0]}")

    @commands.hybrid_command()
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def link(self, ctx, name: str = None):
        """Link your titanfall and discord"""
        if name is None:
            await ctx.reply("Please provide a titanfall name!")
            return
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            did = ctx.author.id
            name_exists = False
            for s in config.servers:
                await cursor.execute(f"SELECT name FROM {s.name} WHERE name = ?", (name,))
                name_exists = True if await cursor.fetchone() is not None else False
                if name_exists:
                    break
            if not name_exists:
                return await ctx.send("User not found. Names are case sensitive.")
            # get uid
            await cursor.execute(f"SELECT uid FROM {s.name} WHERE name = ?", (name,))
            uid = await cursor.fetchone()
            uid = uid[0] if uid is not None else None
            if uid is None:
                await ctx.send("User not found. Names are case sensitive.")
                return
            
            await cursor.execute("SELECT titanfallID from connection WHERE titanfallID = ?", (uid,))
            uid_exists = True if await cursor.fetchone() is not None else False
            if uid_exists:
                await ctx.send("This titanfall account is already linked to a discord account.")
                return
            
            await cursor.execute("SELECT discordID from connection WHERE discordID = ?", (did,))
            did_exists = True if await cursor.fetchone() is not None else False
            if did_exists:
                await ctx.send("This discord account is already linked to a titanfall account.")
                return
            auth_code = secrets.randbits(20) # theres a fringe chance that someone will get the same code as someone else but i dont care
            try:
                await ctx.author.send(f"Your code is: `{auth_code}`\nPlease paste it into the in-game titanfall chat without any spaces or other characters.")
            except discord.Forbidden:
                await ctx.reply("I can't DM you! Please enable DMs from server members and try again.")
                return
            await ctx.reply("Please check your DMs for a code and paste it into the in-game titanfall chat.")
        self.client.auth[auth_code] = {
            "name": name,
            "confirmed": False
        }
        unix = int(time.time())
        while not self.client.auth[auth_code]["confirmed"] and int(time.time()) < unix + 300:
            await asyncio.sleep(1)
        if self.client.auth[auth_code]["confirmed"]:
            async with aiosqlite.connect(config.bank, timeout=10) as db:
                cursor = await db.cursor()
                await cursor.execute("INSERT INTO connection(discordID, titanfallID) VALUES(?, ?)", (did, uid))
                await ctx.reply("Successfully linked your titanfall and discord accounts!")
                await db.commit()
        else:
            await ctx.reply("Code expired. Please try again.")
        del self.client.auth[auth_code]
        
    @commands.hybrid_command()
    async def unlink(self, ctx):
        """Unlink your titanfall and discord"""
        await ctx.send("Are you absolutely sure you want to unlink your titanfall and discord accounts? You can relink them at any time with `,link`.\nType `yes` to confirm.")
        try:
            msg = await self.client.wait_for('message', timeout=30.0, check=lambda message: message.author == ctx.author and message.channel == ctx.channel)
        except asyncio.TimeoutError:
            await ctx.reply("Cancelled.")
            return
        if msg.content is not None:
            if msg.content.lower() == "yes":
                async with aiosqlite.connect(config.bank, timeout=10) as db:
                    cursor = await db.cursor()
                    did = ctx.author.id
                    await cursor.execute("SELECT discordID FROM connection WHERE discordID = ?", (did,))
                    did_exists = True if await cursor.fetchone() is not None else False
                    if not did_exists:
                        await ctx.send("This discord account is not linked to a titanfall account.")
                        return
                    await cursor.execute("DELETE FROM connection WHERE discordID = ?", (did,))
                    await ctx.reply("Successfully unlinked your titanfall and discord accounts!")
                    await db.commit()
            else:
                await ctx.reply("Cancelled.")
                return
                
    @commands.hybrid_command()
    async def whois(self, ctx, name: discord.Member = None):
        """Get the titanfall account linked to a discord account."""
        if name is None:
            name = ctx.author
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT titanfallID FROM connection WHERE discordID = ?", (name.id,))
            uid = await cursor.fetchone()
            uid = uid[0] if uid is not None else None
            if uid is None:
                await ctx.send("This discord account is not linked to a titanfall account.")
                return
            titan_name = await utils.get_name_from_connection(uid)
            if titan_name is None:
                await ctx.send("Something catastrophic has happened. Ping bobby.")
                return
            await ctx.send(f"{name.name} is linked to {titan_name}.")
        
    @commands.hybrid_command()
    async def gamesplayed(self, ctx, name: str = None, server: str = None):
        """See how many games someone has played."""
        name = await utils.get_name_from_connection(ctx.author.id) if name is None else name
        if not server or not await utils.check_server(ctx, server):
            return await ctx.send("Please specify a valid server.")
        if name is None:
            await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
            return

        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()

            # Use a parameterized query for the SELECT statements
            await cursor.execute(f'SELECT "gamesplayed" FROM {server} WHERE name=?', (name,))
            gamesplayed = await cursor.fetchone()
            if gamesplayed is None:
                await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
                return
            await ctx.reply(f"{name}: {gamesplayed[0]}")
            
    
    # sucks
    # @commands.hybrid_command(aliases=["unlucky", "unluckiest", "fic"])
    # async def firstinfectedchance(self, ctx, name: str = None):
    #     """See someone's propensity for being first infected."""
    #     name = await utils.get_name_from_connection(ctx.author.id) if name is None else name
    #     if name is None:
    #         await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
    #         return

    #     async with aiosqlite.connect(config.bank, timeout=10) as db:
    #         cursor = await db.cursor()

    #         # Use a parameterized query for the SELECT statements
    #         await cursor.execute('SELECT "firstinfected" FROM main WHERE name=?', (name,))
    #         firstinfected = await cursor.fetchone()
    #         firstinfected = firstinfected[0] if firstinfected is not None else None
    #         await cursor.execute('SELECT "gamesplayed" FROM main WHERE name=?', (name,))
    #         gamesplayed = await cursor.fetchone()
    #         gamesplayed = gamesplayed[0] if gamesplayed is not None else None
    #         if firstinfected is None or gamesplayed is None:
    #             await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
    #             return
    #         gamesplayed = gamesplayed if gamesplayed != 0 else 1 # handle 0 games played
    #         await ctx.reply(f"{name}: `{((firstinfected/gamesplayed)*100):.2f}% ({firstinfected}/{gamesplayed})`")
    
    
    # needs heavy work & a glow-up tbh... get inspo from nocaro 
#     @commands.hybrid_command(hidden=True)
#     async def profile(self, ctx, name: str = None):
#         """See someone's profile."""
#         name = await utils.get_name_from_connection(ctx.author.id) if name is None else name
#         if name is None:
#             await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
#             return

#         async with aiosqlite.connect(config.bank, timeout=10) as db:
#             cursor = await db.cursor()

#             # Use a parameterized query for the SELECT statements
#             await cursor.execute('SELECT * FROM main WHERE name=?', (name,))
#             profile = await cursor.fetchone()
#             if profile is None:
#                 await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
#                 return
#             await ctx.reply(f"""
# {profile[1]}:
# Survivor kills: {profile[4]}
# Survivor deaths: {profile[6]}
# Infected kills: {profile[3]}
# Infected deaths: {profile[5]}
# Highest Killstreak: {profile[10]}
# Times first infected: {profile[13]}
# Games played: {profile[14]}
# Playtime: {await utils.human_time_duration(profile[9])}""")
        
    @commands.hybrid_command()
    async def amiwhitelisted(self, ctx, name: str = None):
        return await ctx.send("The whitelist has been deprecated for now.")
        if self.client.whitelist == 5:
            await ctx.send("The whitelist does not appear to be on at this time. You should be able to join the server.\n**Remember: to ensure you're whitelisted, please `,.link` your account.**")
            return
        name = await utils.get_name_from_connection(ctx.author.id) if name is None else name
        if name is None:
            await ctx.send("User not found. Either you are not `,.link`ed or you mistyped a name. Names are case sensitive.")
            return
        uid = await utils.get_uid_from_name(name)
        with open("C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\save_data\Whitelist\whitelist.txt", "r") as f:
            if str(uid) in f.readlines():
                await ctx.send("You are whitelisted!")
                return
            else:
                await ctx.send("You are not whitelisted. Please contact an admin to get whitelisted.")
                return
            
async def setup(client):
    await client.add_cog(Stats(client))
