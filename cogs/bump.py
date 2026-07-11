import os
import discord
import time 
from discord.ext import commands
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()

BUMP_USER_ID = int(os.getenv("BUMP_USER_ID"))
HANNEL_BUMP_ID = int(os.getenv("CHANEL_BUMP_ID"))

@commands.cog.listener()
async def on_message(message,self):
     
     if message.author == self.bot.user:
            return
    