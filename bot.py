import os
import math
import traceback
import statistics
import json
import discord
# from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from dotenv import load_dotenv

# For developing only
dev_mode = True # make the bot only active in a certain guild
dev_mode_guild_id = 574350984495628436 # Bot must be in this guild already.
update_guild_data = True # Forces updateing of new guild_data values after a ChadCounting update.

# Initialize variables from environment tables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
guild_data = {};

# Initialize bot and intents
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
    # Testing
    # testing_count = 0
    # while testing_count < 100:
    #     print(calculate_user_penalization(testing_count, 25))
    #     testing_count += 1

    try:
        synced = await bot.tree.sync()
    except Exception as e:
        print(e)
    init_guild_data()
    if dev_mode:
        await check_for_missed_counts(dev_mode_guild_id)
    else:
        for guild in bot.guilds:
            await check_for_missed_counts(guild.id)
    print("ChadCounting is ready.")

def init_guild_data():
    """Initializes the guild_data.json file, or loads it into the bot."""
    global guild_data
    try:
        with open("guild_data.json", "r") as f:
            file_content = f.read()
            if file_content:
                guild_data = json.loads(file_content)
                guild_data = convert_keys_to_int(guild_data)
                # Converts isoformats in guild_data.json to datetime objects
                for v in guild_data.values():
                    if "previous_message" in v and v["previous_message"] != None:
                        v["previous_message"] = datetime.fromisoformat(v["previous_message"])
                    if "users" in v:
                        for value in v["users"].values():
                            if value["time_banned"] != None:
                                value["time_banned"] = datetime.fromisoformat(value["time_banned"])
        print("guild_data.json successfully loaded.")
    except FileNotFoundError:
        write_guild_data(guild_data)
        print("guild_data.json didn't exist and was created.")
    except json.decoder.JSONDecodeError:
        raise Exception("There was an error decoding guild_data.json.")
    finally:
        if dev_mode:
            add_guild_to_guild_data(dev_mode_guild_id, update_guild_data)
        else:
            for guild in bot.guilds:
                add_guild_to_guild_data(guild.id, update_guild_data)
        print(f"Successfully loaded {len(guild_data)} guild(s) to the local dictionary.")

def write_guild_data(guild_data):
    """Writes the dictionary guild_data to guild_data.json."""
    with open("guild_data.json", "w") as f:
        json.dump(guild_data, f, cls=DateTimeEncoder)

