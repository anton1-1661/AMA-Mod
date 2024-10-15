import discord
from discord.ext import commands
import json
import datetime
import pytz
import os
import easy_pil
import random
import uuid  # Zum Erstellen eindeutiger IDs


def has_timeout_permission():
    async def predicate(ctx):  # Prüft, ob der Benutzer über Admin- oder Timeout-Rechte verfügt
        return any(role.permissions.administrator or role.permissions.moderate_members for role in ctx.author.roles)
    return commands.check(predicate)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reaction_roles = {}  # Emojis zu Rollen
        self.reaction_messages = {}  # Nachrichten IDs zu Emojis
        self.allowed_mentions = discord.AllowedMentions(users=True)
        self.bad_words = self.load_bad_words()  # Schimpfwörter laden

        # Lade Daten (Warnungen)
        self.data = self.load_data()

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

    @commands.Cog.listener()  # Schimpfwörtersystem
    async def on_message(self, message):
        """Überprüft jede Nachricht auf Schimpfwörter und löscht sie, wenn welche gefunden werden."""
        if message.author == self.bot.user:
            return

        # Überprüfe, ob die Nachricht nur Großbuchstaben enthält und nicht leer ist
        if message.content.isupper() and message.content.strip():
            print(f"[DEBUG] Nachricht von {message.author} in Großbuchstaben erkannt: {message.content}")
        
            member = message.author
            reason = "Regel 9.2 Caps"

            # Hole den Kontext der Nachricht
            ctx = await self.bot.get_context(message)
            print(f"[DEBUG] Kontext für {message.author}: {ctx}")

            # Überprüfe, ob der Kontext gültig ist
            if ctx and ctx.guild:  # Sicherstellen, dass der Kontext gültig ist
                print(f"[DEBUG] Warn-Befehl wird für {member} ausgeführt.")

                # Verwende den bestehenden warn-Befehl und übergebe die Argumente
                await self.warn(ctx, member, reason=reason)

                # Optional: Eine Nachricht senden, dass der Benutzer gewarnt wurde
                await message.channel.send(f"{member.mention} wurde aufgrund von Großbuchstaben gewarnt.")
            else:
                print("[DEBUG] Kontext ungültig. Warn-Befehl konnte nicht ausgeführt werden.")
                await message.channel.send("Der Befehl konnte nicht ausgeführt werden, da der Kontext ungültig ist.")

        # Überprüfen, ob die Nachricht ein Command ist
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            # Wenn es ein gültiger Command ist, ignoriere den Bad-Word-Filter
            return

        # Überprüfen, ob die Nachricht Schimpfwörter enthält
        for word in self.bad_words:
            if word.lower() in message.content.lower():
                await message.delete()
                await message.channel.send(f"{message.author.mention}, diese Nachricht enthält unangemessene Sprache und wurde gelöscht.", allowed_mentions=self.allowed_mentions)
                return
            
    @commands.command()  # Sendet die Nachricht in den jetztigen Channel
    @commands.has_permissions(administrator=True)
    async def say(self, ctx, message=None):
        await ctx.message.delete()
        await ctx.send(f"{message}")

    @commands.command()  # Sendet dem User per DM die Message
    @commands.has_permissions(administrator=True)
    async def saym(self, ctx, member: discord.Member, message=None):
        await ctx.message.delete()
        await member.send(f"{message}")

    @commands.command(name="add_bad_word")
    @commands.has_permissions(administrator=True)
    async def add_bad_word(self, ctx, *, word):
        """Fügt ein Schimpfwort zur Liste hinzu."""
        word = word.lower()
        if word in self.bad_words:
            await ctx.send(f"Das Wort **{word}** ist bereits in der Liste.")
        else:
            self.bad_words.append(word)
            self.save_bad_words()
            await ctx.send(f"Das Wort **{word}** wurde zur Liste der Schimpfwörter hinzugefügt.")

    @commands.command(name="remove_bad_word")
    @commands.has_permissions(administrator=True)
    async def remove_bad_word(self, ctx, *, word):
        """Entfernt ein Schimpfwort aus der Liste."""
        word = word.lower()
        if word not in self.bad_words:
            await ctx.send(f"Das Wort **{word}** befindet sich nicht in der Liste.")
        else:
            self.bad_words.remove(word)
            self.save_bad_words()
            await ctx.send(f"Das Wort **{word}** wurde aus der Liste der Schimpfwörter entfernt.")

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
        await ctx.send("Pong!")

    @commands.Cog.listener()   # Willkommens Nachricht für neue User + Autorole
    async def on_member_join(self, member: discord.Member):
        role = discord.utils.get(member.guild.roles, name="Mitglied")
        if role:
            await member.add_roles(role)

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
        if action == "add":
            if role in member.roles:
                await ctx.send(f"{member.mention} hat die Rolle {role.mention} bereits!")
            else:
                await member.add_roles(role)
                await ctx.send(f"{role.mention} wurde {member.mention} hinzugefügt! \n\n**Teammitglied**: {ctx.author.mention}")

        elif action == "remove":
            if role not in member.roles:
                await ctx.send(f"{member.mention} hat die Rolle {role.mention} nicht!")
            else:
                await member.remove_roles(role)
                await ctx.send(f"{role.mention} wurde von {member.mention} entfernt! \n\n**Teammitglied**: {ctx.author.mention}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        if reason == None:
            await ctx.send("Du **musst** einen Grund angeben!")
            return
        
        await member.ban(reason=reason)
        await ctx.send(f"{member.mention} wurde **gebannt**! \n\n**Teammitglied**: {ctx.author.mention}", allowed_mentions=self.allowed_mentions)

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        if reason == None:
            await ctx.send("Du **musst** einen Grund angeben!")
            return
        
        await member.kick(reason=reason)
        await ctx.send(f"{member.mention} wurde **gekickt**! \n\n**Teammitglied**: {ctx.author.mention}", allowed_mentions=self.allowed_mentions)

    @commands.command()
    @has_timeout_permission()
    async def warn(self, ctx, member: discord.Member, *, reason=None):
        if reason is None:
            await ctx.send("Du **musst** ein Grund angeben!")
            return

        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        # Initialize Guild data wenn es nicht existiert
        if guild_id not in self.data:
            self.data[guild_id] = {}

        # Initialize User data wenn es nicht existiert
        if member_id not in self.data[guild_id]:
            self.data[guild_id][member_id] = []

        # Jetztige Zeit
        berlin_tz = pytz.timezone('Europe/Berlin')
        berlin_time = datetime.datetime.now(berlin_tz)
        timestamp = berlin_time.strftime("%d. %B %Y, %H:%M:%S")

        # globale warn-id count
        warn_id = self.data.get("warn_id", 0) + 1
        self.data["warn_id"] = warn_id

        # neuer warn mit time und id
        self.data[guild_id][member_id].append({
            "id": warn_id,  # Unique warning ID
            "reason": reason,
            "moderator": str(ctx.author),
            "timestamp": timestamp
        })

        # sava data
        self.save_data()

        await ctx.send(f"{member.mention} wurde **gewarnt** von {ctx.author.mention} \n\n**Grund:** {reason}\n**Warn-ID:** {warn_id}", allowed_mentions=self.allowed_mentions)

    @commands.command()
    @has_timeout_permission()
    async def unwarn(self, ctx, warn_id: int):
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
                return

        # Falls keine Warnung mit dieser ID gefunden wurde
        if not warn_removed:
            await ctx.send(f"Warnung mit der **ID {warn_id}** wurde nicht gefunden.")

    @commands.command()
    @has_timeout_permission()
    async def delwarn(self, ctx, member: discord.Member):
        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        if guild_id in self.data and member_id in self.data[guild_id]:
            self.data[guild_id][member_id] = []
            self.save_data()
            await ctx.send(f"**Alle Verwarnungen** wurden von {member.mention} **entfernt**.\n\n**Teammitglied**: {ctx.author.mention}")
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
                    try:
                        # Versuche, den Moderator anhand des gespeicherten Namen und Discriminator zu finden
                        name = warn["moderator"]
                        moderator = discord.utils.get(ctx.guild.members, name=name)
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

        except Exception as e:
            await ctx.send(f"Es gab einen Fehler beim Muten des Users: {str(e)}")

    @commands.command()
    @has_timeout_permission()
    async def unmute(self, ctx, member: discord.Member):
        await member.edit(timed_out_until=None)
        await ctx.send(f"**{member.mention}** wurde **unmutet**! \n\n**Teammitglied**: {ctx.message.author.mention}")

    """ Auto reactionrole """

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user == self.bot.user:
            return

        if reaction.message.id in self.reaction_messages:
            emoji = str(reaction.emoji)
            role_id = self.reaction_roles.get(emoji)
            if role_id:
                role = discord.utils.get(reaction.message.guild.roles, id=role_id)
                if role:
                    await user.add_roles(role)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user == self.bot.user:
            return

        if reaction.message.id in self.reaction_messages:
            emoji = str(reaction.emoji)
            role_id = self.reaction_roles.get(emoji)
            if role_id:
                role = discord.utils.get(reaction.message.guild.roles, id=role_id)
                if role:
                    await user.remove_roles(role)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reactionmessage(self, ctx, message: discord.Message, role: discord.Role):
        emoji_name = 'check'

        emoji_obj = discord.utils.get(ctx.guild.emojis, name=emoji_name)
        if emoji_obj is None:
            await ctx.send(f"Das Emoji ': {emoji_name} :' konnte nicht gefunden werden.")
            return

        self.reaction_roles.clear()
        self.reaction_roles[str(emoji_obj)] = role.id
        self.reaction_messages[message.id] = str(emoji_obj)

        await message.add_reaction(emoji_obj)

    @commands.command() # Der thypische "Clear" befehl
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        """Löscht die angegebene Anzahl von Nachrichten im aktuellen Kanal."""
        # Überprüfen, dass der Betrag größer als 0 ist
        if amount <= 0:
            await ctx.send("Bitte gib eine Zahl größer als **0** an.")
            return
        
        # Löscht die Anzahl an Nachrichten
        deleted = await ctx.channel.purge(limit=amount)
        
        # Feedback an den Moderator geben
        await ctx.send(f"**{len(deleted)} Nachrichten** wurden **gelöscht**. \n\n**Teammitglied**: {ctx.author.mention}", delete_after=0)  # Nachricht wird nach 2 Sekunden gelöscht 

async def setup(bot):
    await bot.add_cog(Moderation(bot))