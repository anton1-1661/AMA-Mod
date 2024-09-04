import discord
from discord.ext import commands, tasks
import aiohttp
import json
from datetime import datetime

class TwitchNotifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1274432388889448448  # Standard Channel-ID
        self.webhook_url = "https://discord.com/api/webhooks/1277152198907920456/y35xY4nHKoafCUemlCOuH7rnKTvXS8msNyvvO7mwLLGclBiQiB1emU6P2vq9AIGlggDa"  # Standard Webhook-URL
        self.twitch_channel_name = "amaghg"  # Name des Twitch-Kanals
        self.role_id = 1274253001887977502  # ID der Rolle, die benachrichtigt werden soll

        # Lade client_id und client_secret aus der config.json
        with open('cogs/json/config.json', 'r') as config_file:
            config = json.load(config_file)
            self.client_id = config.get('twitch_client_id')
            self.client_secret = config.get('twitch_client_secret')
        
        self.access_token = None
        self.stream_is_live = False

        self.check_stream_status.start()

    def cog_unload(self):
        self.check_stream_status.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print("TwitchNotifier is online!")

    @tasks.loop(seconds=60)
    async def check_stream_status(self):
        if self.access_token is None:
            await self.get_access_token()

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.twitch.tv/helix/streams?user_login={self.twitch_channel_name}", headers=headers) as response:
                if response.status == 401:  # Unauthorized, token expired
                    await self.get_access_token()
                    return

                data = await response.json()

                if data.get("data"):
                    stream = data["data"][0]
                    if not self.stream_is_live:
                        await self.notify_live(stream)
                        self.stream_is_live = True
                else:
                    self.stream_is_live = False

    async def get_access_token(self):
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params) as response:
                data = await response.json()
                self.access_token = data["access_token"]

    async def notify_live(self, stream):
        title = stream["title"]
        game_name = stream["game_name"]
        viewer_count = stream["viewer_count"]
        thumbnail_url = stream["thumbnail_url"].format(width=1280, height=720)
        live_time = datetime.now().strftime('%d.%m.%Y %H:%M')  # Zeit in Form 'Tag.Monat.Jahr Stunde:Minute'

        embed = {
            "title": f"{self.twitch_channel_name} ist jetzt live auf Twitch!",
            "url": f"https://twitch.tv/{self.twitch_channel_name}",
            "description": f"**{title}**",
            "color": 6570406,  # Farbe des Embeds
            "fields": [
                {"name": "Spiel", "value": game_name, "inline": True},
                {"name": "Zuschauer", "value": str(viewer_count), "inline": True}
            ],
            "image": {"url": thumbnail_url},
            "footer": {"text": f"Live seit {live_time}"}
        }

        message_content = f"<@&{self.role_id}> **{self.twitch_channel_name}** ist **live** auf Twitch!"

        async with aiohttp.ClientSession() as session:
            if self.webhook_url:
                webhook = discord.Webhook.from_url(self.webhook_url, session=session)
                await webhook.send(content=message_content, embed=discord.Embed.from_dict(embed))
            else:
                channel = self.bot.get_channel(self.channel_id)
                if channel:
                    await channel.send(content=message_content, embed=discord.Embed.from_dict(embed))

    @commands.command()
    @commands.has_any_role("|| Admin")
    async def setchanneltw(self, ctx, channel: discord.TextChannel):
        self.channel_id = channel.id
        await ctx.send(f'Twitch-Benachrichtigungskanal wurde auf {channel.mention} gesetzt.')

    @commands.command()
    @commands.has_any_role("|| Admin")
    async def setwebhooktw(self, ctx, url: str):
        self.webhook_url = url
        await ctx.send(f'Webhook wurde auf {url} gesetzt.')

async def setup(bot):
    await bot.add_cog(TwitchNotifier(bot))
