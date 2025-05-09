import discord
from discord.ext import commands
from discord import app_commands

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="remind", description="Set a reminder")
    async def remind(self, interaction: discord.Interaction, time: str, message: str):
        await interaction.response.send_message(f"Reminder set for {time}: {message}")

async def setup(bot):
    await bot.add_cog(Reminders(bot))