import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os
from datetime import datetime, timedelta
import re
import pytz
import asyncio
import xml.etree.ElementTree as ET
from http.cookies import SimpleCookie

YT_ATOM_NS = "http://www.w3.org/2005/Atom"
YT_NS = "http://www.youtube.com/xml/schemas/2015"
MEDIA_NS = "http://search.yahoo.com/mrss/"

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def build_youtube_consent_cookies():
    """Baut ein Consent-Cookie mit Domain-Geltungsbereich .youtube.com.

    Wichtig: Cookies, die nur pro Request via `cookies=` an session.get()
    übergeben werden, gehen bei einem Cross-Subdomain-Redirect (z. B.
    youtube.com -> consent.youtube.com) verloren, da aiohttp sie aus
    Sicherheitsgründen nicht automatisch weiterreicht. Deshalb tragen wir
    das Cookie stattdessen direkt mit Domain-Attribut in den Cookie-Jar
    der Session ein - der wird bei jedem Request/Redirect innerhalb von
    *.youtube.com automatisch berücksichtigt.
    """
    cookie = SimpleCookie()
    cookie["CONSENT"] = "YES+cb.20240101-00-p0.de+FX+000"
    cookie["CONSENT"]["domain"] = ".youtube.com"
    cookie["CONSENT"]["path"] = "/"
    cookie["SOCS"] = "CAI"
    cookie["SOCS"]["domain"] = ".youtube.com"
    cookie["SOCS"]["path"] = "/"
    return cookie


STATE_FILE = 'cogs/json/social_notifier_state.json'


class SocialNotifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.allowed_mentions = discord.AllowedMentions(users=True, roles=True)

        # Twitch Notifier
        self.channel_id = 123456789  # channel id für twitch benachrichtigungen
        self.twitch_channel_name = ""  # Name des Twitch-Kanals
        self.tw_discord_role = 123456789  # ID der Rolle, die benachrichtigt werden soll

        # YouTube Notifier
        self.role_id = 123456789  # ID der Rolle, die benachrichtigt werden soll
        self.discord_channel = 123456789
        self.channels = {
            "Name": "https://youtube.com/@test132" # Name des Kanals und URLS des Kanals, bitte ersetzen. Es könnten auch mehrere Kanäle hinzugefügt werden, einfach weitere Zeilen hinzufügen wie z.b. "Name2": "https://youtube.com/@test132"
        }
        self._channel_id_cache = {}  # channel_url -> UC...-Channel-ID (RSS-Auflösung)
        self.videos = {channel_name: [] for channel_name in self.channels}  # embeds
        self.last_checked = {channel_name: datetime.min.replace(tzinfo=pytz.utc) for channel_name in self.channels}
        self.timezone = pytz.timezone('Europe/Berlin')  # Setze die Zeitzone hier

        # Set für gesendete Video-IDs initialisieren
        self.sent_video_ids = {channel_name: set() for channel_name in self.channels}

        # Lade client_id und client_secret aus der config.json
        with open('cogs/json/config.json', 'r') as config_file:
            config = json.load(config_file)
            self.client_id = config.get('twitch_client_id')
            self.client_secret = config.get('twitch_client_secret')

        self.access_token = None
        self.stream_is_live = False

        # --- Persistenz ---
        self._state_lock = asyncio.Lock()
        # pending_updates: Liste von Dicts, die offene Footer-Updates beschreiben
        # {"type": "youtube"/"twitch", "channel_id": int, "message_id": int,
        #  "publish_time": iso-str, "t1": iso-str, "t2": iso-str, "stage": 0/1}
        self.pending_updates = []
        self.check_stream_status.start()
        self.checkvideos.start()
        self.load_state()
        asyncio.create_task(self._delayed_resume_pending_updates())
        
    async def _delayed_resume_pending_updates(self):
        """Wartet, bis der Bot vollständig verbunden ist, bevor offene Footer-Updates
        fortgesetzt werden — sonst liefert self.bot.get_channel() beim Start noch None,
        weil der Cache noch leer ist, und Einträge würden fälschlich verworfen."""
        await self.bot.wait_until_ready()
        self.resume_pending_updates()

    # ------------------------------------------------------------------
    # Persistenz-Helfer
    # ------------------------------------------------------------------
    def load_state(self):
        """Lädt gespeicherten Zustand aus der JSON-Datei, falls vorhanden."""
        if not os.path.exists(STATE_FILE):
            return

        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[SocialNotifier] Konnte State-Datei nicht laden: {e}")
            return

        youtube_state = data.get("youtube", {})
        for channel_name in self.channels:
            ch_state = youtube_state.get(channel_name)
            if not ch_state:
                continue
            self.videos[channel_name] = ch_state.get("videos", [])
            self.sent_video_ids[channel_name] = set(ch_state.get("sent_video_ids", []))
            last_checked_str = ch_state.get("last_checked")
            if last_checked_str:
                self.last_checked[channel_name] = datetime.fromisoformat(last_checked_str)

        self.stream_is_live = data.get("stream_is_live", False)
        self.pending_updates = data.get("pending_updates", [])

    def save_state(self):
        """Schreibt den aktuellen Zustand synchron in die JSON-Datei."""
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

        youtube_state = {}
        for channel_name in self.channels:
            youtube_state[channel_name] = {
                "videos": self.videos[channel_name],
                "sent_video_ids": list(self.sent_video_ids[channel_name]),
                "last_checked": self.last_checked[channel_name].isoformat(),
            }

        data = {
            "youtube": youtube_state,
            "stream_is_live": self.stream_is_live,
            "pending_updates": self.pending_updates,
        }

        tmp_path = STATE_FILE + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, STATE_FILE)  # atomarer Ersatz, verhindert korrupte Dateien

    async def async_save_state(self):
        """Thread-/Task-sicheres Speichern (mehrere Update-Tasks können gleichzeitig laufen)."""
        async with self._state_lock:
            self.save_state()

    def add_pending_update(self, update_type, channel_id, message_id, publish_time):
        """Registriert ein neues offenes Footer-Update und speichert es sofort."""
        t1 = self._next_midnight(publish_time)
        t2 = t1 + timedelta(seconds=86400)

        entry = {
            "type": update_type,
            "channel_id": channel_id,
            "message_id": message_id,
            "publish_time": publish_time.isoformat(),
            "t1": t1.isoformat(),
            "t2": t2.isoformat(),
            "stage": 0,
        }
        self.pending_updates.append(entry)
        self.save_state()
        return entry

    def remove_pending_update(self, entry):
        try:
            self.pending_updates.remove(entry)
        except ValueError:
            pass
        self.save_state()

    def _next_midnight(self, from_time):
        local_time = from_time.astimezone(self.timezone)
        next_midnight = (local_time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return next_midnight

    def resume_pending_updates(self):
        """Beim Start: offene Footer-Updates aus der letzten Sitzung wieder aufnehmen."""
        for entry in list(self.pending_updates):
            asyncio.get_event_loop().create_task(self._run_pending_update(entry))

    async def _run_pending_update(self, entry):
        """Führt ein (evtl. bereits teilweise erledigtes) Footer-Update fort."""
        channel = self.bot.get_channel(entry["channel_id"])
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(entry["channel_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                print(f"[SocialNotifier/Error] Konnte Kanal {entry['channel_id']} für offenes "
                      f"Footer-Update nicht finden, Eintrag wird verworfen: {e}")
                self.remove_pending_update(entry)
                return

        try:
            message = await channel.fetch_message(entry["message_id"])
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            self.remove_pending_update(entry)
            return

        publish_time = datetime.fromisoformat(entry["publish_time"])
        t1 = datetime.fromisoformat(entry["t1"])
        t2 = datetime.fromisoformat(entry["t2"])
        now = datetime.now(pytz.utc)

        prefix = "YouTube" if entry["type"] == "youtube" else "Twitch"
        icon_url = (
            "https://cdn2.iconfinder.com/data/icons/micon-social-pack/512/youtube-512.png"
            if entry["type"] == "youtube"
            else "https://cdn.discordapp.com/attachments/1275021566484414585/1296431882409476199/Unbenannt.png?ex=671243c7&is=6710f247&hm=1d024dc9f3ea47a39cf2a8ebe08bc5a856e6c5f0b9720d569a603ced22e4c8e9&"
        )

        if entry["stage"] == 0:
            wait_seconds = (t1 - now).total_seconds()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            await self._update_footer(message, publish_time, prefix, icon_url)
            entry["stage"] = 1
            self.save_state()
            now = datetime.now(pytz.utc)

        if entry["stage"] == 1:
            wait_seconds = (t2 - now).total_seconds()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            await self._update_footer(message, publish_time, prefix, icon_url)

        self.remove_pending_update(entry)

    async def _update_footer(self, message, publish_time, prefix, icon_url):
        if not message.embeds:
            return
        embed = message.embeds[0]
        footer_text = self.get_custom_footer_time(publish_time)
        embed.set_footer(text=f"{prefix} / {footer_text}", icon_url=icon_url)
        try:
            await message.edit(embed=embed)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
            print(f"[SocialNotifier] Konnte Embed nicht bearbeiten: {e}")

    # ------------------------------------------------------------------
    # Bestehende Hilfsfunktionen
    # ------------------------------------------------------------------
    def get_custom_footer_time(self, publish_time):
        """Generiert den Footer-Text basierend auf der Veröffentlichungszeit."""
        now = datetime.now(self.timezone)

        if publish_time.date() == now.date():
            return f"Heute um {publish_time.strftime('%H:%M')}"
        elif publish_time.date() == (now - timedelta(days=1)).date():
            return f"Gestern um {publish_time.strftime('%H:%M')}"
        else:
            return f"{publish_time.strftime('%d.%m.%y')} {publish_time.strftime('%H:%M')}"

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

    # ------------------------------------------------------------------
    # YouTube RSS-Hilfsfunktionen
    # ------------------------------------------------------------------
    async def resolve_channel_id(self, session, channel_url):
        """Löst eine @handle-URL zur echten UC...-Channel-ID auf (einmalig, dann gecacht)."""
        if channel_url in self._channel_id_cache:
            return self._channel_id_cache[channel_url]

        try:
            async with session.get(channel_url, headers=HTTP_HEADERS) as response:
                html = await response.text()
        except Exception as e:
            print(f"[SocialNotifier/Error] Konnte Kanalseite nicht laden ({channel_url}): {e}")
            return None

        # Mehrere bekannte Stellen ausprobieren, an denen YouTube die Channel-ID einbettet
        patterns = [
            r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
            r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
            r'<meta itemprop="channelId" content="(UC[a-zA-Z0-9_-]{22})"',
            r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})"',
        ]

        channel_id = None
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                channel_id = match.group(1)
                break

        if channel_id is None:
            print(f"[SocialNotifier/Error] Konnte channelId nicht aus {channel_url} extrahieren "
                  f"(HTML-Länge: {len(html)} Zeichen)")
            print(f"[SocialNotifier/Debug] Erste 300 Zeichen der Antwort: {html[:300]!r}")
            return None

        self._channel_id_cache[channel_url] = channel_id
        return channel_id

    async def fetch_channel_videos(self, session, channel_id):
        """Lädt die letzten Videos eines Kanals über den offiziellen YouTube-RSS-Feed."""
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            async with session.get(feed_url, headers=HTTP_HEADERS) as response:
                if response.status != 200:
                    print(f"[SocialNotifier/Error] RSS-Feed antwortete mit Status {response.status} ({feed_url})")
                    return []
                xml_text = await response.text()
        except Exception as e:
            print(f"[SocialNotifier/Error] Konnte RSS-Feed nicht laden ({feed_url}): {e}")
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            print(f"[SocialNotifier/Error] Konnte RSS-Feed nicht parsen: {e}")
            return []

        videos = []
        for entry in root.findall(f"{{{YT_ATOM_NS}}}entry"):
            video_id_el = entry.find(f"{{{YT_NS}}}videoId")
            title_el = entry.find(f"{{{YT_ATOM_NS}}}title")
            published_el = entry.find(f"{{{YT_ATOM_NS}}}published")

            if video_id_el is None or video_id_el.text is None:
                continue

            published_dt = None
            if published_el is not None and published_el.text:
                try:
                    published_dt = datetime.fromisoformat(published_el.text)
                except ValueError:
                    published_dt = None

            videos.append({
                "videoId": video_id_el.text,
                "title": title_el.text if title_el is not None else "Unbekannt",
                "publishedAt": published_dt,
            })

        return videos

    @commands.Cog.listener()
    async def on_ready(self):
        print("SocialNotifier is online!")

    # ------------------------------------------------------------------
    # YouTube
    # ------------------------------------------------------------------
    @tasks.loop(seconds=60)
    async def checkvideos(self):
        async with aiohttp.ClientSession(headers=HTTP_HEADERS) as session:
            session.cookie_jar.update_cookies(build_youtube_consent_cookies())
            for channel_name, channel_url in self.channels.items():
                try:
                    channel_id = await self.resolve_channel_id(session, channel_url)
                    if channel_id is None:
                        continue

                    videos = await self.fetch_channel_videos(session, channel_id)
                    #print(f"[SocialNotifier/Debug] {channel_name}: {len(videos)} Video(s) via RSS erhalten")

                    if not videos:
                        continue

                    video_ids = [video["videoId"] for video in videos]
                    if self.checkvideos.current_loop == 0:
                        self.videos[channel_name] = video_ids
                        self.save_state()
                        continue

                    for video in videos:
                        video_id = video["videoId"]
                        if video_id not in self.videos[channel_name] and video_id not in self.sent_video_ids[channel_name]:
                            url = f"https://youtu.be/{video_id}"
                            message_content = f"[**{channel_name}**]({channel_url}) hat ein **neues Video** hochgeladen! <@&{self.role_id}>"

                            video_url = f"https://youtu.be/{video_id}"
                            link_field = f"[Hier ansehen]({video_url})"

                            embed = discord.Embed(
                                title=video["title"],
                                url=url,
                                description="",
                                color=0xFF0000
                            )
                            embed.set_author(name=f"{channel_name} - YouTube", icon_url="https://cdn.discordapp.com/attachments/1002302289626804244/1281596642306424904/Among_Us_Distraction_Dance_GIF_-_Among_Us_Distraction_Dance_Green_Screen_-_Discover__Share_GIFs.gif?ex=66dc4b62&is=66daf9e2&hm=183f2668bff83283f5b96d824da97e1d3b42340b27dc8cc7dbd7104cc8612812&")
                            embed.add_field(name="Link", value=link_field)

                            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

                            async with session.get(thumbnail_url) as response:
                                if response.status != 200:
                                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

                            embed.set_image(url=thumbnail_url)

                            publish_time = video["publishedAt"]
                            if publish_time is None:
                                publish_time = datetime.utcnow().replace(tzinfo=pytz.utc)

                            publish_time = publish_time.astimezone(self.timezone)

                            footer_text = self.get_custom_footer_time(publish_time)
                            embed.set_footer(text=f"YouTube / {footer_text}", icon_url="https://cdn2.iconfinder.com/data/icons/micon-social-pack/512/youtube-512.png")

                            if publish_time > self.last_checked[channel_name]:
                                self.last_checked[channel_name] = publish_time
                                try:
                                    discord_channel = self.bot.get_channel(self.discord_channel)
                                    sent_message = await discord_channel.send(content=message_content, embed=embed, allowed_mentions=self.allowed_mentions)
                                    if sent_message is not None:
                                        entry = self.add_pending_update(
                                            "youtube", self.discord_channel, sent_message.id, publish_time
                                        )
                                        # non-blocking: läuft im Hintergrund weiter, blockiert den Loop nicht
                                        asyncio.create_task(self._run_pending_update(entry))
                                    else:
                                        print("[Warning / YouTube]: sent_message ist None, Footer-Update wird nicht geplant.")
                                except Exception as e:
                                    print(f"[Error / YouTube]: Fehler beim Senden der Nachricht: {e}")

                            self.sent_video_ids[channel_name].add(video_id)

                    self.videos[channel_name] = video_ids
                    self.save_state()

                except Exception as e:
                    print(f"Fehler beim Verarbeiten des Kanals {channel_name}: {e}")

    # ------------------------------------------------------------------
    # Twitch
    # ------------------------------------------------------------------
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
                if response.status == 401:
                    await self.get_access_token()
                    return

                data = await response.json()

                if data.get("data"):
                    stream = data["data"][0]
                    if not self.stream_is_live:
                        await self.notify_live(stream)
                        self.stream_is_live = True
                        self.save_state()
                else:
                    if self.stream_is_live:
                        self.stream_is_live = False
                        self.save_state()

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
        message_content = f"**[{self.twitch_channel_name}](https://twitch.tv/{self.twitch_channel_name})** ist live auf Twitch! <@&{self.tw_discord_role}>"

        embed = discord.Embed(
            title=f"**{title}**",
            url=stream_url,
            description="",
            color=discord.Color.purple()
        )
        embed.set_author(name=f"{self.twitch_channel_name} - Twitch", icon_url="https://media.discordapp.net/attachments/1002302289626804244/1281715175732543629/amaGHG.png?ex=6710cd07&is=670f7b87&hm=4983ec1312cd6b66f2c54e9efc3943c07ca82e6bcfd317aeac11bf504a857c92&")
        embed.set_image(url=thumbnail_url)
        embed.add_field(name="Spiel:", value=game_name)
        embed.add_field(name="Zuschauer:", value=viewer_count)

        publish_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(self.timezone)
        footer_text = self.get_custom_footer_time(publish_time)
        embed.set_footer(text=f"Twitch / {footer_text}", icon_url="https://cdn.discordapp.com/attachments/1275021566484414585/1296431882409476199/Unbenannt.png?ex=671243c7&is=6710f247&hm=1d024dc9f3ea47a39cf2a8ebe08bc5a856e6c5f0b9720d569a603ced22e4c8e9&")

        try:
            discord_channel = self.bot.get_channel(self.channel_id)
            sent_message = await discord_channel.send(content=message_content, embed=embed, allowed_mentions=self.allowed_mentions)
            if sent_message is not None:
                entry = self.add_pending_update(
                    "twitch", self.channel_id, sent_message.id, publish_time
                )
                asyncio.create_task(self._run_pending_update(entry))
            else:
                print("[Warning / Twitch]: sent_message ist None, Footer-Update wird nicht geplant.")
        except Exception as e:
            print(f"[Error / Twitch]: Fehler beim Senden der Nachricht: {e}")


async def setup(bot):
    await bot.add_cog(SocialNotifier(bot))