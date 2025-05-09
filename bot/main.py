import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize the bot with a command prefix
bot = commands.Bot(command_prefix='!')

# Load cogs
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} - {bot.user.id}')
    print('------')
    for filename in os.listdir('./bot/cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')

# Run the bot with the token from the environment variables
bot.run(os.getenv('DISCORD_TOKEN'))