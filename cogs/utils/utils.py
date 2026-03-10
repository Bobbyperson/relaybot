import time
from datetime import datetime

import aiosqlite
import humanize
from discord.ext import commands

# async def human_time_duration(seconds):
#     TIME_DURATION_UNITS = (
#         ("week", 60 * 60 * 24 * 7),
#         ("day", 60 * 60 * 24),
#         ("hour", 60 * 60),
#         ("minute", 60),
#         ("second", 1),
#     )
#     if seconds == 0:
#         return "No playtime recorded. This user has not played since 9/5/2023!"
#     parts = []
#     for unit, div in TIME_DURATION_UNITS:
#         amount, seconds = divmod(int(seconds), div)
#         if amount > 0:
#             parts.append("{} {}{}".format(amount, unit, "" if amount == 1 else "s"))
#     return ", ".join(parts)


async def human_time_duration(seconds: int) -> str:
    return f"{(seconds / 60 / 60):.1f} hours"


def is_admin() -> bool:
    return commands.check(lambda ctx: ctx.author.id in ctx.bot.config["admins"]["discord_ids"])


async def commafy(num: int) -> str:
    return format(num, ",d")


async def get_uid_from_connection(bot, did):
    async with aiosqlite.connect(bot.config["bot"]["bank"], timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute(
            "SELECT titanfallID FROM connection WHERE discordID = (?)",
            (did,),
        )
        uid = await cursor.fetchone()
        return uid[0] if uid else None


async def get_name_from_connection(bot, did) -> str | None:
    async with aiosqlite.connect(bot.config["bot"]["bank"], timeout=10) as db:
        cursor = await db.cursor()
        uid = await get_uid_from_connection(bot, did)
        for s in bot.servers:
            await cursor.execute(f"SELECT name FROM {s.name} WHERE uid = (?)", (uid,))
            name = await cursor.fetchone()
            if name:
                return name[0]
        return None


async def get_discord_id_user_from_connection(bot, uid):
    async with aiosqlite.connect(bot.config["bot"]["bank"], timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute(
            "SELECT discordID FROM connection WHERE titanfallID = (?)",
            (uid,),
        )
        did = await cursor.fetchone()
        return did[0] if did else None


async def get_uid_from_name(bot, name: str | None = None) -> int | None:
    async with aiosqlite.connect(bot.config["bot"]["bank"], timeout=10) as db:
        cursor = await db.cursor()
        for s in bot.servers:
            await cursor.execute(f"SELECT uid FROM {s.name} WHERE name = (?)", (name,))
            uid = await cursor.fetchone()
            if uid:
                return uid[0]
        return None


async def is_valid_server(bot, server: str | None = None) -> bool:
    for s in bot.servers:
        if server == s.name:
            return True
    for s in bot.tournament_servers:
        if server == s.name:
            return True
    return False


async def check_server_auth(bot, server: str | None = None, auth: str | None = None) -> bool:
    for s in bot.servers:
        if server == s.name:
            return auth == s.key
    for s in bot.tournament_servers:
        if server == s.name:
            return auth == s.key
    return False


async def get_server(bot, server):
    for s in bot.servers:
        if server == s.name:
            return s
    for s in bot.tournament_servers:
        if server == s.name:
            return s
    return None


async def get_row(bot, name, condition, value, table):
    async with aiosqlite.connect(bot.config["bot"]["bank"], timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute(
            f"SELECT {name} FROM {table} WHERE {condition} = (?)",
            (value,),
        )
        result = await cursor.fetchone()
        return result[0] if result else None


async def update_row(bot, name, new_value, condition, cvalue, table):
    async with aiosqlite.connect(bot.config["bot"]["bank"], timeout=10) as db:
        await db.execute(
            f"UPDATE {table} SET {name} = ? WHERE {condition} = ?",
            (new_value, cvalue),
        )
        await db.commit()


async def get_valid_server_names(bot) -> list:
    return [s.name for s in bot.servers]


async def check_server_ip(server: str | None = None, ip: str | None = None) -> bool:
    # for s in config.servers:
    #     if server == s.name:
    #         return ip == s.ip
    # for s in config.tournament_servers:
    #     if server == s.name:
    #         return ip == s.ip
    # return False
    return True


async def is_linked(bot, did) -> bool:
    async with aiosqlite.connect(bot.config["bot"]["bank"], timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute(
            "SELECT discordID FROM connection WHERE discordID = (?)",
            (did,),
        )
        uid = await cursor.fetchone()
        return bool(uid)


async def is_tournament_server(bot, server: str | None = None) -> bool:
    for s in bot.tournament_servers:
        if server == s.name:
            return True
    return False


def human_time_to_seconds(*args) -> int:
    if not args or len(args) == 0 or args[0] == "0" or args[0] == "":
        return 0

    if len(args) == 1:
        time = args[0]
        unit = time[-1]
        try:
            value = float(time[:-1])
        except ValueError:
            return -1

        match unit:
            case "m":
                return int(value * 60)
            case "h":
                return int(value * 60 * 60)
            case "d":
                return int(value * 60 * 60 * 24)
            case "w":
                return int(value * 60 * 60 * 24 * 7)
            case "M":
                return int(value * 60 * 60 * 24 * 30)
            case "y":
                return int(value * 60 * 60 * 24 * 365)
            case "_":
                return int(value)

    value = 0
    for i, arg in enumerate(args):
        if i == 0:
            try:
                time = float(arg)
            except ValueError:
                return -1
            continue

        match arg:
            case "s" | "second" | "seconds" | "sec":
                value += float(time)
            case "m" | "minute" | "minutes" | "min":
                value += float(time) * 60
            case "h" | "hour" | "hours" | "hr" | "hrs":
                value += float(time) * 60 * 60
            case "d" | "day" | "days":
                value += float(time) * 60 * 60 * 24
            case "w" | "week" | "weeks":
                value += float(time) * 60 * 60 * 24 * 7
            case "M" | "month" | "months":
                value += float(time) * 60 * 60 * 24 * 30
            case "y" | "year" | "years":
                value += float(time) * 60 * 60 * 24 * 365

    return int(value)


async def get_ban_info(bot, uid):
    async with aiosqlite.connect(bot.config["bot"]["bank"], timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute("SELECT * FROM banned WHERE uid = (?)", (uid,))
        ban_info = await cursor.fetchall()
        times_banned = len(ban_info)
        is_banned = False
        reason = "None"
        expires = "None"
        async with aiosqlite.connect(bot.config["bot"]["bank"]) as db:
            async with db.execute("SELECT * FROM banned WHERE uid=?", (uid,)) as cursor:
                # uid, reason, expires (datetime object)
                fetched = await cursor.fetchall()
                if fetched:
                    for row in fetched:
                        reason = row[2] or "Not listed"
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
                        is_banned = True
                        break

        ban_info = f"Banned: {is_banned}\nTimes Banned: {times_banned}\nReason for current ban: {reason}\nExpires: {expires}"
        return ban_info


async def ban_user(bot, uid, reason="", expires=""):
    if expires:
        expires = datetime.fromtimestamp(int(time.time()) + expires).strftime(
            "%Y-%m-%d %H:%M:%S",
        )
    else:
        expires = ""
    async with aiosqlite.connect(bot.config["bot"]["bank"], timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute(
            "INSERT INTO banned(uid, reason, expire_date) VALUES(?, ?, ?)",
            (uid, reason, expires),
        )
        await db.commit()


async def unban_user(bot, uid):
    # get current ban and set expire time to right now
    async with aiosqlite.connect(bot.config["bot"]["bank"], timeout=10) as db:
        now = datetime.now()
        cursor = await db.cursor()
        await cursor.execute("SELECT * FROM banned WHERE uid = (?)", (uid,))
        ban_info = await cursor.fetchall()
        for ban in ban_info:
            if not ban[3]:
                await cursor.execute(
                    "UPDATE banned SET expire_date = (?) WHERE uid = (?)",
                    (now.strftime("%Y-%m-%d %H:%M:%S"), uid),
                )
                await db.commit()
            elif datetime.strptime(ban[3], "%Y-%m-%d %H:%M:%S") > now:
                await cursor.execute(
                    "UPDATE banned SET expire_date = (?) WHERE uid = (?) AND expire_date = (?)",
                    (now.strftime("%Y-%m-%d %H:%M:%S"), uid, ban[3]),
                )
                await db.commit()
