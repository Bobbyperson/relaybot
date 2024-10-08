import config
import aiosqlite
from discord.ext import commands
from typing import Union

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
    for s in config.servers:
        if server == s.name:
            return ip == s.ip
    for s in config.tournament_servers:
        if server == s.name:
            return ip == s.ip
    return False


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
