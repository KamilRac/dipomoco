import discord
from discord.ext import commands

from discordtoken import BOT_TOKENex

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

from commands import *
from work import *

BOT_TOKEN = BOT_TOKENex

bot.run(BOT_TOKEN)
