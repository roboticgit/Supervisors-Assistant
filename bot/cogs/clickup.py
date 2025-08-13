import discord
from discord.ext import commands
from discord import app_commands
import requests
import os
from dotenv import load_dotenv
from bot.utils.helpers import get_db_connection
import datetime
from datetime import timezone, timedelta
import pytz
import re

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
        # --- Send initial message (not ephemeral, no embed) ---
        await interaction.response.send_message(
            content="Processing your request...",
            ephemeral=False
        )
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
            await interaction.response.send_message("User data is missing or incomplete! Please run `/settings` and fill out all of the fields", ephemeral=True)
            return

        roblox_username = user_data['roblox_username']
        clickup_email = user_data['clickup_email']
        departments = [user_data['primary_department']]
        if user_data['secondary_department']:
            departments.append(user_data['secondary_department'])

        now = datetime.datetime.now(timezone.utc)
        first_of_month = datetime.datetime(year=now.year, month=now.month, day=1, tzinfo=timezone.utc)
        first_of_month_unix_ms = int(first_of_month.timestamp() * 1000)
        # Calculate last moment of the month (11:59:59.999 PM UTC)
        if now.month == 12:
            next_month = datetime.datetime(year=now.year+1, month=1, day=1, tzinfo=timezone.utc)
        else:
            next_month = datetime.datetime(year=now.year, month=now.month+1, day=1, tzinfo=timezone.utc)
        last_of_month = next_month - timedelta(milliseconds=1)
        last_of_month_unix_ms = int(last_of_month.timestamp() * 1000)

        # --- Prepare status explanation embed (for followup, ephemeral) ---
        intro_embed = discord.Embed(
            title=f"Quota Status Explanation",
            description=(
                "**PASSING:** You have completed enough trainings to meet the quota.\n"
                "**ON-TRACK:** You have not completed enough, but if you attend all your scheduled trainings, you will meet the quota.\n"
                "**FAILING:** You have not completed nor scheduled enough to meet the quota.\n\n"
                "> **Note:** Only trainings where you are an assignee and the due date is after the start of the month are counted. "
            ),
            color=discord.Color.blue()
        )

        # --- After API returns, edit the original message to show the API result (remove intro embed logic) ---
        for department in departments:
            if department == "None":
                continue
            list_id = self.clickup_list_ids.get(department)
            if not list_id:
                await interaction.edit_original_response(content=f"Could not find {department}'s Clickup list. Please check your settings and ensure your primary department is valid.")
                continue
            headers = self.get_clickup_headers()

            # --- Gather all tasks for this department ---
            concluded_username = 0
            concluded_total = 0
            scheduled_username = 0
            scheduled_total = 0
            scheduled_trainings_username = []
            scheduled_trainings_total = []
            concluded_trainings_username = []
            concluded_trainings_total = []

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
                        f"due_date_lt={last_of_month_unix_ms}&"
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
                                concluded_total += 1
                                concluded_trainings_total.append(task)
                                if roblox_username in task['name']:
                                    concluded_username += 1
                                    concluded_trainings_username.append(task)
                    if data.get("last_page", False):
                        break
                    page += 1

            # Scheduled (archived false)
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
                    f"due_date_lt={last_of_month_unix_ms}&"
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
                        scheduled_total += 1
                        scheduled_trainings_total.append(task)
                        if roblox_username in task['name']:
                            scheduled_username += 1
                            scheduled_trainings_username.append(task)
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

            department_emojis = {
                "Driving Department": "<:QD:1379240904887636128>",
                "Dispatching Department": "<:DS:1379240994226307072>",
                "Guarding Department": "<:GD:1379241061951733843>",
                "Signalling Department": "<:SG:1379241116892795010>"
            }
            dept_emoji = department_emojis.get(department, "")
            # --- Username-in-title Embed ---
            host_emoji = '<:host:1379234412096393337>'
            fail_emoji = '<:fail:1373358894444707963>'
            ontrack_emoji = '<:ontrack:1373358874136154293>'
            pass_emoji = '<:pass:1373358844499066991>'
            username_embed = discord.Embed(
                title=f"{dept_emoji} {department}: Just Hosts",
                color=embed_color
            )
            username_embed.add_field(
                name="Completed Hosts",
                value=f"{str(concluded_username)} Hosts",
                inline=False
            )
            # Scheduled with readable date/time and links
            if scheduled_trainings_username:
                user_tz = user_data.get('timezone', 'UTC')
                try:
                    tz = pytz.timezone(user_tz)
                except Exception:
                    tz = pytz.UTC
                scheduled_list = []
                for t in scheduled_trainings_username:
                    due = t.get('due_date')
                    url = t.get('url')
                    if due:
                        dt_utc = datetime.datetime.utcfromtimestamp(int(due)/1000).replace(tzinfo=pytz.UTC)
                        dt_local = dt_utc.astimezone(tz)
                        date_str = dt_local.strftime('%A, %B %d, %Y at %I:%M %p')
                    else:
                        date_str = 'No date'
                    if url:
                        date_str = f"[{date_str}]({url})"
                    scheduled_list.append(date_str)
                scheduled_value = "\n".join(scheduled_list)
            else:
                scheduled_value = "None"
            username_embed.add_field(
                name="Scheduled Hosts",
                value=scheduled_value,
                inline=False
            )
            username_embed.add_field(
                name="All in All (Completed + Scheduled)",
                value=f"{str(concluded_username + scheduled_username)}/2 (" +
                      f"{round((concluded_username + scheduled_username) / 2 * 100)}% of quota)",
                inline=False
            )
            # Quota logic for username-in-title
            host_required = 3 if department == "Driving Department" else 2
            if concluded_username >= host_required:
                status = f"PASSING {pass_emoji}"
            elif concluded_username + scheduled_username >= host_required:
                status = f"ON-TRACK {ontrack_emoji}"
            else:
                status = f"FAILING {fail_emoji}"
            username_embed.add_field(name="Quota Status", value=status, inline=False)
            username_embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1379234412096393337.png")

            # --- Total Trainings Embed ---
            cohost_emoji = '<:cohost:1379234447911817439>'
            total_embed = discord.Embed(
                title=f"{dept_emoji} {department}: All Trainings",
                color=embed_color
            )
            total_embed.add_field(
                name="Completed Trainings",
                value=f"{str(concluded_total)} Trainings",
                inline=False
            )
            # Scheduled with readable date/time and links
            if scheduled_trainings_total:
                user_tz = user_data.get('timezone', 'UTC')
                try:
                    tz = pytz.timezone(user_tz)
                except Exception:
                    tz = pytz.UTC
                scheduled_list = []
                for t in scheduled_trainings_total:
                    due = t.get('due_date')
                    url = t.get('url')
                    if due:
                        dt_utc = datetime.datetime.utcfromtimestamp(int(due)/1000).replace(tzinfo=pytz.UTC)
                        dt_local = dt_utc.astimezone(tz)
                        date_str = dt_local.strftime('%A, %B %d, %Y at %I:%M %p')
                    else:
                        date_str = 'No date'
                    if url:
                        date_str = f"[{date_str}]({url})"
                    scheduled_list.append(date_str)
                scheduled_value = "\n".join(scheduled_list)
            else:
                scheduled_value = "None"
            total_embed.add_field(
                name="Scheduled Trainings",
                value=scheduled_value,
                inline=False
            )
            total_embed.add_field(
                name="All in All (Completed + Scheduled)",
                value=f"{str(concluded_total + scheduled_total)}/8 (" +
                      f"{round((concluded_total + scheduled_total) / 8 * 100)}% of quota)",
                inline=False
            )
            # Quota logic for total
            if concluded_total >= 8:
                status = f"PASSING {pass_emoji}"
            elif concluded_total + scheduled_total >= 8:
                status = f"ON-TRACK {ontrack_emoji}"
            else:
                status = f"FAILING {fail_emoji}"
            total_embed.add_field(name="Quota Status", value=status, inline=False)
            total_embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1379234447911817439.png")

            # Only send the API result as the main message (edit original response)
            if department == departments[0]:
                await interaction.edit_original_response(content=None, embeds=[username_embed, total_embed])
            else:
                await interaction.followup.send(embeds=[username_embed, total_embed], ephemeral=False)

        # Send the status explanation as a hidden (ephemeral) followup
        await interaction.followup.send(embed=intro_embed, ephemeral=True)

    @app_commands.command(name="create", description="Request a new training task in ClickUp.")
    @app_commands.describe(
        date="Date in YYYY-MM-DD format (e.g. 2025-05-16) in **YOUR TIMEZONE**",
        time="Time in 24-hour HH:MM format (e.g. 14:30 for 2:30 PM) in **YOUR TIMEZONE**",
        department="Defaults to your primary department"
    )
    async def create(self, interaction: discord.Interaction, date: str, time: str, department: str = None):
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT primary_department, clickup_email, timezone, roblox_username FROM users WHERE discord_id = %s", (interaction.user.id,))
        user_data = cursor.fetchone()
        connection.close()

        # Immediately acknowledge the interaction
        await interaction.response.send_message("Sorry! This command is receiving an upgrade to be more convenient, along with a new command. Please manually create your training until then.", ephemeral=True)
        return

        # Return early if any required field is 'Not set'
        required_fields = ['primary_department', 'clickup_email', 'timezone', 'roblox_username']
        if not user_data or any(user_data.get(field) == 'Not set' for field in required_fields):
            await interaction.edit_original_response(content="User data is missing or incomplete! Please run `/settings` and fill out all of the fields.")
            return

        if not department:
            department = user_data['primary_department']
        list_id = self.clickup_list_ids.get(department)
        if not list_id:
            await interaction.edit_original_response(content="Invalid department selected.")
            return

        # Get template ID from .env
        template_env_key = f"CLICKUP_TEMPLATE_ID_{department.upper().replace(' ', '_')}"
        template_id = os.getenv(template_env_key)
        if not template_id:
            await interaction.edit_original_response(content="Cannot find card template.")
            return

        user_timezone = user_data['timezone']
        clickup_email = user_data['clickup_email']
        roblox_username = user_data['roblox_username']

        # Convert user input date/time to BST/GMT (Europe/London)
        try:
            user_tz = pytz.timezone(user_timezone)
            naive_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            local_dt = user_tz.localize(naive_dt)
            london_tz = pytz.timezone("Europe/London")
            london_dt = local_dt.astimezone(london_tz)
            # Check if the requested date is more than 19 days in advance
            now_utc = datetime.now(pytz.UTC)
            if (london_dt - now_utc).days > 19:
                await interaction.edit_original_response(content="You cannot request a training more than 18 days in advance.")
                return
            unix_central = int(london_dt.timestamp() * 1000)
            unix_before = int((london_dt - timedelta(hours=2, minutes=30)).timestamp() * 1000)
            unix_after = int((london_dt + timedelta(hours=2, minutes=30)).timestamp() * 1000)
            # For display/creation
            day_of_week = london_dt.strftime('%A')
            day = london_dt.strftime('%d')
            month = london_dt.strftime('%m')
            year = london_dt.strftime('%Y')
            hour_min = london_dt.strftime('%H:%M')
            # Determine if BST or GMT
            is_dst = bool(london_dt.dst())
            tz_label = 'BST' if is_dst else 'GMT'
        except Exception as e:
            await interaction.edit_original_response(content=f"Failed to parse date/time or timezone: {e}")
            return

        # Query for overlapping tasks in the 5-hour window
        url_check = (
            f"https://api.clickup.com/api/v2/list/{list_id}/task?"
            f"archived=false&"
            f"statuses=request&"
            f"statuses=pending%20staff&"
            f"statuses=scheduled&"
            f"due_date_gt={unix_before}&"
            f"due_date_lt={unix_after}"
        )
        headers = self.get_clickup_headers()
        response = requests.get(url_check, headers=headers)
        if response.status_code != 200:
            await interaction.edit_original_response(content="Failed to check ClickUp for overlapping tasks.")
            return
        data = response.json()
        tasks = data.get("tasks", [])
        if tasks:
            embed = discord.Embed(title="Overlapping Training(s) Found", color=discord.Color.red())
            for task in tasks:
                name = task.get('name', 'No Name')
                due = task.get('due_date')
                if due:
                    dt = datetime.datetime.utcfromtimestamp(int(due)/1000).replace(tzinfo=pytz.UTC).astimezone(london_tz)
                    due_str = dt.strftime('%A, %B %d, %Y at %H:%M')
                else:
                    due_str = 'No date'
                url = task.get('url')
                if url:
                    name = f"[{name}]({url})"
                embed.add_field(name="Conflicting training:", value=f"Scheduled for: {due_str}", inline=False)
            await interaction.edit_original_response(content=None, embed=embed)
            return
        training_name = f"{day}/{month}/{year} - {day_of_week} - {hour_min} {tz_label} - {roblox_username}"
        url_create = f"https://api.clickup.com/api/v2/list/{list_id}/taskTemplate/{template_id}"
        payload = { "name": training_name }
        headers_create = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": self.clickup_api_token
        }
        create_resp = requests.post(url_create, headers=headers_create, json=payload)
        if create_resp.status_code == 200:
            task = create_resp.json()
            task_id = task.get('id')
            if not task_id:
                await interaction.edit_original_response(content="Training created, but could not retrieve task ID.")
                return
            # Set due date and assign user by email (if possible)
            # 1. Set due date
            url_update = f"https://api.clickup.com/api/v2/task/{task_id}"
            payload_update = {"due_date": str(unix_central)}
            requests.put(url_update, headers=headers_create, json=payload_update)
            # 2. Assign user by email (requires user id)
            # Fetch ClickUp user id by email
            user_id = None
            workspace_id = os.getenv('CLICKUP_WORKSPACE_ID')
            if workspace_id and clickup_email:
                user_search_url = f"https://api.clickup.com/api/v2/team/{workspace_id}/user"
                user_search_resp = requests.get(user_search_url, headers=headers_create)
                if user_search_resp.status_code == 200:
                    users_data = user_search_resp.json().get('users', [])
                    for u in users_data:
                        if u.get('email', '').lower() == clickup_email.lower():
                            user_id = u.get('id')
                            break
            if user_id:
                payload_update = {"assignees": {"add": [user_id]}}
                requests.put(url_update, headers=headers_create, json=payload_update)
            # Step 3: Fetch the markdown description
            url_get = f"https://api.clickup.com/api/v2/task/{task_id}?include_markdown_description=true"
            get_resp = requests.get(url_get, headers=headers)
            if get_resp.status_code != 200:
                await interaction.edit_original_response(content="Training created, but failed to insert your ROBLOX username in description under Assessment Track A. Everything else is fine.")
                return
            task_data = get_resp.json()
            markdown = task_data.get('markdown_description') or task_data.get('description')
            if not markdown:
                await interaction.edit_original_response(content="Training created, but no description found to update with your ROBLOX username under Assessment Track A. Everything else is fine.")
                return
            # Step 4: Insert ROBLOX username after 'Assessor: '
            pattern = r'(#### Assessment Track A\\s+Assessor: )(.*)'
            replacement = r'\\1' + roblox_username
            new_markdown, count = re.subn(pattern, replacement, markdown, count=1, flags=re.MULTILINE)
            if count == 0:
                # Fallback: try to find 'Assessor:' line and append username
                new_markdown = markdown.replace('Assessor: ', f'Assessor: {roblox_username}', 1)
            # Step 5: Update the description
            payload_update = { "markdown_content": new_markdown }
            update_resp = requests.put(url_update, headers=headers_create, json=payload_update)
            if update_resp.status_code == 200:
                await interaction.edit_original_response(content=f"Training created successfully!\n{training_name}\nAssessor set to: {roblox_username}")
            else:
                await interaction.edit_original_response(content=f"Training created, but failed to update description. ClickUp API response: {update_resp.text}")
        else:
            await interaction.edit_original_response(content=f"All your information was valid, but clickup failed to create training. Loser's (ClickUp's) API response: {create_resp.text}")

async def setup(bot):
    await bot.add_cog(Clickup(bot))