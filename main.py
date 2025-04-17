import asyncio
import os
import sys
import traceback

import discord
from discord.ext import commands
from pretty_help import PrettyHelp

import config

intents = discord.Intents().all()
client = commands.Bot(command_prefix=",.", intents=intents, help_command=PrettyHelp())


@client.command(hidden=True)
async def load(ctx, extension):
    if ctx.author.id == config.owner_id:
        await client.load_extension(f"cogs.{extension}")
        await ctx.send(f"{extension} loaded.")
    else:
        await ctx.send("no")


@client.command(hidden=True)
async def unload(ctx, extension):
    if ctx.author.id == config.owner_id:
        await client.unload_extension(f"cogs.{extension}")
        await ctx.send(f"{extension} unloaded.")
    else:
        await ctx.send("no")


@client.command(hidden=True)
async def reload(ctx, extension):
    if ctx.author.id == config.owner_id:
        await client.unload_extension(f"cogs.{extension}")
        await ctx.send(f"{extension} unloaded.")
        await client.load_extension(f"cogs.{extension}")
        await ctx.send(f"{extension} loaded.")
    else:
        await ctx.send("no")


@client.event
async def on_ready():
    print("I am ready.")


async def main():
    # start the client
    async with client:
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await client.load_extension(f"cogs.{filename[:-3]}")
        await client.start(config.TOKEN)


async def send_error_to_channel(error_message):
    channel = client.get_channel(config.log_channel)
    await channel.send(error_message)


def handle_exception(exc_type, exc_value, exc_traceback):
    error_message = "".join(
        traceback.format_exception(exc_type, exc_value, exc_traceback),
    )
    client.loop.create_task(send_error_to_channel(error_message))


if __name__ == "__main__":
    if not os.path.exists("database.sqlite"):
        with open("database.sqlite", "w") as f:
            f.write("")
    discord.utils.setup_logging()
    sys.excepthook = handle_exception
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
