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
import requests
import traceback
import statistics
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from datetime import datetime
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
#endregion

#region Initialisation
# For developing only
dev_disable_apis = False # Disable connecting to APIs such as bot websites
dev_active_single_guild = False # Make the bot only active in a certain guild
dev_mode_guild_id = 574350984495628436 # If the above is true, bot must be in this guild already
update_guild_data = False # Forces updating of newly added guild_data values after a ChadCounting update

# Initialize variables and load environment tables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") # Normal ChadCounting token
DEV_TOKEN = os.getenv("DEV_TOKEN") # ChadCounting Dev bot account token
DISCORDBOTLIST_TOKEN = os.getenv("DISCORDBOTLIST_TOKEN") # For using the https://discordbotlist.com API
TOPGG_TOKEN = os.getenv("TOPGG_TOKEN") # For using the https://top.gg API
guild_data = {} # Global variable for database
bot_version = "1.0.1-indev"
chadcounting_color = 0xCA93FF # Color of the embeds
image_gigachad = "https://github.com/Gitfoe/ChadCounting/blob/main/gigachad.jpeg?raw=true"
api_discordbotslist = "https://discordbotlist.com/api/v1/bots/chadcounting"
api_topgg = "https://top.gg/api/bots/1066081427935993886"

# Initialize bot and intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', help_command=None, intents=intents)
#endregion

#region Bot events
@bot.event
async def on_ready():
    """Discord event that gets triggered once the connection has been established."""
    # Setup and sync commands
    await setup_grouped_commands(bot)
    try:
        await bot.tree.sync() # Sync commands to Discord
        push_commands_to_discordbotlist() # Sync commands to Discordbotlist
        push_guilds_count_to_all_bot_websites() # Sync guilds count to bot lists
    except Exception as e:
        print(e)
    # Initialise database
    init_guild_data()
    for guild in bot.guilds:
        if not dev_active_single_guild or (dev_active_single_guild and guild.id == dev_mode_guild_id):
            await check_for_missed_counts(guild.id)
    print(f"[{datetime.now()}] ChadCounting is ready.")

@bot.event
async def on_resumed():
    """Discord event that gets triggered once a bot gets resumed from a paused session."""
    for guild in bot.guilds:
        if not dev_active_single_guild or (dev_active_single_guild and guild.id == dev_mode_guild_id):
            await check_for_missed_counts(guild.id)
    print(f"[{datetime.now()}] ChadCounting has resumed.")

@bot.event
async def on_message(message):
    """Discord event that gets triggered once a message is sent."""
    if bot.is_ready() is not True:
        return
    await check_count_message(message)

@bot.event
async def on_message_delete(message):
    """Checks if a deleted message is the current count and notify the users of that."""
    if bot.is_ready() is not True:
        return
    global guild_data
    guild_id = message.guild.id
    current_count = guild_data[guild_id]["current_count"]
    # Ignores messages sent by bots, and if dev_mode is on, exit if message is not from dev mode guild
    if message.author.bot or dev_active_single_guild and not guild_id == dev_mode_guild_id:
        return
    last_count = guild_data[guild_id]["previous_message"]
    if message.created_at == last_count:
        # Ban logic
        banning_enabled = guild_data[guild_id]["s_banning"]
        if banning_enabled:
            maximum_ban = guild_data[guild_id]["s_maximum_ban"]
            troll_amplifier = guild_data[guild_id]["s_troll_amplifier"]
            ban_time_for_troll = maximum_ban * troll_amplifier # Ban the deleter of the message for the troll amount
            success_user_banned = ban_user(message.author.id, guild_id, ban_time_for_troll)
            write_guild_data(guild_data)
        else:
            success_user_banned = None
        guild_data[guild_id]["previous_user"] = None # Reset previous user to no one so anyone can count again
        # Message logic
        embed = chadcounting_embed(f"{message.author.name} deleted a count...")
        full_text = (f"It seems that {message.author.mention} deleted their last counting message!" + 
                    " They likely wanted to purposefully mess up the count. Shame.")
        if success_user_banned == True:
            full_text += f" They are now banned for {minutes_to_fancy_string(ban_time_for_troll)} and can't continue counting."
        elif success_user_banned == False:
            full_text += " However, as they have never counted with ChadCounting before, they won't get banned. Very lucky..."
        embed.add_field(name="", value=full_text, inline=False)
        embed.add_field(name="", value=f"The current count is **{current_count}**. Continue counting from there!", inline=False)
        counting_channel = bot.get_channel(guild_data[guild_id]["counting_channel"])
        await counting_channel.send(embed=embed)

@bot.event
async def on_guild_join(guild):
    """When a new guild adds the bot, this function is called, and the bot is added to guild_data."""
    if bot.is_ready() is not True:
        return
    add_guild_to_guild_data(guild.id)
    push_guilds_count_to_all_bot_websites() # Sync guilds count with bot lists
#endregion                                               

