import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import pytz
import os
import mysql.connector

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.send_quota_reminders.start()
        self.send_training_reminders.start()

    def get_db_connection(self):
        return mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )

    async def get_user_reminder_pref(self, discord_id):
        connection = self.get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT reminder_preferences FROM users WHERE discord_id = %s", (discord_id,))
        row = cursor.fetchone()
        connection.close()
        if not row:
            return None
        return row['reminder_preferences']

    async def log_to_channel(self, message):
        channel = self.bot.get_channel(self.LOG_CHANNEL_ID)
        if channel:
            await channel.send(message)

    LOG_CHANNEL_ID = 1373467224374906910  

    @tasks.loop(hours=24)
    async def send_quota_reminders(self):
        today = datetime.now(pytz.UTC)
        day_of_month = today.day
        days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
        days_left = days_in_month - day_of_month
        # Only run on the 7th, 11th, and when 7 or 3 days left
        if day_of_month not in [7, 11] and days_left not in [7, 3]:
            return
        connection = self.get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT discord_id, primary_department, secondary_department, roblox_username, clickup_email, timezone FROM users")
        users = cursor.fetchall()
        connection.close()
        await self.log_to_channel(f"[Quota] Fetching quota info for {len(users)} users on {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        for user in users:
            # Skip users with missing or 'Not set' data
            if any(user.get(field) in (None, 'Not set') for field in [
                'primary_department', 'roblox_username', 'clickup_email', 'timezone', 'reminder_preferences']):
                continue
            # Only send if 'quota' is in reminder_preferences
            if 'quota' not in user.get('reminder_preferences', '').lower():
                continue
            discord_id = user['discord_id']
            departments = [user['primary_department']]
            if user['secondary_department'] and user['secondary_department'] != 'None':
                departments.append(user['secondary_department'])
            for department in departments:
                # Check reminder preferences
                pref = await self.get_user_reminder_pref(discord_id)
                if not pref or 'quota' not in pref.lower():
                    continue
                # --- ClickUp quota logic (copied from clickup.py) ---
                # Set headers directly
                headers = {
                    "Authorization": os.getenv('CLICKUP_API_TOKEN'),
                    "accept": "application/json"
                }
                # Get list_id directly from .env
                list_id_env_key = f"CLICKUP_LIST_ID_{department.upper().replace(' ', '_')}"
                list_id = os.getenv(list_id_env_key)
                if not list_id:
                    continue
                # Get first of month in ms
                from datetime import timezone as dt_timezone
                now = datetime.now(dt_timezone.utc)
                first_of_month = datetime(year=now.year, month=now.month, day=1, tzinfo=dt_timezone.utc)
                first_of_month_unix_ms = int(first_of_month.timestamp() * 1000)
                roblox_username = user['roblox_username']
                clickup_email = user['clickup_email']
                # Gather all tasks for this department
                concluded_username = 0
                concluded_total = 0
                # Concluded (archived true/false)
                for archived_value in ["false", "true"]:
                    page = 0
                    while True:
                        url_with_params = (
                            f"https://api.clickup.com/api/v2/list/{list_id}/task?"
                            f"archived={archived_value}&"
                            f"statuses=concluded&"
                            f"statuses=concluded&"
                            f"include_closed=true&"
                            f"due_date_gt={first_of_month_unix_ms}&"
                            f"page={page}"
                        )
                        import requests
                        response = requests.get(url_with_params, headers=headers)
                        if response.status_code != 200:
                            break
                        data = response.json()
                        tasks = data.get("tasks", [])
                        if not tasks:
                            break
                        for task in tasks:
                            assignees = [assignee['email'] for assignee in task.get('assignees', [])]
                            if clickup_email in assignees:
                                due_date = task.get('due_date')
                                if due_date and int(due_date) >= first_of_month_unix_ms:
                                    concluded_total += 1
                                    if roblox_username in task['name']:
                                        concluded_username += 1
                        if data.get("last_page", False):
                            break
                        page += 1
                # --- Reminder logic ---
                host_required = 3 if department == "Driving Department" else 2
                if day_of_month in [7, 11]:
                    if concluded_total < 1:
                        found_to_send = True
                        await self.send_reminder(discord_id, department, day_of_month)
                elif days_left in [7, 3]:
                    if concluded_total < 8 or concluded_username < host_required:
                        found_to_send = True
                        await self.send_reminder(discord_id, department, days_left)
                if found_to_send:
                    await self.log_to_channel(f"[Quota] Would DM {discord_id} for {department} (criteria met)")

    async def send_reminder(self, discord_id, department, timing):
        user = self.bot.get_user(discord_id)
        if not user:
            return
        today = datetime.now(pytz.UTC)
        day_of_month = today.day
        days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
        days_left = days_in_month - day_of_month
        # Reminder type logic
        if day_of_month == 7:
            embed = discord.Embed(title=f"Bi-Weekly Reminder: A Week Left ({department})", description="You are receiving this reminder because you have not completed at least one Host/CoHost within the initial 2 weeks of the month!\n- Note that these do NOT account for LOAs\n\nYou can disable these in `/settings`", color=discord.Color.yellow())
        elif day_of_month == 11:
            embed = discord.Embed(title=f"Bi-Weekly Reminder: 3 Days left ({department})", description="You are receiving this reminder because you have not completed at least one Host/CoHost within the initial 2 weeks of the month!\n- Note that these do NOT account for LOAs\n\nYou can disable these in `/settings`", color=discord.Color.orange())
        elif days_left == 7:
            host_required = 3 if department == "Driving Department" else 2
            embed = discord.Embed(title=f"Quota Reminder: A Week Left ({department})", description=f"You are receiving this reminder because you have not completed at least {host_required} hosts and 8 total Hosts/CoHosts yet!\n- Note that these do NOT account for LOAs\n\nYou can disable these in `/settings`", color=discord.Color.yellow())
        elif days_left == 3:
            host_required = 3 if department == "Driving Department" else 2
            embed = discord.Embed(title=f"Quota Reminder: 3 Days Left ({department})", description=f"You are receiving this reminder because you have not completed at least {host_required} hosts and 8 total Hosts/CoHosts yet!\n- Note that these do NOT account for LOAs\n\nYou can disable these in `/settings`", color=discord.Color.red())
        else:
            embed = discord.Embed(title=f"Quota Reminder ({department})", description="How did we get here? The bot has no idea why it's sending you this.", color=discord.Color.blue())
        try:
            await user.send(embed=embed)
        except Exception:
            pass

    @tasks.loop(minutes=1)
    async def send_training_reminders(self):
        import requests
        from time import sleep
        now = datetime.now(pytz.UTC)
        unix_25h_away = int((now + timedelta(hours=25)).timestamp() * 1000)
        unix_24h_away = int((now + timedelta(hours=24)).timestamp() * 1000)
        unix_10h_away = int((now + timedelta(hours=10)).timestamp() * 1000)
        unix_2h_away = int((now + timedelta(hours=2)).timestamp() * 1000)
        unix_30m_away = int((now + timedelta(minutes=30)).timestamp() * 1000)
        unix_15m_away = int((now + timedelta(minutes=15)).timestamp() * 1000)
        department_keys = [
            'CLICKUP_LIST_ID_DRIVING_DEPARTMENT',
            'CLICKUP_LIST_ID_DISPATCHING_DEPARTMENT',
            'CLICKUP_LIST_ID_GUARDING_DEPARTMENT',
            'CLICKUP_LIST_ID_SIGNALLING_DEPARTMENT',
        ]
        connection = self.get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT discord_id, roblox_username, clickup_email, reminder_preferences FROM users")
        users = cursor.fetchall()
        connection.close()
        await self.log_to_channel(f"[Training] Fetching training info for {len(users)} users on {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        user_lookup = {u['clickup_email']: u for u in users if u['clickup_email'] not in (None, 'Not set')}
        for dept_key in department_keys:
            list_id = os.getenv(dept_key)
            if not list_id:
                continue
            url = f"https://api.clickup.com/api/v2/list/{list_id}/task?archived=false&statuses=scheduled&due_date_lt={unix_25h_away}"
            headers = {"Authorization": os.getenv('CLICKUP_API_TOKEN'), "accept": "application/json"}
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                continue
            data = response.json()
            for task in data.get('tasks', []):
                due_date = int(task.get('due_date', 0))
                assignees = [a['email'] for a in task.get('assignees', [])]
                for email in assignees:
                    user = user_lookup.get(email)
                    if not user:
                        continue
                    # Skip users with any field set to 'Not set'
                    if any(user.get(field) == 'Not set' for field in ['discord_id', 'roblox_username', 'clickup_email', 'reminder_preferences']):
                        continue
                    # Only send if 'training' is in reminder_preferences
                    if 'training' not in user.get('reminder_preferences', '').lower():
                        continue
                    discord_id = user['discord_id']
                    roblox_username = user['roblox_username']
                    found_to_send = None
                    # Wait until 24h away
                    if unix_24h_away - 900000 < due_date <= unix_24h_away:
                        found_to_send = 1
                        await self.send_training_embed(discord_id, 1, task)
                    # 10h away
                    elif unix_10h_away - 900000 < due_date <= unix_10h_away:
                        if email in [a['email'] for a in task.get('assignees', [])]:
                            found_to_send = 2
                            await self.send_training_embed(discord_id, 2, task)
                    # 2h away
                    elif unix_2h_away - 900000 < due_date <= unix_2h_away:
                        if email in [a['email'] for a in task.get('assignees', [])]:
                            found_to_send = 3
                            await self.send_training_embed(discord_id, 3, task)
                    # 30m away
                    elif unix_30m_away - 900000 < due_date <= unix_30m_away:
                        if roblox_username in task['name']:
                            found_to_send = 4
                            await self.send_training_embed(discord_id, 4, task)
                    # 15m away
                    elif unix_15m_away - 900000 < due_date <= unix_15m_away:
                        if roblox_username not in task['name']:
                            found_to_send = 5
                            await self.send_training_embed(discord_id, 5, task)
                    if found_to_send:
                        await self.log_to_channel(f"[Training] Would DM {discord_id} for task '{task.get('name','')}' (criteria {found_to_send})")

    async def send_training_embed(self, discord_id, embed_num, task):
        user = self.bot.get_user(discord_id)
        if not user:
            return
        # --- Variable extraction ---
        # Determine type (Host or Co-Host) based on ROBLOX username in task name
        task_name = task.get('name', '')
        # Fetch user's ROBLOX username and timezone from DB
        connection = self.get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT roblox_username, timezone FROM users WHERE discord_id = %s", (discord_id,))
        row = cursor.fetchone()
        connection.close()
        roblox_username = row['roblox_username'] if row and row['roblox_username'] else ''
        user_tz = pytz.timezone(row['timezone']) if row and row['timezone'] else pytz.UTC
        if roblox_username and roblox_username in task_name:
            type_str = 'Host'
        else:
            type_str = 'Co-Host'
        # Get due date in user's timezone
        due_date_ms = int(task.get('due_date', 0))
        due_date_utc = datetime.utcfromtimestamp(due_date_ms / 1000)
        due_date_local = due_date_utc.replace(tzinfo=pytz.UTC).astimezone(user_tz)
        date_str = due_date_local.strftime('%A, %B %d, %Y at %I:%M %p %Z')
        # Get the actual ClickUp task URL
        task_url = task.get('url')
        if not task_url:
            # Fallback: construct from task_id if available
            task_id = task.get('id')
            if task_id:
                task_url = f"https://app.clickup.com/t/{task_id}"
            else:
                task_url = "https://app.clickup.com/"
        # --- Embeds ---
        if embed_num == 1:
            embed = discord.Embed(title=f"Upcoming `{type_str}` in a day", description=f"You have an upcoming `{type_str}` occuring in 24 hours ({date_str}). Now would be a good time to ensure you are available.", color=discord.Color.blue())
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="ClickUp Task", url=task_url))
        elif embed_num == 2:
            embed = discord.Embed(title=f"Reminder:`{type_str}` in 10 hours", description=f"Your `{type_str}` training is in 10 hours ({date_str}). You should probably set an alarm for this training.", color=discord.Color.yellow())
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="ClickUp Task", url=task_url))
        elif embed_num == 3:
            embed = discord.Embed(title=f"Reminder: `{type_str}` in 2 hours", description=f"Your `{type_str}` is happening in 2 hours. You should double check you've set an alarm for this training if you intend to leave your computer.", color=discord.Color.orange())
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="ClickUp Task", url=task_url))
        elif embed_num == 4:
            embed = discord.Embed(title="Open Your Training", description=f"Your `{type_str}` is in 30 minutes! Remember to open the server.", color=discord.Color.red())
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="SCR Server", url="https://www.roblox.com/games/696347899/V2-2-Stepford-County-Railway"))
        elif embed_num == 5:
            embed = discord.Embed(title="Join Your Training", description=f"Your `{type_str}` is in 15 minutes. Join the server if you have not already!", color=discord.Color.red())
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="SCR Server", url="https://www.roblox.com/games/696347899/V2-2-Stepford-County-Railway"))
        else:
            embed = discord.Embed(title="Training Reminder", description="Unknown timing (but there is a training occuring in 24 hours that you are apart of)", color=discord.Color.light_grey())
            view = None
        try:
            if view:
                await user.send(embed=embed, view=view)
            else:
                await user.send(embed=embed)
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(Reminders(bot))