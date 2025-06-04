import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import pytz
import os
import mysql.connector

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._quota_task_started = False
        self._training_task_started = False
        # Schedule the tasks to start after cog is fully ready
        bot.loop.create_task(self._delayed_start())

    async def _delayed_start(self):
        await self.bot.wait_until_ready()
        try:
            self.send_quota_reminders.start()
            self._quota_task_started = True
        except Exception as e:
            print(f"[Reminders] Failed to start send_quota_reminders: {e}")
        try:
            self.send_training_reminders.start()
            self._training_task_started = True
        except Exception as e:
            print(f"[Reminders] Failed to start send_training_reminders: {e}")

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

    async def log_to_channel(self, message, department=None):
        channel = self.bot.get_channel(self.LOG_CHANNEL_ID)
        if channel:
            emoji = ''
            if department:
                dept = department.lower()
                if 'driving' in dept:
                    emoji = '\U0001F534'  # Red circle
                elif 'dispatch' in dept:
                    emoji = '\U0001F7E0'  # Orange circle
                elif 'guard' in dept:
                    emoji = '\U0001F7E1'  # Yellow circle
                elif 'signal' in dept:
                    emoji = '\U0001F7E2'  # Green circle
            await channel.send(f"{emoji} {message}" if emoji else message)

    LOG_CHANNEL_ID = 1374924175000469625  

    @tasks.loop(hours=24)
    async def send_quota_reminders(self):
        today = datetime.now(pytz.UTC)
        day_of_month = today.day
        days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
        days_left = days_in_month - day_of_month
        await self.log_to_channel(f"🗓️ Loop start: day_of_month={day_of_month}, days_left={days_left}")
        if day_of_month not in [7, 11] and days_left not in [7, 3]:
            await self.log_to_channel(f"🗓️ Skipping: Not a reminder day.")
            return
        connection = self.get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT discord_id, primary_department, secondary_department, roblox_username, clickup_email, timezone, reminder_preferences FROM users")
        users = cursor.fetchall()
        connection.close()
        await self.log_to_channel(f"🗓️ Fetching quota info for {len(users)} users on {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        for user in users:
            if any(user.get(field) in (None, 'Not set') for field in [
                'primary_department', 'roblox_username', 'clickup_email', 'timezone', 'reminder_preferences']):
                await self.log_to_channel(f"🗓️ Skipping user {user.get('discord_id')} due to missing data.")
                continue
            if 'quota' not in user.get('reminder_preferences', '').lower():
                await self.log_to_channel(f"🗓️ Skipping user {user.get('discord_id')} (no 'quota' in preferences)")
                continue
            discord_id = user['discord_id']
            departments = [user['primary_department']]
            if user['secondary_department'] and user['secondary_department'] != 'None':
                departments.append(user['secondary_department'])
            for department in departments:
                pref = await self.get_user_reminder_pref(discord_id)
                if not pref or 'quota' not in pref.lower():
                    await self.log_to_channel(f"🗓️ Skipping user {discord_id} for {department} (no 'quota' in pref)")
                    continue
                headers = {
                    "Authorization": os.getenv('CLICKUP_API_TOKEN'),
                    "accept": "application/json"
                }
                list_id_env_key = f"CLICKUP_LIST_ID_{department.upper().replace(' ', '_')}"
                list_id = os.getenv(list_id_env_key)
                if not list_id:
                    await self.log_to_channel(f"🗓️ No list_id for department {department}")
                    continue
                from datetime import timezone as dt_timezone, timedelta
                now = datetime.now(dt_timezone.utc)
                first_of_month = datetime(year=now.year, month=now.month, day=1, tzinfo=dt_timezone.utc)
                first_of_month_unix_ms = int(first_of_month.timestamp() * 1000)
                # Calculate last moment of the month (11:59:59.999 PM UTC)
                if now.month == 12:
                    next_month = datetime(year=now.year+1, month=1, day=1, tzinfo=dt_timezone.utc)
                else:
                    next_month = datetime(year=now.year, month=now.month+1, day=1, tzinfo=dt_timezone.utc)
                last_of_month = next_month - timedelta(milliseconds=1)
                last_of_month_unix_ms = int(last_of_month.timestamp() * 1000)
                roblox_username = user['roblox_username']
                clickup_email = user['clickup_email']
                concluded_username = 0
                concluded_total = 0
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
                            f"due_date_lt={last_of_month_unix_ms}&"
                            f"page={page}"
                        )
                        import requests
                        response = requests.get(url_with_params, headers=headers)
                        # Logging for each task fetch and result
                        await self.log_to_channel(f"\U0001F5D3 [Fetch] {department} | archived={archived_value} | page={page} | status={response.status_code}")
                        if response.status_code != 200:
                            await self.log_to_channel(f"\U0001F5D3 [Error] {department} | Could not fetch tasks: {response.text}")
                            break
                        data = response.json()
                        tasks = data.get("tasks", [])
                        if not tasks:
                            await self.log_to_channel(f"\U0001F5D3 [NoTasks] {department} | archived={archived_value} | page={page} | No tasks found.")
                            break
                        for task in tasks:
                            assignees = [assignee['email'] for assignee in task.get('assignees', [])]
                            if clickup_email in assignees:
                                due_date = task.get('due_date')
                                if due_date and int(due_date) >= first_of_month_unix_ms:
                                    concluded_total += 1
                                    # Log if username is in task name (Host/CoHost credit)
                                    if roblox_username in task['name']:
                                        concluded_username += 1
                                        await self.log_to_channel(f"\U0001F5D3 [HostMatch] User {discord_id} | {department} | Task '{task['name']}' | Host/CoHost credit given (username found in task name)")
                                    else:
                                        await self.log_to_channel(f"\U0001F5D3 [CoHostOnly] User {discord_id} | {department} | Task '{task['name']}' | CoHost credit only (username NOT found in task name)")
                        if data.get("last_page", False):
                            break
                        page += 1
                await self.log_to_channel(f"\U0001F5D3 [Summary] User {discord_id} | {department} | Total Host/CoHost: {concluded_total} | Host: {concluded_username}")
                host_required = 3 if department == "Driving Department" else 2
                found_to_send = False
                if day_of_month in [7, 11]:
                    if concluded_total < 1:
                        found_to_send = True
                        await self.log_to_channel(f"\U0001F5D3 [Trigger] User {discord_id} | {department} | Day {day_of_month}: <1 Host/CoHost completed. Sending reminder.")
                        await self.send_reminder(discord_id, department, day_of_month)
                elif days_left in [7, 3]:
                    if concluded_total < 8 or concluded_username < host_required:
                        found_to_send = True
                        await self.log_to_channel(f"\U0001F5D3 [Trigger] User {discord_id} | {department} | {days_left} days left: <8 Host/CoHost or <{host_required} Host completed. Sending reminder.")
                        await self.send_reminder(discord_id, department, days_left)
                if found_to_send:
                    await self.log_to_channel(f"\U0001F5D3 [DM] Reminder sent to user {discord_id} for {department} (criteria met)")

    async def send_reminder(self, discord_id, department):
        user = self.bot.get_user(discord_id)
        if not user:
            try:
                user = await self.bot.fetch_user(discord_id)
                await self.log_to_channel(f"🗓️ fetch_user succeeded for {discord_id}")
            except Exception as e:
                await self.log_to_channel(f"🗓️ Could not fetch user {discord_id}: {e}")
                return
        today = datetime.now(pytz.UTC)
        day_of_month = today.day
        days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
        days_left = days_in_month - day_of_month
        if day_of_month == 7:
            embed = discord.Embed(title=f"Bi-Weekly Reminder: A Week Left ({department})", description="You are receiving this reminder because you have not completed at least one Host/CoHost within the initial 2 weeks of the month!\n\n- Run `/check` to get more specifics on your quota situation\n- Note that these do NOT account for LOAs\n\nYou can disable these reminders in `/settings`", color=discord.Color.blue())
        elif day_of_month == 11:
            embed = discord.Embed(title=f"Bi-Weekly Reminder: 3 Days left ({department})", description="You are receiving this reminder because you have not completed at least one Host/CoHost within the initial 2 weeks of the month!\n\n- Run `/check` to get more specifics on your quota situation\n- Note that these do NOT account for LOAs\n\nYou can disable these reminders in `/settings`", color=discord.Color.blue())
        elif days_left == 7:
            host_required = 3 if department == "Driving Department" else 2
            embed = discord.Embed(title=f"Quota Reminder: A Week Left ({department})", description=f"You are receiving this reminder because you have not completed at least {host_required} hosts and/or 8 total Hosts/CoHosts yet!\n\n- Run `/check` to get more specifics on your quota situation\n- Note that these do NOT account for LOAs\n\nYou can disable these reminders in `/settings`", color=discord.Color.blue())
        elif days_left == 3:
            host_required = 3 if department == "Driving Department" else 2
            embed = discord.Embed(title=f"Quota Reminder: 3 Days Left ({department})", description=f"You are receiving this reminder because you have not completed at least {host_required} hosts and/or 8 total Hosts/CoHosts yet!\n\n- Run `/check` to get more specifics on your quota situation\n- Note that these do NOT account for LOAs\n\nYou can disable these reminders in `/settings`", color=discord.Color.blue())
        else:
            embed = discord.Embed(title=f"Quota Reminder ({department})", description="How did we get here? The bot has no idea why it's sending you this, but you should probably run `/check` to see whats up.", color=discord.Color.blue())
        try:
            await user.send(embed=embed)
            await self.log_to_channel(f"🗓️ DM sent to user {discord_id} for {department}")
        except Exception as e:
            await self.log_to_channel(f"🗓️ Failed to DM user {discord_id} for {department}: {e}")




    @tasks.loop(minutes=15)
    async def send_training_reminders(self):
        import requests
        now = datetime.now(pytz.UTC)
        unix_25h_away = int((now + timedelta(hours=25)).timestamp() * 1000)
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
        user_lookup = {u['clickup_email']: u for u in users if u['clickup_email'] not in (None, 'Not set')}
        for dept_key in department_keys:
            list_id = os.getenv(dept_key)
            if not list_id:
                continue

            url = f"https://api.clickup.com/api/v2/list/{list_id}/task?archived=false&statuses=scheduled&statuses=scheduled&due_date_lt={unix_25h_away}"
            headers = {"Authorization": os.getenv('CLICKUP_API_TOKEN'), "accept": "application/json"}
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                await self.log_to_channel(f"⚙️ [Error] {dept_key.replace('CLICKUP_LIST_ID_', '').replace('_', ' ').title()} | Could not fetch scheduled tasks: {response.text}")
                continue
            data = response.json()
            for task in data.get('tasks', []):
                due_date = int(task.get('due_date', 0))
                assignees = [a['email'] for a in task.get('assignees', [])]
                now_ms = int(now.timestamp() * 1000)
                intervals = [
                    (24 * 60 * 60 * 1000, 1, '24h'),
                    (10 * 60 * 60 * 1000, 2, '10h'),
                    (2 * 60 * 60 * 1000, 3, '2h'),
                    (30 * 60 * 1000, 4, '30m'),
                    (15 * 60 * 1000, 5, '15m'),
                ]
                for ms, embed_num, label in intervals:
                    if due_date - ms <= now_ms < due_date - ms + 60000:
                        found_user = False
                        for email in assignees:
                            user = user_lookup.get(email)
                            if user:
                                found_user = True
                                discord_id = user['discord_id']
                                roblox_username = user['roblox_username']
                                if any(user.get(field) == 'Not set' for field in ['discord_id', 'roblox_username', 'clickup_email', 'reminder_preferences']):
                                    task_id = task.get('id', 'Unknown')
                                    host = task.get('name', '').split(' - ')[-1].strip() if ' - ' in task.get('name', '') else ''
                                    due_date = int(task.get('due_date', 0))
                                    dt = datetime.fromtimestamp(due_date/1000, tz=timezone.utc)
                                    date_str = dt.strftime('%d/%m/%Y (%A)')
                                    time_str = dt.strftime('%H:%M %Z')
                                    unix_ts = int(dt.timestamp())
                                    task_url = task.get('url') or f"https://app.clickup.com/t/{task_id}"
                                    await self.log_to_channel(
                                        f":gear: **[NoAssignee]** {dept_key.replace('CLICKUP_LIST_ID_', '').replace('_', ' ').title()}\n\n|---> Task\n> ID: {task_id}\n> Date: {date_str}\n> Time: {time_str}\n> Adjusted Time: <t:{unix_ts}:f> (<t:{unix_ts}:R>)\n> Host: {host}\n\n|---> Reminder\n> Interval: {label}\n> Result: Missing required user data. Skipping. Assignees: {assignees}",
                                        department=dept_key.replace('CLICKUP_LIST_ID_', '').replace('_', ' ').title()
                                    )
                                    continue
                                if 'training' not in user.get('reminder_preferences', '').lower():
                                    task_id = task.get('id', 'Unknown')
                                    host = task.get('name', '').split(' - ')[-1].strip() if ' - ' in task.get('name', '') else ''
                                    due_date = int(task.get('due_date', 0))
                                    dt = datetime.fromtimestamp(due_date/1000, tz=timezone.utc)
                                    date_str = dt.strftime('%d/%m/%Y (%A)')
                                    time_str = dt.strftime('%H:%M %Z')
                                    unix_ts = int(dt.timestamp())
                                    task_url = task.get('url') or f"https://app.clickup.com/t/{task_id}"
                                    await self.log_to_channel(
                                        f":gear: **[NoAssignee]** {dept_key.replace('CLICKUP_LIST_ID_', '').replace('_', ' ').title()}\n\n|---> Task\n> ID: {task_id}\n> Date: {date_str}\n> Time: {time_str}\n> Adjusted Time: <t:{unix_ts}:f> (<t:{unix_ts}:R>)\n> Host: {host}\n\n|---> Reminder\n> Interval: {label}\n> Result: 'training' not in reminder preferences. Skipping. Assignees: {assignees}",
                                        department=dept_key.replace('CLICKUP_LIST_ID_', '').replace('_', ' ').title()
                                    )
                                    continue
                                is_host = roblox_username in task['name']
                                # Log sending
                                task_id = task.get('id', 'Unknown')
                                host = task.get('name', '').split(' - ')[-1].strip() if ' - ' in task.get('name', '') else ''
                                due_date = int(task.get('due_date', 0))
                                dt = datetime.fromtimestamp(due_date/1000, tz=timezone.utc)
                                date_str = dt.strftime('%d/%m/%Y (%A)')
                                time_str = dt.strftime('%H:%M %Z')
                                unix_ts = int(dt.timestamp())
                                task_url = task.get('url') or f"https://app.clickup.com/t/{task_id}"
                                await self.log_to_channel(
                                    f":gear: **[Send]** {dept_key.replace('CLICKUP_LIST_ID_', '').replace('_', ' ').title()}\n\n|---> Task\n> ID: {task_id}\n> Date: {date_str}\n> Time: {time_str}\n> Adjusted Time: <t:{unix_ts}:f> (<t:{unix_ts}:R>)\n> Host: {host}\n\n|---> Reminder\n> Interval: {label}\n> Result: DM will be sent. Assignees: {assignees}",
                                    department=dept_key.replace('CLICKUP_LIST_ID_', '').replace('_', ' ').title()
                                )
                                await self.send_training_embed(discord_id, embed_num, task)
                        if not found_user:
                            task_id = task.get('id', 'Unknown')
                            host = task.get('name', '').split(' - ')[-1].strip() if ' - ' in task.get('name', '') else ''
                            due_date = int(task.get('due_date', 0))
                            dt = datetime.fromtimestamp(due_date/1000, tz=timezone.utc)
                            date_str = dt.strftime('%d/%m/%Y (%A)')
                            time_str = dt.strftime('%H:%M %Z')
                            unix_ts = int(dt.timestamp())
                            task_url = task.get('url') or f"https://app.clickup.com/t/{task_id}"
                            await self.log_to_channel(
                                f":gear: **[NoAssignee]** {dept_key.replace('CLICKUP_LIST_ID_', '').replace('_', ' ').title()}\n\n|---> Task\n> ID: {task_id}\n> Date: {date_str}\n> Time: {time_str}\n> Adjusted Time: <t:{unix_ts}:f> (<t:{unix_ts}:R>)\n> Host: {host}\n\n|---> Reminder\n> Interval: {label}\n> Result: No matching user in DB. Assignees: {assignees}",
                                department=dept_key.replace('CLICKUP_LIST_ID_', '').replace('_', ' ').title()
                            )
                        break

    async def send_training_embed(self, discord_id, embed_num, task):
        user = self.bot.get_user(discord_id)
        if not user:
            try:
                user = await self.bot.fetch_user(discord_id)
            except Exception as e:
                await self.log_to_channel(f"⚙️ [Error] Could not fetch user with discord_id {discord_id} for training reminder: {e}")
                return None
        task_name = task.get('name', '')
        # Extract host from task_name (last part after last ' - ')
        if task_name and ' - ' in task_name:
            host = task_name.split(' - ')[-1].strip()
        else:
            host = ''
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
        due_date_ms = int(task.get('due_date', 0))
        due_date_utc = datetime.fromtimestamp(due_date_ms / 1000, tz=timezone.utc)
        due_date_local = due_date_utc.replace(tzinfo=pytz.UTC).astimezone(user_tz)
        date_str = due_date_local.strftime('%A, %B %d, %Y at %I:%M %p %Z')
        task_url = task.get('url')
        if not task_url:
            task_id = task.get('id')
            if task_id:
                task_url = f"https://app.clickup.com/t/{task_id}"
            else:
                task_url = "https://app.clickup.com/"

        if embed_num == 1:
            embed = discord.Embed(title=f"Upcoming Training: {"TRAINING HOST" if type_str == host else f"{type_str} at {host}'s training"}", description=f"You have an upcoming `{"HOST" if type_str == host else f"{type_str} at {host}'s training"}` is occuring in 24 hours ({date_str}).\n\n- **Now would be a good time to ensure you are available.**", color=discord.Color.light_grey())
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Find ClickUp Task", url=task_url))
        elif embed_num == 2:
            embed = discord.Embed(title=f"Secondary Reminder: {"TRAINING HOST" if type_str == host else f"{type_str} at {host}'s training"}", description=f"Your `{"HOST" if type_str == host else f"{type_str} at {host}'s training"}` is occuring in 10 hours ({date_str}).\n\n- **You should probably set an alarm for this training.**", color=discord.Color.light_grey())
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Find ClickUp Task", url=task_url))
        elif embed_num == 3:
            embed = discord.Embed(title=f"Get Ready: {"TRAINING HOST" if type_str == host else f"{type_str} at {host}'s training"}", description=f"Your `{type_str}` is happening in 2 hours.\n\n- **You should double check you've set an alarm for this training, and if you aren't home, now would be a good time to consider returning.**", color=discord.Color.blue())
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Find ClickUp Task", url=task_url))
        elif embed_num == 4:
            embed = discord.Embed(title="Open Your TRAINING HOST", description=f"Your `HOST` is in 30 minutes. **Remember to open the server!**", color=discord.Color.orange())
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Join SCR Server", url="https://www.roblox.com/games/696347899/V2-2-Stepford-County-Railway"))
        elif embed_num == 5:
            embed = discord.Embed(title=f"Join Training: {type_str} at {host}'s training", description=f"Your `{type_str} at {host}'s training` is in 15 minutes. **Join the server if you have not already!**", color=discord.Color.yellow())
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Join SCR Server", url="https://www.roblox.com/games/696347899/V2-2-Stepford-County-Railway"))
        else:
            embed = discord.Embed(title="Training Reminder", description="Unknown timing (but there is a training occuring in 24 hours that you are apart of). Please contact a bot administrator", color=discord.Color.light_grey())
            view = None
        try:
            if view:
                await user.send(embed=embed, view=view)
            else:
                await user.send(embed=embed)
        except Exception as e:
            print(f"[Reminders] Failed to DM user {discord_id}: {e}")
            return None

    @send_quota_reminders.before_loop
    async def before_quota_reminders(self):
        now = datetime.now(pytz.UTC)
        # Calculate next midnight UTC
        next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        print(f"[Reminders] send_quota_reminders will start at {next_run.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        await discord.utils.sleep_until(next_run)
        print(f"[Reminders] send_quota_reminders actually started at {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    @send_training_reminders.before_loop
    async def before_training_reminders(self):
        now = datetime.now(pytz.UTC)
        # Calculate next 15-minute interval
        minute = (now.minute // 15 + 1) * 15
        if minute == 60:
            next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minute)
        print(f"[Reminders] send_training_reminders will start at {next_run.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        await discord.utils.sleep_until(next_run)
        print(f"[Reminders] send_training_reminders actually started at {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")

async def setup(bot):
    await bot.add_cog(Reminders(bot))