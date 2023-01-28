#region Python imports
import os
import re
import math
import json
import copy
import emoji
import discord
import traceback
import statistics
from datetime import datetime
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
#endregion

#region Initialisation
# For developing only
dev_mode = True # Make the bot only active in a certain guild
dev_mode_guild_id = 574350984495628436 # Bot must be in this guild already
update_guild_data = True # Forces updating of newly added guild_data values after a ChadCounting update

# Initialize variables from environment tables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
guild_data = {} # DB

# Initialize bot and intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
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
    print("ChadCounting is ready.")

@bot.event
async def on_message(message):
    """Discord event that gets triggered once a message is sent."""
    await check_count_message(message)

@bot.event
async def on_guild_join(guild):
    """When a new guild adds the bot, this function is called, and the bot is added to guild_data."""
    add_guild_to_guild_data(guild)
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
    # Ignores messages sent by ChadCounting, and if dev_mode is on, exit if message is not from dev mode guild
    if message.author == bot.user or dev_mode and not message.guild.id == dev_mode_guild_id:
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
            await message.reply(f"You are still banned from counting for {current_user_ban_string}, you beta.")
        # End of ban logic
        else:
            if current_user != previous_user:
                if message.content.startswith(str(current_count + 1)):
                    guild_data[guild_id]["current_count"] += 1
                    guild_data[guild_id]["users"][current_user]["correct_counts"] += 1
                    guild_data[guild_id]["previous_user"] = current_user
                    guild_data[guild_id]["previous_message"] = message.created_at
                    if highest_count < current_count: # New high score
                        guild_data[guild_id]["highest_count"] = current_count
                    # Acknowledge a correct count
                    correct_reactions = guild_data[guild_id]["s_correct_reaction"]
                    for r in correct_reactions:
                        await message.add_reaction(r)
                    # React with a funny emoji if ( ͡° ͜ʖ ͡°) is in the number
                    if str(current_count).find("69") != -1:
                        await message.add_reaction("💦")
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
            current_user_minutes_ban = calculate_user_penalization(current_count, average_count, minimum_ban, maximum_ban, ban_range, troll_amplifier, message_count)
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
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        file = f"{file}.bak{timestamp}"
        try:
            with open(file, "r") as f:
                return # Stop backing up if file already exists
        except FileNotFoundError:
            pass # Continue if file doesn't exist
        except Exception as e:
            print(e)
    with open(file, "w") as f:
        json.dump(guild_data, f, cls=DateTimeEncoder)

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
        write_guild_data(copy_guild_data, True) # Force a backup because changes were made
        write_guild_data(guild_data) # 
        full_text = f"Successfully added {added}, changed {changed}, and deleted {deleted} values "
        if user_id == None:
            full_text += f"for guild {guild_id}."
        else:
            full_text += f"for user {user_id} in guild {guild_id}."
        print(full_text)

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
        write_guild_data(guild_data)
        print(f"New guild {guild_id} successfully added.")
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
        write_guild_data(guild_data)
        (f"New user {user_id} successfully added to guild {guild_id}.")
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
    if match:
        message_count_int = int(match.group())
    else:
        message_count_int = current_count
    # Math to calculate the ban time based on the average count and the current count
    difference_from_average = abs(current_count - average_count)
    difference_from_current = abs(current_count - message_count_int)
    minutes_ban = math.pow(ban_range, difference_from_average)
    # Return the ban time in minutes
    if difference_from_current > 72 and current_count * 7 < message_count_int:
        # Penalize hard if the entered count is more than 7x or 72 off from the actual count
        return maximum_ban * troll_amplifier
    elif minutes_ban >= minimum_ban and minutes_ban <= maximum_ban:
        return round(minutes_ban)
    elif minutes_ban > minimum_ban:
        return maximum_ban
    else:
        return 0

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
        channel_error = f"You can only execute ChadCounting commands in the counting channel, which is '{counting_channel}'."
        await interaction.response.send_message(channel_error, ephemeral=True)
        return False
    elif counting_channel == None:
        channel_error = (f"You can only execute ChadCounting commands in the counting channel, however, it has not been set yet. " +
                         f"If you are an admin of this server, use the command /setchannel in the channel you want to count in.")
        await interaction.response.send_message(channel_error, ephemeral=True)
        return False
    else:
        return True

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
@bot.tree.command(name="setchannel", description="Admins only: sets the channel for ChadCounting to the current channel.")
async def setchannel(interaction: discord.Integration):
    try:
        if interaction.user.guild_permissions.administrator:
            global guild_dat
            guild_id = interaction.guild.id
            guild_data[guild_id]["counting_channel"] = interaction.channel_id
            if guild_data[guild_id]["previous_message"] == None: # Set last message to now if no message has ever been recorded
                guild_data[guild_id]["previous_message"] = datetime.now()
            write_guild_data(guild_data)
            await interaction.response.send_message(f"The channel for ChadCounting has been set to {interaction.channel}.", ephemeral=True)
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
        if not await check_correct_channel(interaction):
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sorry, you don't have the rights to change the banning settings.", ephemeral=True)
        else:
            global guild_data
            guild_id = interaction.guild.id
            configure = False # Check if any of the parameters have been entered
            changes_string = "\nNo changes were made to the banning settings. Try again, chad."
            if banning != None:
                configure = True
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
                    configure = True
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
                    configure = True
                    guild_data[guild_id]["s_maximum_ban"] = maximum_ban
            if ban_range != None:
                if ban_range < 1.05:
                    full_text = f"The banning range/width should be more than 1.05. You entered {ban_range}.{changes_string}"
                    await interaction.response.send_message(full_text, ephemeral=True)
                    return
                else:
                    configure = True
                    guild_data[guild_id]["s_ban_range"] = ban_range
            if troll_amplifier != None:
                if troll_amplifier < 1 or troll_amplifier > 1337:
                    full_text = f"You must enter a troll amplifier between 1 and 1337. You entered {troll_amplifier}.{changes_string}"
                    await interaction.response.send_message(full_text, ephemeral=True)
                    return
                else:
                    configure = True
                    guild_data[guild_id]["s_troll_amplifier"] = troll_amplifier
            if pass_doublecount != None:
                configure = True
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
                full_text = f"Successfully changed the banning settings to the following:\n{setting_string}"
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
        if not await check_correct_channel(interaction):
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sorry, you don't have the rights to change the bot reactions.", ephemeral=True)
        else:
            global guild_data
            guild_id = interaction.guild.id
            configure = False # Check if any of the parameters have been entered
            if correct_reactions != None:
                response = await handle_reaction_setting(interaction, correct_reactions)
                if response == None:
                    return
                guild_data[guild_id]["s_correct_reaction"] = response
            if incorrect_reactions != None:
                response = await handle_reaction_setting(interaction, incorrect_reactions)
                if response == None:
                    return
                guild_data[guild_id]["s_incorrect_reaction"] = response    
            s_correct_reactions = guild_data[guild_id]["s_correct_reaction"]
            s_incorrect_reactions = guild_data[guild_id]["s_incorrect_reaction"]
            setting_string = (f"> Correct count reaction(s): {''.join(str(i) for i in s_correct_reactions)}\n" +
                              f"> Incorrect count reaction(s): {''.join(str(i) for i in s_incorrect_reactions)}\n")
            if configure:
                write_guild_data(guild_data)
                full_text = f"Successfully changed the reactions to the following:\n{setting_string}"
            else:
                full_text = f"Here you go, the current reactions:\n{setting_string}"
            await interaction.response.send_message(full_text, ephemeral=True)
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="currentcount", description="Gives the current count in case you're unsure or want to double check.")
async def currentcount(interaction: discord.Integration):
    try:
        if not await check_correct_channel(interaction):
            return
        current_count = guild_data[interaction.guild.id]["current_count"]
        await interaction.response.send_message(f"The current count is {current_count}. So what should the next number be? That's up to you, chad.")
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="highscore", description="Gives the highest count that has been achieved in this Discord server.")
async def highscore(interaction: discord.Integration):
    try:
        if not await check_correct_channel(interaction):
            return
        highest_count = guild_data[interaction.guild.id]["highest_count"]
        current_count = guild_data[interaction.guild.id]["current_count"]
        average_count = round(calculate_average_count_of_guild(interaction.guild.id), 2)
        full_text = f"The high score is {highest_count}. "
        points = 0 # Points get calculated for the last suffix.
        if highest_count > current_count:
            full_text += f"That's {highest_count - current_count} higher than the current count... "
        else:
            full_text += "That's exactly the same as the current count! "
            points += 1
        full_text += f"On average you lads counted to {average_count}, and your current count is "
        if current_count > average_count:
            full_text += f"{round(current_count - average_count, 2)} higher than the average. "
            points += 2
        elif current_count < average_count:
            full_text += f"{round(average_count - current_count, 2)} lower than the average... "
        else:
            full_text += "exactly the same as the average. "
            points += 1
        if points == 0:
            full_text += "Do better, beta's."
        elif points == 1:
            full_text += "Decent work."
        elif points == 2:
            full_text += "Well done."
        elif points >= 3:
            full_text += "Excellent work, chads!"
        await interaction.response.send_message(full_text)
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="banrate", description="Gives a list of the different ban levels showing the consequences of messing up the count.")
async def banrate(interaction: discord.Integration):
    try:
        if not await check_correct_channel(interaction):
            return
        global guild_data
        guild_id = interaction.guild.id
        banning = guild_data[guild_id]["s_banning"]
        if banning:
            first_message = "Banning is currently enabled, beware! Here's the current banrate, you chad:\n```"
        else:
            first_message = "Banning is currently disabled, however, if it were enabled, here's the banrate:\n```"
        consecutive_message = "Here's the continuation of the previous ban rate levels:\n```"
        ban_levels_list = [first_message]
        current_count = 0 # Start at calculating the count from 0
        message_index = 0 # Since there is a 2000 character message limit on Discord
        average_count = calculate_average_count_of_guild(guild_id)
        minimum_ban = guild_data[guild_id]["s_minimum_ban"]
        maximum_ban = guild_data[guild_id]["s_maximum_ban"]
        ban_range = guild_data[guild_id]["s_ban_range"]
        troll_amplifier = guild_data[guild_id]["s_troll_amplifier"]
        current_level = maximum_ban / 2 # Arbritrary level to simulate a do/while loop
        while current_count <= average_count or current_level >= minimum_ban and current_level < maximum_ban:
            current_level = calculate_user_penalization(current_count, average_count, minimum_ban, maximum_ban, ban_range, troll_amplifier)
            current_level_fancy = minutes_to_fancy_string(current_level, True)
            ban_level_string = f"Count {current_count}: {current_level_fancy} ban\n"
            if not len(ban_levels_list[message_index]) + len(ban_level_string) + 3 <= 2000: # 3 for the ```code block
                ban_levels_list[message_index] += "```" # End the level with a quote block
                message_index += 1
                ban_levels_list.append(consecutive_message)
            ban_levels_list[message_index] += ban_level_string
            current_count += 1
        ban_levels_list[message_index] += f"```Messing up at any later counts will result in a ban of {current_level_fancy}."
        for index, level in enumerate(ban_levels_list):
            if index == 0:
                await interaction.response.send_message(level, ephemeral=True)
            else:
                await interaction.followup.send(level, ephemeral=True)
    except Exception:
        await command_exception(interaction)

@bot.tree.command(name="userstats", description="Gives counting statistics of a user for this Discord server.")
@app_commands.describe(user = "Optional: the user you want to check the stats of.")
async def userstats(interaction: discord.Integration, user: discord.Member=None):
    try:
        if not await check_correct_channel(interaction):
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
        if not await check_correct_channel(interaction):
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

bot.run(TOKEN)