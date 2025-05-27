import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, Button, View
from utils.helpers import get_db_connection
import os

# Add a config variable for the approval channel
APPROVAL_CHANNEL_ID = int(os.getenv('SETTINGS_APPROVAL_CHANNEL_ID', '0'))  # Set this in your .env

# In-memory store for pending changes: {user_id: {field: value, ...}}
pending_settings_changes = {}

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
        user_id = interaction.user.id
        if user_id not in pending_settings_changes:
            pending_settings_changes[user_id] = {}
        pending_settings_changes[user_id]["timezone"] = selected_timezone
        # Return to main settings embed with orange color
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE discord_id = %s", (user_id,))
        user_data = cursor.fetchone()
        connection.close()
        pending = pending_settings_changes.get(user_id, {})
        display_data = user_data.copy() if user_data else {}
        display_data.update(pending)
        color = discord.Color.orange() if pending else discord.Color.blue()
        embed = discord.Embed(title="Settings", description="Select a setting to change:", color=color)
        embed.add_field(name="Clickup Email", value=display_data.get('clickup_email', 'Not set'), inline=True)
        embed.add_field(name="ROBLOX Username", value=display_data.get('roblox_username', 'Not set'), inline=True)
        embed.add_field(name="Timezone", value=display_data.get('timezone', 'Not set'), inline=False)
        embed.add_field(name="Primary Department", value=display_data.get('primary_department', 'Not set'), inline=True)
        embed.add_field(name="Secondary Department", value=display_data.get('secondary_department', 'Not set'), inline=True)
        embed.add_field(name="Reminder Preferences", value=display_data.get('reminder_preferences', 'Not set'), inline=False)
        view = SettingsMenuView(display_data, self.cog, pending_mode=True, just_changed=True)
        await interaction.response.edit_message(embed=embed, view=view)
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
        user_id = interaction.user.id
        if user_id not in pending_settings_changes:
            pending_settings_changes[user_id] = {}
        pending_settings_changes[user_id][self.field] = selected_department
        # Return to main settings embed with orange color
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE discord_id = %s", (user_id,))
        user_data = cursor.fetchone()
        connection.close()
        pending = pending_settings_changes.get(user_id, {})
        display_data = user_data.copy() if user_data else {}
        display_data.update(pending)
        color = discord.Color.orange() if pending else discord.Color.blue()
        embed = discord.Embed(title="Settings", description="Select a setting to change:", color=color)
        embed.add_field(name="Clickup Email", value=display_data.get('clickup_email', 'Not set'), inline=True)
        embed.add_field(name="ROBLOX Username", value=display_data.get('roblox_username', 'Not set'), inline=True)
        embed.add_field(name="Timezone", value=display_data.get('timezone', 'Not set'), inline=False)
        embed.add_field(name="Primary Department", value=display_data.get('primary_department', 'Not set'), inline=True)
        embed.add_field(name="Secondary Department", value=display_data.get('secondary_department', 'Not set'), inline=True)
        embed.add_field(name="Reminder Preferences", value=display_data.get('reminder_preferences', 'Not set'), inline=False)
        view = SettingsMenuView(display_data, self.cog, pending_mode=True, just_changed=True)
        await interaction.response.edit_message(embed=embed, view=view)
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
        user_id = interaction.user.id
        if user_id not in pending_settings_changes:
            pending_settings_changes[user_id] = {}
        pending_settings_changes[user_id]["reminder_preferences"] = selected_preference
        # Return to main settings embed with orange color
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE discord_id = %s", (user_id,))
        user_data = cursor.fetchone()
        connection.close()
        pending = pending_settings_changes.get(user_id, {})
        display_data = user_data.copy() if user_data else {}
        display_data.update(pending)
        color = discord.Color.orange() if pending else discord.Color.blue()
        embed = discord.Embed(title="Settings", description="Select a setting to change:", color=color)
        embed.add_field(name="Clickup Email", value=display_data.get('clickup_email', 'Not set'), inline=True)
        embed.add_field(name="ROBLOX Username", value=display_data.get('roblox_username', 'Not set'), inline=True)
        embed.add_field(name="Timezone", value=display_data.get('timezone', 'Not set'), inline=False)
        embed.add_field(name="Primary Department", value=display_data.get('primary_department', 'Not set'), inline=True)
        embed.add_field(name="Secondary Department", value=display_data.get('secondary_department', 'Not set'), inline=True)
        embed.add_field(name="Reminder Preferences", value=display_data.get('reminder_preferences', 'Not set'), inline=False)
        view = SettingsMenuView(display_data, self.cog, pending_mode=True, just_changed=True)
        await interaction.response.edit_message(embed=embed, view=view)
        return True

class SetupModal(Modal):
    def __init__(self, title, placeholder, callback):
        super().__init__(title=title)
        self.callback = callback
        self.add_item(discord.ui.TextInput(label=placeholder))

    async def on_submit(self, interaction: discord.Interaction):
        await self.callback(interaction, self.children[0].value)


