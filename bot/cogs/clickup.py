import discord
from discord.ext import commands
from discord import app_commands
import requests
import os
from dotenv import load_dotenv
from utils.helpers import get_db_connection, convert_to_unix
import asyncio
from discord.ui import Modal, Button, View
from datetime import datetime
import pytz

load_dotenv()

class Clickup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.clickup_api_token = os.getenv('CLICKUP_API_TOKEN')
        self.clickup_list_ids = {
            "Driving Department": os.getenv('CLICKUP_LIST_ID_DRIVING_DEPARTMENT'),
            "Dispatching Department": os.getenv('CLICKUP_LIST_ID_DISPATCHING_DEPARTMENT'),
            "Guarding Department": os.getenv('CLICKUP_LIST_ID_GUARDING_DEPARTMENT'),
            "Signalling Department": os.getenv('CLICKUP_LIST_ID_SIGNALLING_DEPARTMENT')
        }

    def get_clickup_headers(self):
        return {
            "Authorization": self.clickup_api_token,
            "accept": "application/json"
        }

    @app_commands.command(name="check", description="Check if you've reached quota.")
    async def check(self, interaction: discord.Interaction):
        await interaction.response.send_message("Working on your request...", ephemeral=True)
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT primary_department, secondary_department, roblox_username, clickup_email, timezone FROM users WHERE discord_id = %s", (interaction.user.id,))
        user_data = cursor.fetchone()
        connection.close()

        if (not user_data or
            any(
                user_data.get(field) == 'Not set'
                for field in [
                    'primary_department',
                    'secondary_department',
                    'roblox_username',
                    'clickup_email'
                ]
            )):
            await interaction.edit_original_response(content="User data is missing or incomplete! Please run `/settings` and fill out all of the fields")
            return

        roblox_username = user_data['roblox_username']
        clickup_email = user_data['clickup_email']
        departments = [user_data['primary_department']]
        if user_data['secondary_department']:
            departments.append(user_data['secondary_department'])

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        first_of_month = datetime(year=now.year, month=now.month, day=1, tzinfo=timezone.utc)
        first_of_month_unix_ms = int(first_of_month.timestamp() * 1000)

        embeds = []
        for department in departments:
            if department == "None":
                continue
            list_id = self.clickup_list_ids.get(department)
            if not list_id:
                await interaction.followup.send(f"Could not find {department}'s Clickup list. Please check your settings and ensure your primary department is valid.", ephemeral=True)
                continue
            headers = self.get_clickup_headers()

            # --- Completed Trainings ---
            total_tasks = 0
            username_tasks = 0
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
                                total_tasks += 1
                                if roblox_username in task['name']:
                                    username_tasks += 1
                    if data.get("last_page", False):
                        break
                    page += 1

            # --- Scheduled Trainings ---
            scheduled_trainings = []
            archived_value = "false"
            page = 0
            while True:
                url_with_params = (
                    f"https://api.clickup.com/api/v2/list/{list_id}/task?"
                    f"archived={archived_value}&"
                    f"statuses=pending%20staff&"
                    f"statuses=scheduled&"
                    f"include_closed=true&"
                    f"due_date_gt={first_of_month_unix_ms}&"
                    f"page={page}"
                )
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
                        # Only add if user is assigned
                        scheduled_trainings.append({
                            'name': task.get('name', 'No Name'),
                            'due_date': task.get('due_date'),
                            'url': task.get('url')
                        })
                if data.get("last_page", False):
                    break
                page += 1

            department_colors = {
                "Driving Department": 0xE43D2E,  # Red
                "Dispatching Department": 0xF98E2C,  # Orange
                "Guarding Department": 0xFFFF38,  # REALLY Yellow
                "Signalling Department": 0x00B18B  # Green
            }
            embed_color = department_colors.get(department, 0xFFFFFF)

            embed = discord.Embed(
                title=f"{department} Monthly Trainings:",
                color=embed_color
            )

            percentage = round((username_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0
            embed.add_field(name="Total Completed Trainings", value=str(total_tasks), inline=False)
            embed.add_field(name="How many Completed Trainings were Hosts", value=f"{username_tasks}/{total_tasks} ({percentage}%)", inline=False)

            quota = total_tasks >= 8 and username_tasks >= 2
            total_with_scheduled = total_tasks + len(scheduled_trainings)
            scheduled_hosts = 0
            for t in scheduled_trainings:
                if roblox_username in t['name']:
                    scheduled_hosts += 1
            hosts_with_scheduled = username_tasks + scheduled_hosts
            awaiting_quota = not quota and total_with_scheduled >= 8 and hosts_with_scheduled >= 2

            if quota:
                embed.title = f"{department} Monthly Trainings: Passing"
                embed.description = f"Training information will appear below. **PASSING** indicates you've completed sufficient trainings to pass this month's quota.\n\nNote: Trainings are only displayed if their due date is past the start of the current month, and you are marked as an assignee."
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1372371251867160636/1372707760357244948/image.png?ex=6827c139&is=68266fb9&hm=843a33293fca83a6eb4a5fce782cc7f7290e40fc0ef9b97c1af91b5a9ccfb53e&")
            elif awaiting_quota:
                embed.title = f"{department} Monthly Trainings: On-track"
                embed.description = f"Training information will appear below. **ON-TRACK** indicates you have not *completed* sufficient trainings, but you are scheduled for enough, meaning if you attend all your scheduled trainings you'd pass.\n\nNote: Trainings are only displayed if their due date is past the start of the current month, and you are marked as an assignee."
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1372371251867160636/1372742120674431058/image.png?ex=6827e139&is=68268fb9&hm=b30a5936784cd7ca4756da63d21caf69ffc9133ac94db63c0b4ce75f7e39e1fe&") 
            else:
                embed.title = f"{department} Monthly Trainings: Failing"
                embed.description = f"Training information will appear below. **FAILING** indicates you have not completed and/or joined enough scheduled trainings to pass this month's quota.\n\nNote: Trainings are only displayed if their due date is past the start of the current month, and you are marked as an assignee."
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1372371251867160636/1372707760138883202/image.png?ex=6827c139&is=68266fb9&hm=84f5c4edb49e786e8d1db294185bfd8e99a78c348f974349400e0e72a563683c&")

            user_tz = user_data.get('timezone', 'UTC')
            try:
                tz = pytz.timezone(user_tz)
            except Exception:
                tz = pytz.UTC
            scheduled_list = []
            for t in scheduled_trainings:
                if t['due_date']:
                    try:
                        dt_utc = datetime.utcfromtimestamp(int(t['due_date'])/1000).replace(tzinfo=pytz.UTC)
                        dt_local = dt_utc.astimezone(tz)
                        date_str = dt_local.strftime('%A, %B %d, %Y at %I:%M %p')
                    except Exception:
                        date_str = t['due_date']
                else:
                    date_str = 'No date'
                url = t['url']
                if url:
                    date_str = f"[{date_str}]({url})"
                scheduled_list.append(f"- {date_str}")
            if not scheduled_list:
                scheduled_list = ["- None"]
            embed.add_field(name=f"Upcoming Trainings you Joined", value="\n".join(scheduled_list), inline=False)

            embeds.append(embed)

        await interaction.edit_original_response(content="Success, see department(s) trainings below")
        for embed in embeds:
            await interaction.followup.send(embed=embed, ephemeral=True)

    # @app_commands.command(name="create", description="Create a training task in ClickUp.")
    # async def create(self, interaction: discord.Interaction, date: str = None, time: str = None, department: str = None, priority: int = 3, status: str = "to do", tags: str = None):
    #     connection = get_db_connection()
    #     cursor = connection.cursor(dictionary=True)
    #     cursor.execute("SELECT primary_department, clickup_email FROM users WHERE discord_id = %s", (interaction.user.id,))
    #     user_data = cursor.fetchone()
    #     connection.close()

    #     if not user_data:
    #         await interaction.response.send_message("User data not found. Please setup the bot first.")
    #         return

    #     if not department:
    #         department = user_data['primary_department']

    #     list_id = os.getenv(f"CLICKUP_LIST_ID_{department.upper().replace(' ', '_')}")
    #     if not list_id:
    #         await interaction.response.send_message("Invalid department selected.")
    #         return

    #     user_timezone = user_data['timezone']
    #     clickup_email = user_data['clickup_email']

    #     due_date_unix = convert_to_unix(date, time, user_timezone) if time and date else None

    #     task_name = f"Task for {department} on {date} at {time}" if time and date else f"Task for {department}"
    #     task_description = f"This task is assigned to {clickup_email}."

    #     url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
    #     headers = self.get_clickup_headers()
    #     payload = {
    #         "name": task_name,
    #         "description": task_description,
    #         "due_date": due_date_unix,
    #         "assignees": [clickup_email],
    #         "priority": priority,
    #         "status": status,
    #         "tags": tags.split(",") if tags else []
    #     }

    #     response = requests.post(url, headers=headers, json=payload)
    #     if response.status_code == 200:
    #         task = response.json()
    #         await interaction.response.send_message(f"Task created successfully!\nName: {task['name']}\nID: {task['id']}\nStatus: {task['status']['status']}")
    #     else:
    #         await interaction.response.send_message("Failed to create task. Please try again later.")

    async def confirm_change(self, interaction, value, field):
        embed = discord.Embed(title="Confirm Change", description=f"Are you sure you want to change {field.replace('_', ' ').title()} to {value}?")
        view = self.ConfirmChangeView(value, field, self)
        await interaction.response.edit_message(embed=embed, view=view)

    class ConfirmChangeView(View):
        def __init__(self, value, field, cog):
            super().__init__(timeout=300)
            self.value = value
            self.field = field
            self.cog = cog

            self.add_item(Button(label="Confirm", style=discord.ButtonStyle.success, custom_id="confirm"))
            self.add_item(Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel"))

        async def interaction_check(self, interaction: discord.Interaction):
            if interaction.data['custom_id'] == "confirm":
                connection = get_db_connection()
                cursor = connection.cursor()
                cursor.execute(f"UPDATE users SET {self.field} = %s WHERE discord_id = %s", (self.value, interaction.user.id))
                connection.commit()
                connection.close()
                await interaction.response.send_message("Change confirmed and saved", ephemeral=True)
            elif interaction.data['custom_id'] == "cancel":
                await interaction.response.send_message("Change canceled", ephemeral=True)
            return True

async def setup(bot):
    await bot.add_cog(Clickup(bot))