#region Counting logic
async def check_for_missed_counts(guild_id):
    """Checks for up to 100 messages of counts that have not been counted because the bot was not running."""
    last_message = guild_data[guild_id]["previous_message"]
    if last_message == None:
        return
    counting_channel = bot.get_channel(guild_data[guild_id]["counting_channel"])
    message_count = 0
    correct_count_amount = 0
    incorrect_count = False
    if counting_channel != None:
        permissions = counting_channel.permissions_for(counting_channel.guild.me)
        if permissions.read_message_history:
            async for message in counting_channel.history(limit=100, after=last_message):
                message_count += 1 # Count a message
                correct_count = await check_count_message(message)
                if correct_count == True:
                    correct_count_amount += 1 # Count a correct count
                elif correct_count == False:
                    incorrect_count = True
                    break # Stop checking messages after an incorrect count was logged
        else:
            print(f"[{datetime.now()}] {check_for_missed_counts.__name__}: No message history permissions for guild {counting_channel.guild} (ID: {guild_id}) and channel {counting_channel} (ID: {guild_data[guild_id]['counting_channel']}).")
    if correct_count_amount > 0 or incorrect_count == True:
        embed = chadcounting_embed("ChadCounting is back on track!")
        current_count = guild_data[guild_id]["current_count"]
        message = ("ChadCounting was offline for a bit and missed some of your counts. " +
                  f"In total, we caught up to {message_count_to_string(message_count)}, " +
                  f"and {message_count_to_string(correct_count_amount, True)}")
        if incorrect_count == True: # If someone did an incorrect count while offline
            message += (" However, there was an incorrect count... After an incorrect count, you must start over. " +
                        f"Any counts you lads might have made after the incorrect count were not counted.")
            continue_message = "Please start counting again from **1!**"
            # Set previous_message to now, so if the bot goes offline after going online immediately, it knows where to start looking
            guild_data[guild_id]["previous_message"] = datetime.now()
            write_guild_data(guild_data)
        elif message_count >= 100: # If the message history limit was reached
            message += f" Unfortunately, {message_count} is the maximum number of messages we can check. Any counts after count {current_count} have not been counted."
            continue_message = f"The current count is **{current_count}**. Please continue counting from there! Anyone can continue counting."
            guild_data[guild_id]["previous_message"] = datetime.now() # If bot goes offline again
            guild_data[guild_id]["previous_user"] = None # In this case, reset previous user, so anyone can continue counting
            write_guild_data(guild_data)
        else:
            continue_message = f"The current count is **{current_count}**, so continue counting from there!"
        embed.add_field(name="", value=message, inline=False)
        embed.add_field(name="", value=continue_message, inline=False)
        await counting_channel.send(embed=embed)

async def check_count_message(message):
    """Checks if the user has counted correctly and reacts with an emoji if so. Also checks for incorrect counts."""
    """Returns True if the message was a correct count and False if it was incorrect. Returns nothing if count wasn't checked."""
    global guild_data
    # Ignores messages sent by bots, and if dev_mode is on, exit if message is not from dev mode guild
    if message.author.bot or dev_active_single_guild and not message.guild.id == dev_mode_guild_id:
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
            embed = chadcounting_embed("You can't count now!")
            embed.add_field(name="", value=f"{message.author.mention}, you are still banned from counting for {current_user_ban_string}, you beta. ", inline=False)
            embed.add_field(name="", value=f"The current count stays on **{current_count}**. Other users can continue counting.", inline=False)
            await message.reply(embed=embed)
        # End of ban logic
        else:
            if current_user != previous_user:
                if extract_number_from_string(message.content) == current_count + 1:
                    # Save new counting data
                    guild_data[guild_id]["current_count"] += 1 # Current count increases by one
                    guild_data[guild_id]["users"][current_user]["correct_counts"] += 1 # Correct count for user logged
                    guild_data[guild_id]["previous_user"] = current_user # Previous user is now the user who counted
                    guild_data[guild_id]["previous_message"] = message.created_at # Save datetime the message was sent
                    if highest_count < guild_data[guild_id]["current_count"]: # New high score  
                        guild_data[guild_id]["highest_count"] = guild_data[guild_id]["current_count"]
                    write_guild_data(guild_data) # Write count data
                    # Acknowledge a correct count
                    correct_reactions = guild_data[guild_id]["s_correct_reaction"]
                    correct_reactions = remove_unavailable_emoji(correct_reactions, "🙂")
                    await add_reactions(message, correct_reactions, current_count)
                    return True
                else:
                    await handle_incorrect_count(message, current_count, highest_count) # Wrong count
                    return False
            else:
                pass_doublecount = guild_data[guild_id]["s_pass_doublecount"]
                await handle_incorrect_count(message, current_count, highest_count, pass_doublecount) # Repeated count
                return False

async def handle_incorrect_count(message, current_count, highest_count, pass_doublecount=None):
    """Sends the correct error message to the user for counting incorrectly.
    No value for 'pass_doublecount' entered means that it is not a double count."""
    if pass_doublecount == None or pass_doublecount == False: # Only check incorrect counting if passing double counting allowed
        global guild_data
        guild_id = message.guild.id
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
        banning_enabled = guild_data[guild_id]["s_banning"]
        if banning_enabled:
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
                    full_text += f" ⚠️ **Don't be a troll, {message.author.name}.**"
        write_guild_data(guild_data) # Write count data
        # Embed incorrect number message
        embed = chadcounting_embed("Whoops...!")
        embed.add_field(name="", value=full_text)
        await message.reply(embed=embed)
        # Acknowledge an incorrect count
        incorrect_reactions = guild_data[guild_id]["s_incorrect_reaction"]
        incorrect_reactions = remove_unavailable_emoji(incorrect_reactions, "💀")
        await add_reactions(message, incorrect_reactions)
    else: # Pass/do nothing if passing of double counting is allowed
        pass