class SettingsMenuView(View):
    def __init__(self, user_data, cog, pending_mode=False, just_changed=False):
        super().__init__(timeout=300)
        self.user_data = user_data
        self.cog = cog
        self.pending_mode = pending_mode
        self.just_changed = just_changed
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
        # Only show the Request button if there are pending changes and we're on the orange embed
        if self.just_changed and self.pending_mode:
            self.add_item(Button(label="Request", style=discord.ButtonStyle.danger, custom_id="done_settings"))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.data.get('component_type') == 3:  # 3 = Select menu
            selected = interaction.data['values'][0]
            if selected == "email":
                await interaction.response.send_modal(SetupModal("Email", "Enter your email", lambda i, v: self.cog.confirm_change(i, v, "clickup_email", return_to_settings=True)))
            elif selected == "roblox_username":
                await interaction.response.send_modal(SetupModal("ROBLOX Username", "Enter your ROBLOX username", lambda i, v: self.cog.confirm_change(i, v, "roblox_username", return_to_settings=True)))
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
            # Send approval request to the approval channel
            user_id = interaction.user.id
            changes = pending_settings_changes.get(user_id, {})
            if not changes:
                await interaction.response.edit_message(content="No changes to submit for approval.", view=None)
                return True
            # Fetch current user data for 'before' embed
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE discord_id = %s", (user_id,))
            before_data = cursor.fetchone()
            connection.close()
            # Prepare before/after embeds
            before_embed = discord.Embed(title="Settings Before", color=discord.Color.red())
            after_embed = discord.Embed(title="Settings After (Requested)", color=discord.Color.green())
            fields = [
                ("Clickup Email", 'clickup_email'),
                ("ROBLOX Username", 'roblox_username'),
                ("Timezone", 'timezone'),
                ("Primary Department", 'primary_department'),
                ("Secondary Department", 'secondary_department'),
                ("Reminder Preferences", 'reminder_preferences'),
            ]
            for label, key in fields:
                before_val = before_data.get(key, 'Not set') if before_data else 'Not set'
                after_val = changes.get(key, before_val)
                before_embed.add_field(name=label, value=before_val, inline=True)
                after_embed.add_field(name=label, value=after_val, inline=True)
            view = SettingsApprovalView(user_id, changes, self.cog)
            channel = self.cog.bot.get_channel(1373047877248614501)
            content = f"@everyone Settings change request for <@{user_id}> (Discord ID: {user_id})"
            if channel:
                await channel.send(content=content, embeds=[before_embed, after_embed], view=view)
                await interaction.response.edit_message(content="Your request to edit your settings has been submitted successfully! We operate on a request basis to prevent any abuse from non-supervisors or other general mistakes, similar to bots like ShulkerBox.", embed=None, view=None)
            else:
                await interaction.response.edit_message(content="Failed to contact a bot administrator regarding your request.", embed=None, view=None)
            return True
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
                    title="Welcome to the SCR Training Assistant!",
                    description="""Welcome! Please continue with the `/settings` command (if you didn't finish it already) to configure your account information. Many, if not all features **REQUIRE** everything to be properly filled out.

This bot has several main functions at this time:
- It will send you reminders for your trainings (toggleable in settings)
- It will send you reminders to complete your quota (toggleable in settings)
- You can check your quota with a command
- You can automatically create a training request with a command

Additionally, a list of commands can be found below:
> 1. `/ping` - Check if the bot is online and it's response time.
> 2. `/contact` - Contact the bot administrator (Robotic_dony2468) for support or questions, and they'll reply via the bot's DMs.
> 3. `/settings` - Configure your account information.
> 4. `/check` - Check if you've completed this month's quota, or see how far along you are.
> 5. `/create` - Create a new training request in a department (defaults to your primary department), and automatically ensures that timeslot is availible.

---> Please be aware that you'll get developer messages every so often as I push out updates. These cannot be turned off, but are very infrequent.

Note: This bot is still in development, and some features may not work as expected. If you encounter any issues, please report them to the bot administrator (Robotic_dony2468). Thanks again for using SCRTA!""",
                    color=discord.Color.purple()
                )
                sent_dm = await interaction.user.send(embed=embed)
                # Try to pin the welcome message in the user's DMs
                try:
                    await sent_dm.pin(reason="For safekeeping :)")
                except Exception:
                    pass  # Ignore if pinning fails (e.g., DMs or permissions)
            except Exception:
                pass  # Ignore if DMs are closed

        connection.close()

        # Use pending changes if they exist
        pending = pending_settings_changes.get(interaction.user.id, {})
        display_data = user_data.copy() if user_data else {}
        display_data.update(pending)

        async def main_settings_embed(just_changed=False):
            color = discord.Color.orange() if just_changed and pending else discord.Color.blue()
            embed = discord.Embed(title="Settings", description="Select a setting to change:", color=color)
            embed.add_field(name="Clickup Email", value=display_data.get('clickup_email', 'Not set'), inline=True)
            embed.add_field(name="ROBLOX Username", value=display_data.get('roblox_username', 'Not set'), inline=True)
            embed.add_field(name="Timezone", value=display_data.get('timezone', 'Not set'), inline=False)
            embed.add_field(name="Primary Department", value=display_data.get('primary_department', 'Not set'), inline=True)
            embed.add_field(name="Secondary Department", value=display_data.get('secondary_department', 'Not set'), inline=True)
            embed.add_field(name="Reminder Preferences", value=display_data.get('reminder_preferences', 'Not set'), inline=False)
            # Only show the Request button if just_changed and there are pending changes
            view = SettingsMenuView(display_data, self, pending_mode=True, just_changed=just_changed and bool(pending))
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        await main_settings_embed()

    async def confirm_change(self, interaction, value, field, return_to_settings=False):
        # Save the change in memory, not DB
        user_id = interaction.user.id
        if user_id not in pending_settings_changes:
            pending_settings_changes[user_id] = {}
        pending_settings_changes[user_id][field] = value
        if return_to_settings:
            # After a change, return to settings with orange embed
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE discord_id = %s", (user_id,))
            user_data = cursor.fetchone()
            connection.close()
            pending = pending_settings_changes.get(user_id, {})
            display_data = user_data.copy() if user_data else {}
            display_data.update(pending)
            color = discord.Color.orange() if pending else discord.Color.blue()
            embed = discord.Embed(title="Settings", description="Select a setting to change:", color=color)
            embed.add_field(name="Clickup Email", value=display_data.get('clickup_email', 'Not set'), inline=True)
            embed.add_field(name="ROBLOX Username", value=display_data.get('roblox_username', 'Not set'), inline=True)
            embed.add_field(name="Timezone", value=display_data.get('timezone', 'Not set'), inline=False)
            embed.add_field(name="Primary Department", value=display_data.get('primary_department', 'Not set'), inline=True)
            embed.add_field(name="Secondary Department", value=display_data.get('secondary_department', 'Not set'), inline=True)
            embed.add_field(name="Reminder Preferences", value=display_data.get('reminder_preferences', 'Not set'), inline=False)
            view = SettingsMenuView(display_data, self, pending_mode=True, just_changed=True)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            embed = discord.Embed(title="Change Queued", description=f"{field.replace('_', ' ').title()} will be changed to {value} (pending approval)", color=discord.Color.orange())
            view = SettingsMenuView(pending_settings_changes[user_id], self, pending_mode=True, just_changed=True)
            await interaction.response.edit_message(embed=embed, view=view)

