import discord
from dotenv import load_dotenv
import os
import logging
from discord import app_commands
import re
import llm_parse

LOG_HANDLER = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

load_dotenv()
TOKEN = os.environ.get('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True


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
    print(f'Logged in as {client.user}')

# @client.event
# async def on_message(message):
#     if message.author == client.user:
#         return

#     if message.content.startswith('$hello'):
#         await message.channel.send('Hello!')

    

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

#def preprocess_chats():

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
            message_count = int(message_url)
            channel_id = interaction.channel_id
            guild_id = interaction.guild_id
            message_id = None
        except ValueError as e:           
            message_count = None
            parts = message_url.split('/')
            guild_id= int(parts[-3])
            channel_id = int(parts[-2])
            message_id = int(parts[-1])

        channel = client.get_channel(channel_id)
        if channel is None or not (isinstance(channel, discord.TextChannel) or isinstance(channel, discord.Thread)):
            await interaction.response.send_message("Channel not found.")
            return
        if message_id == None:
            message_id = channel.last_message_id

        guild = client.get_guild(guild_id)
        if guild is None or not isinstance(guild, discord.Guild):
            await interaction.response.send_message("Guild not found.")
            return
        start_message = await channel.fetch_message(message_id)
        messages = []
        idxs = {}
        idx = 1
        last_ts = None
        def process(message: discord.Message, reverse=False):
            nonlocal idx, messages, last_ts, idxs, message_count
            idxs[message.id] = idx if not reverse else message_count - idx + 1
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
        
        if message_count == None:
            messages.append(process(start_message))
            async for message in channel.history(after=start_message):    
                messages.append(process(message))
        else:
            async for message in channel.history(before=start_message, limit=message_count):    
                messages.append(process(message, reverse=True))
            messages = list(reversed(messages))
        messages = "\n".join(messages)
        
        if messages:            
            report: str = llm_parse.process_large_text(messages)
            footnote = f"\n> Generated from messages sent from {start_message.jump_url} to {message.jump_url} ({idx} messages; {len(messages)} chars)"
            report += footnote
            
            if len(report) <= 2000:            
                await interaction.followup.send(report)
            else:
                interacted = False
                lines = report.splitlines(keepends=True)  # Split the string into lines, preserving line breaks
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
        else:
            await interaction.followup.send(f"No messages found after the specified message. ({message_url})")

    except Exception as e:
        #e.with_traceback()
        await interaction.followup.send(f"An error occurred: {str(e)}\n - Input: {message_url}")
client.run(TOKEN, log_handler=LOG_HANDLER, log_level=logging.DEBUG)