import discord
from discord.ext import commands
import asyncio

class VCControl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.category_id = 1057262987624325161
        self.base_channel_id = 1151868876821368852  # Der Channel, in den User joinen, um einen eigenen VC zu bekommen
        self.move_channel_id = 1280241871838253097  # Der Channel, aus dem User in den neuen VC verschoben werden können
        self.user_channels = {}  # Speichert User und ihre erstellten Channel
        self.voice_channel_id = 1057263651557482507  # Der spezifische Voice-Channel, den du im event-Befehl verwenden möchtest

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"VCControl is online!")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Prüfen, ob ein Benutzer dem Basis-Channel beigetreten ist
        if after.channel and after.channel.id == self.base_channel_id:
            # Erstelle einen neuen Voice-Channel in derselben Kategorie
            category = after.channel.category
            new_channel = await category.create_voice_channel(name=f"{member.display_name}'s Channel")
            await member.move_to(new_channel)
            self.user_channels[member.id] = new_channel.id

            # Setze Berechtigungen für den neuen Channel
            await new_channel.set_permissions(member, view_channel=True, connect=True, speak=True)
            await new_channel.set_permissions(member.guild.default_role, view_channel=True, connect=True, speak=True)

        # Kanal löschen, wenn er leer ist
        if before.channel and before.channel.id in self.user_channels.values() and len(before.channel.members) == 0:
            await asyncio.sleep(20)
            if len(before.channel.members) == 0:
                await before.channel.delete()
                del self.user_channels[before.channel.id]

    @commands.command(name='vc')
    async def vc_command(self, ctx, action: str = '', value: str = None):
        member = ctx.author
        if member.id not in self.user_channels:
            await ctx.send("Du besitzt **keinen temporären Sprachkanal**.")
            return

        channel = ctx.guild.get_channel(self.user_channels[member.id])

        # Überprüfen, ob keine Aktion angegeben wurde
        if not action:
            await ctx.send(
                "Command List `VC`\n"
                "`.vc limit off/Zahl` - Limit für deinen Voicechannel festlegen\n"
                "`.vc close/open` - Keiner kann mehr beitreten\n"
                "`.vc hide/show` - Dein Kanal ist versteckt\n"
                "`.vc move @user` - Du kannst Leute aus dem 'Move Me' Channel in deinen Channel bewegen, auch wenn er versteckt oder geschlossen ist\n"
                "`.vc kick @user` - Entfernt einen Benutzer aus deinem Sprachkanal"
            )
            return

        # Verarbeiten der angegebenen Aktion
        if action == "limit":
            if value == "off":
                await channel.edit(user_limit=0)
                await ctx.send(f"Benutzerlimit für **{channel.name}** wurde **entfernt**.")
            else:
                try:
                    limit = int(value)
                    await channel.edit(user_limit=limit)
                    await ctx.send(f"Benutzerlimit für **{channel.name}** wurde auf **{limit}** gesetzt.")
                except ValueError:
                    await ctx.send("Ungültiger Wert für das Benutzerlimit. Bitte gib eine gültige Zahl an.")
        
        elif action == "hide":
            await channel.set_permissions(ctx.guild.default_role, view_channel=False)
            await ctx.send(f"Dein Sprachkanal **{channel.name}** ist jetzt **versteckt**.")
        
        elif action == "show":
            await channel.set_permissions(ctx.guild.default_role, view_channel=True)
            await ctx.send(f"Dein Sprachkanal **{channel.name}** ist jetzt **sichtbar**.")

        elif action == "close":
            await channel.set_permissions(ctx.guild.default_role, connect=False)
            await ctx.send(f"Dein Sprachkanal **{channel.name}** ist jetzt **geschlossen**.")

        elif action == "open":
            await channel.set_permissions(ctx.guild.default_role, connect=True)
            await ctx.send(f"Dein Sprachkanal **{channel.name}** ist jetzt **geöffnet**.")

        elif action == "move":
            if not ctx.message.mentions:
                await ctx.send("Bitte erwähne einen Benutzer, den du verschieben möchtest.")
                return

            user = ctx.message.mentions[0]
            member_to_move = ctx.guild.get_member(user.id)
            if not member_to_move:
                await ctx.send("Benutzer **nicht** gefunden.")
                return

            if member_to_move.voice:
                await member_to_move.move_to(channel)
                await ctx.send(f"**{member_to_move.display_name}** wurde in **deinen Kanal verschoben**.")
            else:
                await ctx.send(f"**{member_to_move.display_name}** ist **nicht** in einem **Sprachkanal**.")

        elif action == "kick":
            if not ctx.message.mentions:
                await ctx.send("Bitte erwähne einen Benutzer, den du aus deinem Sprachkanal entfernen möchtest.")
                return

            user = ctx.message.mentions[0]
            member_to_kick = ctx.guild.get_member(user.id)
            if not member_to_kick:
                await ctx.send("Benutzer **nicht** gefunden.")
                return

            if member_to_kick.voice.channel == channel:
                await member_to_kick.move_to(None)  # Entfernt den Benutzer aus dem Sprachkanal
                await ctx.send(f"**{member_to_kick.display_name}** wurde aus **{channel.name} gekickt**.")
            else:
                await ctx.send(f"**{member_to_kick.display_name}** ist **nicht** in deinem **Sprachkanal**.")

    @commands.command(name='event')
    @commands.has_any_role("|| Admin", "「Eventmanager」", "|| Head-Moderator", "|| Moderator")
    async def event(self, ctx, action: str = '', target: str = None, value: str = None):
        guild = ctx.guild
        category = guild.get_channel(self.category_id)
        voice_channel = guild.get_channel(self.voice_channel_id)
        everyone_role = guild.default_role

        if action == "close" and (target is None or target == "category"):
            await category.set_permissions(everyone_role, view_channel=False)
            await ctx.send(f"Kategorie **{category.name}** ist jetzt **geschlossen**.")

        elif action == "open" and (target is None or target == "category"):
            # Alle relevanten Berechtigungen für @everyone aktivieren, einschließlich Sprachaktivierung
            await category.set_permissions(
                everyone_role, 
                view_channel=True, 
                send_messages=True, 
                add_reactions=True, 
                speak=True, 
                connect=True
            )
            await ctx.send(f"Alle relevanten Berechtigungen für **{category.name}** wurden **aktiviert**.")

        elif action == "vc" and target == "limit":
            if value == "off":
                await voice_channel.edit(user_limit=0)
                await ctx.send(f"**User-Limit** für **{voice_channel.name}** wurde **deaktiviert**.")
            else:
                try:
                    limit = int(value)
                    await voice_channel.edit(user_limit=limit)
                    await ctx.send(f"**User-Limit** für **{voice_channel.name}** wurde auf **{limit}** gesetzt.")
                except ValueError:
                    await ctx.send("Ungültiger Wert für das Benutzerlimit. Bitte gib eine gültige Zahl an.")
        
        elif action == "vc" and target == "close":
            # "Verbinden" deaktivieren, während "Kanal anzeigen", "Sprechen", "Nachrichten senden" und "Reaktionen hinzufügen" aktiv bleiben.
            await voice_channel.set_permissions(everyone_role, connect=False, view_channel=True, send_messages=True, add_reactions=True, speak=True)
            await ctx.send(f"**Verbinden** für den Voice-Channel **{voice_channel.name}** wurde **deaktiviert**.")

        elif action == "vc" and target == "open":
            # "Verbinden" aktivieren, während "Kanal anzeigen", "Sprechen", "Nachrichten senden" und "Reaktionen hinzufügen" aktiv bleiben.
            await voice_channel.set_permissions(everyone_role, connect=True, view_channel=True, send_messages=True, add_reactions=True, speak=True)
            await ctx.send(f"**Verbinden** für den Voice-Channel **{voice_channel.name}** wurde **aktiviert**.")

        elif action == "add":
            if not ctx.message.mentions:
                await ctx.send("Bitte erwähne einen Benutzer, dem du Berechtigungen hinzufügen möchtest.")
                return

            user = ctx.message.mentions[0]
            member = guild.get_member(user.id)
            if not member:
                await ctx.send("Benutzer nicht gefunden.")
                return

            # Berechtigungen für den Benutzer in der Kategorie aktivieren, einschließlich Sprachaktivierung
            await category.set_permissions(member, view_channel=True, speak=True, connect=True)
            await ctx.send(f"Berechtigungen für **{member.display_name}** in der Kategorie **{category.name}** wurden **aktiviert**.")

        elif action == "remove":
            if not ctx.message.mentions:
                await ctx.send("Bitte erwähne einen Benutzer, dem du die Berechtigungen entfernen möchtest.")
                return

            user = ctx.message.mentions[0]
            member = guild.get_member(user.id)
            if not member:
                await ctx.send("Benutzer nicht gefunden.")
                return

            # Berechtigungen für den Benutzer auf die von @everyone zurücksetzen
            await category.set_permissions(member, overwrite=None)  # Entfernt alle spezifischen Berechtigungen des Benutzers
            await ctx.send(f"Berechtigungen für **{member.display_name}** in der Kategorie **{category.name}** wurden **entfernt**.")

        else:
            await ctx.send(
                "Ungültiger Befehl.s\n"
                "Verwende `.event open/close`\n"
                "`.event vc limit off/2`\n"
                "`.event vc close/open`\n"
                "`.event add/remove @user`."
            )

async def setup(bot):
    await bot.add_cog(VCControl(bot))
