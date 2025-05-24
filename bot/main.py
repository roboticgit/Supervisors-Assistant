import discord
from discord.ext import commands
from discord import Intents, app_commands
import os
from dotenv import load_dotenv
import mysql.connector
import sys
import requests
import pytz
from datetime import datetime

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

# Set up bot with intents and slash commands
intents = Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Database connection
def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

# Event: Bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    activity = discord.Activity(type=discord.ActivityType.watching, name=f"SCR's supervisors")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    for filename in os.listdir('./bot/cogs'):
        if filename.endswith('.py') and filename != '__init__.py':  # Skip __init__.py
            await bot.load_extension(f'cogs.{filename[:-3]}')
    print('All cogs loaded and bot is ready!')

# Ensure the bot has permission to fetch user information
@bot.event
async def on_member_join(member):
    print(f"New member joined: {member.name} (ID: {member.id})")

@tree.command(name="ping", description="Check if the bot is responsive.")
async def ping(interaction: discord.Interaction):
    import time
    start = time.perf_counter()
    embed = discord.Embed(title=":ping_pong:", description="", color=discord.Color.dark_grey())
    await interaction.response.send_message(embed=embed, ephemeral=True)
    end = time.perf_counter()
    delay_ms = int((end - start) * 1000)
    # Edit the original response to include the delay
    await interaction.edit_original_response(embed=discord.Embed(
        title=":ping_pong:",
        description=f"Response delay: `{delay_ms}ms`",
        color=discord.Color.dark_grey()
    ))

# Text-based commands for the designated guild only
GUILD_ID = 1373047358648094851  # From user.py

