import discord
from discord.ext import commands

class RoleManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Roles are ready!")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        role = discord.utils.get(member.guild.roles, name="Mitglied")
        await member.add_roles(role)

    @commands.command(name="role")
    @commands.has_any_role("|| Moderator", "|| Head-Moderator", "|| Admin")
    async def role(self, ctx, action: str, member: discord.Member, role: discord.Role):
        if action == "add":
            if role in member.roles:
                await ctx.send(f"Diese Rolle hat {member.mention} bereits!")
            else:
                await member.add_roles(role)
                await ctx.send(f"Die Rolle {role.mention} wurde zu {member.mention} hinzugefügt! \n\n**Teammitglied**:{ctx.author.mention}")

        if action == "remove":
            if role not in member.roles:
                await ctx.send(f"Diese Rolle hat {member.mention} nicht!")
            else:
                await member.remove_roles(role)
                await ctx.send(f"Die Rolle {role.mention} wurde vom Benutzer {member.mention} entfernt! \n\n**Teammitglied**:{ctx.author.mention}")

async def setup(bot):
    await bot.add_cog(RoleManagement(bot))