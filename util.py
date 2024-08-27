import discord
import re
import os
import json


class Util():
    """Utility class for processing messages and sending replies in Discord."""

    def __init__(self, client, guild):
        """Initialize the Util class with a Discord client and guild."""
        self.user_dict = {}
        self.client = client
        self.idxs = {}
        self.idx = 1
        self.last_ts = None
        self.guild = guild

    def get_name(self, id: int):
        """Get the name of a user by their ID. If the name is not cached, fetch it from the guild."""
        if id in self.user_dict:
            return self.user_dict[id]
        name = self.guild.get_member(id)
        if name == None:
            return "Unknown/Deleted User"
        name = name.nick
        name = name if name != None else self.client.get_user(
            id).display_name + "*"
        self.user_dict[id] = name
        return name

    def format_time_difference(self, start, end):
        """ Calculate the difference between two datetime objects"""
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

    def process_text(self, str):
        """Process a message text, replacing user pings with their names."""
        def replace_ping(match):
            """Replace a user ping with their name."""
            indices = match.regs[1]
            return '@' + self.get_name(int(match.string[indices[0]:indices[1]]))
        return re.sub(r'<@(\d+)>', replace_ping, str)

    def process(self, message: discord.Message):
        """Process a message, returning a formatted string representation of it."""
        self.idxs[message.id] = self.idx
        line = f"{self.idx}: "
        if self.last_ts != None:
            line += self.format_time_difference(self.last_ts,
                                                message.created_at)

        name = self.get_name(message.author.id)
        line += f" [{name}]: "

        if message.reference != None:
            line += f"(replyto: Msg {self.idxs.get(message.reference.message_id, '?')}) "

        line += self.process_text(message.content) + "\n"

        self.last_ts = message.created_at
        self.idx += 1
        return line

    def get_idx(self):
        """Getter for the idx variable"""
        return self.idx

    async def batch_reply(self, interaction: discord.Interaction, report: str):
        """Send a message in multiple parts if it exceeds the character limit."""
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

    async def verify_json_file_exists(self, file_name):
        """Check if a json file exists, if not create it"""
        if not os.path.exists(file_name):
            with open(file_name, "w") as file:
                file.write("{}")
        if os.stat(file_name).st_size == 0:
            with open(file_name, "w") as file:
                file.write("{}")

    async def get_annon_id(self, user_hash, user_id, new_conversion=False):
        """add a users hash to the db.json file, and return the index of current thread"""
        await self.verify_json_file_exists("db.json")
        with open("db.json", "r") as file:
            data = json.load(file)
            for key in data:
                # if the user hash is already in the db, return the index of the active thread
                if not new_conversion and user_hash == data[key]["hash"]:
                    for key in data:
                        if user_id == data[key]["id"] and data[key]["active"]:
                            print(key)
                            return key
                    return None

            data[str(len(data))] = {
                "hash": user_hash,
                "id": user_id,
                "index": len(data),
                "active": True
            }
            # set all other threads with the same user id to inactive
            for key in data:
                if user_id == data[key]["id"] and key != str(len(data) - 1):
                    data[key]["active"] = False

        with open("db.json", "w") as file:
            json.dump(data, file)
        return len(data) - 1

    async def get_user(self, row):
        """get a users id from the hash"""
        await self.verify_json_file_exists("db.json")
        with open("db.json", "r") as file:
            data = json.load(file)
            return data[str(row)]["id"]

    async def get_rows_with_id(self, user_id):
        """get all the rows with a user id"""
        await self.verify_json_file_exists("db.json")
        with open("db.json", "r") as file:
            data = json.load(file)
            rows = []
            for key in data:
                if user_id == data[key]["id"]:
                    rows.append(key)
            return rows

    async def set_active(self, thread_index, hash):
        """set a users thread to active, and all other threads with the same user id to inactive"""
        await self.verify_json_file_exists("db.json")
        with open("db.json", "r") as file:
            arr = json.load(file)
            for obj in arr:
                if arr[obj]["hash"] == hash and arr[obj]["index"] == thread_index:
                    arr[obj]["active"] = True
                elif arr[obj]["hash"] == hash:
                    arr[obj]["active"] = False
        with open("db.json", "w") as file:
            json.dump(arr, file)

    async def get_thread_by_index(self, index):
        """get a thread by its index"""
        with open("db.json", "r") as file:
            data = json.load(file)
            for key in data:
                if index == data[key]["index"]:
                    return key
            return None

    def convert_mentions_to_string(self, message: discord.Message):
        """Convert mentions in a message to string representations."""
        user_mentions = message.mentions
        role_mentions = message.role_mentions
        ping_regex = re.compile(r"<@!?(\d+)>")
        for user in user_mentions:
            message.content = message.content.replace(
                f"<@{user.id}>", user.name)
        for role in role_mentions:
            message.content = message.content.replace(
                f"<@&{role.id}>", role.name)
        message.content = message.content.replace("@everyone", "everyone")
        message.content = message.content.replace("@here", "here")
        # this will replace any other mentions with someone
        message.content = re.sub(ping_regex, "unknown user", message.content)
        return message

    async def create_thread(self, channel, user_id_str):
        new_message = await channel.send(
            f"Annonymous User {user_id_str}")
        thread = await channel.create_thread(name=f"Annonymous User {user_id_str}", message=new_message)
        return thread

    async def send_attachment(self, message, destination):
        if message.attachments:
            for attachment in message.attachments:
                file = await attachment.to_file()
                await destination.send(file=file)
