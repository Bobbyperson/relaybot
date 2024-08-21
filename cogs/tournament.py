from discord.ext import commands
import config
import requests
import cogs.utils.utils as utils
import json
import aiosqlite


api_key = config.challonge_api


class Tournament(commands.Cog):

    @commands.Cog.listener()
    async def on_ready(self):
        print("Tournament ready")

    # async def get_tournament_id(self):
    # result = requests.get(
    #     f"https://Bobbyperson:{api_key}@api.challonge.com/v1/tournaments.json"
    # )
    # print(result)
    # print(result.text)

    # if result.status_code == 200:
    #     data = result.json()[0]
    #     print(data)
    #     return data
    # return None

    async def get_participants(self, tournament_id):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",  # or any other user-agent you like
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
            "User-Agent": "FuckYouCloudflare/1.0",  # or any other user-agent you like
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
            "User-Agent": "FuckYouCloudflare/1.0",  # or any other user-agent you like
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
            ) and (
                match["match"]["state"] == "open"
                or match["match"]["state"] == "pending"  # ! temporary!!!!
            ):
                return match["match"]["id"]
        return None

    async def get_participant_discord_id(self, tournament_id, participant_id):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",  # or any other user-agent you like
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
                return value

        return None

    async def get_participants_in_match(self, tournament_id, match_id):
        headers = {
            "User-Agent": "FuckYouCloudflare/1.0",  # or any other user-agent you like
        }
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/matches/{match_id}/participants.json?api_key={api_key}",
            headers=headers,
        )

        if result.status_code == 200:
            data = result.json()
            return await self.get_participant(
                tournament_id, data["participant"]["player1_id"]
            ), await self.get_participant(
                tournament_id, data["participant"]["player2_id"]
            )
        return None

    @commands.command()
    @commands.is_owner()
    async def reserve(self, ctx):
        if not await utils.is_linked(ctx.author.id):
            return await ctx.send(
                "Your titanfall and discord accounts are not linked. Please join any of our servers and run the command `,.link` (besides the 1v1 server). Then run this command again."
            )

        author_uid = await utils.get_uid_from_connection(ctx.author.id)

        tournament_id = "jlkdx0i4"

        participants = await self.get_participants(tournament_id)

        author_participant_id = None

        for participant in participants:
            discord_id = await self.get_participant_discord_id(
                tournament_id, participant["participant"]["id"]
            )
            if (
                discord_id == str(ctx.author.id)
                or discord_id == ctx.author.name.lower()
            ):
                author_participant_id = participant["participant"]["id"]
                break

        if not author_participant_id:
            return await ctx.send(
                "Either you are not in the tournament, or you did not supply your discord id when signing up. Please edit your sign-in or ping Bobby."
            )

        await ctx.send("Found user. Checking for open match...")

        next_match = await self.get_participant_next_match(
            tournament_id, author_participant_id
        )

        opponent_discord_id = None
        opponent_uid = None

        if not next_match:
            return await ctx.send(
                "No match found! If you believe this is an error please ping bobby."
            )
        await ctx.send("Match found! Checking for opponent...")
        for participant in await self.get_participants_in_match(
            tournament_id, next_match
        ):
            if participant["participant"]["id"] != author_participant_id:
                opponent_discord_id = await self.get_participant_discord_id(
                    tournament_id, participant["participant"]["id"]
                )
                break

        if not opponent_discord_id:
            return await ctx.send(
                "Your opponent did not supply their discord id when signing up. Please ping them and ask them to edit their sign-in. Ping Bobby if needed."
            )

        opponent_uid = await utils.get_uid_from_name(opponent_discord_id)

        if not opponent_uid:
            opponent = await self.client.fetch_user(opponent_discord_id)
            return await ctx.send(
                f"Your opponent is not linked! {opponent.mention} please join any of our servers and run the command `.link` (besides the 1v1 server). Then run this command again."
            )

        # TODO: check if server already reserved (maybe see if currently occupied?)

        await ctx.send("All checks passed! Reserving server...")
        async with aiosqlite.connect(config.bank, timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM whitelist")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({opponent_uid})")
            await cursor.execute(f"INSERT INTO whitelist(uid) values({author_uid})")
            await db.commit()
        await ctx.send("Done! A server has been reserved.")


async def setup(client):
    await client.add_cog(Tournament(client))
