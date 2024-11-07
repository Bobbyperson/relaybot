import asyncio
import json
import random
from copy import deepcopy

import aiosqlite
import config
import requests
from discord.ext import commands

import cogs.utils.utils as utils


class Player:
    def __init__(self, uid, discord_id, participant_id, discord, position):
        self.uid = uid
        self.discord_id = discord_id
        self.participant_id = participant_id
        self.discord = discord
        self.position = position
        self.scores = [0, 0, 0]


api_key = config.challonge_api

valid_maps = {
    "coliseum": "mp_coliseum",
    "pillars": "mp_coliseum_column",
    "deck": "mp_lf_deck",
    "traffic": "mp_lf_traffic",
    "stacks": "mp_lf_stacks",
    "township": "mp_lf_township",
    "uma": "mp_lf_uma",
    "meadow": "mp_lf_meadow",
}


class Tournament(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.client.tournament_players = {}
        self.client.reserved = False

    @commands.Cog.listener()
    async def on_ready(self):
        print("Tournament ready")

    async def get_tournament_id(self):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",
        }
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments.json?api_key={api_key}",
            headers=headers,
        )

        if result.status_code == 200:
            data = result.json()[0]
            return data
        return None

    async def get_participants(self, tournament_id):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",
        }
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/participants.json?api_key={api_key}",
            headers=headers,
        )

        if result.status_code == 200:
            data = result.json()
            return data
        return None

    async def get_participant(self, tournament_id, participant_id):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",
        }
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/participants/{participant_id}.json?api_key={api_key}",
            headers=headers,
        )

        if result.status_code == 200:
            data = result.json()
            return data
        return None

    async def get_matches(self, tournament_id):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",
        }
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/matches.json?api_key={api_key}",
            headers=headers,
        )

        if result.status_code == 200:
            data = result.json()
            return data
        return None

    async def get_participant_next_match(self, tournament_id, participant_id):
        matches = await self.get_matches(tournament_id)

        for match in matches:
            if (
                match["match"]["player1_id"] == participant_id
                or match["match"]["player2_id"] == participant_id
            ) and (match["match"]["state"] == "open"):
                return match["match"]["id"]
        return None

    async def get_participant_discord_id(self, tournament_id, participant_id):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",
        }
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/participants/{participant_id}.json?api_key={api_key}",
            headers=headers,
        )

        if result.status_code == 200:
            data = json.loads(result.text)
            custom_field_response = data["participant"]["custom_field_response"]

            if not custom_field_response:
                return None

            for _, value in custom_field_response.items():
                # we only care about the first value
                return value.strip()

        return None

    async def get_participants_in_match(self, tournament_id, match_id):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",
        }
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/matches/{match_id}.json?api_key={api_key}",
            headers=headers,
        )

        if result.status_code == 200:
            data = result.json()
            return await self.get_participant(
                tournament_id, data["match"]["player1_id"]
            ), await self.get_participant(tournament_id, data["match"]["player2_id"])
        return None

    async def ask_map(self, ctx, user, maps):
        def check(m):
            if m.content:
                return (
                    m.author == user
                    and m.channel == ctx.channel
                    and m.content.lower() in maps
                )
            return False

        try:
            msg = await self.client.wait_for(
                "message",
                check=check,
                timeout=300.0,
            )
        except asyncio.TimeoutError:
            return None

        if msg.content:
            return msg.content.lower()
        return None

    async def mark_match_as_underway(self, tournament_id, match_id):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",
        }
        result = requests.post(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/matches/{match_id}/mark_as_underway.json?api_key={api_key}",
            headers=headers,
        )

        if result.status_code == 200:
            return True
        return False

    async def update_match(self, tournament_id, match_id, score):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",
        }
        result = requests.put(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/matches/{match_id}.json?api_key={api_key}",
            headers=headers,
            data={"match[scores_csv]": score},
        )

        print(result.status_code)

        if result.status_code == 200:
            return True
        print("failed to update match!!!")
        return False

    async def set_match_winner(self, tournament_id, match_id, winner_id, scores):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",
        }
        result = requests.put(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/matches/{match_id}.json?api_key={api_key}",
            headers=headers,
            data={"match[winner_id]": winner_id, "match[scores_csv]": scores},
        )

        if result.status_code == 200:
            return True
        return False

    @commands.command()
    async def playmatch(self, ctx):
        async def cleanup():
            self.client.reserved = False
            self.client.tournament_players = {}
            async with aiosqlite.connect(config.bank, timeout=10) as db:
                cursor = await db.cursor()
                await cursor.execute("DELETE FROM whitelist")
                await db.commit()

        if not await utils.is_linked(ctx.author.id):
            return await ctx.send(
                "Your titanfall and discord accounts are not linked. Please join any of our servers and run the command `,.link (in-game name)` (besides the 1v1 server). Then run this command again."
            )

        if self.client.reserved:
            return await ctx.send(
                "It looks like someone is currently playing their match. Please try again after they have finished."
            )

        author = Player(
            await utils.get_uid_from_connection(ctx.author.id),
            ctx.author.id,
            None,
            ctx.author,
            None,
        )

        opponent = Player(None, None, None, None, None)

        tournament_id = "atra7egj"

        participants = await self.get_participants(tournament_id)

        for participant in participants:
            discord_id = await self.get_participant_discord_id(
                tournament_id, participant["participant"]["id"]
            )
            if (
                discord_id == str(ctx.author.id)
                or discord_id == ctx.author.name.lower()
            ):
                author.participant_id = participant["participant"]["id"]
                break

        if not author.participant_id:
            return await ctx.send(
                "Either you are not in the tournament, or you did not supply your discord id when signing up. Please edit your sign-in or ping Bobby."
            )

        await ctx.send("Found user. Checking for open match...")

        next_match = await self.get_participant_next_match(
            tournament_id, author.participant_id
        )

        if not next_match:
            return await ctx.send(
                "No match found! Do you currently have an open match? If you believe this is an error please ping bobby."
            )
        await ctx.send("Match found! Checking for opponent...")
        for i, participant in enumerate(
            await self.get_participants_in_match(tournament_id, next_match)
        ):
            if participant["participant"]["id"] != author.participant_id:
                opponent.discord_id = await self.get_participant_discord_id(
                    tournament_id, participant["participant"]["id"]
                )
                opponent.position = i
                opponent.participant_id = participant["participant"]["id"]
            else:
                author.position = i

        if not opponent.discord_id:
            return await ctx.send(
                "Your opponent did not supply their discord id when signing up. Please ping them and ask them to edit their sign-in. Ping Bobby if needed."
            )

        try:
            opponent.discord_id = int(opponent.discord_id)
        except ValueError:
            return await ctx.send(
                "Your opponent did not supply a valid discord id. Please ping them and ask them to edit their sign-in. Ping Bobby if needed."
            )

        opponent.uid = await utils.get_uid_from_connection(opponent.discord_id)

        opponent.discord = await self.client.fetch_user(opponent.discord_id)

        if not opponent.uid:
            return await ctx.send(
                f"Your opponent is not linked! {opponent.discord.mention} please join any of our servers and run the command `,.link (in-game name)` (besides the 1v1 server). Then run this command again."
            )

        self.client.reserved = True

        maps = list(valid_maps.keys())

        await ctx.send(
            "Is your match semifinals or later (look in same column for losers)? Respond yes or no."
        )
        try:
            msg = await self.client.wait_for(
                "message",
                timeout=30.0,
                check=lambda message: message.author == ctx.author
                and message.channel == ctx.channel
                and message.content.lower() in ["yes", "no"],
            )
        except asyncio.TimeoutError:
            await ctx.send("Cancelled.")
            await cleanup()
            return

        if msg.content.lower() == "yes":
            semifinals = True
            self.client.tournament_should_sleep = False
            required_kills = 14
        else:
            semifinals = False
            self.client.tournament_should_sleep = True
            required_kills = 2

        me = await ctx.guild.fetch_member(248984895940984832)

        await ctx.send(f"{me.mention} please confirm")

        try:
            msg = await self.client.wait_for(
                "message",
                timeout=300.0,
                check=lambda message: message.author == me
                and message.channel == ctx.channel
                and message.content.lower() in ["confirm", "deny"],
            )
        except asyncio.TimeoutError:
            await ctx.send("Timeout, cancelled.")
            await cleanup()
            return

        if msg.content.lower() == "deny":
            await ctx.send("bruh")
            await cleanup()
            return

        await ctx.send("All checks passed! Now we need to select the first map.")

        if random.randint(0, 1) == 0:
            first = author
            second = opponent
            # second = author  # ! TEMP
        else:
            first = opponent
            # first = author  # ! TEMP
            second = author

        if semifinals:
            maps.remove("coliseum")
            maps.remove("pillars")

            await ctx.send(
                f"{first.discord.mention} has randomly been chosen to pick first.\n{first.discord.mention} please pick **ONE** map you do **NOT** want to play. Please type the name of the map you want to remove exactly as it is shown:"
            )
        else:

            await ctx.send(
                f"{first.discord.mention} has randomly been chosen to pick first.\n{first.discord.mention} please pick **TWO** maps you do **NOT** want to play. Please type the name of the map you want to remove exactly as it is shown:"
            )
        map_message = await ctx.send(", ".join(maps))
        remove_map1 = await self.ask_map(ctx, first.discord, maps)
        if remove_map1 in maps:
            maps.remove(remove_map1)
            await map_message.edit(content=", ".join(maps))
        else:
            await cleanup()
            await ctx.send(
                "You did not pick a valid map in time! Please run this command again."
            )
            return
        if not semifinals:
            remove_map2 = await self.ask_map(ctx, first.discord, maps)
            if remove_map2 in maps:
                maps.remove(remove_map2)
                await map_message.edit(content=", ".join(maps))
            else:
                await cleanup()
                await ctx.send(
                    "You did not pick a valid map in time! Please run this command again."
                )
                return
        await ctx.send(
            f"{second.discord.mention} please pick the map you **WANT** to play:"
        )
        chosen_map = await self.ask_map(ctx, second.discord, maps)
        if chosen_map in maps:
            maps.remove(chosen_map)
            await map_message.edit(content=", ".join(maps))
        else:
            await cleanup()
            await ctx.send(
                "You did not pick a valid map in time! Please run this command again."
            )
            return
        loadout1 = random.randint(0, 9)
        with open(f"tourney/loadout{loadout1}.json", "r") as f:
            self.client.tournament_loadout = json.loads(f.read())
        server = await utils.get_server("oneVone")
        try:
            if semifinals:
                await server.send_command(
                    f"mp_gamemode ps; map {valid_maps[chosen_map]}"
                )
            else:
                await server.send_command(
                    f"mp_gamemode coliseum; map {valid_maps[chosen_map]}"
                )
        except ConnectionError:
            await ctx.send("Couldn't set map. Is the server online? Ping bobby.")
            return

        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({opponent.uid})")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({author.uid})")
            await db.commit()
        await ctx.send(
            f"Done! Round 1 starting now! Please join the `awesome 1v1 server`. Players will be given loadout {loadout1 + 1}! Please be aware that you will have to come back to this channel after this match."
        )
        self.client.tournament_players = {
            author.uid: {"kills": 0, "wins": 0},
            opponent.uid: {"kills": 0, "wins": 0},
        }

        await self.mark_match_as_underway(tournament_id, next_match)

        temp = deepcopy(self.client.tournament_players)

        round_winner = None
        round_loser = None

        i = 0
        while True:
            await asyncio.sleep(1)
            author_kills = self.client.tournament_players[author.uid]["kills"]
            opponent_kills = self.client.tournament_players[opponent.uid]["kills"]

            author.scores[0] = author_kills
            opponent.scores[0] = opponent_kills

            if author_kills > required_kills:
                self.client.tournament_players[author.uid]["wins"] += 1

            if opponent_kills > required_kills:
                self.client.tournament_players[opponent.uid]["wins"] += 1

            if self.client.tournament_players[author.uid]["wins"] > 0:
                round_winner = author
                round_loser = opponent
                if author.position == 0:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                    )
                break

            if self.client.tournament_players[opponent.uid]["wins"] > 0:
                round_winner = opponent
                round_loser = author
                if author.position == 0:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                    )
                break
            temp = deepcopy(self.client.tournament_players)
            i += 1
            if i > 60 * 30:
                await cleanup()
                await ctx.send(
                    "This is taking too long! Run this command again or ping bobby if your opponent dipped."
                )
                return
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await db.commit()

        await ctx.send(f"{round_winner.discord.mention} wins the round!")
        await ctx.send(
            f"{round_winner.discord.mention} please pick **ONE** map you do **NOT** want to play. Please type the name of the map you want to remove exactly as it is shown:"
        )
        map_message = await ctx.send(", ".join(maps))
        remove_map3 = await self.ask_map(ctx, round_winner.discord, maps)
        if remove_map3 in maps:
            maps.remove(remove_map3)
            await map_message.edit(content=", ".join(maps))
        else:
            await cleanup()
            await ctx.send(
                "You did not pick a valid map in 5 minutes! You have now forfeited."
            )
            if author.position == 0:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    round_loser.participant_id,
                    f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                )
            else:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    round_loser.participant_id,
                    f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                )
            return
        await ctx.send(
            f"{round_loser.discord.mention} please pick the map you **WANT** to play:"
        )
        chosen_map2 = await self.ask_map(ctx, round_loser.discord, maps)
        if chosen_map2 in maps:
            maps.remove(chosen_map2)
            await map_message.edit(content=", ".join(maps))
        else:
            await cleanup()
            await ctx.send(
                "You did not pick a valid map in 5 minutes! You have now forfeited."
            )
            if author.position == 0:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    round_winner.participant_id,
                    f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                )
            else:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    round_winner.participant_id,
                    f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                )
            return

        loadout2 = random.randint(0, 9)
        while loadout2 == loadout1:
            loadout2 = random.randint(0, 9)
        with open(f"tourney/loadout{loadout2}.json", "r") as f:
            self.client.tournament_loadout = json.loads(f.read())
        if semifinals:
            await server.send_command(f"mp_gamemode ps; map {valid_maps[chosen_map2]}")
        else:
            await server.send_command(
                f"mp_gamemode coliseum; map {valid_maps[chosen_map2]}"
            )
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({opponent.uid})")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({author.uid})")
            await db.commit()
        await ctx.send(
            f"Done! Round 2 starting now! Please join the `awesome 1v1 server`. Players will be given loadout {loadout2 + 1}! Please be aware that you will have to come back to this channel after this match."
        )

        self.client.tournament_players[author.uid]["kills"] = 0
        self.client.tournament_players[opponent.uid]["kills"] = 0

        temp = deepcopy(self.client.tournament_players)

        i = 0
        while True:
            await asyncio.sleep(1)
            author_kills = self.client.tournament_players[author.uid]["kills"]
            opponent_kills = self.client.tournament_players[opponent.uid]["kills"]

            author.scores[1] = author_kills
            opponent.scores[1] = opponent_kills

            if author_kills > required_kills:
                self.client.tournament_players[author.uid]["wins"] += 1
            if opponent_kills > required_kills:
                self.client.tournament_players[opponent.uid]["wins"] += 1

            if (
                self.client.tournament_players[author.uid]["wins"]
                > temp[author.uid]["wins"]
            ):
                round_winner = author
                round_loser = opponent
                if author.position == 0:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                    )
                break

            if (
                self.client.tournament_players[opponent.uid]["wins"]
                > temp[opponent.uid]["wins"]
            ):
                round_winner = opponent
                round_loser = author
                if author.position == 0:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                    )
                break
            temp = deepcopy(self.client.tournament_players)
            i += 1
            if i > 60 * 30:
                await cleanup()
                await ctx.send(
                    "This is taking too long! Run this command again or ping bobby if your opponent dipped."
                )
                return

        if self.client.tournament_players[author.uid]["wins"] > 1:
            if author.position == 0:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    author.participant_id,
                    f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                )
            else:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    author.participant_id,
                    f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                )
            await ctx.send(f"Match has been won 2-0 by {author.discord.mention}!!!")
            return await cleanup()

        if self.client.tournament_players[opponent.uid]["wins"] > 1:
            if opponent.position == 0:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    opponent.participant_id,
                    f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                )
            else:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    opponent.participant_id,
                    f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                )
            await ctx.send(f"Match has been won 2-0 by {opponent.discord.mention}!!!")
            return await cleanup()

        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await db.commit()

        await ctx.send(
            f"{round_winner.discord.mention} wins the round! Now entering a tiebreaker!!!"
        )
        if not semifinals:
            await ctx.send(
                f"{round_winner.discord.mention} please pick **ONE** map you do **NOT** want to play. Please type the name of the map you want to remove exactly as it is shown:"
            )
            map_message = await ctx.send(", ".join(maps))
            remove_map4 = await self.ask_map(ctx, round_winner.discord, maps)
            if remove_map4 in maps:
                maps.remove(remove_map4)
                await map_message.edit(content=", ".join(maps))
            else:
                await cleanup()
                await ctx.send(
                    "You did not pick a valid map in 5 minutes! You have now forfeited."
                )
                if author.position == 0:
                    await self.set_match_winner(
                        tournament_id,
                        next_match,
                        round_loser.participant_id,
                        f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                    )
                else:
                    await self.set_match_winner(
                        tournament_id,
                        next_match,
                        round_loser.participant_id,
                        f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                    )
                return await cleanup()
        await ctx.send(
            f"{round_loser.discord.mention} please pick the map you **WANT** to play:"
        )
        map_message = await ctx.send(", ".join(maps))
        chosen_map3 = await self.ask_map(ctx, round_loser.discord, maps)
        if chosen_map3 in maps:
            maps.remove(chosen_map3)
            await map_message.edit(content=", ".join(maps))
        else:
            await cleanup()
            await ctx.send(
                "You did not pick a valid map in 5 minutes! You have now forfeited."
            )
            if author.position == 0:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    round_winner.participant_id,
                    f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                )
            else:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    round_winner.participant_id,
                    f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                )
            return
        loadout3 = random.randint(0, 9)
        while loadout3 == loadout1 or loadout3 == loadout2:
            loadout3 = random.randint(0, 9)
        with open(f"tourney/loadout{loadout3}.json", "r") as f:
            self.client.tournament_loadout = json.loads(f.read())
        if semifinals:
            await server.send_command(f"mp_gamemode ps; map {valid_maps[chosen_map3]}")
        else:
            await server.send_command(
                f"mp_gamemode coliseum; map {valid_maps[chosen_map3]}"
            )
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({opponent.uid})")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({author.uid})")
            await db.commit()
        await ctx.send(
            f"Done! Final round starting now! Players will be given loadout {loadout3 + 1}! Please join the `awesome 1v1 server`. This is the tiebreaker!"
        )

        self.client.tournament_players[author.uid]["kills"] = 0
        self.client.tournament_players[opponent.uid]["kills"] = 0

        temp = deepcopy(self.client.tournament_players)

        i = 0
        while True:
            await asyncio.sleep(1)
            author_kills = self.client.tournament_players[author.uid]["kills"]
            opponent_kills = self.client.tournament_players[opponent.uid]["kills"]

            author.scores[2] = author_kills
            opponent.scores[2] = opponent_kills

            if author_kills > required_kills:
                self.client.tournament_players[author.uid]["wins"] += 1
            if opponent_kills > required_kills:
                self.client.tournament_players[opponent.uid]["wins"] += 1

            if (
                self.client.tournament_players[author.uid]["wins"]
                > temp[author.uid]["wins"]
            ):
                round_winner = author
                round_loser = opponent
                if author.position == 0:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                    )
                break

            if (
                self.client.tournament_players[opponent.uid]["wins"]
                > temp[opponent.uid]["wins"]
            ):
                round_winner = opponent
                round_loser = author
                if author.position == 0:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                    )
                break
            temp = deepcopy(self.client.tournament_players)
            i += 1
            if i > 60 * 30:
                await cleanup()
                await ctx.send(
                    "This is taking too long! Run this command again or ping bobby if your opponent dipped."
                )
                return

        if (
            self.client.tournament_players[author.uid]["wins"]
            > self.client.tournament_players[opponent.uid]["wins"]
        ):
            await ctx.send(f"{author.discord.mention} wins the match! Congrats!")
            if author.position == 0:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    author.participant_id,
                    f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                )
            else:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    author.participant_id,
                    f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                )
        else:
            await ctx.send(f"{opponent.discord.mention} wins the match! Congrats!")
            if author.position == 0:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    opponent.participant_id,
                    f"{author.scores[0]}-{opponent.scores[0]},{author.scores[1]}-{opponent.scores[1]},{author.scores[2]}-{opponent.scores[2]}",
                )
            else:
                await self.set_match_winner(
                    tournament_id,
                    next_match,
                    opponent.participant_id,
                    f"{opponent.scores[0]}-{author.scores[0]},{opponent.scores[1]}-{author.scores[1]},{opponent.scores[2]}-{author.scores[2]}",
                )
        await cleanup()

    @commands.command()
    @commands.is_owner()
    async def reset(self, ctx):
        self.client.reserved = False
        self.client.tournament_players = {}
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await db.commit()
        await ctx.send("Done!")

    @commands.command()
    @commands.is_owner()
    async def reserve(self, ctx, player1: int, player2: int):
        if not player1 or not player2:
            return await ctx.send("dumbass")
        self.client.reserved = True
        self.client.tournament_players = {
            player1: {"kills": 0, "wins": 0},
            player2: {"kills": 0, "wins": 0},
        }
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({player1})")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({player2})")
            await db.commit()
        await ctx.send("Done!")


# @commands.Cog.listener()
# async def on_command_error(self, ctx, error):
#     # check if command is reserve command
#     if ctx.command.name == "reserve":
#         await ctx.send(
#             "It looks like the reserve command errored out! Resetting the server."
#         )
#         self.client.reserved = False
#         self.client.tournament_players = {}
#         async with aiosqlite.connect(config.bank, timeout=10) as db:
#             cursor = await db.cursor()
#             await cursor.execute("DELETE FROM whitelist")
#             await db.commit()


async def setup(client):
    await client.add_cog(Tournament(client))