async def add_reactions(message, reaction_emoji, current_count=None):
    """Adds one or more emoji as reactions to a message."""
    if message.channel.permissions_for(message.guild.me).add_reactions: # Only react if you have permission
        for emoji in reaction_emoji:
            await message.add_reaction(emoji)
        if current_count is not None and str(current_count + 1).find("69") != -1: # React with a funny emoji if ( ͡° ͜ʖ ͡°) is in the number
            await message.add_reaction("💦")
    else:
        print(f"[{datetime.now()}] {add_reactions.__name__}: No add reactions permissions for guild {message.guild.name} (ID: {message.guild.id}).")
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
        print(f"[{datetime.now()}] guild_data.json successfully loaded.")
    except FileNotFoundError:
        write_guild_data(guild_data)
        print(f"[{datetime.now()}] guild_data.json didn't exist and was created.")
    except json.decoder.JSONDecodeError:
        raise Exception("There was an error decoding guild_data.json.")
    finally:
        for guild in bot.guilds:
            if not dev_active_single_guild or (dev_active_single_guild and guild.id == dev_mode_guild_id):
                add_or_update_new_guild_data(guild.id)
        if update_guild_data: # If updating is on, also check the existing guilds in guild_data (if the bot left a guild)
            for guild_id in guild_data:
                if not dev_active_single_guild or (dev_active_single_guild and guild_id == dev_mode_guild_id):
                    add_or_update_new_guild_data(guild_id)
        print(f"[{datetime.now()}] Successfully loaded {len(guild_data)} guild(s).")

def add_or_update_new_guild_data(guild_id):
    """Adds new guilds and/or users to guild_data and updates them if needed."""
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
            print(f"[{datetime.now()}] Guild_data was not (completely) serializable. Tried to write to {file} instead.\nError:{e}")

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
        print(f"[{datetime.now()}] {full_text}")
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
        print(f"[{datetime.now()}] New guild {guild_id} successfully added to dictionary.")
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
    """Bans a user in a certain guild for a certain amount of time. Returns True if successful."""
    global guild_data
    if user_id in guild_data[guild_id]["users"]:
        guild_data[guild_id]["users"][user_id]["time_banned"] = datetime.now()
        guild_data[guild_id]["users"][user_id]["ban_time"] = ban_time
        write_guild_data(guild_data)
        return True
    else:
        return False

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
    
def message_count_to_string(message_count, suffix = False):
    """Converts an integer of a message count to a string of a message count and the notation."""
    if message_count == 1 or message_count == -1:
        message_string = f"{message_count} message"
        if suffix:
            message_string += " was a correct count."
    else:
        message_string = f"{message_count} messages"
        if suffix:
            message_string += " were correct counts."
    return message_string
#endregion

#region Other helper functions
def calculate_average_count_of_guild(guild_id):
    """Calculates the mean of the previous_counts in a certain guild_id and returns 0 if there aren't any."""
    previous_counts = guild_data[guild_id]["previous_counts"]
    if len(previous_counts) > 0:
        return statistics.mean(previous_counts)
    else:
        return 0

def extract_discord_emoji(text):
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
    
def extract_number_from_string(string):
    """Gathers numbers at the start of a string and returns them in integer form."""
    num_str = ""
    for char in string:
        if char.isdigit():
            num_str += char
        else:
            break
    if num_str:
        return int(num_str)
    else:
        return None

def adjust_font_size(title, max_font_size):
    """Adjusts a font size to be smaller on longer texts."""
    font_size = max_font_size
    title_width = len(title)
    while title_width > 35 and font_size > 5:
        font_size -= 1
        title_width = len(title) * (font_size / max_font_size)
    return font_size

def remove_unavailable_emoji(emoji_list, default_emoji=None):
    """Filter out custom emoji that the bot can't display, replace them with default emoji if there's no emoji left."""
    for emoji in emoji_list:
        if emoji[0] == "<": # Custom Discord emoji start with <
            emoji_id = int(re.search(r':\d+', emoji).group()[1:])
            loaded_emoji = bot.get_emoji(emoji_id) # Check if the bot can use it
            if loaded_emoji == None:
                emoji_list.remove(emoji) # Remove from list if not
    if not emoji_list and default_emoji != None:
        emoji_list.append(default_emoji)
    return emoji_list

def chadcounting_embed(title, description=None):
    """Initialises an embed with the default ChadCounting settings."""
    embed = discord.Embed(title=title, description=description, color=chadcounting_color)
    embed.set_thumbnail(url=image_gigachad)
    return embed

def check_dev_disable_apis(executing_method_name):
    """Prints to the console if 'dev_disable_apis' is enabled."""
    if dev_disable_apis:
        print(f"[{datetime.now()}] {executing_method_name}: dev_disable_apis is enabled, method will exit.")
    return dev_disable_apis
#endregion

