#region Python imports
import os
import io
import re
import math
import json
import copy
import pytz
import emoji
import discord
import traceback
import statistics
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from datetime import datetime
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
#endregion

#region Initialisation
# For developing only
dev_mode = False # Make the bot only active in a certain guild
dev_mode_guild_id = 574350984495628436 # Bot must be in this guild already
update_guild_data = False # Forces updating of newly added guild_data values after a ChadCounting update

# Initialize variables and load environment tables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN") # Normal ChadCounting token
DEV_TOKEN = os.getenv("DEV_TOKEN") # ChadCounting Dev bot account token
guild_data = {} # DB
is_ready = False
bot_version = "Feb-4-2023-no3"

# Initialize bot and intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', help_command=None, intents=intents)
#endregion

#region Bot events
@bot.event
async def on_ready():
    """Discord event that gets triggered once the connection has been established."""
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
    global is_ready        
    is_ready = True
    print(f"ChadCounting is ready.")

@bot.event
async def on_message(message):
    """Discord event that gets triggered once a message is sent."""
    await check_count_message(message)

@bot.event
async def on_guild_join(guild):
    """When a new guild adds the bot, this function is called, and the bot is added to guild_data."""
    add_guild_to_guild_data(guild.id)
#endregion                                               

#region Counting logic
async def check_for_missed_counts(guild_id):
    """Checks for up to 100 messages of counts that have not been counted because the bot was not running."""
    last_message = guild_data[guild_id]["previous_message"]
    if last_message != None:
        counting_channel = bot.get_channel(guild_data[guild_id]["counting_channel"])
        async for message in counting_channel.history(limit=100, after=last_message):
            await check_count_message(message) 

async def check_count_message(message):
    """Checks if the user has counted correctly and reacts with an emoji if so."""
    global guild_data
    # Ignores messages sent by bots, and if dev_mode is on, exit if message is not from dev mode guild
    if message.author.bot or dev_mode and not message.guild.id == dev_mode_guild_id:
        return
    # Checks if the message is sent in counting channel and starts with a number
    elif message.channel.id == guild_data[message.guild.id]["counting_channel"] and len(message.content) > 0 and message.content[0].isnumeric():
        # Declare variables for later use
        guild_id = message.guild.id
        current_user = message.author.id
        current_count = guild_data[guild_id]["current_count"]
        previous_user = guild_data[guild_id]["previous_user"]
        highest_count = guild_data[guild_id]["highest_count"]
        add_user_in_guild_data_json(current_user, guild_id) # Try to add new users to the guild
        # Ban logic
        banning = guild_data[guild_id]["s_banning"]
        current_user_minutes_ban = check_user_banned(current_user, guild_id)
        if banning and current_user_minutes_ban >= 1:
            current_user_ban_string = minutes_to_fancy_string(current_user_minutes_ban)
            await message.reply(f"{message.author.mention}, you are still banned from counting for {current_user_ban_string}, you beta.\n" + 
                                f"The current count stays on {current_count}. Other users can continue counting.")
        # End of ban logic
        else:
            if current_user != previous_user:
                if message.content.startswith(str(current_count + 1)):
                    # Acknowledge a correct count
                    correct_reactions = guild_data[guild_id]["s_correct_reaction"]
                    for r in correct_reactions:
                        await message.add_reaction(r)
                    # React with a funny emoji if ( ͡° ͜ʖ ͡°) is in the number
                    if str(current_count).find("69") != -1:
                        await message.add_reaction("💦")
                    # Save new counting data
                    guild_data[guild_id]["current_count"] += 1 # Current count increases by one
                    guild_data[guild_id]["users"][current_user]["correct_counts"] += 1 # Correct count for user logged
                    guild_data[guild_id]["previous_user"] = current_user # Previous user is now the user who counted
                    guild_data[guild_id]["previous_message"] = message.created_at # Save datetime the message was sent
                    if highest_count < current_count: # New high score
                        guild_data[guild_id]["highest_count"] = current_count
                else:
                    await handle_incorrect_count(guild_id, message, current_count, highest_count) # Wrong count
            else:
                pass_doublecount = guild_data[guild_id]["s_pass_doublecount"]
                await handle_incorrect_count(guild_id, message, current_count, highest_count, pass_doublecount) # Repeated count
            write_guild_data(guild_data)

