import discord
from discord.ext import commands, tasks
import aiohttp
import scrapetube
from datetime import datetime, timedelta
import re
import pytz  # Für Zeitzonen

class YouTube(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channels = {
            "AMA": "https://youtube.com/@ama1155",
            "Anton": "https://youtube.com/@antonxd1426",
            "Lol": "https://youtube.com/@antonlol1155"  # Beispielkanal
        }
        self.videos = {channel_name: [] for channel_name in self.channels}
        self.webhook_url = "https://discord.com/api/webhooks/1276184240706420787/GoBMxY-is0Y4BFOhoUyWgXnKu4Ew9R432_GtfKBFtsomqUoDFuh9Gmz1fma9iZLoiK0Q"
        self.discord_channel_id = 1147043427012329482
        self.last_checked = {channel_name: datetime.min for channel_name in self.channels}
        self.timezone = pytz.timezone('Europe/Berlin')  # Setze die Zeitzone hier

    @commands.Cog.listener()
    async def on_ready(self):
        self.checkvideos.start()
        print("YouTubeChecker is online!")

    @tasks.loop(seconds=60)
    async def checkvideos(self):
        discord_channel = self.bot.get_channel(self.discord_channel_id)

        if not discord_channel:
            print("Kein Discord-Kanal gesetzt. Bitte mit !setchannelyt einen Kanal festlegen.")
            return

        for channel_name, channel_url in self.channels.items():
            try:
                videos = list(scrapetube.get_channel(channel_url=channel_url, limit=5))

                if not videos:
                    continue

                video_ids = [video.get("videoId") for video in videos]
                if self.checkvideos.current_loop == 0:
                    self.videos[channel_name] = video_ids
                    continue

                for video in videos:
                    video_id = video.get("videoId")
                    if video_id not in self.videos[channel_name]:
                        url = f"https://youtu.be/{video_id}"
                        message = f"<@&1274253001887977502> **{channel_name}** hat ein **neues Video** hochgeladen!"

                        # Den Video-Link erstellen und die Länge mit einem anklickbaren Link versehen
                        video_url = f"https://youtu.be/{video_id}"
                        length = video.get("lengthText", {}).get("simpleText", "Unbekannt")
                        length_with_link = f"[{length}]({video_url})"

                        # Erstellen des Embeds
                        embed = discord.Embed(
                            title=video.get("title", "Kein Titel"),
                            url=url,
                            description="",
                            color=discord.Color.red()
                        )
                        embed.set_author(name=f"{channel_name} - YouTube")
                        embed.add_field(name="Länge", value=length_with_link, inline=True)

                        # Prüfen, ob die Bild-URL vorhanden und gut formatiert ist
                        thumbnail_url = video.get("thumbnail", {}).get("thumbnails", [{}])[0].get("url")
                        if thumbnail_url and self.is_valid_url(thumbnail_url):
                            embed.set_image(url=thumbnail_url)
                        else:
                            embed.set_image(url="https://via.placeholder.com/150")  # Platzhalterbild, wenn URL ungültig

                        published_time_str = video.get("publishedTimeText", {}).get("simpleText", "Unbekannt")
                        publish_time = self.convert_relative_time(published_time_str)

                        if publish_time:
                            formatted_time = publish_time.astimezone(self.timezone).strftime('%d. %B %Y, %H:%M Uhr')
                            embed.set_footer(text=f"Hochgeladen: {formatted_time}")
                            if publish_time > self.last_checked[channel_name]:
                                self.last_checked[channel_name] = publish_time
                        else:
                            embed.set_footer(text="Hochgeladen um Unbekannt")

                        # Nachricht senden
                        if self.webhook_url:
                            async with aiohttp.ClientSession() as session:
                                webhook = discord.Webhook.from_url(self.webhook_url, session=session)
                                await webhook.send(content=message, embed=embed)
                        elif discord_channel:
                            await discord_channel.send(content=message, embed=embed)

                        # Update der Video-ID-Liste
                        self.videos[channel_name].append(video_id)

            except Exception as e:
                print(f"Fehler beim Verarbeiten des Kanals {channel_name}: {e}")

    def convert_relative_time(self, relative_time_str):
        """Konvertiert relative Zeitangaben wie '3 days ago' in ein absolutes Datum."""
        match = re.match(r'(\d+)\s*(day|days|hour|hours|minute|minutes|second|seconds)\s*ago', relative_time_str)
        if not match:
            return None

        amount, unit = match.groups()
        amount = int(amount)

        now = datetime.utcnow()
        if unit in ['day', 'days']:
            return now - timedelta(days=amount)
        elif unit in ['hour', 'hours']:
            return now - timedelta(hours=amount)
        elif unit in ['minute', 'minutes']:
            return now - timedelta(minutes=amount)
        elif unit in ['second', 'seconds']:
            return now - timedelta(seconds=amount)
        else:
            return None

    def is_valid_url(self, url):
        """Überprüft, ob die gegebene URL gut formatiert ist."""
        try:
            result = re.match(r'^https?://[^\s/$.?#].[^\s]*$', url)
            return result is not None
        except:
            return False

    @commands.command()
    @commands.has_any_role("|| Admin")
    async def setchannelyt(self, ctx, channel: discord.TextChannel):
        self.discord_channel_id = channel.id
        await ctx.send(f'YouTube-Benachrichtigungskanal wurde auf {channel.mention} gesetzt.')

    @commands.command()
    @commands.has_any_role("|| Admin")
    async def setwebhookyt(self, ctx, url: str):
        self.webhook_url = url
        await ctx.send(f'Webhook wurde auf {url} gesetzt.')

async def setup(bot):
    await bot.add_cog(YouTube(bot))