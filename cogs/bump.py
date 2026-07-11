import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

BUMP_USER_ID = int(os.getenv("BUMP_USER_ID"))
CHANNEL_BUMP_ID = int(os.getenv("CHANNEL_BUMP_ID"))

class BumpReminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener() 
    async def on_message(self, message):  
        if message.author == self.bot.user:
            return
       
        if message.author.id == BUMP_USER_ID: 
            
            channel = self.bot.get_channel(CHANNEL_BUMP_ID)
            await channel.send("🎉 Le serveur a été bumped!")
            
    
            await asyncio.sleep(7200)
            
  
            await channel.send("Tu peux bump le serveur!")

async def setup(bot):
    await bot.add_cog(BumpReminder(bot))