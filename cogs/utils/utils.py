import discord
import config
import aiosqlite
import asyncio
from rcon.source import rcon
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

async def ban(name, uid, reason) -> None:
    await rcon(
        'ban', f'{uid}',
        host='127.0.0.1', port=7123, passwd='holyfuckloisimcummingahh'
    )
    await asyncio.sleep(3)
    with open(
        "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\reasons.txt",
        "a+",
    ) as f:
        f.write(f"{uid} // {name} reason: {reason}\n")
    with open(
        "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\banlist.txt",
        "r",
    ) as f:
        if str(uid) in f.readlines():
            return
    with open(
        "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\banlist.txt",
        "a+",
    ) as f:
        f.write(f"{uid}\n")


async def unban(uid, reason) -> None:
    found = False
    with open(
        "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\banlist.txt",
        "r",
    ) as f:
        lines = [line.rstrip() for line in f.readlines()]
        for i, line in enumerate(lines):
            if line == uid:
                lines.pop(i)
                found = True
                break
    if found:
        with open(
            "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\banlist.txt",
            "w",
        ) as g:
            for i, line in enumerate(lines):
                lines[i] = lines[i] + "\n"
            g.writelines(lines)
        with open(
            "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\reasons.txt",
            "a+",
        ) as h:
            h.write(f"UNBANNED: {uid} // reason: {reason}\n")
            
def is_admin() -> bool:
    return commands.check(lambda ctx: ctx.author.id in config.admins)

async def commafy(num: int) -> str:
    return format(num, ",d")

async def get_uid_from_connection(did):
    db = await aiosqlite.connect(config.bank, timeout=10)
    cursor = await db.cursor()
    await cursor.execute("SELECT titanfallID FROM connection WHERE discordID = (?)", (did,))
    uid = await cursor.fetchone()
    return uid[0] if uid else None

async def get_name_from_connection(did):
    db = await aiosqlite.connect(config.bank, timeout=10)
    cursor = await db.cursor()
    uid = await get_uid_from_connection(did)
    await cursor.execute("SELECT name FROM main WHERE uid = (?)", (uid,))
    name = await cursor.fetchone()
    return name[0] if name else None

async def get_discord_id_user_from_connection(uid):
    db = await aiosqlite.connect(config.bank, timeout=10)
    cursor = await db.cursor()
    await cursor.execute("SELECT discordID FROM connection WHERE titanfallID = (?)", (uid,))
    did = await cursor.fetchone()
    return did[0] if did else None

async def get_uid_from_name(name: str = None) -> int:
    db = await aiosqlite.connect(config.bank, timeout=10)
    cursor = await db.cursor()
    await cursor.execute("SELECT uid FROM main WHERE name = (?)", (name,))
    uid = await cursor.fetchone()
    return uid[0] if uid else None