# ChadCounting
<img align="right" src="logo_chadcounting.png" width="172">

ChadCounting is a Discord bot designed to facilitate collaborative counting on your server. With its focus on accuracy and reliability, ChatCounting is the ideal choice for gigachads looking to push their counting abilities to the limit. In contrast to other counting bots, ChatCounting is specifically optimized to minimize missed counts and keep track of the latest count, making it the perfect tool for your server's counting needs.

### [Click here to add the bot to your server/guild](https://discord.com/api/oauth2/authorize?client_id=1066081427935993886&permissions=67648&scope=bot)

## Features
- Counting from 1 to infinity in one designated Discord channel
- Users must follow counting rules, including preventing double counting, counting backwards, and skipping counts
- Temporary bans for count mistakes, with severity determined by an exponential U-curve
- Built-in troll prevention to severely penalize users who intentionally disrupt the count
- Works seamlessly across an unlimited number of servers
- Count data is saved to a JSON database, eliminating the need for external database software
- High score and previous counts are tracked
- Bot catches up on missed counts if users counted while the bot was offline
- The bot counts any message that starts with a number

## Usage
To configue the bot for the first time, add it to your Discord server and use the `/setchannel` command to let the bot know where it should keep track of counting. After that the bot is up and running.

## Commands
The following commands could be used:
- `/setchannel`: sets the counting channel the bot will be active in.
- `/checkcount`: checks the current count in case you're unsure if the count is still correct.
- `/checkhighscore`: shows the current high score and the average.
- `/checkbanrate`: shows how hard you will be penalized for making a mistake at the different counts.

## Developer stuff
### Dependencies
To run the Python program, the following two dependencies need to be installed via pip:
```
pip install -U discord.py
pip install -U dotenv
```
### Discord Developer Portal bot settings
When creating your own fork of ChadCounting, ensure your bot has the `Send Message`, `Read Message History` and `Add Reactions` OAuth2 permissions. The scope should be `bot`.

### Dev-mode
At the top of the bot.py file, you can enable `dev_mode` to make testing real-world scenarios easier. With dev-mode, you can configure the bot to be only active in one (testing) guild.

### Environment tables
In the root of the ChadCounting bot folder (in the same folder as `bot.py`), create a `.env` file. Add the token of your Discord bot like this:
```
# .env
DISCORD_TOKEN=your_discord_bot_token
```
