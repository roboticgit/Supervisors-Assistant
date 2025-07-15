import discord
from discord.ext import commands
from discord import Intents
import os
import time
from dotenv import load_dotenv
import sys
import pytz
from datetime import datetime
from bot.utils.db import get_db_connection
from bot.utils.quotafetch import get_roblox_user_task_counts
import requests
from bot.utils.paginator import SimplePaginator

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Set up bot with intents and slash commands
intents = Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Event: Bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    activity = discord.Activity(type=discord.ActivityType.watching, name=f"ClickUp 24/7")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    for filename in os.listdir('./bot/cogs'):
        if filename.endswith('.py') and filename != '__init__.py':  # Skip __init__.py
            await bot.load_extension(f'bot.cogs.{filename[:-3]}')
    print('All cogs loaded and bot is ready!')

# Ensure the bot has permission to fetch user information
@bot.event
async def on_member_join(member):
    print(f"New member joined: {member.name} (ID: {member.id})")

@tree.command(name="ping", description="Check if the bot is responsive.")
async def ping(interaction: discord.Interaction):
    start = time.perf_counter()
    unix_start = int(time.time() * 1000)
    # Send initial response
    embed = discord.Embed(title=":ping_pong:", description="Pinging...", color=discord.Color.dark_grey())
    await interaction.response.send_message(embed=embed, ephemeral=True)
    # Internal processing ping
    process_end = time.perf_counter()
    process_ping = int((process_end - start) * 1000)
    # Discord API latency (if available)
    try:
        ws_ping = int(bot.latency * 1000)
    except Exception:
        ws_ping = None
    # Fallback: measure time to receive the command and double it
    now_unix = int(time.time() * 1000)
    fallback_ping = (now_unix - unix_start) * 2
    # Shard count
    try:
        shard_count = bot.shard_count if hasattr(bot, 'shard_count') and bot.shard_count else 1
    except Exception:
        shard_count = 1
    # Database connection test
    db_status = 'Unknown'
    try:
        conn = get_db_connection()
        conn.ping(reconnect=True, attempts=1, delay=0)
        db_status = ':green_circle: Connected'
        conn.close()
    except Exception:
        db_status = ':red_circle: Failed'
    # Bot profile picture
    bot_avatar = bot.user.avatar.url if bot.user and bot.user.avatar else None
    # Bot status/activity
    activity = bot.activity.name if bot.activity else 'None'
    # Build embed
    embed = discord.Embed(title=":ping_pong: Pong!", color=discord.Color.blurple())
    embed.add_field(name="Internal Processing Ping", value=f"{process_ping}ms", inline=True)
    if ws_ping is not None:
        embed.add_field(name="Discord WebSocket Ping", value=f"{ws_ping}ms", inline=True)
    else:
        embed.add_field(name="Discord Ping (Fallback)", value=f"{fallback_ping}ms", inline=True)
    embed.add_field(name="Active Shards", value=str(shard_count), inline=True)
    embed.add_field(name="Database", value=db_status, inline=True)
    if bot_avatar:
        embed.set_thumbnail(url=bot_avatar)
    embed.set_footer(text=f"Activity: {activity}")
    await interaction.edit_original_response(embed=embed)

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
        roblox_username = user.get('roblox_username')
        # Get task counts for this user
        task_counts = get_roblox_user_task_counts([roblox_username]) if roblox_username else {roblox_username: {'host': 0, 'cohost': 0, 'total': 0}}
        counts = task_counts.get(roblox_username, {'host': 0, 'cohost': 0, 'total': 0})
        # Format info as embed fields similar to /settings
        embed = discord.Embed(title=f"User DB Info for `{query}`", color=discord.Color.blurple())
        embed.add_field(name="Discord ID", value=user.get('discord_id', 'N/A'), inline=True)
        embed.add_field(name="ROBLOX Username", value=roblox_username or 'N/A', inline=True)
        embed.add_field(name="ClickUp Email", value=user.get('clickup_email', 'N/A'), inline=True)
        embed.add_field(name="Primary Department", value=user.get('primary_department', 'N/A'), inline=True)
        embed.add_field(name="Secondary Department", value=user.get('secondary_department', 'N/A'), inline=True)
        embed.add_field(name="Timezone", value=user.get('timezone', 'N/A'), inline=True)
        embed.add_field(name="Reminder Preferences", value=user.get('reminder_preferences', 'N/A'), inline=True)
        embed.add_field(name="Tasks This Month", value=f"Host: {counts['host']}\nCo-host: {counts['cohost']}\nTotal: {counts['total']}", inline=True)
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
    # >quota
    if content.strip() == '>quota':
        if not is_owner:
            await message.channel.send('You do not have permission to use this command.')
            return
        await message.channel.send('Fetching and counting hosts/co-hosts, this may take a moment...')
        roblox_users = [
            '12321wesee2', 'Cecelia312', 'emallocz', 'idaaa494', 'Jonedaaa', 'mr_fys', 'newmannly', 'norby_y', 'thebeast5432109', 'TheoCoolGpe',
            'finallybeta', '2ndFran80000000', 'aa_efo', 'ansonye', 'Bull4890vivmas', 'charlton_hbx', 'CHIElevatorman', 'chlpr', 'ComradeArmyyy',
            'DeadlyGrandmx', 'DokiDotto', 'DrivingPro63', 'EMU3001_Ouo', 'Extraabyte', 'I_iApple', 'Imnotan_furry', 'InspectorX59', 'Jonsy0930',
            'jurre12124', 'Ka1yen', 'KoalasNattion', 'Littlechocolate3003', 'lucasXD12327', 'lvekis', 'minjaehong2170', 'MoinALTC', 'moscowcode',
            'mrprojl9', 'NotFinn5', 'odlegodo', 'ORollerO', 'play333222', 'polaris65536', 'Pxndx1606', 'quite_mortified', 'Robotic_dony2468',
            'rorow122', 'Storrrent', 'Tobsenheimer', 'Walruses_XD', 'whyevenbothernaming', 'ZedZeeGamer246', '111DannySun', '1TopGTejas',
            '656Cam_GamesReal', 'AbsurdlySmrt', 'AdrianPH624', 'Adrixn0_0', 'Alanek_Alanek', 'AVeryRomanlanHolder', 'CounterBoxes', 'cristi22991',
            'Daan_oontje', 'Demon368xd', 'DJ_Techno1', 'djl_dev', 'Emilsen_2', 'holyHeccCapybara', 'intoxicanto1', 'JanEisJan', 'JumpoutPlayz',
            'kmb_Route934', 'Matthew_19104303', 'Movies22_byTR', 'obi0kenobi', 'Pilots_s', 'purpalyo1234', 'qxPeter', 'Smiling_Tokyo',
            'SolidRedLine', 'SplitYourGamming10', 'SquadFam_9000', 'SquidwardHasDementia', 'suwu27ejdud', 'TheOptimistic_Legend',
            'TheSlavicBeastXD', 'tsilenced', 'VoidyTheReblard', 'WorstLiam8312', 'x_hal3', 'Yengamertv', 'YourDailyMoose', 'BoiledAnchovies',
            'BrendonUrieFrom_PATD', 'codelyokop', 'CriticalErrxr', 'DeepBlue4210', 'deluoi945', 'Endz0Blendz0', 'flippy12052004', 'InhumanDoosh',
            'PeppyThePingu', 'Starquius', 'Stigon_0', 'STM_RBLX', 'yiuivan05', 'ak220905', 'BeaverCop2007', 'Calli656', 'eamonnthediamond',
            'Edoebzd', 'GroundskeeperHagrid', 'iProtaqonist', 'isaaccfchu', 'JakovSonBJ', 'TheYannick25', 'mqxtty', 'PhotoBlockTrollz',
            'RLSJ1997', 'slippyrails1', 'ssbninja', 'TakoThe_Taco', 'TheRandomDutchLad', 'WurstSemmelKopf', 'THEEXILENTGAMER',
            'SkibidiHawkTuahRizz7', 'Gabrieliito9', 'Nojus_Sushis', 'RB54d', 'comfled', 'NotOreo9', 'Fighter_Boy113', 'reflqctnl', 'Real_SK8R',
            'DutchVossi', 'AssortedBaklava', 'Arkadexus', 'colly_oz', 'Ethernel65', 'thecottonn', 'bagg130', 'EatTaco1', 'GL_TongDie',
            'Willmaster453', 'HoustonPlayzRoblox1', 'Sohcool55', 'Iceboy1708', 'RedAl60', 'tom1works', 'jackli0908_HKer', 'AngliaRail'
        ]
        task_counts = get_roblox_user_task_counts(roblox_users)
        all_sorted = sorted(((u, task_counts[u]['total']) for u in roblox_users), key=lambda x: x[1], reverse=True)
        def line_builder(i, tup):
            name, count = tup
            # Only show medal emojis on the first page
            if paginator.page == 0 and i < 3:
                medal_emojis = [":first_place:", ":second_place:", ":third_place:"]
                return f"{medal_emojis[i]} **{name}** ({count})"
            return f"{i+1 + paginator.page * paginator.page_size}. {name} ({count})"
        paginator = SimplePaginator(all_sorted, page_size=20, title="Most Active Supervisors This Month", line_builder=line_builder)
        await paginator.send(message.channel)
        return

    await bot.process_commands(message)

# Run the bot
bot.run(TOKEN)