class SettingsApprovalView(View):
    def __init__(self, user_id, changes, cog):
        super().__init__(timeout=86400)  # 24 hours
        self.user_id = user_id
        self.changes = changes
        self.cog = cog
        self.add_item(Button(label="Approve", style=discord.ButtonStyle.success, custom_id="approve"))
        self.add_item(Button(label="Deny", style=discord.ButtonStyle.danger, custom_id="deny"))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.data['custom_id'] == "approve":
            # Write changes to DB
            connection = get_db_connection()
            cursor = connection.cursor()
            for field, value in self.changes.items():
                cursor.execute(f"UPDATE users SET {field} = %s WHERE discord_id = %s", (value, self.user_id))
            connection.commit()
            connection.close()
            # Remove from pending
            pending_settings_changes.pop(self.user_id, None)
            # DM user with an embed
            user = self.cog.bot.get_user(self.user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="Settings Change Approved",
                        description="Your settings change request has been approved by the bot administrator. Your new settings are now active!",
                        color=discord.Color.green()
                    )
                    await user.send(embed=embed)
                except Exception:
                    pass
            await interaction.response.edit_message(content="Changes approved and applied.", view=None)
        elif interaction.data['custom_id'] == "deny":
            # Remove from pending
            pending_settings_changes.pop(self.user_id, None)
            # DM user with an embed
            user = self.cog.bot.get_user(self.user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="Settings Change Denied",
                        description="Your settings change request was denied for one or more of the following reasons:\n\n- You aren't a supervisor\n- You requested to be the ROBLOX username of someone you're not\n- You have an invalid/the wrong clickup email\n- You requested to be recognized under a department you aren't in\n- Something else (we'll contact you for this)\n\nIf you believe this was a mistake or you have questions, please contact the bot administrator (Robotic_dony2468)",
                        color=discord.Color.red()
                    )
                    await user.send(embed=embed)
                except Exception:
                    pass
            await interaction.response.edit_message(content="Changes denied.", view=None)
        return True

async def setup(bot):
    await bot.add_cog(User(bot))
