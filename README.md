# Discord Bot Project

This project is a user-only Discord bot designed to assist with everyday tasks by accessing APIs, sending reminders, and functioning as an administrative assistant.

## Features

- **Reminders**: Set and manage reminders for yourself.
- **API Access**: Retrieve data from various APIs based on user commands.
- **Administrative Tasks**: Manage user roles and send notifications.

## Project Structure

```
discord-bot-project
├── bot
│   ├── __init__.py
│   ├── main.py
│   ├── cogs
│   │   ├── __init__.py
│   │   ├── reminders.py
│   │   ├── api_access.py
│   │   └── admin_tasks.py
│   └── utils
│       ├── __init__.py
│       ├── helpers.py
│       └── config.py
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd discord-bot-project
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Windows:
     ```
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source venv/bin/activate
     ```

4. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Create a `.env` file in the root directory and add your Discord bot token and any other necessary API keys.

6. Run the bot:
   ```
   python bot/main.py
   ```

## Usage

- Use commands in your Discord server to interact with the bot.
- Refer to the documentation within each cog for specific command usage.

## Contributing

Feel free to submit issues or pull requests to improve the bot's functionality!