def convert_keys_to_int(data):
    """Converts all keys in a dictionary and its nested dictionaries or lists to integers."""
    if isinstance(data, dict):
        return {int(k) if k.isdigit() else k: convert_keys_to_int(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_keys_to_int(i) for i in data]
    else:
        return data

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

def add_guild_to_guild_data(guild_id, update = False):
    """Adds a new empty guild to the guild_data dictionary, or adds missing values."""
    global guild_data
    values = {"current_count": 0,
              "highest_count": 0,
              "previous_user": None,
              "previous_message": None,
              "counting_channel": None,
              "users": {},
              "previous_counts": []}
    if guild_id not in guild_data: 
        guild_data[guild_id] = values
        write_guild_data(guild_data)
        print(f"New guild {guild_id} successfully added.")
    elif update and guild_id in guild_data:
        values_added = 0
        for k, v in values.items():
            if k not in guild_data[guild_id]:
                guild_data[guild_id][k] = v
                values_added += 1
        if values_added > 0:
            write_guild_data(guild_data)
            print(f"Successfully added new guild_data values for guild {guild_id}.")

def add_user_in_guild_data_json(user_id, guild_id, update = False):
    """Adds a new user in the 'users' dictionary in guild_data and writes it to the json file."""
    global guild_data
    values = {"time_banned": None,
              "ban_time": 0}
    if user_id not in guild_data[guild_id]["users"]:
        guild_data[guild_id]["users"][user_id] = values 
        write_guild_data(guild_data)
        (f"New user {user_id} successfully added to guild {guild_id}.")
    elif update and user_id in guild_data[guild_id]["users"]:
        values_added = 0
        for k, v in values.items():
            if k not in guild_data[guild_id]["users"][user_id]:
                guild_data[guild_id]["users"][user_id][k] = v
                values_added += 1
        if values_added > 0:
            write_guild_data(guild_data)
            print(f"Successfully added new user values for user {user_id} in guild {guild_id}.")

@bot.event
async def on_message(message):
    """Discord event that gets triggered once a message is sent."""
    await check_count_message(message)

async def check_count_message(message):
    """Checks if the user has counted correctly and reacts with an emoji if so."""
    global guild_data
    # Ignores messages sent by ChadCounting, and if devmode is on, exit if message is not from dev mode guild
    if message.author == bot.user or dev_mode and not message.guild.id == dev_mode_guild_id:
        return
    # Checks if the message is sent in counting channel and starts with a number
    elif message.channel.id == guild_data[message.guild.id]["counting_channel"] and message.content[0].isnumeric():
        # Declare variables for later use
        guild_id = message.guild.id
        current_count = guild_data[guild_id]["current_count"]
        current_user = message.author.id
        previous_user = guild_data[guild_id]["previous_user"]
        highest_count = guild_data[guild_id]["highest_count"]
        # Ban logic
        add_user_in_guild_data_json(current_user, guild_id, update_guild_data)
        current_user_minutes_ban = check_user_banned(current_user, guild_id)
        if current_user_minutes_ban >= 1:
            current_user_ban_string = minutes_to_fancy_string(current_user_minutes_ban)
            await message.reply(f"You are still banned from counting for {current_user_ban_string}, you beta.")
        # End of ban logic
        else:
            if current_user != previous_user:
                if message.content.startswith(str(current_count + 1)):
                    guild_data[guild_id]["current_count"] += 1
                    guild_data[guild_id]["previous_user"] = current_user
                    guild_data[guild_id]["previous_message"] = message.created_at
                    if guild_data[guild_id]["highest_count"] < current_count:
                        guild_data[guild_id]["highest_count"] = current_count
                    await message.add_reaction("🙂")
                    # React with a funny emoji if ( ͡° ͜ʖ ͡°) is in the number
                    if str(current_count).find("69") != -1:
                        await message.add_reaction("💦")
                else:
                    await handle_incorrect_count(guild_id, message, current_count, highest_count)
            else:
                await handle_incorrect_count(guild_id, message, current_count, highest_count, True)
            write_guild_data(guild_data)

def check_user_banned(user_id, guild_id):
    """Checks if the user is still banned, and if so, returns the minutes of banned time."""
    user_time_banned = guild_data[guild_id]["users"][user_id]["time_banned"]
    if user_time_banned != None:
        current_time = datetime.now()
        time_difference = current_time - user_time_banned
        minutes_passed = round(time_difference.total_seconds() / 60)
        user_ban_time = guild_data[guild_id]["users"][user_id]["ban_time"]
        if minutes_passed > user_ban_time:
            return 0
        else:
            return user_ban_time - minutes_passed
    else:
        return 0

async def handle_incorrect_count(guild_id, message, current_count, highest_count, is_repeated=False):
    """Sends the correct error message to the user for counting incorrectly."""
    guild_data[guild_id]["previous_counts"].append(current_count)
    guild_data[guild_id]["current_count"] = 0
    guild_data[guild_id]["previous_user"] = None
    guild_data[guild_id]["previous_message"] = None
    await message.add_reaction("💀")
    full_text = f"What a beta move by {message.author.mention}. "
    suffix_text = f"Only gigachads should be in charge of counting. Please start again from 1. The high score is {highest_count}."
    if is_repeated:
        full_text += f"A user cannot count twice in a row. {suffix_text}"
    else:
        full_text += f"That's not the right number, it should have been {current_count + 1}. {suffix_text}"
    # User ban logic
    average_count = calculate_average_count_of_guild(guild_id)
    current_user_minutes_ban = calculate_user_penalization(current_count, average_count)
    if current_user_minutes_ban > 0:
        ban_user(message.author.id, guild_id, current_user_minutes_ban)
        current_user_ban_string = minutes_to_fancy_string(current_user_minutes_ban)
        full_text += f" Moreover, because you messed up at such a low count, you are now banned for {current_user_ban_string}."
    # End of user ban logic
    await message.reply(full_text)
    additional_reactions = ["🇳", "🇴"]
    for r in additional_reactions:
        await message.add_reaction(r)

def calculate_average_count_of_guild(guild_id):
    """Calculates the mean of the previous_counts in a certain guild_id and returns 0 if there aren't any."""
    previous_counts = guild_data[guild_id]["previous_counts"]
    if len(previous_counts) > 0:
        return statistics.mean(previous_counts)
    else:
        return 0

def calculate_user_penalization(current_count, average_count, minimum_ban=1, maximum_ban=120, range=1.1):
    """Calculates how long a user should be banned based on an exponential curve around the average count. 
    The further the current count is from the average count, the higher the ban time will be. 
    The ban time will be at least the minimum_ban time and capped at the maximum_ban time.
    Range determines the width of the exponential curve."""
    difference_from_average = abs(current_count - average_count)
    minutes_ban = math.pow(range, difference_from_average)
    if minutes_ban >= minimum_ban and minutes_ban <= maximum_ban:
        return round(minutes_ban)
    elif minutes_ban > minimum_ban:
        return maximum_ban
    else:
        return 0

def ban_user(user_id, guild_id, ban_time):
    """Bans a user for a certain amount of time."""
    guild_data[guild_id]["users"][user_id]["time_banned"] = datetime.now()
    guild_data[guild_id]["users"][user_id]["ban_time"] = ban_time
    write_guild_data(guild_data)

def minutes_to_fancy_string(minutes, short = False):
    """Converts an integer of minutes to a string of hours and minutes."""
    if short:
        hours_text = "h"
        minutes_text = "m"
        and_text = " "
    else:
        hours_text = " hours"
        minutes_text = " minutes"
        and_text = " and "
    hours, minutes = divmod(minutes, 60)
    if hours >= 1 and minutes >= 1:
        return (f"{hours}{hours_text}{and_text}{minutes}{minutes_text}")
    elif hours >= 1:
        return (f"{hours}{hours_text}")
    else:
        return (f"{minutes}{minutes_text}")

@bot.tree.command(name="setchannel", description="Administratos only: sets the channel where the bot needs to keep track of counting.")
async def setchannel(interaction: discord.Integration):
    try:
        if interaction.user.guild_permissions.administrator:
            global guild_dat
            guild_data[interaction.guild.id]["counting_channel"] = interaction.channel_id
            write_guild_data(guild_data)
            await interaction.response.send_message(f"The channel for ChadCounting has been set to {interaction.channel}.")
        else:
            await interaction.response.send_message("Sorry, you don't have the rights to change the channel for counting.", ephemeral=True)
    except Exception:
        error = traceback.format_exc()
        await interaction.response.send_message(f"An error occured setting the channel. Please send this to a developer of ChadCounting:\n```{error}```", ephemeral=True)

@bot.tree.command(name="checkcount", description="Gives the current count in case you're unsure or you think someone deleted their message.")
async def checkcount(interaction: discord.Integration):
    try:
        current_count = guild_data[interaction.guild.id]["current_count"]
        await interaction.response.send_message(f"The current count is {current_count}. So what should the next number be? That's up to you, chad.")
    except Exception:
        error = traceback.format_exc()
        await interaction.response.send_message(f"An error occured obtaining the current count. Please send this to a developer of ChadCounting:\n```{error}```", ephemeral=True)

@bot.tree.command(name="checkhighscore", description="Gives the highest count that has been achieved in this Discord server.")
async def checkcount(interaction: discord.Integration):
    try:
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
    except Exception:
        error = traceback.format_exc()
        await interaction.response.send_message(f"An error occured obtaining the high score. Please send this to a developer of ChadCounting:\n```{error}```", ephemeral=True)

@bot.tree.command(name="checkbanrate", description="Gives a list of the different ban levels if you mess up counting.")
async def checkbanrate(interaction: discord.Integration):
    global guild_data
    try:
        first_message = "Here you go, the current ban rate, you chad:\n```"
        consecutive_message = "Here's the continuation of the previous ban rate levels:\n```"
        ban_levels_list = [first_message]
        current_count = 0 # Start at calculating the count from 0
        message_index = 0 # Since there is a 2000 character message limit on Discord
        average_count = calculate_average_count_of_guild(interaction.guild.id)
        minimum_ban = 1
        maximum_ban = 120
        current_level = maximum_ban / 2 # Arbritrary level to simulate a do/while loop
        while current_level >= minimum_ban and current_level < maximum_ban:
            current_level = calculate_user_penalization(current_count, average_count)
            current_level_fancy = minutes_to_fancy_string(current_level, True)
            ban_level_string = f"Count {current_count}: {current_level_fancy} ban\n"
            if not len(ban_levels_list[message_index]) + len(ban_level_string) + 3 <= 2000: # 3 for the ```code block
                ban_levels_list[message_index] += "```" # End the level with a quote block
                message_index += 1
                ban_levels_list.append(consecutive_message)
            ban_levels_list[message_index] += ban_level_string
            current_count += 1
        ban_levels_list[message_index] += f"```\nMessing up at any later counts will result in a ban of {current_level_fancy}."
        for index, level in enumerate(ban_levels_list):
            if index == 0:
                await interaction.response.send_message(level, ephemeral=True)
            else:
                await interaction.followup.send(level, ephemeral=True)
    except Exception:
        error = traceback.format_exc()
        await interaction.response.send_message(f"An error occured obtaining the ban levels. Please send this to a developer of ChadCounting:\n```{error}```", ephemeral=True)

bot.run(TOKEN)