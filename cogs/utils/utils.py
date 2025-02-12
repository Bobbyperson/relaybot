from typing import Union
import time

import aiosqlite
import config
from datetime import datetime
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
    return commands.check(lambda ctx: ctx.author.id in config.admins)


async def commafy(num: int) -> str:
    return format(num, ",d")


async def get_uid_from_connection(did):
    async with aiosqlite.connect(config.bank, timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute(
            "SELECT titanfallID FROM connection WHERE discordID = (?)", (did,)
        )
        uid = await cursor.fetchone()
        return uid[0] if uid else None


async def get_name_from_connection(did) -> Union[str, None]:
    async with aiosqlite.connect(config.bank, timeout=10) as db:
        cursor = await db.cursor()
        uid = await get_uid_from_connection(did)
        for s in config.servers:
            await cursor.execute(f"SELECT name FROM {s.name} WHERE uid = (?)", (uid,))
            name = await cursor.fetchone()
            if name:
                return name[0]
        return None


async def get_discord_id_user_from_connection(uid):
    async with aiosqlite.connect(config.bank, timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute(
            "SELECT discordID FROM connection WHERE titanfallID = (?)", (uid,)
        )
        did = await cursor.fetchone()
        return did[0] if did else None


async def get_uid_from_name(name: str = None) -> Union[int, None]:
    async with aiosqlite.connect(config.bank, timeout=10) as db:
        cursor = await db.cursor()
        for s in config.servers:
            await cursor.execute(f"SELECT uid FROM {s.name} WHERE name = (?)", (name,))
            uid = await cursor.fetchone()
            if uid:
                return uid[0]
        return None


async def is_valid_server(server: str = None) -> bool:
    for s in config.servers:
        if server == s.name:
            return True
    for s in config.tournament_servers:
        if server == s.name:
            return True
    return False


async def check_server_auth(server: str = None, auth: str = None) -> bool:
    for s in config.servers:
        if server == s.name:
            return auth == s.key
    for s in config.tournament_servers:
        if server == s.name:
            return auth == s.key
    return False


async def get_server(server):
    for s in config.servers:
        if server == s.name:
            return s
    for s in config.tournament_servers:
        if server == s.name:
            return s
    return None


async def get_row(name, condition, value, table):
    async with aiosqlite.connect(config.bank, timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute(
            f"SELECT {name} FROM {table} WHERE {condition} = (?)", (value,)
        )
        result = await cursor.fetchone()
        return result[0] if result else None


async def update_row(name, new_value, condition, cvalue, table):
    async with aiosqlite.connect(config.bank, timeout=10) as db:
        await db.execute(
            f"UPDATE {table} SET {name} = ? WHERE {condition} = ?", (new_value, cvalue)
        )
        await db.commit()


async def get_valid_server_names() -> list:
    return [s.name for s in config.servers]


async def check_server_ip(server: str = None, ip: str = None) -> bool:
    # for s in config.servers:
    #     if server == s.name:
    #         return ip == s.ip
    # for s in config.tournament_servers:
    #     if server == s.name:
    #         return ip == s.ip
    # return False
    return True


async def is_linked(did) -> bool:
    async with aiosqlite.connect(config.bank, timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute(
            "SELECT discordID FROM connection WHERE discordID = (?)", (did,)
        )
        uid = await cursor.fetchone()
        return bool(uid)


async def is_tournament_server(server: str = None) -> bool:
    for s in config.tournament_servers:
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


async def get_ban_info(uid):
    async with aiosqlite.connect(config.bank, timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute("SELECT * FROM banned WHERE uid = (?)", (uid,))
        ban_info = await cursor.fetchall()
        return ban_info


async def ban_user(uid, reason="", expires=""):
    if expires:
        expires = datetime.fromtimestamp(int(time.time()) + expires).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    else:
        expires = ""
    async with aiosqlite.connect(config.bank, timeout=10) as db:
        cursor = await db.cursor()
        await cursor.execute(
            "INSERT INTO banned(uid, reason, expire_date) VALUES(?, ?, ?)",
            (uid, reason, expires),
        )
        await db.commit()


async def unban_user(uid):
    # get current ban and set expire time to right now
    async with aiosqlite.connect(config.bank, timeout=10) as db:
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
            else:
                if datetime.strptime(ban[3], "%Y-%m-%d %H:%M:%S") > now:
                    await cursor.execute(
                        "UPDATE banned SET expire_date = (?) WHERE uid = (?) AND expire_date = (?)",
                        (now.strftime("%Y-%m-%d %H:%M:%S"), uid, ban[3]),
                    )
                    await db.commit()
