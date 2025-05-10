import discord
from discord.ext import commands
from discord import app_commands
import requests
import os
from dotenv import load_dotenv
from utils.helpers import get_db_connection, convert_to_unix

load_dotenv()

class Clickup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.clickup_api_token = os.getenv('CLICKUP_API_TOKEN')
        self.workspace_id = os.getenv('CLICKUP_WORKSPACE_ID')
        self.list_id = os.getenv('CLICKUP_LIST_ID')

    def get_clickup_headers(self):
        return {
            "Authorization": self.clickup_api_token,
            "Content-Type": "application/json"
        }

    @app_commands.command(name="search_tasks", description="Search tasks in ClickUp by assignee or description text.")
    async def search_tasks(self, interaction: discord.Interaction, query: str):
        url = f"https://api.clickup.com/api/v2/team/{self.workspace_id}/task"
        headers = self.get_clickup_headers()
        params = {"search": query}

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            tasks = response.json().get("tasks", [])
            if tasks:
                task_list = "\n".join([f"- {task['name']} (ID: {task['id']})" for task in tasks])
                await interaction.response.send_message(f"Found tasks:\n{task_list}", ephemeral=True)
            else:
                await interaction.response.send_message("No tasks found.", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to search tasks. Please try again later.", ephemeral=True)

    @app_commands.command(name="create_task", description="Create a new task in ClickUp.")
    async def create_task(self, interaction: discord.Interaction, department: str, time: str, date: str):
        # Fetch user timezone and ClickUp email from the database
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT timezone, clickup_email FROM users WHERE discord_id = %s", (interaction.user.id,))
        user_data = cursor.fetchone()
        connection.close()

        if not user_data:
            await interaction.response.send_message("User data not found. Please setup the bot first.", ephemeral=True)
            return

        user_timezone = user_data['timezone']
        clickup_email = user_data['clickup_email']

        # Convert time and date to UNIX timestamp in EST timezone
        due_date_unix = convert_to_unix(date, time, user_timezone)

        # Format task name and description
        task_name = f"Task for {department} on {date} at {time}"  # Example format, replace with your own
        task_description = f"This task is assigned to {clickup_email}."  # Example format, replace with your own

        # Prepare API request
        url = f"https://api.clickup.com/api/v2/list/{self.list_id}/task"
        headers = self.get_clickup_headers()
        payload = {
            "name": task_name,
            "description": task_description,
            "due_date": due_date_unix,
            "assignees": [clickup_email],
            "tags": [os.getenv('CLICKUP_TAG_ID')]
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            await interaction.response.send_message("Task created successfully!", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to create task. Please try again later.", ephemeral=True)

    @app_commands.command(name="setup", description="Set up your user preferences interactively.")
    async def setup_user(self, interaction: discord.Interaction):
        user_data = {}

        async def get_email(interaction, value):
            user_data['email'] = value
            await interaction.response.send_modal(SetupModal("ROBLOX Username", "Enter your ROBLOX username", get_roblox_username))

        async def get_roblox_username(interaction, value):
            user_data['roblox_username'] = value
            await interaction.response.send_modal(SetupModal("Timezone", "Enter your timezone (e.g., EST, PST)", get_timezone))

        async def get_timezone(interaction, value):
            user_data['timezone'] = value
            embed = discord.Embed(title="Reminder Preferences", description="Choose your reminder style:")
            embed.add_field(name="Options", value="1: Style A\n2: Style B\n3: Style C\n4: Style D")
            await interaction.response.send_message(embed=embed, view=SetupView(["1", "2", "3", "4"], get_reminder_preferences))

        async def get_reminder_preferences(interaction, value):
            user_data['reminder_preferences'] = int(value)
            embed = discord.Embed(title="Confirm Your Data", description="Please confirm your setup details:")
            embed.add_field(name="Email", value=user_data['email'], inline=False)
            embed.add_field(name="ROBLOX Username", value=user_data['roblox_username'], inline=False)
            embed.add_field(name="Timezone", value=user_data['timezone'], inline=False)
            embed.add_field(name="Reminder Preferences", value=user_data['reminder_preferences'], inline=False)
            view = View()
            view.add_item(Button(label="Confirm", style=discord.ButtonStyle.success, custom_id="confirm"))
            view.add_item(Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel"))

            async def on_confirm(interaction):
                connection = get_db_connection()
                cursor = connection.cursor()
                cursor.execute(
                    "REPLACE INTO users (discord_id, clickup_email, roblox_username, timezone, reminder_preferences) VALUES (%s, %s, %s, %s, %s)",
                    (interaction.user.id, user_data['email'], user_data['roblox_username'], user_data['timezone'], user_data['reminder_preferences'])
                )
                connection.commit()
                connection.close()
                await interaction.response.send_message(embed=discord.Embed(title="Success", description="Your preferences have been saved!", color=discord.Color.green()))

            async def on_cancel(interaction):
                await interaction.response.send_message(embed=discord.Embed(title="Cancelled", description="Setup process was cancelled.", color=discord.Color.red()))

            view.children[0].callback = on_confirm
            view.children[1].callback = on_cancel

            await interaction.response.send_message(embed=embed, view=view)

        await interaction.response.send_modal(SetupModal("Email", "Enter your email", get_email))

async def setup(bot):
    await bot.add_cog(Clickup(bot))

import asyncio
from discord.ui import Modal, Button, View

class SetupModal(Modal):
    def __init__(self, title, placeholder, callback):
        super().__init__(title=title)
        self.callback = callback
        self.add_item(discord.ui.InputText(label=placeholder))

    async def on_submit(self, interaction: discord.Interaction):
        await self.callback(interaction, self.children[0].value)

class SetupView(View):
    def __init__(self, options, callback):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.callback = callback
        for option in options:
            self.add_item(Button(label=option, style=discord.ButtonStyle.primary, custom_id=option))

    async def interaction_check(self, interaction: discord.Interaction):
        await self.callback(interaction, interaction.data['custom_id'])
        return True