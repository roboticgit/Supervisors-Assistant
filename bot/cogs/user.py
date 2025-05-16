import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, Button, View
from utils.helpers import get_db_connection

class TimezoneMenuView(View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        timezones = [
            "UTC", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
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


class SettingsMenuView(View):
    def __init__(self, user_data, cog):
        super().__init__(timeout=300)
        self.user_data = user_data
        self.cog = cog
        options = [
            discord.SelectOption(label="Clickup Email", value="email"),
            discord.SelectOption(label="ROBLOX Username", value="roblox_username"),
            discord.SelectOption(label="Timezone", value="timezone"),
            discord.SelectOption(label="Primary Department", value="primary_department"),
            discord.SelectOption(label="Secondary Department", value="secondary_department"),
            discord.SelectOption(label="Reminder Preferences", value="reminder_preferences"),
        ]
        self.add_item(discord.ui.Select(
            placeholder="Select a setting to change...",
            options=options,
            custom_id="settings_menu_select"
        ))
        self.add_item(Button(label="Done", style=discord.ButtonStyle.success, custom_id="done_settings"))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.data.get('component_type') == 3:  # 3 = Select menu
            selected = interaction.data['values'][0]
            if selected == "email":
                await interaction.response.send_modal(SetupModal("Email", "Enter your email", lambda i, v: self.cog.confirm_change(i, v, "clickup_email")))
            elif selected == "roblox_username":
                await interaction.response.send_modal(SetupModal("ROBLOX Username", "Enter your ROBLOX username", lambda i, v: self.cog.confirm_change(i, v, "roblox_username")))
            elif selected == "timezone":
                embed = discord.Embed(title="Timezone", description="Select your timezone:")
                await interaction.response.edit_message(embed=embed, view=TimezoneMenuView(self.cog))
            elif selected == "primary_department":
                embed = discord.Embed(title="Primary Department", description="Select your primary department:")
                await interaction.response.edit_message(embed=embed, view=DepartmentMenuView("primary_department", self.cog))
            elif selected == "secondary_department":
                embed = discord.Embed(title="Secondary Department", description="Select your secondary department:")
                await interaction.response.edit_message(embed=embed, view=DepartmentMenuView("secondary_department", self.cog))
            elif selected == "reminder_preferences":
                embed = discord.Embed(title="Reminder Preferences", description="Select your reminder preferences:")
                await interaction.response.edit_message(embed=embed, view=ReminderPreferencesMenuView(self.cog))
        elif interaction.data.get('custom_id') == "done_settings":
            # Fetch updated user data
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE discord_id = %s", (interaction.user.id,))
            user_data = cursor.fetchone()
            connection.close()

            # Create a green embed with updated settings
            embed = discord.Embed(title="Settings updated successfully!", description="Here are your current settings:", color=discord.Color.green())
            embed.add_field(name="Clickup Email", value=user_data['clickup_email'], inline=True)
            embed.add_field(name="ROBLOX Username", value=user_data['roblox_username'], inline=True)
            embed.add_field(name="Timezone", value=user_data['timezone'], inline=False)
            embed.add_field(name="Primary Department", value=user_data['primary_department'], inline=True)
            embed.add_field(name="Secondary Department", value=user_data['secondary_department'], inline=True)
            embed.add_field(name="Reminder Preferences", value=user_data['reminder_preferences'], inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
        return True

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

            # Fetch updated user data
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE discord_id = %s", (interaction.user.id,))
            user_data = cursor.fetchone()
            connection.close()

            # Update the main settings embed
            embed = discord.Embed(title="Settings", description="Select a setting to change:", color=discord.Color.blue())
            embed.add_field(name="Clickup Email", value=user_data['clickup_email'], inline=True)
            embed.add_field(name="ROBLOX Username", value=user_data['roblox_username'], inline=True)
            embed.add_field(name="Timezone", value=user_data['timezone'], inline=False)
            embed.add_field(name="Primary Department", value=user_data['primary_department'], inline=True)
            embed.add_field(name="Secondary Department", value=user_data['secondary_department'], inline=True)
            embed.add_field(name="Reminder Preferences", value=user_data['reminder_preferences'], inline=False)

            await interaction.response.edit_message(embed=embed, view=SettingsMenuView(user_data, self.cog))
        elif interaction.data['custom_id'] == "cancel":
            await interaction.response.edit_message(content="Change canceled.", view=None)
        return True


class User(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="settings", description="Configure your user information and preferences.")
    async def settings(self, interaction: discord.Interaction):
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE discord_id = %s", (interaction.user.id,))
        user_data = cursor.fetchone()

        if not user_data:
            # Create a default user data structure if none exists
            user_data = {
                'clickup_email': 'Not set',
                'roblox_username': 'Not set',
                'timezone': 'Not set',
                'primary_department': 'Not set',
                'secondary_department': 'Not set',
                'reminder_preferences': 'Not set'
            }
            cursor.execute(
                "INSERT INTO users (discord_id, clickup_email, roblox_username, timezone, primary_department, secondary_department, reminder_preferences) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (interaction.user.id, user_data['clickup_email'], user_data['roblox_username'], user_data['timezone'],
                 user_data['primary_department'], user_data['secondary_department'], user_data['reminder_preferences'])
            )
            connection.commit()
            # Send welcome DM on first use
            try:
                embed = discord.Embed(
                    title="Thanks for using the SCR Training Assistant!",
                    description="""Welcome! Please use `/settings` to configure your account information. More information about the bot can be found below:

This bot has several main functions at this time:
- It will send you reminders for your trainings (toggleable)
- It will send you reminders to complete your quota (toggleable)
- You can check your quota with a command
- You can automatically create a training request with a command

Additionally, a list of commands can be found below:
> 1. `/settings` - Configure your account information.
> 2. `/check` - Check if you've completed this month's quota, or see how far along you are.
> 3. `/create` - Create a new training request in a department (defaults to your primary department), and automatically ensures that timeslot is availible.

Note: This bot is still in development, and some features may not work as expected. If you encounter any issues, please report them to the bot administrator (Robotic_dony2468). Additonally, note that you'll get developer messages every so often as I push out updates. Thanks again!""",
                    color=discord.Color.purple()
                )
                await interaction.user.send(embed=embed)
            except Exception:
                pass  # Ignore if DMs are closed

        connection.close()

        async def main_settings_embed():
            embed = discord.Embed(title="Settings", description="Select a setting to change:", color=discord.Color.blue())
            embed.add_field(name="Clickup Email", value=user_data['clickup_email'], inline=True)
            embed.add_field(name="ROBLOX Username", value=user_data['roblox_username'], inline=True)
            embed.add_field(name="Timezone", value=user_data['timezone'], inline=False)
            embed.add_field(name="Primary Department", value=user_data['primary_department'], inline=True)
            embed.add_field(name="Secondary Department", value=user_data['secondary_department'], inline=True)
            embed.add_field(name="Reminder Preferences", value=user_data['reminder_preferences'], inline=False)
            view = SettingsMenuView(user_data, self)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        await main_settings_embed()

    async def confirm_change(self, interaction, value, field):
        embed = discord.Embed(title="Confirm Change", description=f"Are you sure you want to change {field.replace('_', ' ').title()} to {value}?", color=discord.Color.red())
        view = ConfirmChangeView(value, field, self)
        await interaction.response.edit_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(User(bot))
