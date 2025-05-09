# Discord DM Bot

This project is a Discord bot that operates entirely within a user's direct messages, serving as an administrative assistant for everyday tasks. The bot can access various APIs and send reminders to help users manage their time and tasks effectively.

## Features

- **Direct Message Interaction**: The bot communicates with users through direct messages, ensuring privacy and convenience.
- **Reminder Functionality**: Users can set reminders for tasks, and the bot will notify them at the specified times.
- **API Integration**: The bot can fetch data from external APIs to provide users with relevant information.

## Project Structure

```
discord-dm-bot
├── bot
│   ├── __init__.py
│   ├── main.py
│   ├── cogs
│   │   ├── __init__.py
│   │   ├── reminders.py
│   │   └── api_integration.py
│   ├── utils
│   │   ├── __init__.py
│   │   ├── helpers.py
│   │   └── config.py
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/discord-dm-bot.git
   ```
2. Navigate to the project directory:
   ```
   cd discord-dm-bot
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

1. Create a `.env` file in the root directory and add your Discord bot token and any API keys required for the bot to function:
   ```
   DISCORD_TOKEN=your_discord_token
   API_KEY=your_api_key
   ```

## Usage

1. Run the bot:
   ```
   python bot/main.py
   ```
2. Interact with the bot through direct messages on Discord. Use commands to set reminders and fetch data from APIs.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.