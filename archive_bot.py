"""
Discord archive bot
-------------------
Copies every message sent in the server into an archive channel.

Setup:
    pip install discord.py python-dotenv

Create a .env file next to this script:
    DISCORD_TOKEN=your-bot-token
    ARCHIVE_CHANNEL_ID=123456789012345678
    ONLY_USER_ID=                # optional: only archive this user's messages
    DELETE_ORIGINAL=false        # optional: true = "move" instead of "copy"
"""

import os

import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]
ARCHIVE_CHANNEL_ID = int(os.environ["ARCHIVE_CHANNEL_ID"])
ONLY_USER_ID = int(os.getenv("ONLY_USER_ID") or 0)
DELETE_ORIGINAL = os.getenv("DELETE_ORIGINAL", "false").lower() == "true"

intents = discord.Intents.default()
intents.message_content = True  # also enable this in the Developer Portal
client = discord.Client(
    intents=intents,
    activity=discord.Activity(type=discord.ActivityType.watching, name="messages"),
    status=discord.Status.online,
)


@client.event
async def on_ready():
    print(f"Logged in as {client.user} - archiving to channel {ARCHIVE_CHANNEL_ID}")


@client.event
async def on_message(message: discord.Message):
    # Ignore bots (including ourselves), DMs, and the archive channel itself
    if message.author.bot or message.guild is None:
        return
    if message.channel.id == ARCHIVE_CHANNEL_ID:
        return
    if ONLY_USER_ID and message.author.id != ONLY_USER_ID:
        return

    archive = client.get_channel(ARCHIVE_CHANNEL_ID)
    if archive is None:
        archive = await client.fetch_channel(ARCHIVE_CHANNEL_ID)

    embed = discord.Embed(
        description=message.content[:4096] or None,
        timestamp=message.created_at,
        color=discord.Color.blurple(),
    )
    embed.set_author(
        name=message.author.display_name,
        icon_url=message.author.display_avatar.url,
    )
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    embed.add_field(name="Original", value=f"[Jump to message]({message.jump_url})", inline=True)

    # Re-upload attachments so the archive keeps its own copy of each file
    # (links to the original go dead once the original message is deleted).
    files = []
    not_copied = []
    size_limit = archive.guild.filesize_limit
    for a in message.attachments:
        if a.size > size_limit:
            not_copied.append(a)
            continue
        try:
            files.append(await a.to_file())
        except discord.HTTPException:
            not_copied.append(a)

    if not_copied:
        links = "\n".join(f"[{a.filename}]({a.url})" for a in not_copied)
        embed.add_field(
            name="Not copied (too large / failed) - link may expire",
            value=links[:1024],
            inline=False,
        )

    try:
        await archive.send(embed=embed, files=files)
    except discord.HTTPException as e:
        print(f"Failed to archive message {message.id}: {e}")
        return

    if DELETE_ORIGINAL:
        try:
            await message.delete()
        except discord.HTTPException as e:
            print(f"Could not delete original {message.id}: {e}")


client.run(TOKEN)