async def handle_incorrect_count(guild_id, message, current_count, highest_count, pass_doublecount=None):
    """Sends the correct error message to the user for counting incorrectly.
    No value for 'pass_doublecount' entered means that it is not a double count."""
    if pass_doublecount == None or pass_doublecount == False: # Only check incorrect counting if passing double counting allowed
        incorrect_reactions = guild_data[guild_id]["s_incorrect_reaction"]
        for r in incorrect_reactions:
            await message.add_reaction(r)
        guild_data[guild_id]["previous_counts"].append(current_count) # Save the count
        guild_data[guild_id]["current_count"] = 0 # Reset count to 0
        guild_data[guild_id]["previous_user"] = None # Reset previous user to no one so anyone can count again
        guild_data[guild_id]["previous_message"] = None # Reset timer of previous message for the bot catch up code
        guild_data[guild_id]["users"][message.author.id]["incorrect_counts"] += 1 # Save incorrect count for the user
        full_text = f"What a beta move by {message.author.mention}. "
        suffix_text = f"Only gigachads should be in charge of counting. Please start again from 1. The high score is {highest_count}."
        if pass_doublecount == None: # Not a double count
            full_text += f"That's not the right number, it should have been {current_count + 1}. {suffix_text}"
        else: # Is a double count
            full_text += f"A user cannot count twice in a row. {suffix_text}"
        # User ban logic
        banning = guild_data[guild_id]["s_banning"]
        if banning:
            average_count = calculate_average_count_of_guild(guild_id)
            message_count = message.content # What the value was the user sent in the message
            minimum_ban = guild_data[guild_id]["s_minimum_ban"]
            maximum_ban = guild_data[guild_id]["s_maximum_ban"]
            ban_range = guild_data[guild_id]["s_ban_range"]
            troll_amplifier = guild_data[guild_id]["s_troll_amplifier"]
            current_user_minutes_ban = round(calculate_user_penalization(
                current_count, average_count, minimum_ban, maximum_ban, ban_range, troll_amplifier, message_count
                ))
            if current_user_minutes_ban > 0:
                ban_user(message.author.id, guild_id, current_user_minutes_ban)
                current_user_ban_string = minutes_to_fancy_string(current_user_minutes_ban)
                full_text += f" Moreover, because you messed up, you are now banned for {current_user_ban_string}."
                if current_user_minutes_ban > maximum_ban:
                    full_text += f" ⚠️ Don't be a troll, {message.author.name}. ⚠️"
        # End of user ban logic
        await message.reply(full_text)
    else: # Pass/do nothing if passing of double counting is allowed
        pass
#endregion

#region JSON DB helper functions
class DateTimeEncoder(json.JSONEncoder):
    """Extends the JSONEncoder class to serialize unserializable data into strings."""
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)

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
            add_or_update_new_guild_data(dev_mode_guild_id)
        else:
            for guild in bot.guilds:
                add_or_update_new_guild_data(guild.id)
        print(f"Successfully loaded {len(guild_data)} guild(s).")

def add_or_update_new_guild_data(guild_id):
    """Adds new guilds and/or users to guild_data and updates them if needed."""
    global update_guild_data
    add_guild_to_guild_data(guild_id, update_guild_data)
    if update_guild_data:
        for user_id in guild_data[guild_id]["users"]:
            add_user_in_guild_data_json(user_id, guild_id, update_guild_data)

def write_guild_data(guild_data, backup=False):
    """Writes the dictionary guild_data to guild_data.json.
    Optional backup parameter forces a backup filename format."""
    file = "guild_data.json"
    if backup:
        timestamp = format_current_datetime(datetime.now(), False, False)
        file = f"{file}.bak{timestamp}"
        try:
            with open(file, "r") as f:
                return # Stop backing up if file already exists
        except FileNotFoundError:
            pass # Continue if file doesn't exist
        except Exception as e:
            print(e)
    if is_jsonable(guild_data):
        with open(file, "w") as f:
            json.dump(guild_data, f, cls=DateTimeEncoder)
    else:
        file = "guild_data.json.err"
        try:
            with open(file, "w") as f:
                json.dump(guild_data, f, cls=DateTimeEncoder)
        except Exception as e:
            print(f"Guild_data was not (completely) serializable. Tried to write to {file} instead.\nError:{e}")

def is_jsonable(x):
    """Checks if data X is json serializable."""
    try:
        json.dumps(x, cls=DateTimeEncoder)
        return True
    except (TypeError, OverflowError):
        return False

