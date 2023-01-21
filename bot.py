import os
import discord
import json
from dotenv import load_dotenv

# Initialize variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
guild_data = {};

# Set the intents to corrospond with the Developer Bot page and declare the client
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    init_guild_data()

def init_guild_data():
    global guild_data
    try:
        with open("guild_data.json", "r") as f:
            file_content = f.read()
            if file_content:
                guild_data = json.loads(file_content)
    except FileNotFoundError:
        with open("guild_data.json", "w") as f:
            json.dump({}, f)
    except json.decoder.JSONDecodeError:
        raise Exception("There was an error decoding guild_data.json")
    finally:
        for guild in client.guilds:
            if guild.id not in guild_data: 
                guild_data[guild.id] = {"current_count": 0, "highest_count:": 0, "previous_user": None, "counting_channel": None}
        with open("guild_data.json", "w") as f:
            json.dump(guild_data, f)

@client.event
async def on_message(message):
    global guild_data
    # Check if the message has been sent by the bot itself, and if so, ignore the message
    if message.author == client.user:
        return
    elif message.content.isnumeric():
        guild_id = message.guild.id
        current_count = guild_data[guild_id]["current_count"]
        previous_user = guild_data[guild_id]["previous_user"]
        if message.author.id != previous_user:
            if message.content.startswith(str(current_count + 1)):
                current_count += 1
                previous_user = message.author.id
                guild_data[guild_id] = {"current_count": current_count, "previous_user": previous_user}
                await message.add_reaction('👍')
            else:
                await handle_incorrect_count(guild_id, message, current_count, previous_user)
        else:
            await handle_incorrect_count(guild_id, message, current_count, previous_user, True) 
    with open("guild_data.json", "w") as f:
        json.dump(guild_data, f)

async def handle_incorrect_count(guild_id, message, current_count, previous_user, is_repeated=False):
    prefix_text = f"What a beta move by {message.author.mention}."
    suffix_text = "Only gigachads should be in charge of counting. Please start again from 1."
    await message.add_reaction('👎')
    guild_data[guild_id] = {"current_count": 0, "previous_user": None}
    if is_repeated:
        await message.channel.send(f"{prefix_text} A user cannot count twice in a row. {suffix_text}")
    else:
        await message.channel.send(f"{prefix_text} That's not the right number, it should have been {current_count + 1}. {suffix_text}")

client.run(TOKEN)