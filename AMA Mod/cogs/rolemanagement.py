import discord
from discord.ext import commands

class RoleManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Roles are ready!")

    @commands.Cog.listener()
    async def on_member_join(self, ctx, member: discord.Member):
        await member.add_roles("Mitglied")

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Headmoderator", "|| Admin")
    async def addrole(self, ctx, member: discord.Member, role: discord.Role):
        if role in member.roles:
            await ctx.send(f"Diese Rolle hat {member.mention} bereits!")
        else:
            await member.add_roles(role)
            await ctx.send(f"Die Rolle {role.mention} wurde zu {member.mention} hinzugefügt! \n\n**Teammitglied**:{ctx.author.mention}")

    @commands.command(aliases=["removerole"])
    @commands.has_any_role("|| Moderator", "|| Headmoderator", "|| Admin")
    async def remrole(self, ctx, member: discord.Member, role: discord.Role):
        if role not in member.roles:
            await ctx.send(f"Diese Rolle hat {member.mention} nicht!")
        else:
            await member.remove_roles(role)
            await ctx.send(f"Die Rolle {role.mention} wurde vom Benutzer {member.mention} entfernt! \n\n**Teammitglied**:{ctx.author.mention}")

async def setup(bot):
    await bot.add_cog(RoleManagement(bot))