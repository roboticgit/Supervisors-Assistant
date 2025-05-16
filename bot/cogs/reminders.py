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
        for user in users:
            # Skip users with missing or 'Not set' data
            if any(user.get(field) in (None, 'Not set') for field in [
                'primary_department', 'roblox_username', 'clickup_email', 'timezone']):
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
                        await self.send_reminder(discord_id, department, day_of_month)
                elif days_left in [7, 3]:
                    if concluded_total < 8 or concluded_username < host_required:
                        await self.send_reminder(discord_id, department, days_left)

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

async def setup(bot):
    await bot.add_cog(Reminders(bot))