#region Command helper functions
async def handle_reaction_setting(interaction, reactions, embed):
    """Handles the reaction setting and sends the response. Part of /setreactions command."""
    changes_string = "\nNo changes were made to the reactions. Try again, chad."
    emoji_string = extract_discord_emoji(reactions)
    emoji_string_length = len(emoji_string)
    filtered_emoji_string_length = len(remove_unavailable_emoji(emoji_string))
    if emoji_string_length < 1 or emoji_string_length > 10:
        full_text = f"Please enter no less than 1 and no more than 10 emoji for one reaction. You entered {emoji_string_length} emoji.{changes_string}"
        embed.add_field(name="", value=full_text)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return None
    elif emoji_string_length > filtered_emoji_string_length:
        full_text = f"One or more emoji could not be set, likely because ChadCounting doesn't have access to that emoji.{changes_string}"
        embed.add_field(name="", value=full_text)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return None
    else:
        return emoji_string

async def command_exception(interaction, exception):
    """Sends the traceback of a command exception to the user. Traceback if it fits as a Discord message, exception if not."""
    traceback.print_exc()
    error = f"An error occured executing the command. Please send this to a developer of ChadCounting:\n```"
    trace = f"{traceback.format_exc()}```"
    if len(error) + len(trace) > 2000:
        error += f"{trace}```"
    elif len(error) + len(str(exception)) <= 2000:
        error += f"{str(exception)}```"
    else:
        error += "No exception data. The exception was too large to fit in a Discord message.```"
    embed = chadcounting_embed("Error")
    embed.add_field(name="", value=error)
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def check_correct_channel(interaction):
    """Checks if the command has been executed in the correct channel. Sends a response and returns False if not."""
    global guild_data
    counting_channel = guild_data[interaction.guild.id]["counting_channel"]
    embed = chadcounting_embed("Incorrect channel")
    channel_error = f"You can only execute ChadCounting commands in the counting channel, "
    if counting_channel == None:
        channel_error += (f"however, it has not been set yet. " +
                          f"If you are an admin of this server, use the command `/set channel` in the channel you want to count in.")
        embed.add_field(name="", value=channel_error)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False
    elif interaction.channel.id != counting_channel:
        channel = interaction.guild.get_channel(counting_channel)
        if channel is not None:
            channel_error += f"which is **'{channel.name}'** Use `/help` for more information."
        else:
            channel_error += "however, it doesn't exist anymore. Contact your server admin if you believe this is an error."
        embed.add_field(name="", value=channel_error)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False
    else:
        return True

async def check_bot_ready(interaction):
    """Checks if the bot is ready and sends a reaction explaining that the bot is still starting up if not."""
    embed = chadcounting_embed("ChadCounting is preparing for takeoff")
    if bot.is_ready() is not True:
        embed.add_field(name="", value=f"ChadCounting is starting up, please try again in a couple of seconds!")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False
    return True

def get_all_commands(bot):
    """Returns a list of all the commands the bot has."""
    return [
        *bot.walk_commands(),
        *bot.tree.walk_commands()
    ]
#endregion

#region View subclasses
class ViewYesNoButtons(View):
    """Makes a view with a yes and a no button. Resets the view after the button has been pressed."""
    def __init__(self, interaction):
        super().__init__()
        self.interaction = interaction
        self.button_answer = None # If the user clicked on yes (True) or no (False)
        self.followup_message = None # In case the message that has to be edited is a followup message
        self.title = ""
    async def clear_view_of_interaction(self):
        if self.followup_message != None:
            await self.interaction.followup.edit_message(self.followup_message.id, view=None)
        else:
            await self.interaction.edit_original_response(view=None)
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, emoji="🙂")
    async def yes_button_callback(self, button, interaction):
        self.button_answer = True
        await self.clear_view_of_interaction()
        self.stop()
    @discord.ui.button(label="No", style=discord.ButtonStyle.red, emoji="💀")
    async def no_button_callback(self, button, interaction):
        self.button_answer = False
        await self.clear_view_of_interaction()
        self.stop()
    async def on_timeout(self):
        await self.clear_view_of_interaction()
        embed = chadcounting_embed(title=self.title)
        embed.add_field(name="", value="Timeout: you didn't give an answer. No changes were made.")
        await self.interaction.followup.send(embed=embed, ephemeral=True)

class ViewHelpButtons(View):
    """Makes a view with some helpful links for the help command."""
    def __init__(self):
        super().__init__()
        buttons = [
            {"label": "More information", "url": "https://github.com/Gitfoe/ChadCounting", "emoji": "ℹ️"},
            {"label": "Vote on top.gg", "url": "https://top.gg/bot/1066081427935993886/vote", "emoji": "⬆️"},
            {"label": "Vote on discordbotlist", "url": "https://discordbotlist.com/bots/chadcounting/upvote", "emoji": "⬆️"},
        ]
        for button in buttons:
            self.add_item(Button(**button))

#endregion

#region Discord commands
async def setup_grouped_commands(bot: commands.Bot) -> None:
  """Initializes the commands grouped into cogs."""
  await bot.add_cog(SetCog(bot))
  await bot.add_cog(CountCog(bot))
  await bot.add_cog(StatsCog(bot))