def convert_keys_to_int(data):
    """Converts all keys in a dictionary and its nested dictionaries or lists to integers."""
    if isinstance(data, dict):
        return {int(k) if k.isdigit() else k: convert_keys_to_int(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_keys_to_int(i) for i in data]
    else:
        return data
#endregion

#region Adding guilds/users to DB functions
def update_values(update_dict, values, guild_id, user_id=None):
    """Updates the given dictionary with new values, adds missing values, and deletes old values, for users or guilds."""
    global guild_data
    copy_guild_data = copy.deepcopy(guild_data)
    added = 0
    changed = 0
    deleted = 0
    for k, v in values.items():
        if k not in update_dict: # New values get added
            update_dict[k] = v
            added += 1
        elif v != None and type(update_dict[k]) != type(v): # Check for changed type and add if type changed, ignore None
            update_dict[k] = v
            changed += 1
    for k in update_dict.keys():
        if k not in values: # Old values get deleted
            del update_dict[k]
            deleted += 1
    if added > 0 or changed > 0 or deleted > 0:
        full_text = f"Successfully added {added}, changed {changed}, and deleted {deleted} values "
        if user_id == None:
            full_text += f"for guild {guild_id}."
        else:
            full_text += f"for user {user_id} in guild {guild_id}."
        print(full_text)
        write_guild_data(copy_guild_data, True) # Force a backup because changes were made
        write_guild_data(guild_data)

def add_guild_to_guild_data(guild_id, update=False):
    """Adds new guild to guild_data dictionary, or adds/changes/deletes values corrosponding to new values."""
    global guild_data
    values = {"current_count": 0,
              "highest_count": 0,
              "previous_user": None,
              "previous_message": None,
              "counting_channel": None,
              "users": {},
              "previous_counts": [],
              "s_correct_reaction": ["🙂"],
              "s_incorrect_reaction": ["💀"],
              "s_pass_doublecount": False,
              "s_banning": True,
              "s_minimum_ban": 1,
              "s_maximum_ban": 120,
              "s_ban_range": 1.1,
              "s_troll_amplifier": 7}
    if guild_id not in guild_data: 
        guild_data[guild_id] = values
        print(f"New guild {guild_id} successfully added to dictionary.")
        write_guild_data(guild_data)
    elif update:
        update_values(guild_data[guild_id], values, guild_id)

def add_user_in_guild_data_json(user_id, guild_id, update=False):
    """Adds new user to 'users' dictionary in guild_data, or adds/changes/deletes values corrosponding to new values."""
    global guild_data
    values = {"time_banned": None,
              "ban_time": 0,
              "correct_counts": 0,
              "incorrect_counts": 0}
    if user_id not in guild_data[guild_id]["users"]:
        guild_data[guild_id]["users"][user_id] = values 
        (f"New user {user_id} successfully added to guild {guild_id}.")
        write_guild_data(guild_data)
    elif update:
        update_values(guild_data[guild_id]["users"][user_id], values, guild_id, user_id)
#endregion

#region Banning helper functions
def calculate_user_penalization(current_count, average_count, minimum_ban, maximum_ban, ban_range, troll_amplifier, message_count=""):
    """Calculates how long a user should be banned based on an exponential curve around the average count. 
    The further the current count is from the average count, the higher the ban time will be. 
    The ban time will be at least the minimum_ban time and capped at the maximum_ban time.
    Range determines the width of the exponential curve.
    Users who are off very much from the actual count (and probably trolling) will get penalized harder."""
    # Convert string of message into integer, or the current_count if no numbers are found
    match = re.match(r'^\d+', message_count)
    message_count_int = int(match.group()) if match else current_count
    # Math to calculate the ban time based on the average count and the current count
    difference_from_average = abs(current_count - average_count)
    difference_from_current = abs(current_count - message_count_int)
    try:
        minutes_ban = min(maximum_ban, max(minimum_ban, math.pow(ban_range, difference_from_average)))
    except Exception:
        minutes_ban = maximum_ban
    if difference_from_current > 72 and current_count * 7 < message_count_int:
        return maximum_ban * troll_amplifier # Penalize hard if the entered count is more than 7x or 72 off from the actual count
    else:
        return minutes_ban

def ban_user(user_id, guild_id, ban_time):
    """Bans a user in a certain guild for a certain amount of time."""
    guild_data[guild_id]["users"][user_id]["time_banned"] = datetime.now()
    guild_data[guild_id]["users"][user_id]["ban_time"] = ban_time
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

def minutes_to_fancy_string(minutes, short = False):
    """Converts an integer of minutes to a string of hours and minutes."""
    hours, minutes = divmod(minutes, 60)
    hours_text = "h" if short else " hour" if hours == 1 else " hours"
    minutes_text = "m" if short else " minute" if minutes == 1 else " minutes"
    and_text = " " if short else " and "
    if hours >= 1 and minutes >= 1:
        return (f"{hours}{hours_text}{and_text}{minutes}{minutes_text}")
    elif hours >= 1:
        return (f"{hours}{hours_text}")
    else:
        return (f"{minutes}{minutes_text}")
#endregion

#region Other helper functions and classes
def calculate_average_count_of_guild(guild_id):
    """Calculates the mean of the previous_counts in a certain guild_id and returns 0 if there aren't any."""
    previous_counts = guild_data[guild_id]["previous_counts"]
    if len(previous_counts) > 0:
        return statistics.mean(previous_counts)
    else:
        return 0

async def check_correct_channel(interaction):
    """Checks if the command has been executed in the correct channel. Returns False if not."""
    global guild_data
    counting_channel = guild_data[interaction.guild.id]["counting_channel"]
    if interaction.channel.id != counting_channel:
        channel_error = f"You can only execute ChadCounting commands in the counting channel, "
        channel = interaction.guild.get_channel(counting_channel)
        if channel is not None:
            channel_error += f"which is '{channel.name}'."
        else:
            channel_error += "however, it doesn't exist anymore. Contact your server admin if you believe this is an error."
        await interaction.response.send_message(channel_error, ephemeral=True)
        return False
    elif counting_channel == None:
        channel_error = (f"You can only execute ChadCounting commands in the counting channel, however, it has not been set yet. " +
                         f"If you are an admin of this server, use the command /setchannel in the channel you want to count in.")
        await interaction.response.send_message(channel_error, ephemeral=True)
        return False
    else:
        return True

async def check_bot_ready(interaction):
    """Checks if the bot is ready and sends a reaction explaining that the bot is still starting up if not."""
    if not is_ready:
        await interaction.response.send_message(f"ChadCounting is still starting up, please try again in a couple seconds!", ephemeral=True)
        return is_ready
    else:
        return is_ready

def extract_discord_emojis(text):
    """Extracts unicode and custom emojis into a list, preserving order."""
    emoji_list = []
    # Unicode emoji
    unicode_dict = emoji.emoji_list(text)
    for match in unicode_dict:
        emoji_list.append((match['emoji'], match['match_start']))
    # Custom emoji pattern
    custom_emoji_pattern = re.compile(r"<a?:[a-zA-Z0-9_]+:[0-9]+>")
    for match in custom_emoji_pattern.finditer(text):
        emoji_list.append((match.group(0), match.start()))
    # Sort the emojis based on their indices
    emoji_list.sort(key=lambda x: x[1])
    # Return just the emojis
    return [emoji[0] for emoji in emoji_list]

def format_current_datetime(date_time, timezone, spaces):
    """Formats a datetime to a readable string and returns it."""
    if not timezone and not spaces:
        return date_time.now().strftime("%Y%m%d-%H%M%S")
    elif timezone and spaces:
        return date_time.strftime("%Y-%m-%d %H:%M:%S %Z")
    elif timezone and not spaces:
        return date_time.strftime("%Y%m%d-%H%M%S-%Z")
    else:
        return ""

def adjust_font_size(title, max_font_size=14):
    """Adjusts a font size to be smaller on longer texts."""
    font_size = max_font_size
    title_width = len(title)
    while title_width > 35 and font_size > 5:
        font_size -= 1
        title_width = len(title) * (font_size / max_font_size)
    return font_size

async def handle_reaction_setting(interaction, reactions):
    """Handles the reaction setting and sends the response. Part of /setreactions command."""
    changes_string = "\nNo changes were made to the reactions. Try again, chad."
    converted_string = extract_discord_emojis(reactions)
    converted_string_len = len(converted_string)
    if converted_string_len < 1 or converted_string_len > 10:
        full_text = f"Please enter no less than 1 and no more than 10 emoji. You entered {converted_string_len} emoji.{changes_string}"
        await interaction.response.send_message(full_text, ephemeral=True)
        return None
    else:
        configure = True
        return converted_string

async def command_exception(interaction):
    """Sends the traceback of a command exception to the user."""
    error = traceback.format_exc()
    await interaction.response.send_message(f"An error occured executing the command. Please send this to a developer of ChadCounting:\n```{error}```", ephemeral=True)
#endregion

#region Discord commands
@bot.tree.command(name="help", description="Gives information about ChadCounting.")
async def currentcount(interaction: discord.Integration):
    try:
        embed = discord.Embed(title="Welcome to ChadCounting", description="ChadCounting is a Discord bot designed to facilitate collaborative counting. With its focus on accuracy and reliability, ChatCounting is the ideal choice for gigachads looking to push their counting abilities to the limit. You're a chad, aren't you? If so, welcome, and start counting in the counting channel!", color=0xCA93FF)
        embed.add_field(name="Slash commands", value="Because this bot makes use of the newest Discord technology, you can use slash commands! The slash commands describe what they do and how to use them. Just type `/` in the chat and see all the commands ChadCounting has to offer.", inline=False)
        embed.add_field(name="Rules", value="In this counting game, users take turns counting with the next number. Double counting by the same user is not allowed. You can use the command `/setbanning` to see this server's configured rules for incorrect counts.", inline=False)
        embed.add_field(name="Counting feedback", value="After a user counts, the bot will respond with emoji to indicate if the count was correct or not. If the bot is unavailable (e.g. due to maintenance) and doesn't respond, you can still continue counting as it will catch up on missed counts upon its return. If you're unsure of the current recorded count, use the command `/currentcount` to check.", inline=False)
        embed.add_field(name="More information", value="For more information about this bot, go to [the GitHub page.](https://github.com/Gitfoe/ChadCounting)", inline=False)
        embed.set_footer(text=f"ChadCounting version {bot_version}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="setchannel", description="Admins only: sets the channel for ChadCounting to the current channel.")
async def setchannel(interaction: discord.Integration):
    try:
        if not await check_bot_ready(interaction):
            return
        if interaction.user.guild_permissions.administrator:
            global guild_data
            guild_id = interaction.guild.id
            guild_data[guild_id]["counting_channel"] = interaction.channel_id
            if guild_data[guild_id]["previous_message"] == None: # Set last message to now if no message has ever been recorded
                guild_data[guild_id]["previous_message"] = datetime.now()
            write_guild_data(guild_data)
            await interaction.response.send_message(f"The channel for ChadCounting has been set to '{interaction.channel}'.", ephemeral=True)
        else:
            await interaction.response.send_message("Sorry, you don't have the rights to change the channel for counting.", ephemeral=True)
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="setbanning", description="Admins only: configure the banning settings. No parameters gives current settings.")
@app_commands.describe(banning = "Enable or disable banning altogether. Default: True",
                       minimum_ban = "The minimum (or lowest) ban duration in minutes. Default: 1",
                       maximum_ban = "The maximum (or highest) ban duration in minutes. Default: 120",
                       ban_range = "The range/width of the exponentional banning curve. Lower values mean a wider curve. Default: 1.1",
                       troll_amplifier = "How much harder than the maximum ban duration a troll should be penalized for. Default: 7",
                       pass_doublecount = "Double counting by same user will be ignored (enabled) or penalized (disabled). Default: False")
async def setbanning(interaction: discord.Integration, banning: bool=None,
                                                       minimum_ban: int=None,
                                                       maximum_ban: int=None,
                                                       ban_range: float=None,
                                                       troll_amplifier: int=None,
                                                       pass_doublecount: bool=None):
    try:
        if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
            return
        else:
            global guild_data
            guild_id = interaction.guild.id
            changes_string = "\nNo changes were made to the banning settings. Try again, chad."
            # Check if any of the parameters have been entered
            configure = all(v is not None for v in (banning, minimum_ban, maximum_ban, ban_range, troll_amplifier, pass_doublecount))
            if configure and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Sorry, you don't have the rights to change the banning settings.", ephemeral=True)
                return
            if banning != None:
                guild_data[guild_id]["s_banning"] = banning
            if minimum_ban != None:
                if maximum_ban != None:
                    s_maximum_ban = maximum_ban
                else:
                    s_maximum_ban = guild_data[guild_id]["s_maximum_ban"]
                if minimum_ban < 0:
                    full_text = f"You can't set the minimum ban minutes lower than 0.{changes_string}"
                    await interaction.response.send_message(full_text, ephemeral=True)
                    return
                elif minimum_ban > s_maximum_ban:
                    full_text = ("You can't set the minimum ban duration higher than the maximum ban duration.\n" +
                                f"You tried to configure {minimum_ban} for the minimum duration and {s_maximum_ban} for the maximum duration.{changes_string}")
                    await interaction.response.send_message(full_text, ephemeral=True)
                    return
                else:
                    guild_data[guild_id]["s_minimum_ban"] = minimum_ban
            if maximum_ban != None:
                if minimum_ban != None:
                    s_minimum_ban = minimum_ban
                else:
                    s_minimum_ban = s_maximum_ban = guild_data[guild_id]["s_minimum_ban"]
                if maximum_ban < s_minimum_ban:
                    full_text = ("You can't set the maximum ban duration lower than the minimum ban duration.\n" +
                                f"You tried to configure {s_minimum_ban} for the minimum duration and {maximum_ban} for the maximum duration.{changes_string}")
                    await interaction.response.send_message(full_text, ephemeral=True)
                    return
                else:
                    guild_data[guild_id]["s_maximum_ban"] = maximum_ban
            if ban_range != None:
                if ban_range <= 1.001:
                    full_text = f"The banning range/width should be at least 1.001. You entered {ban_range}.{changes_string}"
                    await interaction.response.send_message(full_text, ephemeral=True)
                    return
                else:
                    guild_data[guild_id]["s_ban_range"] = ban_range
            if troll_amplifier != None:
                if troll_amplifier < 1 or troll_amplifier > 1337:
                    full_text = f"You must enter a troll amplifier between 1 and 1337. You entered {troll_amplifier}.{changes_string}"
                    await interaction.response.send_message(full_text, ephemeral=True)
                    return
                else:
                    guild_data[guild_id]["s_troll_amplifier"] = troll_amplifier
            if pass_doublecount != None:
                guild_data[guild_id]["s_pass_doublecount"] = pass_doublecount
            s_banning = guild_data[guild_id]["s_banning"]
            s_minimum_ban = minutes_to_fancy_string(guild_data[guild_id]["s_minimum_ban"])
            s_maximum_ban = minutes_to_fancy_string(guild_data[guild_id]["s_maximum_ban"])
            s_ban_range = guild_data[guild_id]["s_ban_range"]
            s_troll_amplifier = guild_data[guild_id]["s_troll_amplifier"]
            s_pass_doublecount = guild_data[guild_id]["s_pass_doublecount"]
            setting_string = (f"> Banning enabled: {s_banning}\n" +
                              f"> Minimum ban duration: {s_minimum_ban}\n" +
                              f"> Maximum ban duration: {s_maximum_ban}\n" +
                              f"> Ban range/width: exponent of {s_ban_range} squared\n" +
                              f"> Troll amplifier: {s_troll_amplifier}x\n" +
                              f"> Ignoring of double counts: {s_pass_doublecount}")
            if configure:
                write_guild_data(guild_data)
                full_text = f"{interaction.user.name} changed the banning settings to the following:\n{setting_string}"
                await interaction.response.send_message(full_text)
            else:
                full_text = f"Here you go, the current banning settings:\n{setting_string}"
                await interaction.response.send_message(full_text, ephemeral=True)
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="setreactions", description="Admins only: configure the correct/incorrect count reactions. No parameters gives current settings.")
@app_commands.describe(correct_reactions = "One or more emoji the bot will react with when someome counted correctly. Default: 🙂",
                       incorrect_reactions = "One or more emoji the bot will react with when someone messes up the count. Default: 💀")
