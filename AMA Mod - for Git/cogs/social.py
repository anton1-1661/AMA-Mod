import discord
from discord.ext import commands, tasks
import aiohttp
import json
import scrapetube
from datetime import datetime, timedelta
import re
import pytz
import asyncio

class SocialNotifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.allowed_mentions = discord.AllowedMentions(users=True)

        # Twitch Notifier
        self.channel_id = 1234567890123456789  # Standard Channel-ID für Twitch
        self.twitch_webhook_url = ""  # Webhook-URL für Twitch
        self.twitch_channel_name = ""  # Name des Twitch-Kanals

        # YouTube Notifier
        self.youtube_webhook_url = ""  # Webhook-URL für YouTube
        self.role_id = 1234567890123456789  # ID der Rolle, die benachrichtigt werden soll
        self.discord_channel_id = 1234567890123456789 # Standart channel für YouTube
        self.channels = {
            "Test": "https://youtube.com/@test" # Beispielkanal
        }
        self.videos = {channel_name: [] for channel_name in self.channels}
        self.last_checked = {channel_name: datetime.min.replace(tzinfo=pytz.utc) for channel_name in self.channels}
        self.timezone = pytz.timezone('Europe/Berlin')  # Zeitzone

        # Lade client_id und client_secret aus der config.json / Twitch
        with open('cogs/json/config.json', 'r') as config_file:
            config = json.load(config_file)
            self.client_id = config.get('twitch_client_id')
            self.client_secret = config.get('twitch_client_secret')
            self.twicon_url = config["twicon_url"]

        self.access_token = None
        self.stream_is_live = False

        self.check_stream_status.start()
        self.checkvideos.start()

    def extract_text_from_json(self, json_data):
        """Extrahiert einfachen Text aus einer komplexen JSON-Textstruktur."""
        if isinstance(json_data, dict) and "runs" in json_data:
            runs = json_data["runs"]
            if isinstance(runs, list) and len(runs) > 0 and "text" in runs[0]:
                return runs[0]["text"]
        return "Unbekannt"

    def convert_relative_time(self, relative_time_str):
        """Konvertiert relative Zeitangaben wie '3 days ago' in ein absolutes Datum."""
        if not relative_time_str:
            return None

        match = re.match(r'(\d+)\s*(day|days|hour|hours|minute|minutes|second|seconds)\s*ago', relative_time_str)
        if not match:
            return None

        amount, unit = match.groups()
        amount = int(amount)

        now = datetime.utcnow().replace(tzinfo=pytz.utc)  # UTC Zeit mit Zeitzone
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

    def get_formatted_time(self, publish_time):
        """Formatiert die Veröffentlichungszeit in ein lesbares Format."""
        now = datetime.now(self.timezone)  # Aktuelle Zeit in 'Europe/Berlin'
        publish_time = publish_time.astimezone(self.timezone)  # Veröffentlichte Zeit in 'Europe/Berlin'

        if publish_time.date() == now.date():
            return f"Heute um {publish_time.strftime('%H:%M')}"
        elif publish_time.date() == (now - timedelta(days=1)).date():
            return f"Gestern um {publish_time.strftime('%H:%M')}"
        else:
            return f"{publish_time.strftime('%d.%m.%y um %H:%M')}"

    def is_valid_url(self, url):
        """Überprüft, ob die gegebene URL gut formatiert ist."""
        try:
            result = re.match(r'^https?://[^\s/$.?#].[^\s]*$', url)
            return result is not None
        except:
            return False

    def cog_unload(self):
        self.check_stream_status.cancel()
        self.checkvideos.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print("SocialNotifier is online!")

    @tasks.loop(seconds=60)
    async def checkvideos(self):
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
                        message_content = f"[**{channel_name}**]({channel_url}) hat ein **neues Video** hochgeladen! <@&{self.role_id}>"

                        # Den Video-Link erstellen und die Länge in einem separaten Feld darstellen
                        video_url = f"https://youtu.be/{video_id}"
                        length = video.get("lengthText", {}).get("simpleText", "Unbekannt")
                        length_field = f"{length}"
                        link_field = f"[Hier ansehen]({video_url})"  # Linkfeld für das Video

                        # Erstellen des Embeds ohne Bild, aber mit Thumbnail
                        embed = discord.Embed(
                            title=self.extract_text_from_json(video.get("title", {})),
                            url=url,
                            description="",
                            color=0xFF0000
                        )
                        embed.set_author(name=f"{channel_name} - YouTube", icon_url="https://cdn.discordapp.com/attachments/1002302289626804244/1281596642306424904/Among_Us_Distraction_Dance_GIF_-_Among_Us_Distraction_Dance_Green_Screen_-_Discover__Share_GIFs.gif?ex=66dc4b62&is=66daf9e2&hm=183f2668bff83283f5b96d824da97e1d3b42340b27dc8cc7dbd7104cc8612812&")
                        embed.add_field(name="Länge", value=length_field)  # Länge ohne Link
                        embed.add_field(name="Link", value=link_field)  # Link zum Video

                        # Generiere Thumbnail URL
                        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

                        # Versuche das Bild zu laden, falls nicht verfügbar, verwende hqdefault.jpg
                        async with aiohttp.ClientSession() as session:
                            async with session.get(thumbnail_url) as response:
                                if response.status != 200:  # Wenn maxresdefault.jpg nicht verfügbar ist
                                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

                        # Füge das Bild in den Embed ein
                        embed.set_image(url=thumbnail_url)

                        published_time_str = self.extract_text_from_json(video.get("publishedTimeText", {}))
                        publish_time = self.convert_relative_time(published_time_str)

                        if publish_time is None:
                            publish_time = datetime.utcnow().replace(tzinfo=pytz.utc)  # Setze auf aktuelle Zeit in UTC, wenn keine gültige Zeit vorhanden ist

                        # Konvertiere die Veröffentlichungszeit in die definierte Zeitzone
                        publish_time = publish_time.astimezone(self.timezone)

                        # Setze den Footer je nach Veröffentlichungszeit
                        footer_text = self.get_formatted_time(publish_time)
                        embed.set_footer(text=f"YouTube / {footer_text}", icon_url="https://www.google.com/url?sa=i&url=https%3A%2F%2Fwww.vecteezy.com%2Ffree-png%2Fyoutube-icon-png&psig=AOvVaw3g-YhHWKme-RgXyQfkDbhd&ust=1728660915846000&source=images&cd=vfe&opi=89978449&ved=0CBEQjRxqFwoTCNjPmu6RhIkDFQAAAAAdAAAAABAS")

                        # Nachricht senden
                        if publish_time > self.last_checked[channel_name]:
                            self.last_checked[channel_name] = publish_time
                            
                            # Sende die Nachricht in den festgelegten Discord-Kanal
                            discord_channel = self.bot.get_channel(self.discord_channel_id)
                            if self.youtube_webhook_url:
                                sent_message = await discord_channel.send(content=message_content, embed=embed, allowed_mentions=self.allowed_mentions)
                            
                                # Füge eine Task hinzu, um das Embed nach Mitternacht zu aktualisieren
                                await self.update_embed_after_midnight(sent_message, publish_time)
                            else:
                                print(f"Discord-Kanal mit ID {self.discord_channel_id} nicht gefunden.")

            except Exception as e:
                print(f"Fehler beim Verarbeiten des Kanals {channel_name}: {e}")

    # Neue Funktion, die das Embed nach Mitternacht bearbeitet
    async def update_embed_after_midnight(self, message, publish_time):
        """Wartet bis nach Mitternacht und aktualisiert dann das Embed mit neuen Informationen."""
        now = datetime.now(self.timezone)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_until_midnight = (next_midnight - now).total_seconds()

        # Warte bis nach Mitternacht
        await asyncio.sleep(seconds_until_midnight)

        # Aktualisiere den Embed-Footer nach Mitternacht
        embed = message.embeds[0]
        footer_text = self.get_formatted_time(publish_time)
        embed.set_footer(text=f"YouTube / {footer_text}", icon_url="https://www.google.com/url?sa=i&url=https%3A%2F%2Fwww.vecteezy.com%2Ffree-png%2Fyoutube-icon-png&psig=AOvVaw3g-YhHWKme-RgXyQfkDbhd&ust=1728660915846000&source=images&cd=vfe&opi=89978449&ved=0CBEQjRxqFwoTCNjPmu6RhIkDFQAAAAAdAAAAABAS")

        # Bearbeite das ursprüngliche Embed
        await message.edit(embed=embed)

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
        title = stream.get("title", "Kein Titel")
        game_name = stream.get("game_name", "Kein Spiel")
        thumbnail_url = stream.get("thumbnail_url", "").format(width=1280, height=720)
        viewer_count = stream.get("viewer_count", "Unbekannt")
        stream_url = f"https://www.twitch.tv/{self.twitch_channel_name}"
        twrole_id = 1261325628943110154
        message_content = f"**[{self.twitch_channel_name}](https://twitch.tv/{self.twitch_channel_name})** ist live auf Twitch! <@&{twrole_id}>"

        embed = discord.Embed(
            title=f"**{title}**",
            url=stream_url,
            description="",
            color=discord.Color.purple()  # Setze die Farbe auf Lila, oder ersetze 0xFF0000 für saftiges Rot
        )
        twicon_url = self.twicon_url
        embed.set_author(name=f"{self.twitch_channel_name} - Twitch", icon_url=twicon_url)
        embed.set_image(url=thumbnail_url)
        embed.add_field(name="Spiel:", value=game_name)
        embed.add_field(name="Zuschauer:", value=viewer_count)
        embed.set_footer(text=f"Twitch / ") # Footer noch nicht fertig!!

        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(self.twitch_webhook_url, session=session)
                await webhook.send(content=message_content, embed=embed, allowed_mentions=self.allowed_mentions)
        except Exception as e:
            print(f"Fehler beim Versenden der Benachrichtigung: {e}")

async def setup(bot):
    await bot.add_cog(SocialNotifier(bot))
