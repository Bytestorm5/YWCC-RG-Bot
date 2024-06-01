import discord
from dotenv import load_dotenv
import os
import logging
from discord import app_commands
import re
import llm_parse
from json_interact import JsonInteractor
import random
import string

LOG_HANDLER = logging.FileHandler(
    filename='discord.log', encoding='utf-8', mode='w')

load_dotenv()
TOKEN = os.environ.get('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

modmail_path = 'modmail.json'
modmail_info = JsonInteractor(modmail_path)
if not os.path.exists(modmail_path):
    modmail_info['channel'] = int(os.environ.get("MOD_CHANNEL"))
    modmail_info['users'] = {}
modmail_channel: discord.TextChannel = None

class YWCCBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix="ywcc!", intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        server_id = discord.Object(id=1229521003001024562)
        self.tree.copy_global_to(guild=server_id)
        await self.tree.sync(guild=server_id)


client = YWCCBot()


@client.event
async def on_ready():
    global modmail_channel
    modmail_channel = client.get_channel(modmail_info['channel'])
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        author_id = modmail_info['users'].get(str(message.author.id))
        if author_id == None:
            # Astronomical odds of a collision realistically but I aint taking chances
            while author_id == None or author_id in modmail_info['users']:
                author_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            modmail_info['users'][str(message.author.id)] = author_id
            modmail_info.update_file()
        
        if '\n' in message.content:
            content = f"**[{author_id}]:**\n>>> {message.content}"
        else:
            content = f"**[{author_id}]:** {message.content}"
        
        def replace_ping(match):
            try:
                indices = match.regs[1]
                id = int(match.string[indices[0]:indices[1]])
                name = client.get_user(id).display_name
                return '\@ ' + name
            except:
                return "[unresolved ping]"
        content = re.sub(r'<@(\d+)>', replace_ping, content)
        content = content.replace("@everyone", "`[mass ping]`")
        content = content.replace("@here", "`[mass ping]`")
        if len(content) <= 2000:
            await modmail_channel.send(content)
        else:
            lines = content.splitlines(keepends=True)
            current_chunk = ""
            for line in lines:
                if len(current_chunk) + len(line) > 2000:
                    await modmail_channel.send(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += line
            
        await message.add_reaction("📨")

async def _reply_modmail(id: str, sender_name: str, message:str):
    reverse_mapping = {v:k for k,v in modmail_info['users'].items()}
    target = client.get_user(int(reverse_mapping[id]))
    content = f"> Message from {sender_name} at YWCC Reform:\n{message}"
    if len(content) <= 2000:
        await target.send(content)
    else:
        lines = content.splitlines(keepends=True)
        current_chunk = ""
        for line in lines:
            if len(current_chunk) + len(line) > 2000:
                await target.send(current_chunk)
                current_chunk = line
            else:
                current_chunk += line
    
@client.tree.command(name='reply', description='Respond to an anonymous modmail message')
@app_commands.describe()
async def reply_modmail(interaction: discord.Interaction, id: str, message: str):
    await interaction.response.defer(ephemeral=False)
    await _reply_modmail(id, interaction.user.display_name, message)
    await interaction.followup.send("Sent!")

def format_time_difference(start, end):
    # Calculate the difference between two datetime objects
    delta = end - start
    total_seconds = int(delta.total_seconds())

    # Determine the time units to use for the difference
    if abs(total_seconds) < 60:
        return f"{total_seconds:+d} sec"
    elif abs(total_seconds) < 3600:
        minutes = total_seconds // 60
        return f"{minutes:+d} min"
    elif abs(total_seconds) < 86400:
        hours = total_seconds // 3600
        return f"{hours:+d} h"
    else:
        days = total_seconds // 86400
        return f"{days:+d} d"

# def preprocess_chats():

async def batch_reply(interaction: discord.Interaction, report: str):
    if len(report) <= 2000:
        await interaction.followup.send(report)
    else:
        interacted = False
        # Split the string into lines, preserving line breaks
        lines = report.splitlines(keepends=True)
        current_chunk = ""

        async def send(text):
            nonlocal interacted, interaction
            if not interacted:
                await interaction.followup.send(text)
                interacted = True
            else:
                await interaction.channel.send(text)

        for line in lines:
            if len(current_chunk) + len(line) > 2000:
                await send(current_chunk)
                current_chunk = line
            else:
                current_chunk += line
        await send(current_chunk)

@client.tree.command(name='get_history', description='Get chat history from a specific message link onwards')
@app_commands.describe(message_url='The URL of the message to start history from')
async def get_chat_history(interaction: discord.Interaction, message_url: str):
    user_dict = {}

    def get_name(id):
        if id in user_dict:
            return user_dict[id]
        name = guild.get_member(id).nick
        name = name if name != None else client.get_user(id).display_name + "*"
        user_dict[id] = name
        return name

    def process_text(str):
        def replace_ping(match):
            indices = match.regs[1]
            return '@' + get_name(int(match.string[indices[0]:indices[1]]))
        return re.sub(r'<@(\d+)>', replace_ping, str)
    await interaction.response.defer(ephemeral=False)
    try:
        try:
            message_count = None
            parts = message_url.split('/')
            guild_id = int(parts[-3])
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
        except ValueError as e:
            interaction.followup.send("Failed: Invalid URL")
            return

        channel = client.get_channel(channel_id)
        if channel is None or not (isinstance(channel, discord.TextChannel) or isinstance(channel, discord.Thread)):
            await interaction.followup.send("Channel not found.")
            return
        if message_id == None:
            message_id = channel.last_message_id

        guild = client.get_guild(guild_id)
        if guild is None or not isinstance(guild, discord.Guild):
            await interaction.followup.send("Guild not found.")
            return
        start_message = await channel.fetch_message(message_id)
        messages = []
        idxs = {}
        idx = 1
        last_ts = None

        def process(message: discord.Message):
            nonlocal idx, messages, last_ts, idxs, message_count
            idxs[message.id] = idx
            line = f"{idx}: "
            if last_ts != None:
                line += format_time_difference(last_ts, message.created_at)

            name = get_name(message.author.id)
            line += f" [{name}]: "

            if message.reference != None:
                line += f"(replyto: Msg {idxs.get(message.reference.message_id, '?')}) "

            line += process_text(message.content) + "\n"

            last_ts = message.created_at
            idx += 1
            return line

        
        messages.append(process(start_message))
        async for message in channel.history(after=start_message):
            messages.append(process(message))
        messages = "\n".join(messages)

        if messages:
            report: str = llm_parse.process_large_text(messages)
            footnote = f"\n> Generated from messages sent from {start_message.jump_url} to {message.jump_url} ({idx} messages; {len(messages)} chars)"
            report += footnote

            await batch_reply(interaction, report)
        else:
            await interaction.followup.send(f"No messages found after the specified message. ({message_url})")

    except Exception as e:
        # e.with_traceback()
        await interaction.followup.send(f"An error occurred: {str(e)}\n - Input: {message_url}")

@client.tree.command(name='get_last_x_messages', description='Get the last x messages from a channel')
@app_commands.describe(channel='The channel to get messages from', count='The number of messages to get')
async def get_last_x_messages(interaction: discord.Interaction, channel: discord.TextChannel, count: int):
    user_dict = {}

    def get_name(id):
        if id in user_dict:
            return user_dict[id]
        name = guild.get_member(id).nick
        name = name if name != None else client.get_user(id).display_name + "*"
        user_dict[id] = name
        return name

    def process_text(str):
        def replace_ping(match):
            indices = match.regs[1]
            return '@' + get_name(int(match.string[indices[0]:indices[1]]))
        return re.sub(r'<@(\d+)>', replace_ping, str)
    await interaction.response.defer(ephemeral=False)
    try:
        guild = channel.guild
        messages = []
        idxs = {}
        idx = 1
        last_ts = None

        def process(message: discord.Message):
            nonlocal idx, messages, last_ts, idxs, count
            idxs[message.id] = count - idx + 1
            line = f"{idx}: "
            if last_ts != None:
                line += format_time_difference(last_ts, message.created_at)

            name = get_name(message.author.id)
            line += f" [{name}]: "

            if message.reference != None:
                line += f"(replyto: Msg {idxs.get(message.reference.message_id, '?')}) "

            line += process_text(message.content) + "\n"

            last_ts = message.created_at
            idx += 1
            return line

        async for message in channel.history(limit=count):
            messages.append(process(message))
        messages = "\n".join(messages)

        if messages:
            report: str = llm_parse.process_large_text(messages)
            footnote = f"\n> Generated from the last {count} messages in {channel.mention} ({idx} messages; {len(messages)} chars)"
            report += footnote

            await batch_reply(interaction, report)
        else:
            await interaction.followup.send(f"No messages found in {channel.mention}")

    except Exception as e:
        # e.with_traceback()
        await interaction.followup.send(f"An error occurred: {str(e)}")


client.run(TOKEN, log_handler=LOG_HANDLER, log_level=logging.DEBUG)