async def setreactions(interaction: discord.Integration, correct_reactions: str=None,
                                                       incorrect_reactions: str=None):
    try:
        if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
            return
        else:
            global guild_data
            guild_id = interaction.guild.id
            # Check if any of the parameters have been entered
            configure = all(v is not None for v in (correct_reactions, incorrect_reactions))
            if configure and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Sorry, you don't have the rights to change the bot's reactions.", ephemeral=True)
                return
            if correct_reactions != None:
                response = await handle_reaction_setting(interaction, correct_reactions)
                if response == None: # None or incorrect amount of emoji
                    return
                guild_data[guild_id]["s_correct_reaction"] = response
                configure = True
            if incorrect_reactions != None:
                response = await handle_reaction_setting(interaction, incorrect_reactions)
                if response == None: # None or incorrect amount of emoji
                    return
                guild_data[guild_id]["s_incorrect_reaction"] = response
                configure = True
            s_correct_reactions = guild_data[guild_id]["s_correct_reaction"]
            s_incorrect_reactions = guild_data[guild_id]["s_incorrect_reaction"]
            setting_string = (f"> Correct count reaction(s): {''.join(str(i) for i in s_correct_reactions)}\n" +
                              f"> Incorrect count reaction(s): {''.join(str(i) for i in s_incorrect_reactions)}\n")
            if configure:
                write_guild_data(guild_data)
                full_text = f"{interaction.user.name} changed ChadCounting's reactions to the following:\n{setting_string}"
                await interaction.response.send_message(full_text)
            else:
                full_text = f"Here you go, the current reactions:\n{setting_string}"
                await interaction.response.send_message(full_text, ephemeral=True)
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="currentcount", description="Gives the current count in case you're unsure or want to double check.")
async def currentcount(interaction: discord.Integration):
    try:
        if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
            return
        current_count = guild_data[interaction.guild.id]["current_count"]
        await interaction.response.send_message(f"The current count is {current_count}. So what should the next number be? That's up to you, chad.")
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="highscore", description="Gives the highest count that has been achieved in this Discord server.")
async def highscore(interaction: discord.Integration):
    try:
        if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
            return
        guild_id = interaction.guild.id
        highest_count = guild_data[guild_id]["highest_count"]
        current_count = guild_data[guild_id]["current_count"]
        average_count = round(calculate_average_count_of_guild(guild_id), 2)
        amount_of_attempts = len(guild_data[guild_id]["previous_counts"])
        full_text = f"The high score is {highest_count}. "
        points = 0 # Points get calculated for the last suffix
        if highest_count > current_count:
            full_text += f"That's {highest_count - current_count} higher than the current count... "
        else:
            full_text += "That's exactly the same as the current count! "
            if highest_count >= 27: # Only award points if it's higher than or equal to 27
                points += 1
        full_text += f"On average you lads counted to {average_count}, and your current count is "
        if current_count > average_count:
            full_text += f"{round(current_count - average_count, 2)} higher than the average. "
            points += 2 if average_count >= 27 else 1 # Award less points if average not at least 27
        elif current_count < average_count:
            full_text += f"{round(average_count - current_count, 2)} lower than the average... "
        else:
            full_text += "exactly the same as the average. "
            if average_count >= 27: # Only award points if average is higher than or equal to 27
                points += 1
        full_text += f"You lads messed up the count {amount_of_attempts} "
        full_text += "time. " if amount_of_attempts == 1 else "times. "
        full_text += {0: "Do better, beta's.", 
                      1: "Decent work.", 
                      2: "Well done.", 
                      3: "Excellent work, chads!"}.get(points, "")
        await interaction.response.send_message(full_text)
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="banrate", description="Gives a list of the different ban levels showing the consequences of messing up the count.")
async def banrate(interaction: discord.Integration):
    try:
        if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
            return
        # Define variables
        guild_id = interaction.guild.id
        current_count = 0 # Start at calculating the count from 0
        average_count = calculate_average_count_of_guild(guild_id)
        minimum_ban = guild_data[guild_id]["s_minimum_ban"]
        maximum_ban = guild_data[guild_id]["s_maximum_ban"]
        ban_range = guild_data[guild_id]["s_ban_range"]
        troll_amplifier = guild_data[guild_id]["s_troll_amplifier"]
        banning = guild_data[guild_id]["s_banning"]
        # Define text for message
        full_text = (
            "Banning is currently enabled, beware! Here's the current banrate, you chad. "
            if banning
            else "Banning is currently disabled, however, if it were enabled, here's the banrate. "
        )
        full_text += f"If you get banned at any later count than on the far right of the graph, you will get banned for {minutes_to_fancy_string(maximum_ban)}. "
        full_text += "Use the command `/setbanning` to see the currently configured banning settings."
        # Calculate banning levels
        counts = []
        ban_times = []
        current_level = maximum_ban / 2 # Arbritrary level to simulate a do/while loop
        while current_count <= average_count or current_level >= minimum_ban and current_level < maximum_ban:
            current_level = calculate_user_penalization(current_count, average_count, minimum_ban, maximum_ban, ban_range, troll_amplifier)
            counts.append(current_count)
            ban_times.append(current_level)
            current_count += 1
        # Generate plot of ban times
        fig, ax = plt.subplots(facecolor="#353840")
        ax.plot(counts, ban_times, linewidth=1.5, color="#FFFFFF")
        ax.set_facecolor("#353840")
        ax.set_xlabel("Count", fontsize=12, color="#FFFFFF")
        ax.set_ylabel("Bantime (minutes)", fontsize=12, color="#FFFFFF")
        title_text = f"ChadCounting banrate of {interaction.guild.name}"
        ax.set_title(title_text, fontsize=adjust_font_size(title_text), color="#FFFFFF")
        ax.grid(color="#FFFFFF", alpha=0.5)
        ax.spines["bottom"].set_color("#FFFFFF")
        ax.spines["left"].set_color("#FFFFFF")
        ax.spines["right"].set_color("#FFFFFF")
        ax.spines["top"].set_color("#FFFFFF")
        ax.tick_params(axis="both", colors="#FFFFFF", labelsize="10")
        img = mpimg.imread("logo_chadcounting.png")
        img_ax = fig.add_axes([0, 0, 0.12, 0.12])
        img_ax.imshow(img)
        img_ax.axis("off")
        utc = pytz.UTC
        timestamp = format_current_datetime(datetime.now(utc), True, True)
        fig.text(0.98, 0.98, timestamp, ha="right", va="top", color="#FFFFFF", alpha=0.5, fontsize=8, transform=fig.transFigure)
        # Generate image from plot and send to user
        img = io.BytesIO()
        plt.savefig(img, format="png")
        img.seek(0)
        timestamp = format_current_datetime(datetime.now(utc), True, False)
        await interaction.response.send_message(full_text, file=discord.File(img, f"ChadCounting-banrate-{guild_id}-{timestamp}.png"))
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="userstats", description="Gives counting statistics of a user for this Discord server.")
@app_commands.describe(user = "Optional: the user you want to check the stats of.")
async def userstats(interaction: discord.Integration, user: discord.Member=None):
    try:
        if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
            return
        global guild_data
        guild_id = interaction.guild.id
        if user == None:
            user_id = interaction.user.id
            username = interaction.user.name
        else:
            user_id = user.id
            username = user.name   
        # Define statistics
        if user_id in guild_data[guild_id]["users"]:
            correct_counts = guild_data[guild_id]["users"][user_id]["correct_counts"]
            incorrect_counts = guild_data[guild_id]["users"][user_id]["incorrect_counts"]
            total_counts = correct_counts + incorrect_counts
            if total_counts > 0:
                percent_correct = round((correct_counts / (total_counts)) * 100)
                thresholds = {99: "What an absolute gigachad.",
                              95: "Chad performance.",
                              90: "Not bad, not good.",
                              80: "Nearing beta performance. Do better.",
                              70: "Definitely not chad performance."}
                chad_or_not = "Full beta performance. Become chad." # Default value if lower than lowest threshold
                for threshold, message in thresholds.items():
                    if percent_correct >= threshold:
                        chad_or_not = message
                        break
            else:
                percent_correct = "N/A"
            active_in_guilds = 0
            for values in guild_data.values():
                if user_id in values["users"]:
                    active_in_guilds += 1
        else:
            await interaction.response.send_message(f"{username} has not participated in ChadCounting yet. Shame.")
        # End of defining statistics
        full_text = (f"Here you go, the counting statistics of {username}.\n```" +
                     f"Correct counts: {correct_counts}\n" +
                     f"Incorrect counts: {incorrect_counts}\n" + 
                     f"Total counts: {total_counts}\n" +
                     f"Percent correct: {percent_correct}%\n" +
                     f"Active in Discord servers: {active_in_guilds}```" +
                     f"{chad_or_not}")
        await interaction.response.send_message(full_text)
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="serverstats", description="Gives counting statistics of this Discord server.")
async def serverstats(interaction: discord.Integration):
    try:
        if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
            return
        global guild_data
        guild_id = interaction.guild.id
        users = guild_data[guild_id]["users"]
        user_list = [(user_id, user_data["correct_counts"], user_data["incorrect_counts"]) for user_id, user_data in users.items()]
        sorted_user_list = sorted(user_list, key=lambda x: (x[1] + x[2], x[1]), reverse=True)
        full_text = "Here you go chad, the server statistics:\n"
        for i, user in enumerate(sorted_user_list[:10]):
            user_id, correct_counts, incorrect_counts = user
            user_id = await bot.fetch_user(user_id)
            total_counts = correct_counts + incorrect_counts
            full_text += f"> {i+1}. {user_id} - {total_counts} total, {correct_counts} correct, {incorrect_counts} incorrect\n"
        await interaction.response.send_message(full_text)
    except Exception:
        await command_exception(interaction)
#endregion

bot.run(DEV_TOKEN)
# Coded by https://github.com/Gitfoe