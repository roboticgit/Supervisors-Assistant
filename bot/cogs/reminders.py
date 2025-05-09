from discord.ext import commands
import asyncio
from datetime import datetime, timedelta

class RemindersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = {}

    @commands.command(name='set_reminder')
    async def set_reminder(self, ctx, time: str, *, message: str):
        """Sets a reminder for the user."""
        user_id = ctx.author.id
        reminder_time = self.parse_time(time)

        if reminder_time:
            self.reminders[user_id] = (reminder_time, message)
            await ctx.send(f'Reminder set for {time}: {message}')
            await self.wait_for_reminder(user_id, reminder_time, message)
        else:
            await ctx.send('Invalid time format. Please use a format like "10m" for 10 minutes.')

    @commands.command(name='list_reminders')
    async def list_reminders(self, ctx):
        """Lists all reminders for the user."""
        user_id = ctx.author.id
        if user_id in self.reminders:
            reminder_time, message = self.reminders[user_id]
            await ctx.send(f'Reminder: {message} at {reminder_time}')
        else:
            await ctx.send('You have no reminders set.')

    async def wait_for_reminder(self, user_id, reminder_time, message):
        await asyncio.sleep((reminder_time - datetime.now()).total_seconds())
        if user_id in self.reminders:
            await self.bot.get_user(user_id).send(f'Reminder: {message}')
            del self.reminders[user_id]

    def parse_time(self, time_str):
        """Parses a time string into a datetime object."""
        try:
            if time_str.endswith('m'):
                minutes = int(time_str[:-1])
                return datetime.now() + timedelta(minutes=minutes)
            elif time_str.endswith('h'):
                hours = int(time_str[:-1])
                return datetime.now() + timedelta(hours=hours)
            elif time_str.endswith('d'):
                days = int(time_str[:-1])
                return datetime.now() + timedelta(days=days)
        except ValueError:
            return None
        return None