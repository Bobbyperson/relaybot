from discord.ext import commands
import config
import requests


api_key = config.challonge_api


class Tournament(commands.Cog):

    @commands.Cog.listener()
    async def on_ready(self):
        print("Tournament ready")

    async def get_tournament_id(self, ctx):
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments.json?api_key={api_key}"
        )

        if result.status_code == 200:
            data = result.json()[0]
            return data
        return None

    async def get_participants(self, tournament_id):
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/participants.json?api_key={api_key}"
        )

        if result.status_code == 200:
            data = result.json()
            return data
        return None

    async def get_matches(self, tournament_id):
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/matches.json?api_key={api_key}"
        )

        if result.status_code == 200:
            data = result.json()
            return data
        return None

    async def participant_has_open_match(self, tournament_id, participant_id):
        result = requests.get(
            f"https://api.challonge.com/v1/tournaments/{tournament_id}/participants/{participant_id}/has_open_match.json?api_key={api_key}"
        )

        if result.status_code == 200:
            data = result.json()
            return data
        return None


async def setup(client):
    await client.add_cog(Tournament(client))
