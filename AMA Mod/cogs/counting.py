import discord
from discord.ext import commands

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_number = 1
        self.channel_id = 1253409683516162048  # Deine Channel-ID
        self.last_user_id = None
        

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Counting ist online!')
        channel = self.bot.get_channel(self.channel_id)
        await channel.send("Wegen einem  Restart vom **Bot** starten wir wieder bei **1**! ")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        if message.channel.id != self.channel_id:
            return
        
        # Hier holen wir uns den Channel
        channel = self.bot.get_channel(self.channel_id)

        try:
            number = int(message.content)
        except ValueError:
            return  # Wenn die Nachricht keine Zahl ist, ignorieren

        if message.author.id == self.last_user_id:
            # Wenn derselbe User wieder eine Zahl sendet, lösche die Nachricht
            await message.delete()
            await channel.send(f"{message.author.mention}, du musst dich mit anderen **abwechseln**!")
            return

        if number == self.current_number:
            await message.add_reaction('✅')  # Grüner Haken für richtige Zahl
            self.current_number += 1
            self.last_user_id = message.author.id
        else:
            await message.add_reaction('❌')  # Rotes X für falsche Zahl
            await message.channel.send(f'**Verloren!** \n\nWir starten bei **1**.')
            self.current_number = 1
            self.last_user_id = None

    @commands.command()
    async def setchannelco(self, ctx, channel: discord.TextChannel):
        self.channel_id = channel.id
        await ctx.send(f'Zählkanal wurde auf {channel.mention} gesetzt.')

async def setup(bot):
    await bot.add_cog(Counting(bot))