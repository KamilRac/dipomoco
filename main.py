import discord
from discord.ext import commands
import mysql.connector
from discordtoken import BOT_TOKENex
from emailpasscode import email_passwordex

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

#bot.load_extension("defs")
#bot.load_extension("commands")
#bot.load_extension("work")
from commands import *
from work import *



print(mydb)

BOT_TOKEN = BOT_TOKENex
CHANNEL_ID = 571661921686781952


email_sender = 'dipomoco@gmail.com'
email_password = email_passwordex
email_body = "haya"

bot.run(BOT_TOKEN)