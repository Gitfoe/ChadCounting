import os
import discord
from discord import app_commands
from discord.ext import commands
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
guild_data = {};

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
    except Exception as e:
        print(e)
    init_guild_data()

def init_guild_data():
    global guild_data
    try:
        with open("guild_data.json", "r") as f:
            file_content = f.read()
            if file_content:
                guild_data = json.loads(file_content)
                guild_data = {int(k): v for k, v in guild_data.items()}
    except FileNotFoundError:
        with open("guild_data.json", "w") as f:
            json.dump({}, f)
    except json.decoder.JSONDecodeError:
        raise Exception("There was an error decoding guild_data.json")
    finally:
        for guild in bot.guilds:
            if guild.id not in guild_data: 
                guild_data[guild.id] = {"current_count": 0, "highest_count:": 0, "previous_user": None, "counting_channel": None}
        with open("guild_data.json", "w") as f:
            json.dump(guild_data, f)

@bot.tree.command(name="setchannel")
async def setchannel(interaction: discord.Integration):
    if interaction.user.guild_permissions.administrator:
        global guild_dat
        await interaction.response.send_message(f"The channel for ChadCounting has been set to {interaction.channel}.", ephemeral=True)
        guild_data[interaction.guild.id]["counting_channel"] = interaction.channel_id
        with open("guild_data.json", "w") as f:
            json.dump(guild_data, f)
    else:
        await interaction.response.send_message("Sorry, you don't have the rights to change the channel for counting.")

@bot.event
async def on_message(message):
    global guild_data
    if message.author == bot.user:
        return
    elif message.channel.id == guild_data[message.guild.id]["counting_channel"] and message.content[0].isnumeric():
        guild_id = message.guild.id
        current_count = guild_data[guild_id]["current_count"]
        previous_user = guild_data[guild_id]["previous_user"]
        if message.author.id != previous_user:
            if message.content.startswith(str(current_count + 1)):
                current_count += 1
                previous_user = message.author.id
                guild_data[guild_id]["current_count"] = current_count
                guild_data[guild_id]["previous_user"] = previous_user
                await message.add_reaction("🙂")
            else:
                await handle_incorrect_count(guild_id, message, current_count, previous_user)
        else:
            await handle_incorrect_count(guild_id, message, current_count, previous_user, True) 
        with open("guild_data.json", "w") as f:
            json.dump(guild_data, f)

async def handle_incorrect_count(guild_id, message, current_count, previous_user, is_repeated=False):
    prefix_text = f"What a beta move by {message.author.mention}."
    suffix_text = "Only gigachads should be in charge of counting. Please start again from 1."
    await message.add_reaction("💀")
    guild_data[guild_id]["current_count"] = 0
    guild_data[guild_id]["previous_user"] = None
    if is_repeated:
        await message.channel.send(f"{prefix_text} A user cannot count twice in a row. {suffix_text}")
    else:
        await message.channel.send(f"{prefix_text} That's not the right number, it should have been {current_count + 1}. {suffix_text}")

bot.run(TOKEN)