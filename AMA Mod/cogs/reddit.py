import discord
from discord.ext import commands
from random import choice
import asyncpraw as praw

class Reddit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reddit = praw.Reddit(client_id="uq8OU-0Iwcc2ZBOFGmpKOw", client_secret="2Fucwsuas55ZjbSiAoPWYe2_zxBEfw", user_agent="script:randommeme:v1.0 (by u/Anton1661)")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Memes are ready!")

    @commands.command(aliases=["randommeme"])
    async def meme(self, ctx: commands.Context):
        
        
        subreddit = await self.reddit.subreddit("memes")
        posts_lists = []

        async for post in subreddit.hot(limit=30):
            if not post.over_18 and post.author is not None and any(post.url.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif"]):
                author_name = post.author.name
                posts_lists.append((post.url, author_name))
            if post.author is None:
                posts_lists.append((post.url, "N/A"))
        if posts_lists:

            random_post = choice(posts_lists)

            meme_embed = discord.Embed(title="Random Meme", description="Random Meme von r/memes", color=discord.Color.random())
            meme_embed.set_author(name=f"Meme wurde angefrgt von {ctx.author.name}", icon_url=ctx.author.avatar)
            meme_embed.set_image(url=random_post[0])
            meme_embed.set_footer(text=f"Post erstellt von {random_post[1]}", icon_url=None)
            await ctx.send(embed=meme_embed)

        else:
            await ctx.send("Fehler 303, bitte versuche später nochmal.")
    
    def cog_unload(self):
        self.bot.loop.create_task(self.reddit.close())
        
async def setup(bot):
    await bot.add_cog(Reddit(bot))