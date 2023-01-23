# ChadCounting
ChatCounting is a simple Discord bot designed to keep track of counting from one to infinity in a specific channel on your Discord server. Multiple people in the Discord channel should work together to count as high as possible. Unlike other counting bots, ChadCounting is specifically designed for skilled chads with highly accurate counting skills and does not sometimes miss a count, therefore ruining the count.

## Features
- Counting from 1 to ∞ (actually the 32-bit integer) in a specific Discord channel
- Users cannot count twice in a row, go backwards in count or skip a count
- Works seamlessly on multiple servers
- Saves the count data to a JSON database
- Keeps track of the high score
- Bot catches up to missed counts in the channel if people counted while the bot was off
- As long as the message starts with a number, the bot counts it

## Usage
To configue the bot for the first time, add it to your Discord server and use the `/setchannel` command to let the bot know where it should keep track of counting. After that the bot is up and running.

## Commands
The following commands could be used:
- `/setchannel`: sets the counting channel the bot will be active in.
- `/checkcount`: checks the current count in case you think someone might have deleted or edited their message.
- `/checkhighscore`: shows the current high score and the difference between the current count and the high score.

## Developer stuff
### Dependencies
To run the Python program, the following two dependencies need to be installed via pip:
```
pip3 install -U discord.py
pip3 install -U dotenv
```
### Discord Developer Portal bot settings
Create your own bot and ensure it has the `Send Message`, `Read Message History` and `Add Reactions` OAuth2 permissions. The scope should be `bot`.

### Environment tables
In the root of the ChadCounting bot folder (in the same folder as `bot.py`), create a `.env` file. Add the token of your Discord bot like this:
```
# .env
DISCORD_TOKEN=your_discord_bot_token
```
