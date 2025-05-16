import discord
from discord.ext import commands, tasks
from discord import app_commands
import mysql.connector
from datetime import datetime, timedelta
import pytz
import os
import requests

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_tasks.start()

    def cog_unload(self):
        self.check_tasks.cancel()

    def get_db_connection(self):
        return mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )

    @tasks.loop(minutes=10)
    async def check_tasks(self):
        now = datetime.now(pytz.timezone('EST'))
        headers = {
            "Authorization": os.getenv('CLICKUP_API_TOKEN'),
            "Content-Type": "application/json"
        }

        # Iterate through departments and fetch tasks
        departments = [
            "Driving Department",
            "Dispatching Department",
            "Guarding Department",
            "Signalling Department"
        ]

        for department in departments:
            list_id = os.getenv(f"CLICKUP_LIST_ID_{department.upper().replace(' ', '_')}")
            if not list_id:
                continue

            url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
            params = {
                "due_date_gt": int(now.timestamp() * 1000),
                "due_date_lt": int((now + timedelta(days=1)).timestamp() * 1000)
            }

            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                continue

            tasks = response.json().get("tasks", [])
            for task in tasks:
                assignees = [assignee['email'] for assignee in task.get('assignees', [])]
                if os.getenv('CLICKUP_USER_EMAIL') in assignees:
                    due_date = datetime.fromtimestamp(task['due_date'] / 1000, pytz.timezone('EST'))
                    time_left = (due_date - now).total_seconds()

                    if time_left <= 10 * 60:
                        interval = "10 minutes"
                    elif time_left <= 30 * 60:
                        interval = "30 minutes"
                    elif time_left <= 1 * 60 * 60:
                        interval = "1 hour"
                    elif time_left <= 6 * 60 * 60:
                        interval = "6 hours"
                    elif time_left <= 24 * 60 * 60:
                        interval = "24 hours"
                    else:
                        continue

                    user = await self.bot.fetch_user(task['creator']['id'])
                    await user.send(f"Reminder: Task '{task['name']}' is due in {interval}.")

    # @app_commands.command(name="set_reminder", description="Set a reminder for a task.")
    async def set_reminder(self, interaction: discord.Interaction, task_id: str):
        connection = self.get_db_connection()
        cursor = connection.cursor()

        # Example query to associate a reminder with a task
        cursor.execute("INSERT INTO reminders (discord_id, task_id) VALUES (%s, %s)", (
            interaction.user.id, task_id
        ))
        connection.commit()
        connection.close()

        embed = discord.Embed(title="Reminder Set", description="Your reminder has been set successfully!", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    # Handle errors or missing information
    async def handle_error(interaction: discord.Interaction, error_message: str):
        await interaction.response.send_message(error_message)

async def setup(bot):
    await bot.add_cog(Reminders(bot))