import discord
from dotenv import load_dotenv
import os
import logging
from discord import app_commands
import llm_parse
from util import Util
from typing import Literal
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
        # server_id = discord.Object(id=os.environ.get('DISCORD_SERVER_ID'))
        # self.tree.copy_global_to(guild=server_id) # comment this so that the commands are global and can be used in dms
        await self.tree.sync()


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

    try:
        if message.guild is None and message.author.bot == False:
            user_id = await util.get_annon_id(str(hash(message.author)), str(message.author.id))
            user_id_str = str(user_id)
            channel = client.get_channel(int(channel_id))
            # get all the threads in the channel
            threads = channel.threads
            # check if the user has a thread
            thread = [thread for thread in threads if thread.name ==
                      f"Annonymous User {user_id_str}"]
            if len(thread) == 1:
                thread = thread[0]
            else:
                thread = None
            if thread not in threads or thread.archived == True or thread.locked == True:
                # if the thread is archived, locked or not in the list of threads, create a new thread
                thread = await util.create_thread(channel, user_id_str)
            await thread.send(f"Annonymous User: {message.content}")
            await util.send_attachment(message, thread)
            await message.add_reaction("📨")
        elif int(message.channel.parent_id) == int(channel_id) and message.author.bot == False:
            thread = message.channel
            user_id = int(thread.name.split(" ")[-1])
            discord_user_id = await util.get_user(user_id)
            user = client.get_user(int(discord_user_id))
            sender_name = message.author.display_name
            await user.send(f"""**{sender_name}**   💬   in the {thread.name} thread
>>> {message.content}""")
            await util.send_attachment(message, user)
            # react to the message
            await message.add_reaction("📨")
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        if message.author.bot == False:
            await message.channel.send(f"An error occurred: {str(e)}")


# make a command that can be used in dms to make a new thread
@client.tree.command(name='new_conversation', description='Create a new thread on the modamail channel unaffected with past messages')
@app_commands.describe()
async def new_thread(interaction: discord.Interaction):
    """Create a new thread."""
    await interaction.response.defer(ephemeral=True)
    try:
        if interaction.guild is not None:
            await interaction.followup.send("This command can only be used in DMs, it creates a new thread in the modmail channel.")
            return
        channel_id = os.environ.get('MODAMAIL_ID')
        util = Util(client, None)
        user_id = await util.get_annon_id(str(hash(interaction.user)), str(interaction.user.id), new_conversion=True)
        user_id_str = str(user_id)
        channel = client.get_channel(int(channel_id))
        threads = channel.threads
        thread = [thread for thread in threads if thread.name ==
                  f"Annonymous User {user_id_str}"]
        if len(thread) == 1:
            thread = thread[0]
        else:
            thread = None
        if thread not in threads or thread.archived == True or thread.locked == True:
            thread = await util.create_thread(channel, user_id_str)
        await interaction.followup.send(f"Thread created, new messages will be sent to the new thread called \"{thread.name}\"")
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}")
# list the threads command


@client.tree.command(name='list_threads', description='List all the threads in the modamail channel that you have made')
async def list_threads(interaction: discord.Interaction):
    """List all the threads in the modamail channel."""
    await interaction.response.defer(ephemeral=True)
    try:
        if interaction.guild is not None:
            # await interaction.followup.send("This command can only be used in DMs, it lists all the threads you have created.", ephemeral=True)
            # make this only visible to the user, as a reply
            await interaction.followup.send("This command can only be used in DMs, it lists all the threads you have created.")
            return
        util = Util(client, None)
        thread_names = await util.get_rows_with_id(str(hash(interaction.user.id)))
        thread_names = [
            f"Annonymous User {thread_name}" for thread_name in thread_names]
        if len(thread_names) > 0:
            await interaction.followup.send(f"Threads: {', '.join(thread_names)}")
        else:
            await interaction.followup.send(f"No threads found.")
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}")


@client.tree.command(name='send_modmail', description='Send a message to a specific modmail thread')
async def send_modmail(interaction: discord.Interaction):
    """Send a message to a specific modmail thread."""
    await interaction.response.defer(ephemeral=True)
    try:
        if interaction.guild is not None:
            # make it only visible to the user
            await interaction.followup.send("This command can only be used in DMs, it sends a message to a specific modmail thread.")
            return
        channel_id = os.environ.get('MODAMAIL_ID')
        channel = client.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Modmail channel not found.")
            return

        async def get_thread_names(user_id):
            thread_data = [{"name": f"Annonymous User {thread_name}", "id": thread_name} for thread_name in await Util(client, None).get_rows_with_id(str(hash(user_id)))]
            return thread_data
        threads = await get_thread_names(interaction.user.id)
        if not threads:
            await interaction.followup.send("No active threads found.")
            return

        options = [discord.SelectOption(
            label=thread["name"], value=thread["id"]) for thread in threads]
        if not options:
            await interaction.followup.send("No available threads.")
            return

        class ThreadSelect(discord.ui.Select):
            def __init__(self, options):
                super().__init__(placeholder='Choose a thread...',
                                 min_values=1, max_values=1, options=options)

            async def callback(self, interaction: discord.Interaction):
                selected_thread_id = self.values[0]
                selected_thread = discord.utils.get(
                    channel.threads, name=f"Annonymous User {selected_thread_id}")
                if not selected_thread:
                    await interaction.response.send_message("Selected thread not found.", ephemeral=True)
                    return

                class ModmailModal(discord.ui.Modal, title="Send Modmail"):
                    message = discord.ui.TextInput(
                        label="Message", style=discord.TextStyle.paragraph)

                    async def on_submit(self, modal_interaction: discord.Interaction):
                        try:
                            await selected_thread.send(f"Annonymous User: {self.message.value}")
                            await Util(client, None).send_attachment(interaction.message, selected_thread)
                            new_message = await interaction.followup.send(f"Message sent to thread \"{selected_thread.name}\".", ephemeral=False)
                            await new_message.add_reaction("📨")
                            await modal_interaction.response.edit_message(content="Message sent.", view=None)
                        except Exception as e:
                            print(e)
                            # await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

                await interaction.response.send_modal(ModmailModal())

        select = ThreadSelect(options)
        view = discord.ui.View()
        view.add_item(select)
        await interaction.followup.send("Select a thread to send a message to:", view=view, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)


client.run(TOKEN, log_handler=LOG_HANDLER, log_level=logging.DEBUG)
