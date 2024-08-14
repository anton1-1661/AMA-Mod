import discord
from discord.ext import commands
import aiohttp
import json

class ChatGPT(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"ChatGPT is online!")

    @commands.command(aliases=["chatgpt"])
    @commands.has_any_role("|| Verified", "|| Admin")
    async def gpt(self, ctx: commands.Context, *, prompt: str):
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "davinci-002",
                "prompt": prompt,
                "temperature": 0.5,
                "max_tokens": 50,
                "presence_penalty": 0,
                "frequency_penalty": 0,
                "best_of": 1,
            }
            
            with open("api_key.txt") as file:
                API_KEY = file.read().strip()
        
            headers = {"Authorization": f"Bearer {API_KEY}"}
            try:
                async with session.post("https://api.openai.com/v1/completions", json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        response = await resp.json()
                        gpt_text = response["choices"][0]["text"].strip()
                        gpt_embed = discord.Embed(title="ChatGPT's Antwort:", description=gpt_text)
                        await ctx.reply(embed=gpt_embed)
                    else:
                        error_message = await resp.text()
                        await ctx.reply(f"Fehler bei der Anfrage: {error_message}")
            except Exception as e:
                await ctx.reply(f"Es gab einen Fehler bei der Anfrage: {str(e)}")

async def setup(bot):
    await bot.add_cog(ChatGPT(bot))
