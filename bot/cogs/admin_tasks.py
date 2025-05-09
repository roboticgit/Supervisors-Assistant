class AdminTasksCog:
    def __init__(self, bot):
        self.bot = bot

    async def manage_roles(self, ctx, member: discord.Member, role: discord.Role):
        """Assigns a role to a member."""
        if ctx.author.guild_permissions.manage_roles:
            await member.add_roles(role)
            await ctx.send(f"Role {role.name} has been assigned to {member.display_name}.")
        else:
            await ctx.send("You do not have permission to manage roles.")

    async def send_notification(self, ctx, message: str):
        """Sends a notification to all members in the server."""
        for member in ctx.guild.members:
            if member.bot:
                continue
            try:
                await member.send(message)
            except discord.Forbidden:
                continue
        await ctx.send("Notification sent to all members.")

    async def list_members(self, ctx):
        """Lists all members in the server."""
        members = [member.display_name for member in ctx.guild.members]
        await ctx.send("\n".join(members))