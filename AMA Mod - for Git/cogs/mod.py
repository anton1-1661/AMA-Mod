from email.mime import message

import discord
from discord.ext import commands
import json
import datetime
import pytz
import os
import easy_pil
import random
import uuid

STATE_FILE = 'cogs/json/reaction_roles_state.json'  # Zum Erstellen eindeutiger IDs


def has_timeout_permission():
    async def predicate(ctx):  # Prüft, ob der Benutzer über Admin- oder Timeout-Rechte verfügt
        return any(role.permissions.administrator or role.permissions.moderate_members for role in ctx.author.roles)
    return commands.check(predicate)


class Moderation(commands.Cog):
    BAD_WORD_WARN_THRESHOLD = 3  # Nach so vielen gelöschten Nachrichten folgt eine automatische Verwarnung
    BAD_WORD_OFFENSE_WINDOW_DAYS = 7  # Nur Verstöße innerhalb dieses Zeitfensters zählen mit

    def __init__(self, bot):
        self.bot = bot
        self.reaction_roles = {}  # Emojis zu Rollen
        self.reaction_messages = {}  # Nachrichten IDs zu Emojis
        self.reaction_locations = {}  # message_id -> {"channel_id": int, "guild_id": int}, für Jump-Links    def load_state(self):
        self.load_state()
        self.allowed_mentions = discord.AllowedMentions(users=True)
        self.bad_words = self.load_bad_words()  # Schimpfwörter laden
        self.bot_deleted_messages = {}  # message_id -> Grund, für zuverlässige Logs bei bot-eigenen Löschungen
        self.bad_word_offenses = {}  # user_id -> Anzahl gelöschter Bad-Word-Nachrichten seit letzter Auto-Verwarnung
        self.message_log_channel = 1232456789 # Channel-ID für Nachrichten-Logs Z.b. nachrichten edits und nachrichten löschungen
        self.mod_logs_channel = 123456789 # Channel-ID für Moderations-Logs

        # Lade Daten (Warnungen)
        self.data = self.load_data()
        
    def load_state(self):
        """Lädt gespeicherte Reaction-Roles aus der JSON-Datei, falls vorhanden."""
        if not os.path.exists(STATE_FILE):
            return

        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[ReactionRoles] Konnte State-Datei nicht laden: {e}")
            return

        self.reaction_roles = data.get("reaction_roles", {})
        self.reaction_locations = data.get("reaction_locations", {})
 
    def save_state(self):
        """Schreibt den aktuellen Zustand synchron in die JSON-Datei."""
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

        data = {
            "reaction_roles": self.reaction_roles,
            "reaction_locations": self.reaction_locations,
        }

        tmp_path = STATE_FILE + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, STATE_FILE)  # atomarer Ersatz, verhindert korrupte Dateien

    def load_data(self):
        try:
            with open("cogs/json/warn.json", "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_data(self):
        with open("cogs/json/warn.json", "w") as f:
            json.dump(self.data, f, indent=4)
        
    def load_bad_words(self):
        """Lädt die Liste der Schimpfwörter aus einer JSON-Datei."""
        try:
            with open("cogs/json/bad_words.json", "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_bad_words(self):
        """Speichert die Liste der Schimpfwörter in einer JSON-Datei."""
        with open("cogs/json/bad_words.json", "w") as f:
            json.dump(self.bad_words, f, indent=4)

    async def register_bad_word_offense(self, message):
        """Zählt Schimpfwort-Löschungen der letzten BAD_WORD_OFFENSE_WINDOW_DAYS Tage pro User
        (persistent in warn.json) und verwarnt automatisch nach mehrfachem Verstoß."""
        member = message.author
        guild_id = str(message.guild.id)
        member_id = str(member.id)
        now = datetime.datetime.now(pytz.utc)
        window = datetime.timedelta(days=self.BAD_WORD_OFFENSE_WINDOW_DAYS)

        offenses = self.data.setdefault("bad_word_offenses", {}).setdefault(guild_id, {}).setdefault(member_id, [])

        # Verstöße außerhalb des Zeitfensters entfernen (werden dadurch "vergessen")
        offenses[:] = [ts for ts in offenses if now - datetime.datetime.fromisoformat(ts) <= window]

        offenses.append(now.isoformat())
        self.save_data()

        if len(offenses) < self.BAD_WORD_WARN_THRESHOLD:
            return

        offenses.clear()  # Zähler zurücksetzen
        self.save_data()

        guild_id_key = guild_id
        member_id_key = member_id
        reason = f"Automatische Verwarnung: {self.BAD_WORD_WARN_THRESHOLD}x Nachricht mit unerlaubtem Wort " \
                 f"innerhalb von {self.BAD_WORD_OFFENSE_WINDOW_DAYS} Tagen gelöscht"

        if guild_id_key not in self.data:
            self.data[guild_id_key] = {}
        if member_id_key not in self.data[guild_id_key]:
            self.data[guild_id_key][member_id_key] = []

        berlin_tz = pytz.timezone('Europe/Berlin')
        berlin_time = datetime.datetime.now(berlin_tz)
        timestamp = berlin_time.strftime("%d. %B %Y, %H:%M:%S")

        warn_id = self.data.get("warn_id", 0) + 1
        self.data["warn_id"] = warn_id

        self.data[guild_id_key][member_id_key].append({
            "id": warn_id,
            "reason": reason,
            "moderator": str(self.bot.user),
            "moderator_id": str(self.bot.user.id),
            "timestamp": timestamp
        })
        self.save_data()

        await message.channel.send(
            f"{member.mention} wurde **gewarnt** von {self.bot.user.mention} \n\n"
            f"**Grund**: {reason}\n**Warn-ID**: {warn_id}",
            allowed_mentions=self.allowed_mentions
        )

        logs_channel = discord.utils.get(message.guild.channels, id=self.mod_logs_channel)
        if logs_channel:
            embed = discord.Embed(
                title='「Mitgliedmanagement」',
                description=f'{member.mention} wurde **automatisch gewarnt** (Bad-Word-Filter).\n\n'
                            f'**Grund**: {reason}\n**Warn-ID**: {warn_id}\n**Teammitglied**: {self.bot.user.mention}',
                color=discord.Color.red()
            )
            embed.set_author(name="Moderation Logs", icon_url=message.guild.icon)
            await logs_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Überprüft jede Nachricht auf Schimpfwörter und löscht sie, wenn welche gefunden werden."""
        if message.author == self.bot.user:
            return

        # Überprüfe, ob die Nachricht nur Großbuchstaben enthält und nicht leer ist
        if message.content.isupper() and message.content.strip():
            member = message.author
            channel = message.channel
            self.bot_deleted_messages[message.id] = "Caps-Filter"
            await message.delete()
            await channel.send(f"{member.mention}, **bitte nicht zu viel in Caps schreiben!**\n_Nur eine Hinweis, keine Verwarnung_", delete_after=10, allowed_mentions=self.allowed_mentions)

        # Überprüfen, ob die Nachricht ein Command ist
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            # Wenn es ein gültiger Command ist, ignoriere den Bad-Word-Filter
            return

        # Überprüfen, ob die Nachricht Schimpfwörter enthält
        for word in self.bad_words:
            if word.lower() in message.content.lower():
                member = message.author
                self.bot_deleted_messages[message.id] = "Wortfilter"
                await message.delete()
                await message.channel.send(f"{member.mention}, **bitte schreibe keine schlechten Wörter in diesen Discord!**\n_Nur eine Hinweis, keine Verwarnung_", allowed_mentions=self.allowed_mentions, delete_after=10)
                await self.register_bad_word_offense(message)
                return
            
    @commands.command(aliases=["white"])
    @has_timeout_permission()
    async def whitelist(self, ctx, target: str = '', action: str = '', value: str = ''):
        guild = ctx.guild
        linkrole = discord.utils.get(ctx.guild.roles, id=1305620568615292928)
        soundrole = discord.utils.get(ctx.guild.roles, id=1342470339405418539)
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)

        if target == 'link':
            if action == 'add':
                if not ctx.message.mentions:
                    await ctx.send(f"Bitte **erwähne einen Benutzer**!")

                user = ctx.message.mentions[0]
                member = guild.get_member(user.id)
                if not member:
                    await ctx.send("Benutzer **nicht** gefunden.")
                    return
            
                if linkrole in member.roles:
                    await ctx.send(f"{member.mention} hat die Rolle bereits!")
                    return
            
                await member.add_roles(linkrole)
                await member.send(f"Herzlichen Glückwunsch! Sie haben die Rolle `Link Whitelist` erhalten!\nMit dieser Rolle können sie Links in AMA Community senden.\n\n**Teammitglied**:{ctx.author.mention}")
                await ctx.send(f"Die Rolle wurde **erfolgreich** zu {member.mention} **hinzugefügt**!\n\n**Teammitglied**:{ctx.author.mention}")

                #Logs
                logembed = discord.Embed(
                    title='「Link-Whitelist」',
                    description=f'{member.mention} wurde zur Link-Whitelist **hinzugefügt**.\n\n**Teammitglied**:{ctx.author.mention}',
                    color=discord.Color.green()
                )
                logembed.set_author(name="Moderation Log", icon_url=ctx.guild.icon)
                await logs_channel.send(embed=logembed)

            elif action == 'remove':
                if not ctx.message.mentions:
                    await ctx.send(f"Bitte **erwähne einen Benutzer**!")

                user = ctx.message.mentions[0]
                member = guild.get_member(user.id)
                if not member:
                    await ctx.send("Benutzer **nicht** gefunden.")
                    return

                if linkrole not in member.roles:
                    await ctx.send(f"{member.mention} hat die Rolle nicht!")
                    return

                await member.remove_roles(linkrole)
                await member.send(f"Hallo,\nihnen wurde die Rolle `Link Whitelist` weggenommen!\n\n_Dies würde **nie** ohne Grund geschehen_")
                await ctx.send(f"Die Rolle wurde **erfolgreich** von {member.mention} **entfernt**!\n\n**Teammitglied**:{ctx.author.mention}") 

                #Logs
                embed = discord.Embed(
                    title='「Link-Whitelist」',
                    description=f'{member.mention} wurde aus der Link-Whitelist **entfernt**.\n\n**Teammitglied**:{ctx.author.mention}',
                    color=discord.Color.red()
                )
                embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
                await logs_channel.send(embed=embed)

        elif target == 'soundboard':
            if action == 'add':
                if not ctx.message.mentions:
                    await ctx.send(f"Bitte **erwähne einen Benutzer**!")

                user = ctx.message.mentions[0]
                member = guild.get_member(user.id)
                if not member:
                    await ctx.send("Benutzer **nicht** gefunden.")
                    return
            
                if soundrole in member.roles:
                    await ctx.send(f"{member.mention} hat die Rolle bereits!")
                    return
            
                await member.add_roles(soundrole)
                await member.send(f"Herzlichen Glückwunsch! Sie haben die Rolle `Soundboard Whitelist` erhalten!\nMit dieser Rolle können sie das Soundboard in AMA Community verwenden.\n\n**Teammitglied**:{ctx.author.mention}")
                await ctx.send(f"Die Rolle wurde **erfolgreich** zu {member.mention} **hinzugefügt**!\n\n**Teammitglied**:{ctx.author.mention}")  

                #Logs
                embed = discord.Embed(
                    title='「Soundboard-Whitelist」',
                    description=f'{member.mention} wurde zur Soundboard-Whitelist **hinzugefügt**.\n\n**Teammitglied**:{ctx.author.mention}',
                    color=discord.Color.green()
                )
                embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
                await logs_channel.send(embed=embed)

            elif action == 'remove':
                if not ctx.message.mentions:
                    await ctx.send(f"Bitte **erwähne einen Benutzer**!")

                user = ctx.message.mentions[0]
                member = guild.get_member(user.id)
                if not member:
                    await ctx.send("Benutzer **nicht** gefunden.")
                    return

                if soundrole not in member.roles:
                    await ctx.send(f"{member.mention} hat die Rolle nicht!")
                    return

                await member.remove_roles(soundrole)
                await member.send(f"Hallo,\nihnen wurde die Rolle `Soundboard-Whitelist` weggenommen!\n\n_Dies würde **nie** ohne Grund geschehen_")
                await ctx.send(f"Die Rolle wurde **erfolgreich** von {member.mention} **entfernt**!\n\n**Teammitglied**:{ctx.author.mention}") 

                #Logs
                embed = discord.Embed(
                    title='「Soundboard-Whitelist」',
                    description=f'{member.mention} wurde aus der Soundboard-Whitelist **entfernt**.\n\n**Teammitglied**:{ctx.author.mention}',
                    color=discord.Color.red()
                )
                embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
                await logs_channel.send(embed=embed)
              
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def say(self, ctx, *,  message=None):
        await ctx.message.delete()
        await ctx.send(f"{message}")
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)

        #Logs
        embed = discord.Embed(
            title='「Command benutzung」',
            description=f'{ctx.author.mention} hat den `say` Command **benutzt**.\n\n**Message**:{message}',
            color=discord.Color.orange()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed)


    @commands.command()
    @commands.has_permissions(administrator=True)
    async def saym(self, ctx, member: discord.Member, *, message=None):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        await ctx.message.delete()
        await member.send(f"{message}")

        #Logs
        embed = discord.Embed(
            title='「Command benutzung」',
            description=f'{ctx.author.mention} hat den `saym` Command **benutzt**.\n\n**Empfänger**:{member.mention}\n**Message**:{message}',
            color=discord.Color.orange()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed)

    @commands.command(name="add_bad_word")
    @commands.has_permissions(administrator=True)
    async def add_bad_word(self, ctx, *, word):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        """Fügt ein Schimpfwort zur Liste hinzu."""
        word = word.lower()
        if word in self.bad_words:
            await ctx.send(f"Das Wort **{word}** ist bereits in der Liste.")
        else:
            self.bad_words.append(word)
            self.save_bad_words()
            await ctx.send(f"Das Wort **{word}** wurde zur Liste der Schimpfwörter hinzugefügt.")

            #Logs 
            embed = discord.Embed(
                title='「Schimpfwortliste」',
                description=f'{ctx.author.mention} hat ein Wort zu der Schimpfwortliste **hinzugefügt**.\n\n**Schimpfwort**:{word}',
                color=discord.Color.dark_orange()
            )
            embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
            await logs_channel.send(embed=embed)

    @commands.command(name="remove_bad_word")
    @commands.has_permissions(administrator=True)
    async def remove_bad_word(self, ctx, *, word):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        """Entfernt ein Schimpfwort aus der Liste."""
        word = word.lower()
        if word not in self.bad_words:
            await ctx.send(f"Das Wort **{word}** befindet sich nicht in der Liste.")
        else:
            self.bad_words.remove(word)
            self.save_bad_words()
            await ctx.send(f"Das Wort **{word}** wurde aus der Liste der Schimpfwörter entfernt.")

            #Logs 
            embed = discord.Embed(
                title='「Schimpfwortliste」',
                description=f'{ctx.author.mention} hat ein Wort zu der Schimpfwortliste **entfernt**.\n\n**Schimpfwort**:{word}',
                color=discord.Color.dark_orange()
            )
            embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
            await logs_channel.send(embed=embed)

    @commands.command(name="list_bad_words")
    @commands.has_permissions(administrator=True)
    async def listbw(self, ctx):
        """Listet alle Schimpfwörter auf."""
        if self.bad_words:
            await ctx.send(f"Liste der Schimpfwörter: _{', '.join(self.bad_words)}_")
        else:
            await ctx.send("Es gibt **keine Schimpfwörter** auf der Liste.")

    @commands.Cog.listener()
    async def on_ready(self):
        print("Moderation is ready!")

    @commands.command()
    async def ping(self, ctx):
        latency = ctx.bot.latency * 1000
        await ctx.send(f"Pong! (**{latency:.2f} ms**)")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        # Überprüfen, ob die Nachricht existiert und nicht von einem Bot stammt
        if message and not message.author.bot:
            message_logs = self.bot.get_channel(self.message_log_channel)
            if message_logs:
                deleter_info = ""

                bot_reason = self.bot_deleted_messages.pop(message.id, None)
                if bot_reason:
                    deleter_info = f" **durch** {self.bot.user.mention} ({bot_reason})"
                else:
                    try:
                        async for entry in message.guild.audit_logs(limit=5, action=discord.AuditLogAction.message_delete):
                            if (entry.target.id == message.author.id
                                    and entry.extra.channel.id == message.channel.id
                                    and (discord.utils.utcnow() - entry.created_at).total_seconds() < 5):
                                deleter_info = f" **von** {entry.user.mention}"
                                break
                    except discord.Forbidden:
                        pass  # Bot hat keine "Audit-Log anzeigen"-Berechtigung

                # Nachricht formatieren
                content = (
                    f"{message.author.mention} **->** {message.channel.mention} "
                    f"**[Nachricht gelöscht{deleter_info}]**: \n* \"{message.content}\""
                )
                await message_logs.send(content)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before and after and not before.author.bot:
            log_channel = self.bot.get_channel(self.message_log_channel)
            if log_channel:
                content = (
                    f"{before.author.mention} **->** {before.channel.mention} **[Nachricht bearbeitet]**:\n"
                    f"**Vorher:** \n* \"{before.content}\"\n"
                    f"**Nachher:** \n* \"{after.content}\""
                )
                await log_channel.send(content)


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        member_role = discord.utils.get(member.guild.roles, name="Mitglied")
        pings_role = discord.utils.get(member.guild.roles, id=1279435671198498816)
        if member_role and pings_role:
            await member.add_roles(member_role)
            await member.add_roles(pings_role)

        # Willkommensnachricht mit Bild
        welcome_channel = member.guild.system_channel
        if welcome_channel:
            images = [image for image in os.listdir("./cogs/welcome_images")]
            randomized_image = random.choice(images)

            bg = easy_pil.Editor(f"./cogs/welcome_images/{randomized_image}").resize((1920, 1080))
            avatar_image = await easy_pil.load_image_async(str(member.avatar.url))
            avatar = easy_pil.Editor(avatar_image).resize((250, 250)).circle_image()

            font_big = easy_pil.Font.poppins(size=90, variant="bold")
            font_small = easy_pil.Font.poppins(size=60, variant="bold")

            bg.paste(avatar, (835, 340))
            bg.ellipse((835, 340), 250, 250, outline="white", stroke_width=5)

            bg.text((960, 620), f"Willkommen zu {member.guild.name}!", color="White", font=font_big, align="center")
            bg.text((960, 740), f"{member.name} ist der #{member.guild.member_count}!", color="White", font=font_small, align="center")

            img_file = discord.File(fp=bg.image_bytes, filename=randomized_image)
            await welcome_channel.send(f"Hallo {member.mention}! Bitte lies und halte dich an die Regeln. Viel Spaß :)")
            await welcome_channel.send(file=img_file)

    @commands.command(name="role")
    @commands.has_permissions(manage_roles=True)
    async def role(self, ctx, action: str, member: discord.Member, role: discord.Role):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        if action == "add":
            if role in member.roles:
                await ctx.send(f"{member.mention} hat die Rolle {role.mention} bereits!")
            else:
                await member.add_roles(role)
                await ctx.send(f"{role.mention} wurde {member.mention} hinzugefügt! \n\n**Teammitglied**: {ctx.author.mention}")

                #Logs 
                embed = discord.Embed(
                    title='「Rollenmanagement」',
                    description=f'{member.mention}, wurde eine Rolle **hinzugefügt**.\n\n**Rolle**:{role.mention}\n**Teammitglied**:{ctx.author.mention}',
                    color=discord.Color.green()
                )
                embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
                await logs_channel.send(embed=embed)


        elif action == "remove":
            if role not in member.roles:
                await ctx.send(f"{member.mention} hat die Rolle {role.mention} nicht!")
            else:
                await member.remove_roles(role)
                await ctx.send(f"{role.mention} wurde von {member.mention} entfernt! \n\n**Teammitglied**: {ctx.author.mention}")

                #Logs 
                embed = discord.Embed(
                    title='「Rollenmanagement」',
                    description=f'{member.mention}, wurde eine Rolle **weggenommen**.\n\n**Rolle**:{role.mention}\n**Teammitglied**:{ctx.author.mention}',
                    color=discord.Color.red()
                )
                embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
                await logs_channel.send(embed=embed)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        if reason == None:
            await ctx.send("Du **musst** einen Grund angeben!")
            return
        
        await member.ban(reason=reason)
        await ctx.send(f"{member.mention} wurde **gebannt**! \n\n**Teammitglied**: {ctx.author.mention}", allowed_mentions=self.allowed_mentions)

        #Logs 
        embed = discord.Embed(
            title='「Mitgliedmanagement」',
            description=f'{member.mention} wurde **gebannt**.\n\n**Grund**:{reason}\n**Teammitglied**:{ctx.author.mention}',
            color=discord.Color.dark_red()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed)

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        if reason == None:
            await ctx.send("Du **musst** einen Grund angeben!")
            return
        
        await member.kick(reason=reason)
        await ctx.send(f"{member.mention} wurde **gekickt**! \n\n**Teammitglied**: {ctx.author.mention}", allowed_mentions=self.allowed_mentions)

        #Logs 
        embed = discord.Embed(
            title='「Mitgliedmanagement」',
            description=f'{member.mention} wurde **gekickt**.\n\n**Grund**:{reason}\n**Teammitglied**:{ctx.author.mention}',
            color=discord.Color.dark_red()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed)

    @commands.command()
    @has_timeout_permission()
    async def warn(self, ctx, member: discord.Member, *, reason=None):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        if reason is None:
            await ctx.send("Du **musst** ein Grund angeben!")
            return

        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        # Initialize the guild's data if it doesn't exist
        if guild_id not in self.data:
            self.data[guild_id] = {}

        # Initialize the member's data if it doesn't exist
        if member_id not in self.data[guild_id]:
            self.data[guild_id][member_id] = []

        # Get the current time in Berlin timezone
        berlin_tz = pytz.timezone('Europe/Berlin')
        berlin_time = datetime.datetime.now(berlin_tz)
        timestamp = berlin_time.strftime("%d. %B %Y, %H:%M:%S")

        # Increment the global warn ID
        warn_id = self.data.get("warn_id", 0) + 1
        self.data["warn_id"] = warn_id

        # Add a new warning with a timestamp and ID
        self.data[guild_id][member_id].append({
            "id": warn_id,  # Unique warning ID
            "reason": reason,
            "moderator": str(ctx.author),
            "moderator_id": str(ctx.author.id),
            "timestamp": timestamp
        })

        # Save the updated data
        self.save_data()

        await ctx.send(f"{member.mention} wurde **gewarnt** von {ctx.author.mention} \n\n**Grund**: {reason}\n**Warn-ID**: {warn_id}", allowed_mentions=self.allowed_mentions)

        #Logs 
        embed = discord.Embed(
            title='「Mitgliedmanagement」',
            description=f'{member.mention} wurde **gewarnt**.\n\n**Grund**: {reason}\n**Warn-ID**: {warn_id}\n**Teammitglied**: {ctx.author.mention}',
            color=discord.Color.red()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed)

    @commands.command()
    @has_timeout_permission()
    async def unwarn(self, ctx, warn_id: int):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        """Entfernt eine spezifische Verwarnung anhand der Warn-ID."""
        guild_id = str(ctx.guild.id)
        warn_removed = False  # Flag, um zu überprüfen, ob die Warnung gefunden und entfernt wurde

        # Durchlaufe alle Mitglieder und deren Verwarnungen in der Gilde
        for member_id, warnings in self.data.get(guild_id, {}).items():
            # Suche nach der Warnung mit der entsprechenden ID
            for warning in warnings:
                if warning["id"] == warn_id:
                    warnings.remove(warning)  # Entferne die Warnung
                    warn_removed = True
                    break

            # Speichere die Daten und beende die Schleife, falls Warnung entfernt wurde
            if warn_removed:
                self.save_data()
                await ctx.send(f"Warnung **ID: {warn_id}** wurde **entfernt**. \n\n**Teammitglied**: {ctx.author.mention}")

                #Logs 
                embed = discord.Embed(
                    title='「Mitgliedmanagement」',
                    description=f'Ein Warn wurde **entfernt**.\n\n**Warn-ID**:{warn_id}\n**Teammitglied**:{ctx.author.mention}',
                    color=discord.Color.green()
                )
                embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
                await logs_channel.send(embed=embed)

                return

        # Falls keine Warnung mit dieser ID gefunden wurde
        if not warn_removed:
            await ctx.send(f"Warnung mit der **ID {warn_id}** wurde nicht gefunden.")

    @commands.command()
    @has_timeout_permission()
    async def delwarn(self, ctx, member: discord.Member):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        if guild_id in self.data and member_id in self.data[guild_id]:
            self.data[guild_id][member_id] = []
            self.save_data()
            await ctx.send(f"**Alle Verwarnungen** wurden von {member.mention} **entfernt**.\n\n**Teammitglied**: {ctx.author.mention}")

            #Logs 
            embed = discord.Embed(
                title='「Mitgliedmanagement」',
                description=f'{member.mention}, wurden **alle** Warns **entfernt**.\n\n**Teammitglied**:{ctx.author.mention}',
                color=discord.Color.green()
            )
            embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
            await logs_channel.send(embed=embed)

        else:
            await ctx.send(f"{member.mention} hat keine Verwarnungen.")

    @commands.command(aliases=["warns", "warnings"])
    async def findwarn(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author

        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        if guild_id in self.data and member_id in self.data[guild_id]:
            warnings = self.data[guild_id][member_id]

            if warnings:
                warn_messages = []

                for warn in warnings:
                    timestamp = warn["timestamp"]
                    reason = warn["reason"]
                    moderator_name = warn["moderator"]
                    id = warn["id"]

                    moderator = None
                    moderator_id = warn.get("moderator_id")
                    if moderator_id:
                        moderator = ctx.guild.get_member(int(moderator_id))
                    if moderator is None:
                        try:
                            # Versuche, den Moderator anhand des gespeicherten Namen und Discriminator zu finden
                            moderator = discord.utils.get(ctx.guild.members, name=moderator_name)
                        except Exception as e:
                            print(f"Fehler beim Finden des Moderators: {e}")
                    moderator_mention = moderator.mention if moderator else moderator_name

                    warn_messages.append(f"**-** Am {timestamp}, **Grund**: {reason}, **Teammitglied**: {moderator_mention}  (_ID: {id}_)")
                
                warn_message_str = "\n".join(warn_messages)
                
                await ctx.send(f"**Verwarnungen von {member.mention}:**\n\n{warn_message_str}")
            else:
                await ctx.send(f"**Verwarnungen von {member.mention}:** \n\n_Dieser User hat keine Verwarnungen._")
        else:
            await ctx.send(f"**Verwarnungen von {member.mention}.** \n\n_Dieser User hat keine Verwarnungen._")

    @commands.command()
    @has_timeout_permission()
    async def mute(self, ctx, member: discord.Member, timelimit):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        try:
            # Ermitteln der Zeiteinheit und des Zeitwerts
            if timelimit.endswith("s"):
                time_unit = "seconds"
                time_value = int(timelimit[:-1])
            elif timelimit.endswith("m"):
                time_unit = "minutes"
                time_value = int(timelimit[:-1])
            elif timelimit.endswith("h"):
                time_unit = "hours"
                time_value = int(timelimit[:-1])
            elif timelimit.endswith("d"):
                time_unit = "days"
                time_value = int(timelimit[:-1])
            elif timelimit.endswith("w"):
                time_unit = "weeks"
                time_value = int(timelimit[:-1])
            else:
                await ctx.reply("Bitte eine gültige Zeiteinheit angeben (s, m, h, d, w).")
                return

            # ÃberprÃ¼fung der maximalen Zeit
            max_times = {
                "seconds": 2419200,  # 28 Tage in Sekunden
                "minutes": 40320,    # 28 Tage in Minuten
                "hours": 672,        # 28 Tage in Stunden
                "days": 28,          # 28 Tage
                "weeks": 4           # 4 Wochen
            }

            if time_value > max_times[time_unit]:
                await ctx.send("Du kannst einen User **max. 28 Tage muten**!")
                return

            # Berechnung der Zeitspanne
            time_delta = datetime.timedelta(**{time_unit: time_value})

            # Mute den Benutzer fÃ¼r die berechnete Zeitspanne
            await member.edit(timed_out_until=discord.utils.utcnow() + time_delta)
            await ctx.send(f"**{member.mention}** wurde **gemutet** von **{ctx.message.author.mention}**! \n\n**Zeit**: {time_value} {time_unit}", allowed_mentions=self.allowed_mentions)

            #Logs 
            embed = discord.Embed(
                title='「Mitgliedmanagement」',
                description=f'{member.mention} wurde **gemutet**.\n\n**Zeit**:{time_value} {time_unit}\n**Teammitglied**:{ctx.author.mention}',
                color=discord.Color.red()
            )
            embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
            await logs_channel.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Es gab einen Fehler beim Muten des Users: {str(e)}")

    @commands.command()
    @has_timeout_permission()
    async def unmute(self, ctx, member: discord.Member):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        await member.edit(timed_out_until=None)
        await ctx.send(f"**{member.mention}** wurde **unmutet**! \n\n**Teammitglied**: {ctx.message.author.mention}")

        #Logs 
        embed = discord.Embed(
            title='「Mitgliedmanagement」',
            description=f'{member.mention} wurde **unmutet**.\n\n**Teammitglied**:{ctx.author.mention}',
            color=discord.Color.green()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        message_key = str(payload.message_id)
        emoji_map = self.reaction_roles.get(message_key)
        if not emoji_map:
            return

        role_id = emoji_map.get(str(payload.emoji))
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        role = guild.get_role(role_id)
        if role is None:
            return

        member = payload.member or guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.NotFound:
                return

        await member.add_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        message_key = str(payload.message_id)
        emoji_map = self.reaction_roles.get(message_key)
        if not emoji_map:
            return

        role_id = emoji_map.get(str(payload.emoji))
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        role = guild.get_role(role_id)
        if role is None:
            return

        try:
            member = await guild.fetch_member(payload.user_id)
        except discord.NotFound:
            return

        await member.remove_roles(role)

    async def resolve_emoji(self, ctx, emoji_input: str):
        """Löst die Eingabe zu einem Custom-Emoji des Servers auf, falls möglich,
        sonst wird die Eingabe als normales Unicode-Emoji verwendet."""
        try:
            return await commands.EmojiConverter().convert(ctx, emoji_input)
        except commands.EmojiNotFound:
            return emoji_input

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reactionmessage(self, ctx, message: discord.Message, role: discord.Role, emoji: str):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        emoji_obj = await self.resolve_emoji(ctx, emoji)

        message_key = str(message.id)
        self.reaction_roles.setdefault(message_key, {})
        self.reaction_roles[message_key][str(emoji_obj)] = role.id
        self.reaction_locations[message_key] = {"channel_id": message.channel.id, "guild_id": message.guild.id}
        self.save_state()

        await message.add_reaction(emoji_obj)
        await ctx.send(f"Reaction-Role für {emoji_obj} wurde **hinzugefügt**.")

        #Logs
        embed = discord.Embed(
            title='「Reaktionsrolle」',
            description=f'Zu {message.jump_url} wurde eine Reaktionsrolle **hinzugefügt**.\nRolle: {role.mention}\nEmoji: {emoji_obj}\n\n**Teammitglied**:{ctx.author.mention}',
            color=discord.Color.green()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def delreactionmessage(self, ctx, message: discord.Message, emoji: str):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        emoji_obj = await self.resolve_emoji(ctx, emoji)
        emoji_key = str(emoji_obj)
        message_key = str(message.id)

        emoji_map = self.reaction_roles.get(message_key)
        if not emoji_map or emoji_key not in emoji_map:
            await ctx.send("Für dieses Emoji ist auf dieser Nachricht keine Reaction-Role gespeichert.")
            return
        
        removed_role_id = emoji_map[emoji_key]  # für die Logs merken, bevor gelöscht wird


        del emoji_map[emoji_key]
        if not emoji_map:
            del self.reaction_roles[message_key]
            if message_key in self.reaction_locations:
                del self.reaction_locations[message_key]
        self.save_state()

        await message.clear_reaction(emoji_obj)
        await ctx.send(f"Reaction-Role für {emoji_obj} wurde **gelöscht** und alle Reaktionen mit diesem Emoji entfernt.")

        removed_role = ctx.guild.get_role(removed_role_id)
        removed_role_display = removed_role.mention if removed_role else f"_gelöschte Rolle ({removed_role_id})_"
        
        #Logs
        embed = discord.Embed(
            title='「Reaktionsrolle」',
            description=f'Von {message.jump_url} wurde eine Reaktionsrolle **entfernt**.\nRolle: {removed_role_display}\nEmoji: {emoji_obj}\n\n**Teammitglied**:{ctx.author.mention}',
            color=discord.Color.orange()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed)

    @commands.command(aliases=["findreactionmessage", "reactionsmessages"])
    @commands.has_permissions(administrator=True)
    async def reactionmessages(self, ctx, message: discord.Message = None):
        """Zeigt alle Reaction-Role-Nachrichten (oder eine bestimmte) mit Link und zugewiesenen Rollen an."""
        if message is not None:
            message_key = str(message.id)
            emoji_map = self.reaction_roles.get(message_key)
            if not emoji_map:
                await ctx.send("Für diese Nachricht sind keine Reaction-Roles gespeichert.")
                return

            role_lines = []
            for emoji_str, role_id in emoji_map.items():
                role = ctx.guild.get_role(role_id)
                role_display = role.mention if role else f"_gelöschte Rolle ({role_id})_"
                role_lines.append(f"**-** {emoji_str} **->** {role_display}")

            await ctx.send(
                f"**Reaction-Roles für [diese Nachricht]({message.jump_url}):**\n\n"
                + "\n".join(role_lines)
            )
            return

        if not self.reaction_roles:
            await ctx.send("**Reaction-Role-Nachrichten:**\n\n_Es gibt aktuell keine._")
            return

        lines = []
        for message_key, emoji_map in self.reaction_roles.items():
            location = self.reaction_locations.get(message_key)
            if location:
                jump_url = f"https://discord.com/channels/{location['guild_id']}/{location['channel_id']}/{message_key}"
                message_display = jump_url
            else:
                message_display = f"Nachricht-ID `{message_key}`"

            role_parts = []
            for emoji_str, role_id in emoji_map.items():
                role = ctx.guild.get_role(role_id)
                role_display = role.mention if role else f"_gelöschte Rolle ({role_id})_"
                role_parts.append(f"{emoji_str} : {role_display}")

            lines.append(f"**-** {message_display} **->** {', '.join(role_parts)}")

        await ctx.send("**Reaction-Role-Nachrichten:**\n\n" + "\n".join(lines))

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        """Löscht die angegebene Anzahl von Nachrichten im aktuellen Kanal."""
        # Überprüfen, dass der Betrag größer als 0 ist
        if amount <= 0:
            await ctx.send("Bitte gib eine Zahl größer als **0** an.")
            return
        
        await ctx.message.delete()
        
        # Löscht die Anzahl an Nachrichten
        deleted = await ctx.channel.purge(limit=amount)
        
        # Feedback an den Moderator geben
        await ctx.send(f"**{len(deleted)} Nachrichten** wurden **gelöscht**. \n\n**Teammitglied**: {ctx.author.mention}")  # Nachricht wird nach 2 Sekunden gelöscht

        #Logs 
        embed = discord.Embed(
            title='「Purge」',
            description=f'**{len(deleted)} Nachrichten wurden **gelöscht**.\n\n**Teammitglied**:{ctx.author.mention}',
            color=discord.Color.orange()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed) 

async def setup(bot):
    await bot.add_cog(Moderation(bot))