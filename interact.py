import discord
from dotenv import load_dotenv
import os
import logging
from discord import app_commands
import llm_parse
from util import Util

LOG_HANDLER = logging.FileHandler(
    filename='discord.log', encoding='utf-8', mode='w')

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
        server_id = discord.Object(id=os.environ.get('DISCORD_SERVER_ID'))
        self.tree.copy_global_to(guild=server_id)
        await self.tree.sync(guild=server_id)


client = YWCCBot()


@client.event
async def on_ready():
    print(f'Logged in as {client.user}')


@client.tree.command(name='get_history', description='Get chat history from a specific message link onwards')
@app_commands.describe(message_url='The URL of the message to start history from')
async def get_chat_history(interaction: discord.Interaction, message_url: str):
    """Get chat history from a specific message link onwards."""
    await interaction.response.defer(ephemeral=False)
    try:
        try:
            parts = message_url.split('/')
            guild_id = int(parts[-3])
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
            guild = client.get_guild(guild_id)
            util = Util(client, guild)
        except ValueError as e:
            interaction.followup.send("Failed: Invalid URL")
            return
        channel = client.get_channel(channel_id)
        if channel is None or not (isinstance(channel, discord.TextChannel) or isinstance(channel, discord.Thread)):
            await interaction.followup.send("Channel not found.")
            return
        if message_id == None:
            message_id = channel.last_message_id

        if guild is None or not isinstance(guild, discord.Guild):
            await interaction.followup.send("Guild not found.")
            return
        start_message = await channel.fetch_message(message_id)
        messages = []
        messages.append(util.process(start_message))
        async for message in channel.history(after=start_message):
            messages.append(util.process(message))
        messages = "\n".join(messages)

        if messages:
            report: str = llm_parse.process_large_text(messages)
            footnote = f"\n> Generated from messages sent from {start_message.jump_url} to {message.jump_url} ({util.get_idx()} messages; {len(messages)} chars)"
            report += footnote
            await util.batch_reply(interaction, report)
        else:
            await interaction.followup.send(f"No messages found after the specified message. ({message_url})")
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}\n - Input: {message_url}")


@client.tree.command(name='get_last_x_messages', description='Get the last x messages from a channel')
@app_commands.describe(channel='The channel to get messages from', count='The number of messages to get')
async def get_last_x_messages(interaction: discord.Interaction, channel: discord.TextChannel, count: int):
    """Get the last x messages from a channel."""
    await interaction.response.defer(ephemeral=False)
    try:
        guild = channel.guild
        util = Util(client, guild)
        messages = []
        async for message in channel.history(limit=count):
            messages.append(util.process(message))
        messages = "\n".join(messages)
        if messages:
            report: str = llm_parse.process_large_text(messages)
            footnote = f"\n> Generated from the last {count} messages in {channel.mention} ({util.get_idx()} messages; {len(messages)} chars)"
            report += footnote
            await util.batch_reply(interaction, report)
        else:
            await interaction.followup.send(f"No messages found in {channel.mention}")
    except Exception as e:
        # e.with_traceback()
        await interaction.followup.send(f"An error occurred: {str(e)}")


@client.event
async def on_message(message):
    channel_id = os.environ.get('MODAMAIL_ID')
    util = Util(client, None)
    message = util.convert_mentions_to_string(message)
    # if (message.author.create_public_threads == False):
    #     logging.info(
    #         f"User {message.author} tried to create a thread but is not allowed to")
    #     await message.channel.send("The bot is not allowed to create threads for you. Please enable the 'Create Public Threads' permission for the bot.")
    #     return

    try:
        if message.guild is None and message.author.bot == False:
            user_id = await util.get_annon_id(str(hash(message.author)), str(message.author.id))
            user_id_str = str(user_id)
            channel = client.get_channel(int(channel_id))
            # get all the threads in the channel
            threads = channel.threads
            # get the names of the threads
            thread_names = [thread.name for thread in threads]
            # check if the user has a thread
            if len(thread_names) > 0 and f"Annonymous User {user_id_str}" in thread_names:
                thread = [thread for thread in threads if thread.name ==
                          f"Annonymous User {user_id_str}"][0]
                if (thread.archived == True or thread.locked == True):
                    new_message = await channel.send(
                        f"Annonymous User {user_id_str}")
                    thread = await channel.create_thread(name=f"Annonymous User {user_id_str}", message=new_message)
                await thread.send(f"Annonymous User: {message.content}")
                await message.add_reaction("📨")
            else:
                new_message = await channel.send(
                    f"Annonymous User {user_id_str}")
                thread = await channel.create_thread(name=f"Annonymous User {user_id_str}", message=new_message)
                await thread.send(f"Annonymous User: {message.content}")
                await message.add_reaction("📨")
        elif int(message.channel.parent_id) == int(channel_id) and message.author.bot == False:
            thread = message.channel
            user_id = int(thread.name.split(" ")[-1])
            discord_user_id = await util.get_user(user_id)
            user = client.get_user(int(discord_user_id))
            sender_name = message.author.display_name
            await user.send(f"{sender_name}: {message.content}")
            # react to the message
            await message.add_reaction("📨")
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        if message.author.bot == False:
            await message.channel.send(f"An error occurred: {str(e)}")

        # if a message is sent in the modamail channel in one of the threads, send it to the user


client.run(TOKEN, log_handler=LOG_HANDLER, log_level=logging.DEBUG)