@bot.tree.command(name="help", description="Gives information about ChadCounting.")
async def help(interaction: discord.Integration):
    try:
        view = ViewHelpButtons()
        embed = chadcounting_embed("Welcome to ChadCounting", "ChadCounting is a Discord bot designed to facilitate collaborative counting. With its focus on accuracy and reliability, ChatCounting is the ideal choice for gigachads looking to push their counting abilities to the limit. You're a chad, aren't you? If so, welcome, and start counting in the counting channel!")
        embed.add_field(name="Slash commands", value="Because this bot makes use of the newest Discord technology, you can use slash commands! The slash commands describe what they do and how to use them. Just type `/` in the chat and see all the commands ChadCounting has to offer.", inline=False)
        embed.add_field(name="Rules", value="In this counting game, users take turns counting with the next number. Double counting by the same user is not allowed. You can use the command `/set banning` to see this server's configured rules for incorrect counts.", inline=False)
        embed.add_field(name="Counting feedback", value="After a user counts, the bot will respond with emoji to indicate if the count was correct or not. If the bot is unavailable (e.g. due to maintenance) and doesn't respond, you can still continue counting as it will catch up on missed counts upon its return. If you're unsure of the current recorded count, use the command `/count current` to check.", inline=False)
        embed.add_field(name="Voting", value="Voting is one of the best ways to support ChadCounting and help it reach more servers. Show your love for accurate counting by casting your vote! You can vote every 12 hours.", inline=False)
        embed.set_footer(text=f"ChadCounting version {bot_version}")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    except Exception as e:
        await command_exception(interaction, e)

