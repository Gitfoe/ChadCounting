# ChadCounting
#### Say goodbye to ruined counts with ChadCounting, the bot that never misses a count. Count as high as you can and become the ultimate gigachad.
<img align="right" src="logo_chadcounting.png" width="172">

ChadCounting is a Discord bot that makes it easy for users on a server to collaborate on counting. With an emphasis on accuracy and reliability, ChadCounting is the ideal choice for gigachads who want to push their skills to the limit. In contrast to other counting bots, ChatCounting is specifically optimized to prevent incorrect counting on the bots side, making it the perfect tool for your server's counting needs.

### [Click here to add the bot to your server/guild](https://discord.com/api/oauth2/authorize?client_id=1066081427935993886&permissions=329792&scope=bot)

As an avid user of counting bots myself, one of the main issues I've encountered with other counting bots is that they had difficulty counting themselves. Most of the time, when the count was ruined, it was not because of our inability to count like chads, but the counting bot's inability to keep up with our chadness. For example, the counting bot went offline, didn't count our counts, then when it came back online it told us we've ruined the count and should start over. Or the bot ignored our correct count, we counted the number again, and it told us we can't count twice in a row. Frustrating for highly-capable counting chads. That's why I've developed ChadCounting.

One of the distinctive features of ChadCounting is the catch-up feature. In case ChadCounting or Discord is offline for a bit (e.g. due to maintenance), the bot catches up to missed counts and lets you know that it did so. This means that when ChadCounting didn't respond with an emoji to your message, you can still continue counting, because you can have the peace of mind that the bot will catch up to you. But of course, that's not the only distinctive feature!

## Features
- Counting from 1 to infinity in one designated Discord channel,
- Users must follow counting rules, such as preventing double counting, not counting backwards, and skipping counts,
- Users can get banned temporarily for counting mistakes, with severity determined by an exponential U-curve,
- Built-in troll prevention to severely penalize users who intentionally disrupt the count,
- Flexible customization options, including the ability to modify ban settings and bot reactions,
- Keeps track of user and server statistics, like correct and incorrect counts and high scores,
- Catches up on missed counts if users counted while the bot was offline,
- Works seamlessly across an unlimited number of servers,
- Counts any message that starts with a number.

## Usage
To configure the bot for the first time, add it to your Discord server and use the `/setchannel` command to let the bot know where it should keep track of counting. After that, ChadCounting is up and running and you can start competing!

## Commands
The following commands could be used:
- `/setchannel`: sets the counting channel the bot will be active in.
- `/setreactions`: allows you to change the way the bot reacts when you count.
- `/setbanning`: allows you to change banning settings, for instance, the ban duration.
- `/currentcount`: shows you the current recorded count in case you're unsure.
- `/highscore`: shows the server's high score and the average score.
- `/userstats`: gives counting statistics of a user and tells you if you're a chad.
- `/serverstats`: shows the ranks of all users in the server based on their counting performance.
- `/banrate`: shows how hard you will be penalized for making a mistake at different counts.
- `/help`: gives basic information about ChadCounting.

## Technical information
### Dependencies
To run the Python program, the following dependencies need to be installed via `pip3`:
```
pip3 install -U discord.py (confirmed with version 2.1.0)
pip3 install -U python-dotenv (confirmed with version 0.21.1)
pip3 install -U emoji (confirmed with version 2.2.0)
pip3 install -U matplotlib (confirmed with version 3.6.3)
pip3 install -U pytz (confirmed with version 2022.7.1)
```
### Discord Developer Portal bot settings
When creating your own fork of ChadCounting, ensure your bot has at least the `Send Message`, `Read Message History` and `Add Reactions` OAuth2 permissions. `Use External Emojis` is an optional permission, but recommended. The scope should be `bot`.

### Dev-mode
In the `Initialisation` region of the `bot.py` file, `dev_mode` can be enabled to facilitate the testing of real-world scenarios. By enabling `dev-mode`, the bot can be configured to operate solely within a designated (testing) guild, thus preventing beta code from impacting production guilds. It is recommended to have two separate Discord bots, one for production and one for development, to safely test new code without putting the production environment at risk.

[Link to add ChadCounting Dev to a guild](https://discord.com/api/oauth2/authorize?client_id=1069230219094921318&permissions=329792&scope=bot)

### Updating the database
Counting and guild data is saved to a JSON database, eliminating the need for external database software. After changing values in the database, the current guilds need to be updated to corrospond to the new database values. Ensure to enable `update_guild_data` in the 'Initialisation' region of the bot.py file. The script will automatically create a backup of guild_data before updating. After updating and seeing `ChadCounting is ready` in the terminal, you can disable updating again.

### Environment tables
For added security and to comply by Discord's ToS, create a .env file in the root directory of the ChadCounting bot folder (where bot.py is located). This file serves as the designated location to securely store bot tokens. To add your Discord bot tokens, follow the example below:
```
# .env
DISCORD_TOKEN=your_discord_bot_token
DEV_TOKEN=your_discord_dev_bot_token
```

### Pre-release versioning
To properly manage versioning, it is recommended to update the `bot_version` variable in the `Initialization` section of the `bot.py` file every time a functional version is committed to the `dev` branch. This version will be displayed in the output of the `/help` command. The naming convention follows the pattern: `MMM-DD-YYYY-noX`, where X is a sequential number starting from 1 for each new day. Example: `Feb-27-2023-no2`.
