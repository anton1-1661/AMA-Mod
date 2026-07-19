import os
import json
import discord
from discord.ext import commands

TRICKS_FILE = 'cogs/json/tricks.json'
RESERVED_TRICK_NAMES = {"createtrick", "deltrick", "tricks", "addtrick"}

class Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_channels={}
        self.allowed_mentions = discord.AllowedMentions(users=True)
        self.tricks = {}  # Trickname -> Inhalt
        self._registered_trick_commands = set() 
        self.load_tricks()
        self.register_all_tricks()
        self.mod_logs_channel = 123456789  # Channel-ID für Moderations-Logs, bitte anpassen

    def load_tricks(self):
        """Lädt gespeicherte Tricks aus der JSON-Datei, falls vorhanden."""
        if not os.path.exists(TRICKS_FILE):
            return

        try:
            with open(TRICKS_FILE, 'r', encoding='utf-8') as f:
                self.tricks = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Tricks] Konnte tricks.json nicht laden: {e}")
            self.tricks = {}

    def save_tricks(self):
        """Schreibt den aktuellen Trick-Zustand synchron in die JSON-Datei."""
        os.makedirs(os.path.dirname(TRICKS_FILE), exist_ok=True)

        tmp_path = TRICKS_FILE + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(self.tricks, f, ensure_ascii=False, indent=4)
        os.replace(tmp_path, TRICKS_FILE)

    def register_trick_command(self, name):
        """Registriert einen Trick als eigenen aufrufbaren Bot-Command (z. B. !modpacks)."""
        if self.bot.get_command(name) is not None:
            print(f"[Tricks] Konnte Trick '{name}' nicht als Command registrieren: Name bereits vergeben.")
            return False

        async def callback(ctx, _name=name):
            content = self.tricks.get(_name)
            if content is None:
                await ctx.send("Dieser Trick existiert nicht (mehr).")
                return
            await ctx.send(f"**.{_name}**\n\n{content}")

        command = commands.Command(callback, name=name)
        self.bot.add_command(command)
        self._registered_trick_commands.add(name)
        return True
    
    def unregister_trick_command(self, name):
        """Entfernt einen dynamisch registrierten Trick-Command wieder."""
        if name in self._registered_trick_commands:
            self.bot.remove_command(name)
            self._registered_trick_commands.discard(name)

    def register_all_tricks(self):
        """Registriert beim Cog-Start alle gespeicherten Tricks als Commands."""
        for name in list(self.tricks.keys()):
            self.register_trick_command(name)

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Support is online!")

    @commands.command(aliases=["createtrick"])
    @commands.has_permissions(administrator=True)
    async def addtrick(self, ctx, name: str, *, content: str):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        """Erstellt einen neuen Trick oder aktualisiert einen bestehenden."""
        name = name.lower()

        if name in RESERVED_TRICK_NAMES:
            await ctx.send(f"`{name}` ist ein reservierter Name und kann nicht als Trickbefehl verwendet werden.")
            return

        is_new = name not in self.tricks
        self.tricks[name] = content
        self.save_tricks()

        if is_new:
            success = self.register_trick_command(name)
            if not success:
                await ctx.send(f"Der Trickbefehl **{name}** wurde gespeichert, konnte aber **nicht** als eigener Command "
                                f"registriert werden, da `{name}` bereits ein anderer Befehl ist. "
                                f"Wähle einen anderen Namen.")
                return

        await ctx.send(f"Trickbefehl **{name}** wurde **{'erstellt' if is_new else 'aktualisiert'}**. "
                        f"Aufrufbar mit `.{name}`.")
        
        #Logs 
        embed = discord.Embed(
            title='「Trickbefehl」',
            description=f'Der Trickbefehl **{name}** wurde **erstellt**.\n\n**Teammitglied**:{ctx.author.mention}',
            color=discord.Color.green()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed) 

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def deltrick(self, ctx, name: str):
        logs_channel = discord.utils.get(ctx.guild.channels, id=self.mod_logs_channel)
        """Löscht einen Trick wieder, inklusive des zugehörigen Commands."""
        name = name.lower()
        if name not in self.tricks:
            await ctx.send(f"Es gibt keinen Trickbefehl mit dem Namen **{name}**.")
            return

        del self.tricks[name]
        self.save_tricks()
        self.unregister_trick_command(name)

        await ctx.send(f"Trickbefehl **{name}** wurde **gelöscht**.")

        #Logs 
        embed = discord.Embed(
            title='「Trickbefehl」',
            description=f'Der Trickbefehl **{name}** wurde **gelöscht**.\n\n**Teammitglied**:{ctx.author.mention}',
            color=discord.Color.orange()
        )
        embed.set_author(name="Moderation Logs", icon_url=ctx.guild.icon)
        await logs_channel.send(embed=embed) 

    @commands.command(name="tricks")
    async def list_tricks(self, ctx):
        """Listet alle vorhandenen Tricks auf."""
        if not self.tricks:
            await ctx.send("**Verfügbare Trickbefehle:**\n\n_Es gibt aktuell keine Trickbefehle._")
            return

        trick_lines = [f"**-** `.{name}`" for name in sorted(self.tricks.keys())]
        trick_list_str = "\n".join(trick_lines)

        await ctx.send(f"**Verfügbare Trickbefehle:**\n\n{trick_list_str}")

async def setup(bot):
    await bot.add_cog(Support(bot))