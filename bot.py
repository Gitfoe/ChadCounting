import os
import discord
#from discord import app_commands
from discord.ext import commands
from datetime import date, datetime
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
guild_data = {};

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
    except Exception as e:
        print(e)
    init_guild_data()
    for guild in bot.guilds:
        await check_for_missed_counts(guild.id)

def init_guild_data():
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
            if guild.id not in guild_data: 
                guild_data[guild.id] = {"current_count": 0,
                                        "highest_count": 0,
                                        "previous_user": None,
                                        "previous_message": None,
                                        "counting_channel": None}
        with open("guild_data.json", "w") as f:
            json.dump(guild_data, f, cls=DateTimeEncoder)

async def check_for_missed_counts(guild_id):
    last_message = guild_data[guild_id]["previous_message"]
    if last_message != None:
        counting_channel = bot.get_channel(guild_data[guild_id]["counting_channel"])
        async for message in counting_channel.history(limit=1000, after=last_message):
            await check_count_message(message)

@bot.tree.command(name="setchannel", description="Administratos only: sets the channel where the bot needs to keep track of counting.")
async def setchannel(interaction: discord.Integration):
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

@bot.event
async def on_message(message):
    await check_count_message(message)

async def check_count_message(message):
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
            else:
                await handle_incorrect_count(guild_id, message, current_count, highest_count)
        else:
            await handle_incorrect_count(guild_id, message, current_count, highest_count, True) 
        with open("guild_data.json", "w") as f:
            json.dump(guild_data, f, cls=DateTimeEncoder)

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

async def handle_incorrect_count(guild_id, message, current_count, highest_count, is_repeated=False):
    guild_data[guild_id]["current_count"] = 0
    guild_data[guild_id]["previous_user"] = None
    guild_data[guild_id]["previous_message"] = None
    await message.add_reaction("💀")
    await message.add_reaction("⚠️")
    await message.add_reaction("🇳")
    await message.add_reaction("🇴")
    await message.add_reaction("❗")
    await message.add_reaction("☠️")
    prefix_text = f"What a beta move by {message.author.mention}."
    suffix_text = "Only gigachads should be in charge of counting. Please start again from 1."
    if is_repeated:
        full_text= f"{prefix_text} A user cannot count twice in a row. {suffix_text}"
    else:
        full_text = f"{prefix_text} That's not the right number, it should have been {current_count + 1}. {suffix_text}"
    if highest_count == current_count:
        full_text += f" The high score is now {highest_count}."
    else:
        full_text += f" The high score is {highest_count}."
    await message.channel.send(full_text)

bot.run(TOKEN)