class SetCog(commands.GroupCog, name="set", description="Admins only: sets and configures various settings for ChadCounting."):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name="channel", description="Admins only: sets the channel for ChadCounting to the current channel.")
    async def set_channel(self, interaction: discord.Integration) -> None:
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
                embed = chadcounting_embed("ChadCounting channel set")
                embed.add_field(name="", value=f"The counting channel is now **'{interaction.channel}'**.")
            else:
                embed = chadcounting_embed("ChadCounting channel not set")
                embed.add_field(name="", value="Sorry, you don't have the rights to change the channel for counting.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await command_exception(interaction, e)

    @app_commands.command(name="banning", description="Admins only: configure the banning settings. No parameters gives current settings.")
    @app_commands.describe(banning = "Enable or disable banning altogether. Default: True",
                        minimum_ban = "The minimum (or lowest) ban duration in minutes. Default: 1",
                        maximum_ban = "The maximum (or highest) ban duration in minutes. Default: 120",
                        ban_range = "The range/width of the exponentional banning curve. Lower values mean a wider curve. Default: 1.1",
                        troll_amplifier = "How much harder than the maximum ban duration a troll should be penalized for. Default: 7",
                        pass_doublecount = "Double counting by same user will be ignored (enabled) or penalized (disabled). Default: False")
    async def set_banning(self, interaction: discord.Integration, banning: bool=None,
                                                                  minimum_ban: int=None,
                                                                  maximum_ban: int=None,
                                                                  ban_range: float=None,
                                                                  troll_amplifier: int=None,
                                                                  pass_doublecount: bool=None) -> None:
        try:
            if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
                return
            global guild_data
            guild_id = interaction.guild.id
            embed = chadcounting_embed("Banning settings")
            changes_string = "\nNo changes were made to the banning settings. Try again, chad."
            # Check if any of the parameters have been entered
            configure = any([banning, minimum_ban, maximum_ban, ban_range, troll_amplifier, pass_doublecount])
            if configure and not interaction.user.guild_permissions.administrator:
                embed.add_field(name="", value="Sorry, you don't have the rights to change the banning settings.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
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
                    embed.add_field(name="", value=full_text)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                elif minimum_ban > s_maximum_ban:
                    full_text = ("You can't set the minimum ban duration higher than the maximum ban duration.\n" +
                                f"You tried to configure {minimum_ban} for the minimum duration and {s_maximum_ban} for the maximum duration.{changes_string}")
                    embed.add_field(name="", value=full_text)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
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
                    embed.add_field(name="", value=full_text)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                elif maximum_ban >= 1440:
                    view = ViewYesNoButtons(interaction)
                    view.title = embed.title
                    full_text = ("You entered a maximum ban duration of 1440 minutes (1 day) or more. Are you sure you want to do this? " +
                                "It is not possible to unban users, so users will potentially be banned for a very long time.")
                    embed.add_field(name="", value=full_text)
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                    await view.wait()
                    if view.button_answer == False:
                        full_text = "The new maximum ban duration has not been set. Please try again."
                        embed.clear_fields()
                        embed.add_field(name="", value=full_text)
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return
                    elif view.button_answer == None: # Timeout, no button was pressed
                        return
                    else:
                        guild_data[guild_id]["s_maximum_ban"] = maximum_ban
                        write_guild_data(guild_data) # Write already because troll_amplifier can also be called later
                else:
                    guild_data[guild_id]["s_maximum_ban"] = maximum_ban
            if ban_range != None:
                if ban_range < 1.001:
                    full_text = f"The banning range/width should be at least 1.001. You entered {ban_range}.{changes_string}"
                    embed.add_field(name="", value=full_text)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                else:
                    guild_data[guild_id]["s_ban_range"] = ban_range
            if troll_amplifier != None:
                if troll_amplifier >= 10:
                    view = ViewYesNoButtons(interaction)
                    view.title = embed.title
                    full_text = ("You entered a troll amplifier of 10x or more. Are you sure you want to do this? " +
                                "It is not possible to unban users, so users will potentially be banned for a very long time.")
                    embed.clear_fields()
                    embed.add_field(name="", value=full_text)
                    if interaction.response.is_done(): # Check if need to send followup because maximum_ban already sent message
                        view.followup_message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                    else:
                        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                    await view.wait()
                    if view.button_answer == False:
                        full_text = "The new troll amplifier has not been set. Please try again."
                        embed.clear_fields()
                        embed.add_field(name="", value=full_text)
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return
                    elif view.button_answer == None: # Timeout, no button was pressed
                        return
                    else:
                        guild_data[guild_id]["s_troll_amplifier"] = troll_amplifier
                elif troll_amplifier < 1 or troll_amplifier > 1337:
                    full_text = f"You must enter a troll amplifier between 1 and 1337. You entered {troll_amplifier}.{changes_string}"
                    embed.add_field(name="", value=full_text)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                else:
                    guild_data[guild_id]["s_troll_amplifier"] = troll_amplifier
            if pass_doublecount != None:
                guild_data[guild_id]["s_pass_doublecount"] = pass_doublecount
            # Import settings and format text
            s_banning = guild_data[guild_id]["s_banning"]
            s_minimum_ban = minutes_to_fancy_string(guild_data[guild_id]["s_minimum_ban"])
            s_maximum_ban = minutes_to_fancy_string(guild_data[guild_id]["s_maximum_ban"])
            s_ban_range = guild_data[guild_id]["s_ban_range"]
            s_troll_amplifier = guild_data[guild_id]["s_troll_amplifier"]
            s_pass_doublecount = guild_data[guild_id]["s_pass_doublecount"]
            setting_string = (f"**Banning enabled:** {s_banning}\n" +
                            f"**Minimum ban duration:** {s_minimum_ban}\n" +
                            f"**Maximum ban duration:** {s_maximum_ban}\n" +
                            f"**Ban range/width:** exponent of {s_ban_range} squared\n" +
                            f"**Troll amplifier:** {s_troll_amplifier}x\n" +
                            f"**Ignoring of double counts:** {s_pass_doublecount}")
            if configure:
                write_guild_data(guild_data)
                embed = chadcounting_embed(f"{interaction.user.name} changed the banning settings to the following")
                embed.add_field(name="", value=setting_string)
                if interaction.response.is_done(): # Check if last message needs to be a followup or normal response
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.response.send_message(embed=embed)
            else:
                embed = chadcounting_embed(title="Here you go, the current banning settings")
                embed.add_field(name="", value=setting_string)
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await command_exception(interaction, e)

    @app_commands.command(name="reactions", description="Admins only: configure the correct/incorrect count reactions. No parameters gives current settings.")
    @app_commands.describe(correct_reactions = "One or more emoji the bot will react with when someome counted correctly. Default: 🙂",
                           incorrect_reactions = "One or more emoji the bot will react with when someone messes up the count. Default: 💀")
    async def set_reactions(self, interaction: discord.Integration, correct_reactions: str=None, incorrect_reactions: str=None) -> None:
        try:
            if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
                return
            else:
                global guild_data
                guild_id = interaction.guild.id
                embed = chadcounting_embed("Reaction settings")
                # Check if any of the parameters have been entered
                configure = any([correct_reactions, incorrect_reactions])
                if configure and not interaction.user.guild_permissions.administrator:
                    full_text = "Sorry, you don't have the rights to change the bot's reactions."
                    embed.add_field(name="", value=full_text)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                if correct_reactions != None:
                    response = await handle_reaction_setting(interaction, correct_reactions, embed)
                    if response == None: # None or incorrect amount of emoji
                        return
                    guild_data[guild_id]["s_correct_reaction"] = response
                if incorrect_reactions != None:
                    response = await handle_reaction_setting(interaction, incorrect_reactions, embed)
                    if response == None: # None or incorrect amount of emoji
                        return
                    guild_data[guild_id]["s_incorrect_reaction"] = response
                s_correct_reactions = guild_data[guild_id]["s_correct_reaction"]
                s_incorrect_reactions = guild_data[guild_id]["s_incorrect_reaction"]
                s_correct_reactions = remove_unavailable_emoji(s_correct_reactions, "🙂")
                s_incorrect_reactions = remove_unavailable_emoji(s_incorrect_reactions, "💀")
                setting_string = (f"**Correct count reaction(s):** {''.join(str(i) for i in s_correct_reactions)}\n" +
                                f"**Incorrect count reaction(s):** {''.join(str(i) for i in s_incorrect_reactions)}\n")
                if configure:
                    write_guild_data(guild_data)
                    embed = chadcounting_embed(f"{interaction.user.name} changed ChadCounting's reactions to the following")
                    embed.add_field(name="", value=setting_string)
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = chadcounting_embed("Here you go, the current reactions")
                    embed.add_field(name="", value=setting_string)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await command_exception(interaction, e)

class CountCog(commands.GroupCog, name="count", description="Gives various counting statusses."):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name="current", description="Gives the current count in case you're unsure or want to double check.")
    async def count_current(self, interaction: discord.Integration) -> None:
        try:
            if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
                return
            current_count = guild_data[interaction.guild.id]["current_count"]
            embed = chadcounting_embed("Current count")
            embed.add_field(name="", value=f"The current count is **{current_count}**. So what should the next number be? That's up to you chads.")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await command_exception(interaction, e)

    @app_commands.command(name="highest", description="Gives the highest count that has been achieved in this Discord server.")
    async def count_highest(self, interaction: discord.Integration) -> None:
        try:
            if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
                return
            guild_id = interaction.guild.id
            highest_count = guild_data[guild_id]["highest_count"]
            current_count = guild_data[guild_id]["current_count"]
            average_count = round(calculate_average_count_of_guild(guild_id), 2)
            amount_of_attempts = len(guild_data[guild_id]["previous_counts"])
            full_text = f"The high score is **{highest_count}**. "
            points = 0 # Points get calculated for the last suffix
            if highest_count > current_count:
                full_text += f"That's **{highest_count - current_count}** higher than the current count... "
            else:
                full_text += "That's exactly the same as the current count! "
                if highest_count >= 27: # Only award points if it's higher than or equal to 27
                    points += 1
            full_text += f"On average you lads counted to **{average_count}**, and your current count is "
            if current_count > average_count:
                full_text += f"**{round(current_count - average_count, 2)}** higher than the average. "
                points += 2 if average_count >= 27 else 1 # Award less points if average not at least 27
            elif current_count < average_count:
                full_text += f"**{round(average_count - current_count, 2)}** lower than the average... "
            else:
                full_text += "exactly the same as the average. "
                if average_count >= 27: # Only award points if average is higher than or equal to 27
                    points += 1
            full_text += f"You lads messed up the count **{amount_of_attempts}** "
            full_text += "time. " if amount_of_attempts == 1 else "times. "
            full_text += {0: "Do better, beta's.", 
                        1: "Decent work.", 
                        2: "Well done.", 
                        3: "Excellent work, chads!"}.get(points, "")
            embed = chadcounting_embed(title="Counting high score")
            embed.add_field(name="", value=full_text)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await command_exception(interaction, e)

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
        full_text += "Use the command `/set banning` to see the currently configured banning settings."
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
        ax.set_title(title_text, fontsize=adjust_font_size(title_text, 14), color="#FFFFFF")
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
        # Send embed with image in it
        filename = f"ChadCounting-banrate-{guild_id}-{timestamp}.png"
        file = discord.File(img, filename)
        embed = chadcounting_embed("Banning rate")
        embed.add_field(name="", value=full_text)
        embed.set_image(url=f"attachment://{filename}")
        await interaction.response.send_message(file=file, embed=embed)
    except Exception as e:
        await command_exception(interaction, e)

class StatsCog(commands.GroupCog, name="stats", description="Gives various counting statistics."):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name="user", description="Gives counting statistics of a user for this Discord server.")
    @app_commands.describe(user="Optional: the user you want to check the stats of.")
    async def stats_user(self, interaction: discord.Integration, user: discord.Member=None) -> None:
        try:
            if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
                return
            guild_id = interaction.guild.id
            if user == None: # No user entered, so check the caller
                user_id = interaction.user.id
                username = interaction.user.name
                username_mention = interaction.user.mention
            else:
                user_id = user.id
                username = user.name
                username_mention = user.mention
            if user_id not in guild_data[guild_id]["users"]:
                full_text = f"I can't give you the stats of {username_mention}, because they haven't participated in ChadCounting yet. Shame."
                embed = chadcounting_embed(title="User statistics")
                embed.add_field(name="", value=full_text)
                await interaction.response.send_message(embed=embed)
            else:
                # Define statistics
                correct_counts = guild_data[guild_id]["users"][user_id]["correct_counts"]
                incorrect_counts = guild_data[guild_id]["users"][user_id]["incorrect_counts"]
                total_counts = correct_counts + incorrect_counts
                if total_counts > 0:
                    percent_correct = round((correct_counts / (total_counts)) * 100, 2)
                else:
                    percent_correct = "N/A"
                active_in_guilds = 0
                for values in guild_data.values():
                    if user_id in values["users"]:
                        active_in_guilds += 1
                thresholds = {99.5: "What an absolute gigachad.",
                              95: "Chad performance.",
                              90: "Not bad, not good.",
                              80: "Nearing beta performance. Do better.",
                              70: "Definitely not chad performance."}
                chad_level = "Full beta performance. Become chad." # Default value if lower than lowest threshold
                for threshold, message in thresholds.items():
                    if percent_correct >= threshold:
                        chad_level = message
                        break
                # End of defining statistics
                full_text = (f"**Correct counts:** {correct_counts}\n" +
                            f"**Incorrect counts:** {incorrect_counts}\n" + 
                            f"**Total counts:** {total_counts}\n" +
                            f"**Percent correct:** {percent_correct}%\n" +
                            f"**Active in Discord servers:** {active_in_guilds}")
                embed = chadcounting_embed(f"Here you go, the user statistics of {username}")
                embed.add_field(name="", value=full_text)
                embed.set_footer(text=chad_level)
                await interaction.response.send_message(embed=embed)
        except Exception as e:
            await command_exception(interaction, e)

    @app_commands.command(name="server", description="Gives counting statistics of this Discord server.")
    async def stats_server(self, interaction: discord.Integration) -> None:
        try:
            if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
                return
            guild_id = interaction.guild.id
            users = guild_data[guild_id]["users"]
            user_list = [(user_id, user_data["correct_counts"], user_data["incorrect_counts"]) for user_id, user_data in users.items()]
            sorted_user_list = sorted(user_list, key=lambda x: (x[1] + x[2], x[1]), reverse=True)
            full_text = ""
            for i, user in enumerate(sorted_user_list[:10]):
                user_id, correct_counts, incorrect_counts = user
                user_id = await bot.fetch_user(user_id)
                total_counts = correct_counts + incorrect_counts
                if total_counts > 0:
                    percent_correct = round((correct_counts / (total_counts)) * 100, 2)
                full_text += f"**{i+1}. {user_id}**{total_counts} total counts ({percent_correct}% correct) {correct_counts} correct and {incorrect_counts} incorrect counts\n"
            if len(full_text) > 0:
                embed = chadcounting_embed("Here you go, the server statistics")
                embed.add_field(name="", value=full_text)
            else:
                embed = chadcounting_embed("Server statistics")
                embed.add_field(name="", value="Nobody has participated in ChadCounting yet. Shame. Start counting!")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await command_exception(interaction, e)

    @app_commands.command(name="global", description="Gives counting statistics of this Discord server against other servers using ChadCounting.")
    async def serverstats(self, interaction: discord.Interaction) -> None:
        try:
            if not await check_bot_ready(interaction) or not await check_correct_channel(interaction):
                return
            guild_ids_bot_is_in = {guild.id for guild in bot.guilds}
            server_stats = [
                (
                    guild_id,
                    guild_data[guild_id]["highest_count"],
                    total_counts := sum(user_data["correct_counts"] + user_data["incorrect_counts"] for user_data in users["users"].values()),
                    round((sum(user_data["correct_counts"] for user_data in users["users"].values()) / total_counts) * 100, 2) if total_counts > 0 else 0,
                    guild_data[guild_id]["current_count"]
                )
                for guild_id, users in guild_data.items() if guild_id in guild_ids_bot_is_in
            ]
            sorted_server_stats = sorted(server_stats, key=lambda x: (x[3], x[2], x[1]), reverse=True)[:10]
            full_text = "\n".join(
                f"**{i+1}. {discord.utils.get(bot.guilds, id=guild_id).name}**Highest count: {highest_count}, total: {total_counts} ({percent_correct}% correct), current: {current_count}"
                for i, (guild_id, highest_count, total_counts, percent_correct, current_count) in enumerate(sorted_server_stats)
            )
            embed = chadcounting_embed("Here you go, the best servers on ChadCounting")
            embed.add_field(name="", value=full_text if full_text else "No servers have participated in ChadCounting yet. Shame. Start counting!")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await command_exception(interaction, e)