@bot.event
async def on_message(message):
    if message.guild is None or message.guild.id != GUILD_ID or message.author.bot:
        return
    app_info = await bot.application_info()
    is_owner = message.author.id == app_info.owner.id
    content = message.content.strip()
    # >publish [content]
    if content.startswith('>publish '):
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        embed_content = content[len('>publish '):].strip()
        if not embed_content:
            await message.channel.send('Usage: >publish [content]')
            return
        # Fetch all users registered in the DB
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT discord_id FROM users")
        users = cursor.fetchall()
        connection.close()
        embed = discord.Embed(title="Bot Update:", description=f"{embed_content}", color=discord.Color.purple())
        sent = 0
        for user in users:
            try:
                member = await bot.fetch_user(user['discord_id'])
                if member:
                    await member.send(embed=embed)
                    sent += 1
            except Exception:
                continue
        await message.channel.send(f"Published to {sent} users.")
        return
    # >pm [user] [content]
    if content.startswith('>pm '):
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        try:
            _, user_id, *msg_parts = content.split()
            user_id = int(user_id)
            embed_content = ' '.join(msg_parts)
        except Exception:
            await message.channel.send('Usage: >pm [user] [content]')
            return
        member = message.guild.get_member(user_id)
        if not member:
            await message.channel.send('User not found.')
            return
        embed = discord.Embed(title="Message from the Bot Administrator:", description=f"*{embed_content}*", color=discord.Color.gold())
        try:
            await member.send(embed=embed)
            await message.channel.send(f"PM sent to {member.display_name}.")
        except Exception:
            await message.channel.send('Failed to send PM.')
        return
    # >reset
    if content.strip() == '>reset':
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        await message.channel.send('Resetting bot: clearing slash commands and restarting...')
        # Clear all slash commands (do not await, it's not a coroutine in discord.py 2.5.2)
        tree.clear_commands(guild=discord.Object(id=GUILD_ID))
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        # Restart the bot process
        os.execv(sys.executable, ['python'] + sys.argv)
        return
    # >shutdown
    if content.strip() == '>shutdown':
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        await message.channel.send('Shutting down bot...')
        await bot.close()
        os._exit(0)
        return
    # >find [taskID]
    if content.startswith('>find '):
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        try:
            _, task_id = content.split(maxsplit=1)
        except Exception:
            await message.channel.send('Usage: >find [taskID]')
            return
        # Fetch task from ClickUp API (with markdown)
        headers = {"Authorization": os.getenv('CLICKUP_API_TOKEN'), "accept": "application/json"}
        url = f"https://api.clickup.com/api/v2/task/{task_id}?include_markdown_description=true"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            await message.channel.send(f'Failed to fetch task: {response.text}')
            return
        task = response.json()
        # Get user timezone from DB
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT timezone FROM users WHERE discord_id = %s", (message.author.id,))
        row = cursor.fetchone()
        connection.close()
        user_tz = pytz.timezone(row['timezone']) if row and row['timezone'] else pytz.UTC
        # Get space info
        space_name = task.get('list', {}).get('space', {}).get('name', 'Unknown')
        # Department color emoji
        emoji = ''
        if 'driving' in space_name.lower():
            emoji = '\U0001F534'  # Red
        elif 'dispatch' in space_name.lower():
            emoji = '\U0001F7E0'  # Orange
        elif 'guard' in space_name.lower():
            emoji = '\U0001F7E1'  # Yellow
        elif 'signal' in space_name.lower():
            emoji = '\U0001F7E2'  # Green
        # Build embed
        name = task.get('name', 'Unknown')
        desc = task.get('description', 'No description.')
        markdown_desc = task.get('markdown_description', desc)
        tags = ', '.join([t['name'] for t in task.get('tags', [])]) or 'None'
        status = task.get('status', {}).get('status', 'Unknown')
        assignees = ', '.join([a.get('username') or a.get('email') or str(a.get('id')) for a in task.get('assignees', [])]) or 'None'
        due_date = task.get('due_date')
        if due_date:
            due_dt = datetime.utcfromtimestamp(int(due_date) / 1000).replace(tzinfo=pytz.UTC).astimezone(user_tz)
            due_str = due_dt.strftime('%A, %B %d, %Y at %I:%M %p %Z')
        else:
            due_str = 'None'
        # Created date
        created_date = task.get('date_created')
        if created_date:
            created_dt = datetime.utcfromtimestamp(int(created_date) / 1000).replace(tzinfo=pytz.UTC).astimezone(user_tz)
            created_str = created_dt.strftime('%A, %B %d, %Y at %I:%M %p %Z')
        else:
            created_str = 'Unknown'
        # Comments & activity (fetch comments)
        comments_url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
        comments_resp = requests.get(comments_url, headers=headers)
        comments = []
        if comments_resp.status_code == 200:
            comments_data = comments_resp.json()
            for c in comments_data.get('comments', []):
                author = c.get('user', {}).get('username', 'Unknown')
                text = c.get('comment_text', '')
                created = c.get('date')
                if created:
                    created_dt = datetime.utcfromtimestamp(int(created) / 1000).replace(tzinfo=pytz.UTC).astimezone(user_tz)
                    created_str_c = created_dt.strftime('%Y-%m-%d %H:%M')
                else:
                    created_str_c = 'Unknown'
                comments.append(f"**{author}** ({created_str_c}): {text}")
        # History & events (fetch task history)
        history_url = f"https://api.clickup.com/api/v2/task/{task_id}/history"
        history_resp = requests.get(history_url, headers=headers)
        events = []
        if history_resp.status_code == 200:
            history_data = history_resp.json()
            for e in history_data.get('history', []):
                event_type = e.get('type', 'Unknown')
                user = e.get('user', {}).get('username', 'Unknown')
                date = e.get('date')
                if date:
                    event_dt = datetime.utcfromtimestamp(int(date) / 1000).replace(tzinfo=pytz.UTC).astimezone(user_tz)
                    event_str = event_dt.strftime('%Y-%m-%d %H:%M')
                else:
                    event_str = 'Unknown'
                details = e.get('field', '')
                value = e.get('after', '')
                events.append(f"**{user}** [{event_type}] ({event_str}): {details} {value}")
        # Build embed
        embed = discord.Embed(title=f"Task: {name}", color=discord.Color.blue())
        embed.add_field(name="Space", value=f"{emoji} {space_name}", inline=False)
        embed.add_field(name="Tags", value=tags, inline=False)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Assignees", value=assignees, inline=True)
        embed.add_field(name="Due Date", value=due_str, inline=False)
        embed.add_field(name="Created", value=created_str, inline=False)
        if comments:
            embed.add_field(name="Comments", value='\n'.join(comments), inline=False)
        if events:
            embed.add_field(name="History / Events", value='\n'.join(events[:10]), inline=False)
        embed.add_field(name="Markdown Description", value=f"```markdown\n{markdown_desc[:1900]}\n```", inline=False)
        await message.channel.send(embed=embed)
        return
    await bot.process_commands(message)

# Run the bot
bot.run(TOKEN)