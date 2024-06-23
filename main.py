import discord
import os
import asyncio
from discord.ext import commands
from pretty_help import PrettyHelp
import config


async def main():
    # start the client
    async with client:
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await client.load_extension(f"cogs.{filename[:-3]}")
        await client.start(config.TOKEN)


intents = discord.Intents().all()
client = commands.Bot(command_prefix=",.", intents=intents, help_command=PrettyHelp())


@client.command(hidden=True)
async def load(ctx, extension):
    if ctx.author.id == config.owner_id:
        await client.load_extension(f"cogs.{extension}")
        await ctx.send(f"{extension} loaded.")
    if ctx.author.id != config.owner_id:
        await ctx.send("no")


@client.command(hidden=True)
async def unload(ctx, extension):
    if ctx.author.id == config.owner_id:
        await client.unload_extension(f"cogs.{extension}")
        await ctx.send(f"{extension} unloaded.")

    if ctx.author.id != config.owner_id:
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
    

if __name__ == "__main__":
    if not os.path.exists("database.sqlite"):
        with open("database.sqlite", "w") as f:
            pass
    discord.utils.setup_logging()
    asyncio.run(main())