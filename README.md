# ChadCounting
<img align="right" src="logo_chadcounting.png" width="172">

ChadCounting is a Discord bot designed to facilitate collaborative counting on your server. With its focus on accuracy and reliability, ChatCounting is the ideal choice for gigachads looking to push their counting abilities to the limit. In contrast to other counting bots, ChatCounting is specifically optimized to minimize missed counts in case the bot is offline, making it the perfect tool for your server's counting needs.

### [Click here to add the bot to your server/guild](https://discord.com/api/oauth2/authorize?client_id=1066081427935993886&permissions=67648&scope=bot)

## Features
- Counting from 1 to infinity in one designated Discord channel,
- Users must follow counting rules, including preventing double counting, counting backwards, and skipping counts,
- Temporary bans for count mistakes, with severity determined by an exponential U-curve,
- Built-in troll prevention to severely penalize users who intentionally disrupt the count,
- Flexible customization options, including the ability to modify ban settings and bot reactions,
- Keeps track of user statistics like correct and incorrect counts,
- Works seamlessly across an unlimited number of servers,
- Count data is saved to a JSON database, eliminating the need for external database software,
- High score and previous counts are tracked,
- Bot catches up on missed counts if users counted while the bot was offline,
- Counts any message that starts with a number.

## Usage
To configure the bot for the first time, add it to your Discord server and use the /setchannel command to let the bot know where it should keep track of counting. After that, the bot is up and running.

## Commands
The following commands could be used:
- `/setchannel`: sets the counting channel the bot will be active in.
- `/setreactions`: allows you to change the way the bot reacts when you count.
- `/setbanning`: allows you to change ban settings, for instance, the ban duration.
- `/currentcount`: checks the current count in case you're unsure if the count is still correct.
- `/highscore`: shows the current high score and the average.
- `/userstats`: gives counting statistics of a user.
- `/serverstats`: counting statistics of all users in the server.
- `/banrate`: shows how hard you will be penalized for making a mistake at the different counts.
- `/help`: gives information about ChadCounting.

## Technical information
### Dependencies
To run the Python program, the following dependencies need to be installed via `pip`:
```
pip install -U discord.py (confirmed with version 2.1.0)
pip install -U python-dotenv (confirmed with version 0.21.1)
pip install -U emoji (confirmed with version 2.2.0)
pip install -U matplotlib (confirmed with version 3.6.3)
```
### Discord Developer Portal bot settings
When creating your own fork of ChadCounting, ensure your bot has the `Send Message`, `Read Message History` and `Add Reactions` OAuth2 permissions. The scope should be `bot`.

### Dev-mode
In the 'Initialisation' section of the bot.py file, the dev_mode can be enabled to facilitate the testing of real-world scenarios. By enabling dev-mode, the bot can be configured to operate solely within a designated (testing) guild, thus preventing beta code from impacting production guilds. It is recommended to have two separate Discord bots, one for production and one for development, to safely test new code without putting the production environment at risk.

[Link to add ChadCounting Dev to a guild](https://discord.com/api/oauth2/authorize?client_id=1069230219094921318&permissions=67648&scope=bot)

### Updating the database
After changing values in the database, the current guilds need to be updated to corrospond to the new database values. Ensure to enable `update_guild_data` in the 'Initialisation' region of the bot.py file. The script will automatically create a backup of guild_data before updating. After updating and seeing `ChadCounting is ready` in the terminal, you can dissable updating again.

### Environment tables
For added security and to comply by Discord's ToS, create a .env file in the root directory of the ChadCounting bot folder (where bot.py is located). This file serves as the designated location to securely store bot tokens. To add your Discord bot tokens, follow the example below:
```
# .env
DISCORD_TOKEN=your_discord_bot_token
DEV_TOKEN=your_discord_dev_bot_token
```