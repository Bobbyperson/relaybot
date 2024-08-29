from discord.ext import commands
import config
import requests
import cogs.utils.utils as utils
import json
import aiosqlite
import random
import asyncio


class Player:
    def __init__(self, uid, discord_id, participant_id, discord, position):
        self.uid = uid
        self.discord_id = discord_id
        self.participant_id = participant_id
        self.discord = discord
        self.position = position


api_key = config.challonge_api

tf2_assault_rifles = {
    "R-201": "mp_weapon_rspn101",
    "R-101": "mp_weapon_rspn101_og",
    "Hemlock": "mp_weapon_hemlock",
    "Flatline": "mp_weapon_vinson",
    "G2A5": "mp_weapon_g2",
}

tf2_smgs = {
    "CAR": "mp_weapon_car",
    "Alternator": "mp_weapon_alternator_smg",
    "Volt": "mp_weapon_hemlok_smg",
    "R-97": "mp_weapon_r97",
}

tf2_lmg = {
    "Spitfire": "mp_weapon_lmg",
    "L-Star": "mp_weapon_lstar",
    "Devotion": "mp_weapon_devotion",
}

tf2_snipers = {
    "Kraber": "mp_weapon_sniper",
    "Double-Take": "mp_weapon_doubletake",
    "DMR": "mp_weapon_dmr",
}

tf2_shotguns = {"EVA-8": "mp_weapon_shotgun", "Mastiff": "mp_weapon_mastiff"}

tf2_grenadiers = {
    "Sidewinder": "mp_weapon_smr",
    "EPG": "mp_weapon_epg",
    "Softball": "mp_weapon_softball",
    "Cold-War": "mp_weapon_pulse_lmg",
}

