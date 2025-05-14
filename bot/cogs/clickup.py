import discord
from discord.ext import commands
from discord import app_commands
import requests
import os
from dotenv import load_dotenv
from utils.helpers import get_db_connection, convert_to_unix
import asyncio
from discord.ui import Modal, Button, View

load_dotenv()

class TimezoneMenuView(View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        timezones = ["UTC", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
"America/Toronto", "America/Vancouver", "America/Sao_Paulo", "Europe/London", "Europe/Paris", "Europe/Berlin",
"Europe/Moscow",  "Europe/Madrid", "Europe/Rome", "Asia/Tokyo", "Asia/Shanghai", "Asia/Kolkata", "Asia/Singapore", 
"Asia/Dubai", "Asia/Seoul", "Asia/Hong_Kong", "Australia/Sydney", "Africa/Johannesburg", "Africa/Cairo","Pacific/Auckland"
]
        self.add_item(discord.ui.Select(
            placeholder="Select your timezone",
            options=[discord.SelectOption(label=tz, value=tz) for tz in timezones],
            custom_id="timezone_select"
        ))

    async def interaction_check(self, interaction: discord.Interaction):
        selected_timezone = interaction.data['values'][0]
        await self.cog.confirm_change(interaction, selected_timezone, "timezone")
        return True

class DepartmentMenuView(View):
    def __init__(self, field, cog):
        super().__init__(timeout=300)
        self.field = field
        self.cog = cog
        departments = [
            {"label": "Driving Department", "emoji": "<:QD:1323990343095681095>"},
            {"label": "Dispatching Department", "emoji": "<:DS:1323990336950767616>"},
            {"label": "Guarding Department", "emoji": "<:GD:1323990339031269496>"},
            {"label": "Signalling Department", "emoji": "<:SG:1323990431809142835>"},
            {"label": "None", "emoji": "❌"} 
        ]
        self.add_item(discord.ui.Select(
            placeholder="Select your department",
            options=[discord.SelectOption(label=dept["label"], value=dept["label"], emoji=dept["emoji"]) for dept in departments],
            custom_id="department_select"
        ))

    async def interaction_check(self, interaction: discord.Interaction):
        selected_department = interaction.data['values'][0]
        await self.cog.confirm_change(interaction, selected_department, self.field)
        return True

class ReminderPreferencesMenuView(View):
    preferences = [
        "No reminders",
        "Quota reminders",
        "Training reminders",
        "Quota and Training reminders"
    ]

    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        self.add_item(discord.ui.Select(
            placeholder="Select your reminder preference",
            options=[discord.SelectOption(label=name, value=name) for name in self.preferences],
            custom_id="reminder_preferences_select"
        ))

    async def interaction_check(self, interaction: discord.Interaction):
        selected_preference = interaction.data['values'][0]
        await self.cog.confirm_change(interaction, selected_preference, "reminder_preferences")
        return True

class SetupModal(Modal):
    def __init__(self, title, placeholder, callback):
        super().__init__(title=title)
        self.callback = callback
        self.add_item(discord.ui.TextInput(label=placeholder))

    async def on_submit(self, interaction: discord.Interaction):
        await self.callback(interaction, self.children[0].value)

class Clickup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.clickup_api_token = os.getenv('CLICKUP_API_TOKEN')
        self.clickup_space_ids = {
            "Driving Department": os.getenv('CLICKUP_SPACE_ID_DRIVING_DEPARTMENT'),
            "Dispatching Department": os.getenv('CLICKUP_SPACE_ID_DISPATCHING_DEPARTMENT'),
            "Guarding Department": os.getenv('CLICKUP_SPACE_ID_GUARDING_DEPARTMENT'),
            "Signalling Department": os.getenv('CLICKUP_SPACE_ID_SIGNALLING_DEPARTMENT')
        }

    def get_clickup_headers(self):
        return {
            "Authorization": self.clickup_api_token,
            "Content-Type": "application/json"
        }

    @app_commands.command(name="check", description="Check if you've reached quota.")
    async def check(self, interaction: discord.Interaction):
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT primary_department, secondary_department, roblox_username, clickup_email FROM users WHERE discord_id = %s", (interaction.user.id,))
        user_data = cursor.fetchone()
        connection.close()

        if not user_data:
            await interaction.response.send_message("User data not found. Please setup the bot first.", ephemeral=True)
            return

        roblox_username = user_data['roblox_username']
        clickup_email = user_data['clickup_email']
        departments = [user_data['primary_department']]
        if user_data['secondary_department']:
            departments.append(user_data['secondary_department'])

        embeds = []
        for department in departments:
            list_id = os.getenv(f"CLICKUP_LIST_ID_{department.upper().replace(' ', '_')}")
            if not list_id:
                await interaction.response.send_message(f"No space ID found for {department}. Please check your configuration.", ephemeral=True)
                continue

            url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
            headers = self.get_clickup_headers()
            params = {"status": "CONCLUDED"}

            page = 0
            total_tasks = 0
            username_tasks = 0

            while True:
                response = requests.get(url, headers=headers, params={**params, "page": page})
                if response.status_code != 200:
                    break

                tasks = response.json().get("tasks", [])
                if not tasks:
                    break

                for task in tasks:
                    assignees = [assignee['email'] for assignee in task.get('assignees', [])]
                    if clickup_email in assignees:
                        total_tasks += 1
                        if roblox_username in task['name']:
                            username_tasks += 1

                page += 1

            department_colors = {
                "Driving Department": 0xE43D2E,  # Red
                "Dispatching Department": 0xF98E2C,  # Orange
                "Guarding Department": 0xF2B322,  # Yellow
                "Signalling Department": 0x00B18B  # Green
            }
            embed_color = department_colors.get(department, 0x000000)  # Default to black if not found

            embed = discord.Embed(
                title=f"{department} Department Summary",
                description=f"Summary of tasks for the {department} department.",
                color=embed_color
            )

            if total_tasks > 0:
                embed.add_field(name="Total Tasks", value=str(total_tasks), inline=False)
                embed.add_field(name="Tasks with Username", value=str(username_tasks), inline=False)
            else:
                embed.description = "No trainings completed this month."

            embeds.append(embed)

        for embed in embeds:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="create", description="Create a training task in ClickUp.")
    async def create(self, interaction: discord.Interaction, date: str = None, time: str = None, department: str = None, priority: int = 3, status: str = "to do", tags: str = None):
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT primary_department, clickup_email FROM users WHERE discord_id = %s", (interaction.user.id,))
        user_data = cursor.fetchone()
        connection.close()

        if not user_data:
            await interaction.response.send_message("User data not found. Please setup the bot first.", ephemeral=True)
            return

        if not department:
            department = user_data['primary_department']

        list_id = os.getenv(f"CLICKUP_LIST_ID_{department.upper().replace(' ', '_')}")
        if not list_id:
            await interaction.response.send_message("Invalid department selected.", ephemeral=True)
            return

        user_timezone = user_data['timezone']
        clickup_email = user_data['clickup_email']

        due_date_unix = convert_to_unix(date, time, user_timezone) if time and date else None

        task_name = f"Task for {department} on {date} at {time}" if time and date else f"Task for {department}"
        task_description = f"This task is assigned to {clickup_email}."

        url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
        headers = self.get_clickup_headers()
        payload = {
            "name": task_name,
            "description": task_description,
            "due_date": due_date_unix,
            "assignees": [clickup_email],
            "priority": priority,
            "status": status,
            "tags": tags.split(",") if tags else []
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            task = response.json()
            await interaction.response.send_message(f"Task created successfully!\nName: {task['name']}\nID: {task['id']}\nStatus: {task['status']['status']}")
        else:
            await interaction.response.send_message("Failed to create task. Please try again later.", ephemeral=True)

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
                await interaction.response.send_message("Change confirmed and saved.")
            elif interaction.data['custom_id'] == "cancel":
                await interaction.response.send_message("Change canceled.")
            return True

async def setup(bot):
    await bot.add_cog(Clickup(bot))