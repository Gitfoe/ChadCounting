import os
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
guild_data = {};

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

class DateTimeEncoder(json.JSONEncoder):
    """Extends the JSONEncoder class to serialize unserializable data into strings."""
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)

@bot.event
async def on_ready():
    """Discord event that gets triggered once the connection has been established."""
    try:
        synced = await bot.tree.sync()
    except Exception as e:
        print(e)
    init_guild_data()
    for guild in bot.guilds:
        await check_for_missed_counts(guild.id)   

def init_guild_data():
    """Initializes the guild_data.json file, or loads it into the bot."""
    global guild_data
    try:
        with open("guild_data.json", "r") as f:
            file_content = f.read()
            if file_content:
                guild_data = json.loads(file_content)
                guild_data = {int(k): v for k, v in guild_data.items()}
                for v in guild_data.values():
                    if v["previous_message"] != None:
                        v["previous_message"] = datetime.fromisoformat(v["previous_message"])
    except FileNotFoundError:
        with open("guild_data.json", "w") as f:
            json.dump({}, f, cls=DateTimeEncoder)
        print("guild_data.json didn't exist and was created.")
    except json.decoder.JSONDecodeError:
        raise Exception("There was an error decoding guild_data.json.")
    finally:
        for guild in bot.guilds:
            add_guild_to_guild_data(guild)     

async def check_for_missed_counts(guild_id):
    """Checks for up to 100 messages of counts that have not been counted because the bot was not running."""
    last_message = guild_data[guild_id]["previous_message"]
    if last_message != None:
        counting_channel = bot.get_channel(guild_data[guild_id]["counting_channel"])
        async for message in counting_channel.history(limit=100, after=last_message):
            await check_count_message(message)                                               

@bot.event
async def on_guild_join(guild):
    """When a new guild adds the bot, this function is called, and the bot is added to guild_data."""
    add_guild_to_guild_data(guild)

def add_guild_to_guild_data(guild):
    if guild.id not in guild_data: 
        guild_data[guild.id] = {"current_count": 0,
                                "highest_count": 0,
                                "previous_user": None,
                                "previous_message": None,
                                "counting_channel": None}
    with open("guild_data.json", "w") as f:
            json.dump(guild_data, f, cls=DateTimeEncoder)     

@bot.tree.command(name="setchannel", description="Administratos only: sets the channel where the bot needs to keep track of counting.")
async def setchannel(interaction: discord.Integration):
    """Usable by admins of a guild to set the correct channel for ChadCounting to count in."""
    if interaction.user.guild_permissions.administrator:
        global guild_dat
        await interaction.response.send_message(f"The channel for ChadCounting has been set to {interaction.channel}.")
        guild_data[interaction.guild.id]["counting_channel"] = interaction.channel_id
        with open("guild_data.json", "w") as f:
            json.dump(guild_data, f, cls=DateTimeEncoder)
    else:
        await interaction.response.send_message("Sorry, you don't have the rights to change the channel for counting.", ephemeral=True)

@bot.tree.command(name="checkcount", description="Gives the current count in case you're unsure or you think someone deleted their message.")
async def checkcount(interaction: discord.Integration):
    current_count = guild_data[interaction.guild.id]["current_count"]
    await interaction.response.send_message(f"The current count is {current_count}. So what should the next number be? That's up to you, chad.")

@bot.tree.command(name="checkhighscore", description="Gives the highest count that has been achieved in this Discord server.")
async def checkcount(interaction: discord.Integration):
    highest_count = guild_data[interaction.guild.id]["highest_count"]
    current_count = guild_data[interaction.guild.id]["current_count"]
    full_text = f"The high score is {highest_count}. "
    if highest_count > current_count:
        full_text += f"That's {highest_count - current_count} higher than the current count. Do better, chads."
    else:
        full_text += "That's exactly the same as the current count!"
        if current_count > 100:
            full_text += " Well done, chads."
    await interaction.response.send_message(full_text)

# @bot.tree.command(name="say", description="Let the bot say something. It has to be something chad, however!")
# @app_commands.describe(thing_to_say = "What should I say?")
# async def say(interaction: discord.Integration, thing_to_say: str):
#     await interaction.response.send_message(thing_to_say)

@bot.event
async def on_message(message):
    """Discord event that gets triggered once a message is sent."""
    await check_count_message(message)

async def check_count_message(message):
    """Checks if the user has counted correctly and reacts with an emoji if so."""
    global guild_data
    if message.author == bot.user and message.channel.id != guild_data[message.guild.id]["counting_channel"]:
        return
    elif message.channel.id == guild_data[message.guild.id]["counting_channel"] and message.content[0].isnumeric():
        guild_id = message.guild.id
        current_count = guild_data[guild_id]["current_count"]
        previous_user = guild_data[guild_id]["previous_user"]
        previous_message = guild_data[guild_id]["previous_message"]
        highest_count = guild_data[guild_id]["highest_count"]
        if message.author.id != previous_user:
            if message.content.startswith(str(current_count + 1)):
                current_count += 1
                previous_user = message.author.id
                previous_message = message.created_at
                guild_data[guild_id]["current_count"] = current_count
                guild_data[guild_id]["previous_user"] = previous_user
                guild_data[guild_id]["previous_message"] = previous_message
                if guild_data[guild_id]["highest_count"] < current_count:
                    guild_data[guild_id]["highest_count"] = current_count
                await message.add_reaction("🙂")
                if str(current_count).find("69") != -1:
                    await message.add_reaction("💦")
            else:
                await handle_incorrect_count(guild_id, message, current_count, highest_count)
        else:
            await handle_incorrect_count(guild_id, message, current_count, highest_count, True) 
        with open("guild_data.json", "w") as f:
            json.dump(guild_data, f, cls=DateTimeEncoder)

async def handle_incorrect_count(guild_id, message, current_count, highest_count, is_repeated=False):
    """Sends the correct error message to the user for counting incorrectly."""
    guild_data[guild_id]["current_count"] = 0
    guild_data[guild_id]["previous_user"] = None
    guild_data[guild_id]["previous_message"] = None
    reactions = ["💀", "🇳", "🇴", "☠️"]
    for r in reactions:
        await message.add_reaction(r)
    full_text = f"What a beta move by {message.author.mention}. "
    suffix_text = f"Only gigachads should be in charge of counting. Please start again from 1. The high score is {highest_count}."
    if is_repeated:
        full_text += f"A user cannot count twice in a row. {suffix_text}"
    else:
        full_text += f"That's not the right number, it should have been {current_count + 1}. {suffix_text}"
    await message.reply(full_text)

bot.run(TOKEN)