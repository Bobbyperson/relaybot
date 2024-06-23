import discord
from discord.ext import commands
import requests
import json


class Parkour(commands.Cog):
    """Parkour commands."""
    def __init__(self, client):
        self.client = client

    # events
    @commands.Cog.listener()
    async def on_ready(self):
        print("Parkour ready")
        
    @commands.command()
    @commands.is_owner()
    async def get_events(self, ctx):
        response = requests.get('https://parkour.bluetick.dev/v1/events', headers={"authentication": "holyshitballsbatman051404"})
        pretty_json = json.dumps(response.json(), indent=4)  # This makes it pretty
        pretty_json = pretty_json.replace('    ', '\t')
        if len(pretty_json) > 1900:  # Considering the markdown backticks and json tag
            for chunk in [pretty_json[i:i+1900] for i in range(0, len(pretty_json), 1900)]:
                await ctx.send(f'```json\n{chunk}\n```')
        else:
            await ctx.send(f'```json\n{pretty_json}\n```')

        
    @commands.command()
    @commands.is_owner()
    async def create_event(self, ctx, *, arg):
        try:
            data = json.loads(arg)
            response = requests.post('https://parkour.bluetick.dev/v1/events', headers={"authentication": "holyshitballsbatman051404"}, json=data)
            await ctx.send(f'Response Code: {response.status_code}\nContent: {response.content}')
        except json.JSONDecodeError:
            await ctx.send('That\'s not valid JSON. :(')
            
    @commands.command()
    @commands.is_owner()
    async def get_event_maps(self, ctx, event_id):
        response = requests.get(f'https://parkour.bluetick.dev/v1/events/{event_id}/maps', headers={"authentication": "holyshitballsbatman051404"})
        pretty_json = json.dumps(response.json(), indent=4)  # This makes it pretty
        pretty_json = pretty_json.replace('    ', '\t')
        if len(pretty_json) > 1900:  # Considering the markdown backticks and json tag
            for chunk in [pretty_json[i:i+1900] for i in range(0, len(pretty_json), 1900)]:
                await ctx.send(f'```json\n{chunk}\n```')
        else:
            await ctx.send(f'```json\n{pretty_json}\n```')

        
    @commands.command()
    @commands.is_owner()
    async def create_event_map(self, ctx, event_id, *, arg):
        try:
            data = json.loads(arg)
            response = requests.post(f'https://parkour.bluetick.dev/v1/events/{event_id}/maps', headers={"authentication": "holyshitballsbatman051404"}, json=data)
            await ctx.send(f'Response Code: {response.status_code}\nContent: {response.content}')
        except json.JSONDecodeError:
            await ctx.send('Check your JSON!')
            
    @commands.command()
    @commands.is_owner()
    async def get_map_scores(self, ctx, map_id):
        response = requests.get(f'https://parkour.bluetick.dev/v1/maps/{map_id}/scores', headers={"authentication": "holyshitballsbatman051404"})
        pretty_json = json.dumps(response.json(), indent=4)  # This makes it pretty
        pretty_json = pretty_json.replace('    ', '\t')
        if len(pretty_json) > 1900:  # Considering the markdown backticks and json tag
            for chunk in [pretty_json[i:i+1900] for i in range(0, len(pretty_json), 1900)]:
                await ctx.send(f'```json\n{chunk}\n```')
        else:
            await ctx.send(f'```json\n{pretty_json}\n```')

        
    @commands.command()
    @commands.is_owner()
    async def create_map_score(self, ctx, map_id, *, arg):
        try:
            data = json.loads(arg)
            response = requests.post(f'https://parkour.bluetick.dev/v1/maps/{map_id}/scores', headers={"authentication": "holyshitballsbatman051404"}, json=data)
            await ctx.send(f'Response Code: {response.status_code}\nContent: {response.content}')
        except json.JSONDecodeError:
            await ctx.send('Fix that JSON.')

    @commands.command()
    @commands.is_owner()
    async def get_map_config(self, ctx, map_id):
        response = requests.get(f'https://parkour.bluetick.dev/v1/maps/{map_id}/configuration', headers={"authentication": "holyshitballsbatman051404"})
        pretty_json = json.dumps(response.json(), indent=4)  # This makes it pretty
        pretty_json = pretty_json.replace('    ', '\t')
        if len(pretty_json) > 1900:  # Considering the markdown backticks and json tag
            for chunk in [pretty_json[i:i+1900] for i in range(0, len(pretty_json), 1900)]:
                await ctx.send(f'```json\n{chunk}\n```')
        else:
            await ctx.send(f'```json\n{pretty_json}\n```')

    @commands.command()
    @commands.is_owner()
    async def update_map_config(self, ctx, map_id, *, arg):
        try:
            data = json.loads(arg)
            response = requests.post(f'https://parkour.bluetick.dev/v1/maps/{map_id}/configuration', headers={"authentication": "holyshitballsbatman051404"}, json=data)
            await ctx.send(f'Response Code: {response.status_code}\nContent: {response.content}')
        except json.JSONDecodeError:
            await ctx.send('Oh, come on, you can do better. That JSON is a mess.')

        
async def setup(client):
    await client.add_cog(Parkour(client))