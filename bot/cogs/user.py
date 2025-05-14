import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, Button, View
from utils.helpers import get_db_connection
from .clickup import TimezoneMenuView, DepartmentMenuView, ReminderPreferencesMenuView, SetupModal


class SettingsMenuView(View):
    def __init__(self, user_data, cog):
        super().__init__(timeout=300)
        self.user_data = user_data
        self.cog = cog

        self.add_item(Button(label="Email", style=discord.ButtonStyle.primary, custom_id="email"))
        self.add_item(Button(label="ROBLOX Username", style=discord.ButtonStyle.primary, custom_id="roblox_username"))
        self.add_item(Button(label="Timezone", style=discord.ButtonStyle.primary, custom_id="timezone"))
        self.add_item(Button(label="Primary Department", style=discord.ButtonStyle.primary, custom_id="primary_department"))
        self.add_item(Button(label="Secondary Department", style=discord.ButtonStyle.primary, custom_id="secondary_department"))
        self.add_item(Button(label="Reminder Preferences", style=discord.ButtonStyle.primary, custom_id="reminder_preferences"))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.data['custom_id'] == "email":
            await interaction.response.send_modal(SetupModal("Email", "Enter your email", lambda i, v: self.cog.confirm_change(i, v, "clickup_email")))
        elif interaction.data['custom_id'] == "roblox_username":
            await interaction.response.send_modal(SetupModal("ROBLOX Username", "Enter your ROBLOX username", lambda i, v: self.cog.confirm_change(i, v, "roblox_username")))
        elif interaction.data['custom_id'] == "timezone":
            embed = discord.Embed(
                title="Timezone",
                description="Select your timezone:",
            )
            await interaction.response.edit_message(embed=embed, view=TimezoneMenuView(self.cog))
        elif interaction.data['custom_id'] == "primary_department":
            embed = discord.Embed(
                title="Primary Department",
                description="Select your primary department:",
            )
            await interaction.response.edit_message(embed=embed, view=DepartmentMenuView("primary_department", self.cog))
        elif interaction.data['custom_id'] == "secondary_department":
            embed = discord.Embed(
                title="Secondary Department",
                description="Select your secondary department:",
            )
            await interaction.response.edit_message(embed=embed, view=DepartmentMenuView("secondary_department", self.cog))
        elif interaction.data['custom_id'] == "reminder_preferences":
            embed = discord.Embed(
                title="Reminder Preferences",
                description="Select your reminder preferences:",
            )
            await interaction.response.edit_message(embed=embed, view=ReminderPreferencesMenuView(self.cog))
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
            embed = discord.Embed(title="Settings", description="Select a setting to change:")
            embed.add_field(name="Email", value=user_data['clickup_email'], inline=True)
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

        connection.close()

        async def main_settings_embed():
            embed = discord.Embed(title="Settings", description="Select a setting to change:")
            embed.add_field(name="Email", value=user_data['clickup_email'], inline=False)
            embed.add_field(name="ROBLOX Username", value=user_data['roblox_username'], inline=True)
            embed.add_field(name="Timezone", value=user_data['timezone'], inline=True)
            embed.add_field(name="Primary", value=user_data['primary_department'], inline=False)
            embed.add_field(name="Secondary", value=user_data['secondary_department'], inline=True)
            embed.add_field(name="Reminder Preferences", value={user_data['reminder_preferences']}, inline=False)
            view = SettingsMenuView(user_data, self)
            await interaction.response.send_message(embed=embed, view=view)

        await main_settings_embed()

    async def confirm_change(self, interaction, value, field):
        embed = discord.Embed(title="Confirm Change", description=f"Are you sure you want to change {field.replace('_', ' ').title()} to {value}?")
        view = ConfirmChangeView(value, field, self)
        await interaction.response.edit_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(User(bot))