valid_maps = {
    "Coliseum": "mp_coliseum",
    "Pillars": "mp_coliseum_column",
    "Deck": "mp_lf_deck",
    "Traffic": "mp_lf_traffic",
    "Stacks": "mp_lf_stacks",
    "Township": "mp_lf_township",
    "UMA": "mp_lf_uma",
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
        try:
            msg = await self.client.wait_for(
                "message",
                check=lambda message: message.author == user
                and message.channel == ctx.channel
                and message.content in maps,
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            return None

        return msg.content

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

    async def set_match_winner(self, tournament_id, match_id, winner_id):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",
        }
        result = requests.put(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/matches/{match_id}.json?api_key={api_key}",
            headers=headers,
            data={"match[winner_id]": winner_id},
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

        tournament_id = "jlkdx0i4"

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
                "No match found! If you believe this is an error please ping bobby."
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
            else:
                author.position = i

        if not opponent.discord_id:
            return await ctx.send(
                "Your opponent did not supply their discord id when signing up. Please ping them and ask them to edit their sign-in. Ping Bobby if needed."
            )

        opponent.uid = await utils.get_uid_from_connection(opponent.discord_id)

        opponent.discord = await self.client.fetch_user(opponent.discord_id)

        if not opponent.uid:
            return await ctx.send(
                f"Your opponent is not linked! {opponent.discord.mention} please join any of our servers and run the command `,.link (in-game name)` (besides the 1v1 server). Then run this command again."
            )

        self.client.reserved = True

        maps = list(valid_maps.keys())

        await ctx.send("All checks passed! Now we need to select the first map.")

        map_message = await ctx.send(", ".join(maps))

        if random.randint(0, 1) == 0:
            first = author
            second = opponent
            # second = author  # ! TEMP
        else:
            first = opponent
            # first = author  # ! TEMP
            second = author

        await ctx.send(
            f"{first.discord.mention} has randomly been chosen to pick first.\n{first.discord.mention} please pick **TWO** maps you do **NOT** want to play. Please type the name of the map you want to remove exactly as it is shown:"
        )
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
        server = await utils.get_server("1v1")
        try:
            await server.send_command(f"map {valid_maps[chosen_map]}")
        except (
            ConnectionRefusedError,
            ConnectionResetError,
            ConnectionError,
            ConnectionAbortedError,
        ):
            await ctx.send("Couldn't set map. Is the server online? Ping bobby.")
            return

        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({opponent.uid})")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({author.uid})")
            await db.commit()
        await ctx.send(
            "Done! Round 1 starting now! Please join the `awesome 1v1 server`. Please be aware that you will have to come back to this channel after this match."
        )
        self.client.tournament_players = {
            author.uid: {"kills": 0, "wins": 0},
            opponent.uid: {"kills": 0, "wins": 0},
        }

        await self.mark_match_as_underway(tournament_id, next_match)

        temp = self.client.tournament_players.copy()

        round_winner = None
        round_loser = None

        while True:
            await asyncio.sleep(1)
            author_kills = self.client.tournament_players[author.uid]["kills"]
            opponent_kills = self.client.tournament_players[opponent.uid]["kills"]
            author_wins = self.client.tournament_players[author.uid]["wins"]
            opponent_wins = self.client.tournament_players[opponent.uid]["wins"]

            temp = self.client.tournament_players.copy()

            if author_kills > 2:
                self.client.tournament_players[author.uid]["wins"] += 1

            if opponent_kills > 2:
                self.client.tournament_players[opponent.uid]["wins"] += 1

            if self.client.tournament_players[author.uid]["wins"] > 0:
                round_winner = author
                round_loser = opponent
                if author.position == 0:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{author_wins}-{opponent_wins},{opponent_wins}-{author_wins}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent_wins}-{author_wins},{author_wins}-{opponent_wins}",
                    )
                break

            if self.client.tournament_players[opponent.uid]["wins"] > 0:
                round_winner = opponent
                round_loser = author
                if author.position == 0:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{author_wins}-{opponent_wins},{opponent_wins}-{author_wins}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent_wins}-{author_wins},{author_wins}-{opponent_wins}",
                    )
                break
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
            await self.set_match_winner(
                tournament_id, next_match, round_loser.participant_id
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
            await self.set_match_winner(
                tournament_id, next_match, round_winner.participant_id
            )
            return
        await server.send_command(f"map {valid_maps[chosen_map2]}")
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({opponent.uid})")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({author.uid})")
            await db.commit()
        await ctx.send(
            "Done! Round 2 starting now! Please join the `awesome 1v1 server`. Please be aware that you will have to come back to this channel after this match."
        )

        temp = self.client.tournament_players.copy()

        while True:
            await asyncio.sleep(1)
            author_kills = self.client.tournament_players[author.uid]["kills"]
            opponent_kills = self.client.tournament_players[opponent.uid]["kills"]
            author_wins = self.client.tournament_players[author.uid]["wins"]
            opponent_wins = self.client.tournament_players[opponent.uid]["wins"]

            temp = self.client.tournament_players.copy()

            if author_kills > 2:
                self.client.tournament_players[author.uid]["wins"] += 1
            if opponent_kills > 2:
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
                        f"{author_wins}-{opponent_wins},{opponent_wins}-{author_wins}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent_wins}-{author_wins},{author_wins}-{opponent_wins}",
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
                        f"{author_wins}-{opponent_wins},{opponent_wins}-{author_wins}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent_wins}-{author_wins},{author_wins}-{opponent_wins}",
                    )
                break

        if self.client.tournament_players[author.uid]["wins"] > 1:
            await self.set_match_winner(tournament_id, next_match, author.uid)
            await ctx.send(f"Match has been won 2-0 by {author.discord.mention}!!!")
            return await cleanup()

        if self.client.tournament_players[opponent.uid]["wins"] > 1:
            await self.set_match_winner(tournament_id, next_match, opponent.uid)
            await ctx.send(f"Match has been won 2-0 by {opponent.discord.mention}!!!")
            return await cleanup()

        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await db.commit()

        await ctx.send(
            f"{round_winner.discord.mention} wins the round! Now entering a tiebreaker!!!"
        )
        remove_map4 = await self.ask_map(ctx, round_winner.discord, maps)
        map_message = await ctx.send(", ".join(maps))
        await ctx.send(
            f"{round_winner.discord.mention} please pick **ONE** map you do **NOT** want to play. Please type the name of the map you want to remove exactly as it is shown:"
        )
        if remove_map4 in maps:
            maps.remove(remove_map4)
            await map_message.edit(content=", ".join(maps))
        else:
            await cleanup()
            await ctx.send(
                "You did not pick a valid map in 5 minutes! You have now forfeited."
            )
            await self.set_match_winner(
                tournament_id, next_match, round_loser.participant_id
            )
            return
        await ctx.send(
            f"{round_loser.discord.mention} please pick the map you **WANT** to play:"
        )
        chosen_map3 = await self.ask_map(ctx, round_loser.discord, maps)
        if chosen_map3 in maps:
            maps.remove(chosen_map3)
            await map_message.edit(content=", ".join(maps))
        else:
            await cleanup()
            await ctx.send(
                "You did not pick a valid map in 5 minutes! You have now forfeited."
            )
            await self.set_match_winner(
                tournament_id, next_match, round_winner.participant_id
            )
            return
        await server.send_command(f"map {valid_maps[chosen_map3]}")
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({opponent.uid})")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({author.uid})")
            await db.commit()
        await ctx.send(
            "Done! Final round starting now! Please join the `awesome 1v1 server`. This is the tiebreaker!"
        )
        while True:
            await asyncio.sleep(1)
            author_kills = self.client.tournament_players[author.uid]["kills"]
            opponent_kills = self.client.tournament_players[opponent.uid]["kills"]
            author_wins = self.client.tournament_players[author.uid]["wins"]
            opponent_wins = self.client.tournament_players[opponent.uid]["wins"]

            if author_kills > 2:
                self.client.tournament_players[author.uid]["wins"] += 1
            if opponent_kills > 2:
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
                        f"{author_wins}-{opponent_wins},{opponent_wins}-{author_wins}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent_wins}-{author_wins},{author_wins}-{opponent_wins}",
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
                        f"{author_wins}-{opponent_wins},{opponent_wins}-{author_wins}",
                    )
                else:
                    await self.update_match(
                        tournament_id,
                        next_match,
                        f"{opponent_wins}-{author_wins},{author_wins}-{opponent_wins}",
                    )
                break
            temp = self.client.tournament_players.copy()

        if (
            self.client.tournament_players[author.uid]["wins"]
            > self.client.tournament_players[opponent.uid]["wins"]
        ):
            await ctx.send(f"{author.discord.mention} wins the match! Congrats!")
            await self.set_match_winner(tournament_id, next_match, author.uid)
        else:
            await ctx.send(f"{opponent.discord.mention} wins the match! Congrats!")
            await self.set_match_winner(tournament_id, next_match, opponent.uid)

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