#endregion

#region APIs
def discordbotlist_api_authorization_header():
    """Base headers for the Discordbotlist API"""
    return {
        "Authorization": f"Bot {DISCORDBOTLIST_TOKEN}",
        "Content-Type": "application/json"
    }

def topgg_api_authorization_header():
    """Base headers for the Top.GG API."""
    return {
        "Authorization": TOPGG_TOKEN,
        "Content-Type": "application/json"
    }

def push_commands_to_discordbotlist():
    """Sends the bot's commands via the API."""
    if check_dev_disable_apis(push_commands_to_discordbotlist.__name__): return
    url = f"{api_discordbotslist}/commands"
    headers = discordbotlist_api_authorization_header()
    # Convert list of commands to json-serializable and API-understandable format
    commands_list = []
    for command in get_all_commands(bot):
        commands_list.append({"name": command.qualified_name, "description": command.description})
    response = requests.post(url, headers=headers, json=commands_list)
    print(f"[{datetime.now()}] {push_commands_to_discordbotlist.__name__}: API response {response.status_code}.")

def push_guilds_count_to_all_bot_websites():
    """Pushes the current guild count to all bot websites configured."""
    if check_dev_disable_apis(push_guilds_count_to_all_bot_websites.__name__): return
    discordbotlist_headers = discordbotlist_api_authorization_header()
    topgg_headers = topgg_api_authorization_header()
    push_guilds_count_to_bot_website(f"{api_discordbotslist}/stats", "guilds", discordbotlist_headers)
    push_guilds_count_to_bot_website(f"{api_topgg}/stats", "server_count", topgg_headers)

def push_guilds_count_to_bot_website(url, payload_string, headers):
    """Sends the number of guilds via the API."""
    payload = {payload_string: len(bot.guilds)}
    response = requests.post(url, headers=headers, json=payload)
    print(f"[{datetime.now()}] {push_guilds_count_to_bot_website.__name__}: {url} API response {response.status_code}.")
#endregion

bot.run(DEV_TOKEN)
# Coded by https://github.com/Gitfoe