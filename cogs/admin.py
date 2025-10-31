import difflib
import time

import aiosqlite
from discord.ext import commands

import config
from cogs.utils import utils  # this is stupid


class Admin(commands.Cog):
    """Admin only commands."""

    def __init__(self, client):
        self.client = client

    # events
    @commands.Cog.listener()
    async def on_ready(self):
        print("Admin ready")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def sync(self, ctx):
        try:
            synced = await self.client.tree.sync()
            print(f"Synced {len(synced)} commands!")
            await ctx.send(f"Synced {len(synced)} commands!")
        except Exception as e:
            print(e)
            await ctx.send(f"`{e}`")

    @commands.command(aliases=["pong"], hidden=True)
    async def ping(self, ctx):
        start = time.perf_counter()
        message = await ctx.send("Ping...")
        end = time.perf_counter()
        duration = (end - start) * 1000
        await message.edit(
            content=f"🏓 Pong!\n"
            f"API Latency: `{round(duration)}ms`\n"
            f"Websocket Latency: `{round(self.client.latency * 1000)}ms`",
        )

    @commands.command()
    @utils.is_admin()
    async def lookup(self, ctx, user):
        """Lookup a user in the database."""

        async def closest_match(name, server):
            await cursor.execute(f"SELECT name FROM {server}")
            users = await cursor.fetchall()
            good_list = []
            for shit in users:
                good_list.append(shit[0])  # tuple to array
            closest_match = difflib.get_close_matches(name, good_list, n=4, cutoff=0.3)
            await ctx.send(
                f"This player has never joined {server}! Did you type the name incorrectly? The closest matches I found were `{closest_match}`.",
            )

        if ctx.author.id not in config.admins:
            await ctx.send("no")
            return
        if user is None:
            await ctx.send("Please specify a user.")
            return
        try:
            user = int(user)
        except ValueError:
            pass
        message = ""
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            for s in config.servers:
                try:
                    if isinstance(user, str):
                        await cursor.execute(
                            f"SELECT name FROM {s.name} WHERE name = ?",
                            (user,),
                        )
                        fetched = await cursor.fetchone()
                    elif isinstance(user, int):
                        await cursor.execute(
                            f"SELECT name FROM {s.name} WHERE uid = ?",
                            (user,),
                        )
                        fetched = await cursor.fetchone()
                        uid = user
                    else:
                        await ctx.send("You should never see this message. :)")
                except aiosqlite.OperationalError:
                    if isinstance(user, str):
                        await closest_match(user, s.name)
                    elif isinstance(user, int):
                        await ctx.send("Could not find UID in database!")
                    continue
                if fetched is None and isinstance(user, str):
                    await closest_match(user, s.name)
                    continue
                if fetched is None and isinstance(user, int):
                    await ctx.send("Could not find UID in database!")
                    continue
                fetched = fetched[0]
                if isinstance(user, str):
                    await cursor.execute(
                        f"SELECT uid FROM {s.name} WHERE name = ?",
                        (user,),
                    )
                    uid = await cursor.fetchone()
                    if uid is None:
                        uid = user
                    else:
                        uid = uid[0]
                    await cursor.execute(
                        f"SELECT last_join FROM {s.name} WHERE name = ?",
                        (user,),
                    )
                    timestamp = await cursor.fetchone()
                    await cursor.execute(
                        f"SELECT first_join FROM {s.name} WHERE name = ?",
                        (user,),
                    )
                    first_join = await cursor.fetchone()
                    await cursor.execute(
                        f"SELECT playtime FROM {s.name} WHERE name = ?",
                        (user,),
                    )
                    playtime = await cursor.fetchone()
                elif isinstance(user, int):
                    await cursor.execute(
                        f"SELECT last_join FROM {s.name} WHERE uid = ?",
                        (user,),
                    )
                    timestamp = await cursor.fetchone()
                    await cursor.execute(
                        f"SELECT first_join FROM {s.name} WHERE uid = ?",
                        (user,),
                    )
                    first_join = await cursor.fetchone()
                    await cursor.execute(
                        f"SELECT playtime FROM {s.name} WHERE uid = ?",
                        (user,),
                    )
                    playtime = await cursor.fetchone()
                    await cursor.execute(
                        f"SELECT name FROM {s.name} WHERE uid = ?",
                        (user,),
                    )
                    user = await cursor.fetchone()
                    user = user[0]
                timestamp = timestamp[0]
                first_join = first_join[0]
                playtime = playtime[0]
                message += f"`{s.name}:\n{user}`:\nUID: `{uid}`\nFirst seen: `{first_join}`\nLast seen: `{timestamp}`\nPlaytime: `{await utils.human_time_duration(playtime)}`\n"
        await ctx.send(message)
        await ctx.send(await utils.get_ban_info(uid))

    @commands.hybrid_command()
    @utils.is_admin()
    async def ban(self, ctx, uid: str = "", reason: str = "", length: str = ""):
        if ctx.author.id not in config.admins:
            return await ctx.reply("naw")
        if not uid:
            return await ctx.reply("Please specify a uid!")
        async with ctx.typing():
            await utils.ban_user(uid, reason, utils.human_time_to_seconds(length))
            for server in config.servers:
                try:
                    await server.send_command("checkbans")
                except ConnectionError:
                    await ctx.reply(
                        f"couldn't tell {server.name} to update banlist! ban may be delayed for one round.",
                    )
        await ctx.send("done!")

    @commands.hybrid_command()
    @utils.is_admin()
    async def unban(self, ctx, uid: str = ""):
        if ctx.author.id not in config.admins:
            await ctx.reply("naw")
            return
        if uid == "":
            await ctx.reply("Please specify a uid!")
            return
        await utils.unban_user(uid)
        await ctx.send("ok done")

    @commands.command(aliases=["rcon"])
    @utils.is_admin()
    async def parse(self, ctx, server: str | None = None, *args):
        if (not server or not await utils.get_server(server)) and server != "all":
            return await ctx.reply("Please specify a server!")
        if server == "all":
            for s in config.servers:
                await s.send_command(" ".join(args))
            await ctx.reply("ok done")
            channel = await self.client.fetch_channel(config.bigbrother)
            await channel.send(
                f"`{ctx.author.name}` just ran `{' '.join(args)}` thru the bot to all servers",
            )
            return None
        s = await utils.get_server(server)
        if not args:
            return await ctx.reply("Please specify a command!")
        await s.send_command(" ".join(args))
        await ctx.reply("ok done")
        channel = await self.client.fetch_channel(config.bigbrother)
        await channel.send(
            f"`{ctx.author.name}` just ran `{' '.join(args)}` thru the bot to {server}",
        )

    @commands.command(aliases=["spl"], hidden=True)
    @commands.is_owner()
    async def sql(self, ctx, command: str | None = None):
        if not command:
            await ctx.send("Please provide an SQL command to run.")
            return

        await ctx.send(f"Executing: {command}")

        try:
            async with aiosqlite.connect(config.bank, timeout=10) as db:
                async with db.cursor() as cursor:
                    # Begin the transaction
                    await cursor.execute("BEGIN TRANSACTION;")

                    await cursor.execute(command)
                    result = await cursor.fetchall()
                    await ctx.send(result)

                    # Ask user if they want to commit the changes
                    await ctx.send(
                        "Do you want to commit these changes? Reply with 'yes' or 'no'.",
                    )
                    try:
                        msg = await self.client.wait_for(
                            "message",
                            check=lambda m: m.author == ctx.author
                            and m.channel == ctx.channel,
                            timeout=60,
                        )
                        if msg.content.lower() == "yes":
                            await cursor.execute("COMMIT;")
                            await ctx.send(f"Changes committed!\n{result}")
                        else:
                            await cursor.execute("ROLLBACK;")
                            await ctx.send("Changes rolled back.")
                    except TimeoutError:
                        await cursor.execute("ROLLBACK;")
                        await ctx.send("Confirmation timeout. Changes rolled back.")

        except Exception as e:
            print(e)
            await ctx.send(f"Error: {e!s}")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def audit(self, ctx):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            for s in config.servers:
                for uid in config.admin_uids:
                    await cursor.execute(
                        f"SELECT name FROM {s.name} WHERE uid = ?",
                        (uid,),
                    )
                    name = await cursor.fetchone()
                    name = name[0]
                    await cursor.execute(
                        f"SELECT last_join FROM {s.name} WHERE uid = ?",
                        (uid,),
                    )
                    last_join = await cursor.fetchone()
                    last_join = last_join[0]
                    await cursor.execute(
                        f"SELECT playtime FROM {s.name} WHERE uid = ?",
                        (uid,),
                    )
                    playtime = await cursor.fetchone()
                    playtime = await utils.human_time_duration(playtime[0])
                    await ctx.send(
                        f"{name}:\nLast seen: `{last_join}`\nPlaytime: `{playtime}`",
                    )

    # @commands.command(aliases=["defcon"])
    # @utils.is_admin()
    # async def whitelistmode(self, ctx, mode: int = None):
    #     date_format = "%Y-%m-%d %H:%M:%S"
    #     whitelist_file = "C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\save_data\Whitelist\whitelist.txt"
    #     whitelist_on = "C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\save_data\Whitelist\whitelist_on.txt"
    #     if mode is None:
    #         with open(whitelist_file, "r") as f:
    #             lines = f.readlines()
    #         await ctx.send(f"We are currently at **DEFCON {self.client.whitelist}**\nWhitelist contains `{len(lines)}` users.")
    #         return
    #     if mode == 5:
    #         with open(whitelist_on, "w") as f:
    #             f.write("0")
    #         with open(whitelist_file, "w") as f:
    #             f.write("")
    #         await ctx.send("whitelist off and recent crashes cleared, thank fuck")
    #         self.client.crash_handler.crashes = []
    #         self.client.whitelist = 5
    #         return
    #     elif mode == 4:
    #         with open(whitelist_on, "w") as f:
    #             f.write("1")
    #         async with ctx.typing():
    #             async with aiosqlite.connect(config.bank, timeout=10) as db:
    #                 cursor = await db.cursor()
    #                 await cursor.execute("SELECT uid FROM main")
    #                 uids = await cursor.fetchall()
    #                 with open(whitelist_file, "w") as f:
    #                     for uid in uids:
    #                         uid = uid[0]
    #                         f.write(f"{uid}\n")
    #             await ctx.send("Of fucking course, ok anyone who has ever joined the server ever is now whitelisted.")
    #             self.client.whitelist = 4
    #     elif mode == 3:
    #         with open(whitelist_on, "w") as f:
    #             f.write("1")
    #         async with ctx.typing():
    #             async with aiosqlite.connect(config.bank, timeout=10) as db:
    #                 cursor = await db.cursor()
    #                 await cursor.execute("SELECT * FROM main")
    #                 uids = await cursor.fetchall()
    #                 with open(whitelist_file, "w") as f:
    #                     for uid in uids:
    #                         last_join = datetime.strptime(uid[8], date_format)
    #                         first_join = datetime.strptime(uid[7], date_format)
    #                         if last_join > (datetime.now() - relativedelta(months=1)) and first_join < (datetime.now() - relativedelta(weeks=1)):
    #                             f.write(f"{uid[2]}\n")
    #             await ctx.send("well shit, everyone who has joined within the last month, and was first seen at least 1 week ago, is now whitelisted.")
    #             self.client.whitelist = 3
    #     elif mode == 2:
    #         with open(whitelist_on, "w") as f:
    #             f.write("1")
    #         async with ctx.typing():
    #             async with aiosqlite.connect(config.bank, timeout=10) as db:
    #                 cursor = await db.cursor()
    #                 await cursor.execute("SELECT titanfallID FROM connection")
    #                 uids = await cursor.fetchall()
    #                 with open(whitelist_file, "w") as f:
    #                     for uid in uids:
    #                         uid = uid[0]
    #                         f.write(f"{uid}\n")
    #             await ctx.send("jeez ok, everyone who has a linked account can join")
    #             self.client.whitelist = 2
    #     elif mode == 1:
    #         with open(whitelist_on, "w") as f:
    #             f.write("1")
    #         with open(whitelist_file, "w") as f:
    #             f.write(f"{secrets.randbelow(1000)}") # Random fake uid in case uid spoofing is a thing again, needed because whitelist mod will turn off with nothing in whitelist
    #         await ctx.send("we're officially at DEFCON 1, no one is whitelisted, may god save our souls.")
    #         self.client.whitelist = 1
    #     else:
    #         await ctx.reply("Please specify a valid mode. This follows the DEFCON system, so 5 is no whitelist and 1 is nuclear war.")
    #     with open(whitelist_file, "r") as f:
    #         lines = f.readlines()
    #     await asyncio.sleep(1)
    #     await ctx.send(f"Whitelist now contains `{len(lines)}` users.\nReminder: You may use `,.whitelistadd (uid)` and ``,.whitelistremove (uid)` to manually add or remove users from the whitelist.")

    # @commands.command(aliases=["whitelist"])
    # @utils.is_admin()
    # async def whitelistadd(self, ctx, uid):
    #     whitelist_file = "C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\save_data\Whitelist\whitelist.txt"
    #     with open(whitelist_file, "a+") as f:
    #         f.write(f"{uid}\n")
    #     await ctx.send(f"`{uid}` has been added to the whitelist.")

    # @commands.command(aliases=["unwhitelist"])
    # @utils.is_admin()
    # async def whitelistremove(self, ctx, uid):
    #     whitelist_file = "C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\save_data\Whitelist\whitelist.txt"
    #     with open(whitelist_file, "r") as f:
    #         lines = f.readlines()
    #     with open(whitelist_file, "w") as f:
    #         for line in lines:
    #             if line != f"{uid}\n":
    #                 f.write(line)
    #     await ctx.send(f"`{uid}` has been removed from the whitelist.")

    @commands.command()
    @utils.is_admin()
    async def forcelink(self, ctx, did, uid):
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute(
                "INSERT INTO connection(discordID, titanfallID) VALUES(?, ?)",
                (did, uid),
            )
            await db.commit()
            await ctx.send("ok done")

    # @commands.command()
    # @commands.is_owner()
    # async def parkour(self, ctx):
    #     return

    # @commands.group(invoke_without_command=True)
    # @commands.has_permissions(manage_messages=True)
    # async def automod(self, ctx):
    #     """Basic Automod"""
    #     await ctx.send(
    #         "This is a barebones automod command which utilizes regex. Available sub commands: `create`, `remove`, `list`, `edit`, `report`"
    #     )

    # @automod.command(name="create")
    # async def automod_create(self, ctx):
    #     return


async def setup(client):
    await client.add_cog(Admin(client))
