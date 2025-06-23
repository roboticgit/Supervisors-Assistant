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
    activity = discord.Activity(type=discord.ActivityType.watching, name=f"ClickUp 24/7")
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
        # Build the embed preview
        embed = discord.Embed(title="Bot Publication:", description=f"{embed_content}", color=discord.Color.purple())
        class ConfirmView(discord.ui.View):
            def __init__(self, *, timeout=60):
                super().__init__(timeout=timeout)
                self.value = None
            @discord.ui.button(label="Send", style=discord.ButtonStyle.green)
            async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.value = True
                self.stop()
                await interaction.response.edit_message(content="Sending publication...", view=None)
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
            async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.value = False
                self.stop()
                await interaction.response.edit_message(content="Publication cancelled.", view=None)
        view = ConfirmView()
        preview_msg = await message.channel.send(content="Preview of publication:", embed=embed, view=view)
        await view.wait()
        if not view.value:
            return
        # Fetch all users registered in the DB, but only those with all required fields set
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT discord_id, roblox_username, clickup_email, primary_department, timezone, reminder_preferences FROM users")
        users = cursor.fetchall()
        connection.close()
        eligible_users = [
            user for user in users
            if all(user.get(field) not in (None, 'Not set') for field in [
                'discord_id', 'roblox_username', 'clickup_email', 'primary_department', 'timezone', 'reminder_preferences']
            )
        ]
        sent = 0
        for user in eligible_users:
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
        try:
            member = await bot.fetch_user(user_id)
        except Exception:
            member = None
        if not member:
            await message.channel.send('User not found.')
            return
        embed = discord.Embed(title="Message from the Bot Administrator:", description=embed_content, color=discord.Color.gold())
        try:
            await member.send(embed=embed)
            await message.channel.send(f"PM sent to {member.display_name if hasattr(member, 'display_name') else member.name}.")
        except Exception:
            await message.channel.send('Failed to send PM.')
        return
    # >restart
    if content.strip() == '>restart':
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        await message.channel.send('Restarting bot process...')
        os.execv(sys.executable, ['python'] + sys.argv)
        return
    # >clear
    if content.strip() == '>clear':
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        await message.channel.send('Clearing all global slash commands...')
        tree.clear_commands(guild=None)
        await message.channel.send('All global slash commands have been cleared.')
        return
    # >sync
    if content.strip() == '>sync':
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        await message.channel.send('Syncing slash commands globally...')
        await tree.sync()
        await message.channel.send('Slash commands have been synced globally.')
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
    # >user [email|roblox_username]
    if content.startswith('>user '):
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        try:
            _, query = content.split(maxsplit=1)
        except Exception:
            await message.channel.send('Usage: >user [email|roblox_username]')
            return
        # Try to find by email first, then roblox_username
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE clickup_email = %s OR roblox_username = %s", (query, query))
        user = cursor.fetchone()
        connection.close()
        if not user:
            await message.channel.send('No user found with that email or ROBLOX username.')
            return
        # Format info as embed fields similar to /settings
        embed = discord.Embed(title=f"User DB Info for `{query}`", color=discord.Color.blue())
        embed.add_field(name="Discord ID", value=user.get('discord_id', 'N/A'), inline=True)
        embed.add_field(name="ROBLOX Username", value=user.get('roblox_username', 'N/A'), inline=True)
        embed.add_field(name="ClickUp Email", value=user.get('clickup_email', 'N/A'), inline=True)
        embed.add_field(name="Primary Department", value=user.get('primary_department', 'N/A'), inline=True)
        embed.add_field(name="Secondary Department", value=user.get('secondary_department', 'N/A'), inline=True)
        embed.add_field(name="Timezone", value=user.get('timezone', 'N/A'), inline=True)
        embed.add_field(name="Reminder Preferences", value=user.get('reminder_preferences', 'N/A'), inline=True)
        await message.channel.send(embed=embed, delete_after=120)
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
        space_obj = task.get('space', {})
        space_id = str(space_obj.get('id', 'Unknown')) if isinstance(space_obj, dict) else str(space_obj)
        # Map space_id to department using .env direct mapping (only for >find)
        space_map = {
            '90151850368': 'DRIVING',
            '90151887568': 'DISPATCHING',
            '90151887602': 'GUARDING',
            '90151887660': 'SIGNALLING',
        }
        space_name = space_map.get(space_id, space_id)
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
        # Build embed color based on status
        status_lower = status.lower() if status else ''
        if status_lower == 'request':
            embed_color = discord.Color.light_grey()
        elif status_lower == 'pending staff':
            embed_color = discord.Color.from_rgb(235, 21, 122) 
        elif status_lower == 'scheduled':
            embed_color = discord.Color.green()
        elif status_lower == 'concluded':
            embed_color = discord.Color.blue()
        elif status_lower == 'declined':
            embed_color = discord.Color.red()
        else:
            embed_color = discord.Color.dark_grey()
        # Build embed
        embed = discord.Embed(title=name, color=embed_color)
        embed.add_field(name="Space", value=f"{emoji} {space_name}", inline=True)
        embed.add_field(name="Tags", value=tags, inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Assignees", value=assignees, inline=True)
        embed.add_field(name="Due Date", value=due_str, inline=True)
        embed.add_field(name="Created", value=created_str, inline=True)
        if comments:
            embed.add_field(name="Comments", value='\n'.join(comments), inline=True)
        if events:
            embed.add_field(name="History / Events", value='\n'.join(events[:10]), inline=True)
        embed.add_field(name="Description", value=f"```markdown\n{markdown_desc[:1900]}\n```", inline=False)
        await message.channel.send(embed=embed)
        return
    # >toptrainers
    if content.strip() == '>toptrainers':
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        await message.channel.send('Fetching and counting hosts/co-hosts, this may take a moment...')
        list_ids = [
            os.getenv('CLICKUP_LIST_ID_DRIVING_DEPARTMENT'),
            os.getenv('CLICKUP_LIST_ID_DISPATCHING_DEPARTMENT'),
            os.getenv('CLICKUP_LIST_ID_GUARDING_DEPARTMENT'),
            os.getenv('CLICKUP_LIST_ID_SIGNALLING_DEPARTMENT'),
        ]
        headers = {"Authorization": os.getenv('CLICKUP_API_TOKEN'), "accept": "application/json"}
        from collections import Counter
        from datetime import datetime, timezone, timedelta
        import pytz
        # Fetch all users and their ROBLOX usernames for host/co-host detection
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT roblox_username FROM users WHERE roblox_username IS NOT NULL AND roblox_username != ''")
        roblox_users = [row['roblox_username'] for row in cursor.fetchall()]
        connection.close()
        host_counter = Counter()
        cohost_counter = Counter()
        total_counter = Counter()
        now = datetime.now(timezone.utc)
        first_of_month = datetime(year=now.year, month=now.month, day=1, tzinfo=timezone.utc)
        first_of_month_unix_ms = int(first_of_month.timestamp() * 1000)
        seen_task_ids = set()
        for list_id in list_ids:
            if not list_id:
                continue
            for archived_value in ["false", "true"]:
                page = 0
                while True:
                    url = (
                        f"https://api.clickup.com/api/v2/list/{list_id}/task?"
                        f"archived={archived_value}&"
                        f"statuses=concluded&"
                        f"statuses=concluded&"
                        f"include_closed=true&"
                        f"due_date_gt={first_of_month_unix_ms}&"
                        f"page={page}"
                    )
                    response = requests.get(url, headers=headers)
                    if response.status_code != 200:
                        break
                    data = response.json()
                    tasks = data.get('tasks', [])
                    if not tasks:
                        break
                    for task in tasks:
                        task_id = task.get('id')
                        if task_id in seen_task_ids:
                            continue
                        seen_task_ids.add(task_id)
                        due_date = task.get('due_date')
                        if due_date and int(due_date) >= first_of_month_unix_ms:
                            title = task.get('name', '')
                            desc = task.get('description', '')
                            for roblox_username in roblox_users:
                                if roblox_username and roblox_username in desc:
                                    if roblox_username in title:
                                        host_counter[roblox_username] += 1
                                        total_counter[roblox_username] += 1
                                    else:
                                        cohost_counter[roblox_username] += 1
                                        total_counter[roblox_username] += 1
                    if data.get('last_page', False):
                        break
                    page += 1
        # Pagination logic for embed
        all_sorted = total_counter.most_common()
        page_size = 10
        def get_page(page_num):
            start = page_num * page_size
            end = start + page_size
            return all_sorted[start:end]
        class SupervisorPaginator(discord.ui.View):
            def __init__(self, *, timeout=120):
                super().__init__(timeout=timeout)
                self.page = 0
                self.max_page = (len(all_sorted) - 1) // page_size
                self.message = None
            async def update_embed(self, interaction=None):
                page_entries = get_page(self.page)
                medal_emojis = [":first_place:", ":second_place:", ":third_place:"]
                lines = []
                for i, (name, count) in enumerate(page_entries):
                    if self.page == 0 and i < 3:
                        lines.append(f"{medal_emojis[i]} **{name}** ({count})")
                    else:
                        lines.append(f"{self.page*page_size + i + 1}. {name} ({count})")
                embed = discord.Embed(
                    title="Most Active Supervisors This Month",
                    description='\n'.join(lines) or 'None',
                    color=discord.Color.blurple()
                )
                if interaction:
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    await self.message.edit(embed=embed, view=self)
            @discord.ui.button(emoji='⬅️', style=discord.ButtonStyle.secondary)
            async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.page > 0:
                    self.page -= 1
                    await self.update_embed(interaction)
            @discord.ui.button(label='Page', style=discord.ButtonStyle.secondary, disabled=True)
            async def page_display(self, interaction: discord.Interaction, button: discord.ui.Button):
                pass
            @discord.ui.button(emoji='➡️', style=discord.ButtonStyle.secondary)
            async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.page < self.max_page:
                    self.page += 1
                    await self.update_embed(interaction)
            async def on_timeout(self):
                for item in self.children:
                    item.disabled = True
                if self.message:
                    await self.message.edit(view=self)
            async def interaction_check(self, interaction: discord.Interaction):
                return interaction.user == message.author
            def refresh_page_label(self):
                self.children[1].label = f"Page {self.page+1}/{self.max_page+1}"
            async def send(self, channel):
                self.refresh_page_label()
                embed = discord.Embed(
                    title="Most Active Supervisors This Month",
                    description='\n'.join([f"{':first_place:' if i==0 and self.page==0 else ':second_place:' if i==1 and self.page==0 else ':third_place:' if i==2 and self.page==0 else f'{self.page*page_size + i + 1}.'} **{name}** ({count})" if self.page==0 and i<3 else f"{self.page*page_size + i + 1}. {name} ({count})" for i, (name, count) in enumerate(get_page(self.page))]) or 'None',
                    color=discord.Color.blurple()
                )
                self.message = await channel.send(embed=embed, view=self)
        paginator = SupervisorPaginator()
        await paginator.send(message.channel)
        return
    await bot.process_commands(message)

# Run the bot
bot.run(TOKEN)