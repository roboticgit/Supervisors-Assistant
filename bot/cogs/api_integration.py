import discord
from discord.ext import commands
from discord import app_commands

class APIIntegration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="fetch", description="Fetch data from an API")
    async def fetch(self, interaction: discord.Interaction, endpoint: str):
        # Example API call logic
        await interaction.response.send_message(f"Fetching data from {endpoint}...")

async def setup(bot):
    await bot.add_cog(APIIntegration(bot))