import discord
from discord.ext import commands
import asyncio
import datetime
from datetime import timedelta, datetime
import json
from urllib.parse import quote
import mysql.connector
import pytz
import smtplib
import ssl
from email.message import EmailMessage
import logging
import traceback
import random
import string
import re

from databasepasscode import database_passcodeex, database_hostex, database_userex, database_nameex
from testingconfig import CHANNEL_IDex, test_emailex
from emailpasscode import email_senderex, email_bodyex, email_passwordex

logging.basicConfig(level=logging.DEBUG)

conversation_states = [("test",1)]

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

mydb = mysql.connector.connect(
  host=database_hostex,
  user=database_userex,
  password=database_passcodeex,
  database=database_nameex,
)

CHANNEL_ID = CHANNEL_IDex

async def get_mood_and_motivation(ctx, stage):
    mood = await ask_for_rating(ctx, f"How are you feeling at the {stage} of your work session? (1-5)")
    motivation = await ask_for_rating(ctx, f"How motivated are you at the {stage} of your work session? (1-5)")
    return mood, motivation

async def ask_for_rating(ctx, question):
    await ctx.send(question)
    while True:
        rating_msg = await bot.wait_for('message', check=lambda m: m.author == ctx.author and m.content.isdigit())
        rating = int(rating_msg.content)
        if 1 <= rating <= 5:
            return rating
        await ctx.send("Invalid rating. Please enter a number between 1 and 5.")

def get_user_preference(user_id, preference_name):
    try:
        cursor = mydb.cursor()
        query = f"SELECT {preference_name} FROM Users WHERE UserID = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        return result[0] if result else False  # Default to False
    except mysql.connector.Error as err:
        print(f"Error fetching user preference: {err}")
        return False
    finally:
        cursor.close()

async def _store_work_session(ctx, user_id, start_time, finish_time):
    if user_already_registered(user_id):
        try:
            cursor = mydb.cursor()
            query = "INSERT INTO WorkTimes (UserID, StartTime, FinishTime) VALUES (%s, %s, %s)" 
            cursor.execute(query, (user_id, start_time, finish_time))
            mydb.commit()
        except mysql.connector.Error as err:
            await ctx.send(f"Error storing work session: {err}")
        finally:
            cursor.close()
    else:
        await ctx.send("Session ended, but not tracked because you're not registered.")

def email_already_exists(email):
    cursor = mydb.cursor()
    query = "SELECT UserID FROM Users WHERE Email = %s"
    cursor.execute(query, (email,))
    result = cursor.fetchone()
    cursor.close()
    return result is not None

def get_weekly_work_data(user_id, summary_day_of_week, sunday_included=False):

    cursor = mydb.cursor()

    user_timezone_str = get_user_timezone(user_id)
    
    try:
        if user_timezone_str.startswith('GMT'):
            offset_hours = int(user_timezone_str[3:])
            user_timezone = pytz.FixedOffset(offset_hours * 60)
        else:
            user_timezone = pytz.timezone(user_timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        logging.error(f"Error: Invalid timezone '{user_timezone_str}' for user ID {user_id}")
        return {}

    current_time = datetime.now(user_timezone)

    # Calculate the start and end of the week
    days_since_summary_day = (current_time.weekday() - (int(summary_day_of_week) - 1)) % 7
    start_of_week = current_time - timedelta(days=days_since_summary_day)

    if sunday_included and int(summary_day_of_week) == 7: 
        start_of_week -= timedelta(days=7)

    end_of_week = start_of_week + timedelta(days=6)

    query = """
        SELECT DATE(StartTime), SUM(TIMESTAMPDIFF(SECOND, StartTime, FinishTime))
        FROM WorkTimes
        WHERE UserID = %s AND StartTime >= %s AND StartTime < %s
        GROUP BY DATE(StartTime)
    """
    cursor.execute(query, (user_id, start_of_week, end_of_week))
    data = cursor.fetchall()

    daily_work = {day_name: 0 for day_name in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']}
    for row in data:
        day_name = row[0].strftime('%A')
        daily_work[day_name] = row[1] // 60

    adjusted_daily_work = {}
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    for i in range(7):
        day_index = (int(summary_day_of_week) - 1 + i) % 7  # Start from summary day, cycle through days
        day_name = day_names[day_index]
        if not sunday_included and day_name == 'Sunday':
            continue
        adjusted_daily_work[day_name] = daily_work.get(day_name, 0)

    cursor.close()
    return adjusted_daily_work

def get_user_timezone(user_id):
    cursor = mydb.cursor()
    query = "SELECT Timezone FROM Users WHERE UserID = %s"
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    cursor.close()
    return result[0] if result else 'UTC'  # Default to UTC if not found

def get_total_work_minutes(user_id):
    cursor = mydb.cursor()
    query = """
        SELECT SUM(TIMESTAMPDIFF(SECOND, StartTime, FinishTime))
        FROM WorkTimes
        WHERE UserID = %s
    """
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    cursor.close()
    return int(result[0] // 60) if result[0] else 0

async def generate_summary_email(user_id):

    cursor = mydb.cursor(dictionary=True)
    query = "SELECT UserNickname, Email, Timezone, SummaryIsSundayIncluded, SummaryDayOfWeek, SummaryTime FROM Users WHERE UserID = %s"
    cursor.execute(query, (user_id,))
    user_data = cursor.fetchone()
    cursor.close()

    if not user_data:
        return

    nickname = user_data['UserNickname']
    recipient_email = user_data['Email']
    timezone_str = user_data['Timezone']
    sunday_included = user_data['SummaryIsSundayIncluded']
    day_of_week = user_data['SummaryDayOfWeek']
    time_of_day = user_data['SummaryTime']

    try:
        if timezone_str.startswith('GMT'):
            offset_hours = int(timezone_str[3:])
            timezone = pytz.FixedOffset(offset_hours * 60)
        else:
            timezone = pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        logging.error(f"Error: Invalid timezone '{timezone_str}' for user ID {user_id}")
        return

    current_time = datetime.now(timezone)


    daily_work = get_weekly_work_data(user_id, day_of_week, sunday_included)
    total_minutes = get_total_work_minutes(user_id)


    chart_data = {
        'type': 'bar',
        'data': {
            'labels': list(daily_work.keys()),
            'datasets': [{
                'label': 'Work Minutes',
                'data': list(daily_work.values()),
                'backgroundColor': '#007bff'  # Blue color for the bars
            }]
        }
    }
    encoded_config = quote(json.dumps(chart_data))
    chart_url = f'https://quickchart.io/chart?c={encoded_config}'


    subject = "Dipomoco Weekly Work Summary"
    email_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    body {{
        font-family: Arial, sans-serif;
        background-color: #f4f4f4;
        margin: 0;
        padding: 0;
    }}

    .container {{
        width: 600px;
        margin: 0 auto;
        background-color: #fff;
        padding: 20px;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    }}

    h2 {{
        color: #007bff; /* Blue */
    }}

    p {{
        line-height: 1.6;
    }}

    .chart-container {{
        width: 80%;
        margin: 20px auto;
    }}
    </style>
    </head>
    <body>
        <div class="container">
            <h2>Hi {nickname},</h2>
            <p>Here's your weekly work summary for the week ending on {current_time.strftime('%A, %B %d, %Y')}:</p>

            <div class="chart-container">
                <img src="{chart_url}" alt="Weekly Work Chart" style="width:100%;"/>
            </div>

            <p>You've worked a total of {total_minutes} minutes since joining Dipomoco.</p>
        </div>
    </body>
    </html>
    """

    await send_email(recipient_email, subject, email_body)

async def check_and_send_summaries():
    while True:
        now_utc = datetime.now(pytz.UTC)

        # Calculate the delay until the next full hour
        next_hour = now_utc.replace(microsecond=0, second=0, minute=0) + timedelta(hours=1)
        delay = (next_hour - now_utc).total_seconds()

        print(f"[DEBUG] Checking for summaries at UTC time: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            users_to_email = get_users_to_email()
            if users_to_email:
                print("Preparing and sending summary emails...")
                for user_id in users_to_email:
                    try:
                        await generate_summary_email(user_id)
                        print(f"Sent summary email to user ID: {user_id}")
                    except Exception as e:
                        print(f"Error sending email to user ID {user_id}: {e}\n{traceback.format_exc()}")
            else:
                print("No users to email at this time.")
        except Exception as e:
            print(f"Error during email check: {e}\n{traceback.format_exc()}")

        print(f"Waiting for the next check ({delay} seconds)...")
        await asyncio.sleep(delay)  # Sleep until the next full hour


def get_users_to_email():

    try:
        cursor = mydb.cursor()
        now_utc = datetime.now(pytz.UTC)
        
        logging.debug(f"Checking for summaries at UTC time: {now_utc}")
        
        query = """
            SELECT UserID, Timezone, SummaryDayOfWeek, SummaryTime
            FROM Users
        """
        cursor.execute(query)
        users = cursor.fetchall()
        cursor.close()
        
        users_to_email = []
        for user_id, timezone_str, summary_day, summary_time in users:
            try:
                logging.debug(f"Processing user {user_id} with timezone: {timezone_str}")
                
                if timezone_str.startswith('GMT'):
                    offset_hours = int(timezone_str[3:])
                    timezone = pytz.FixedOffset(offset_hours * 60)
                else:
                    timezone = pytz.timezone(timezone_str)
                
                user_time = now_utc.astimezone(timezone)
                

                summary_day = int(summary_day)

                if isinstance(summary_time, timedelta):
                    total_seconds = int(summary_time.total_seconds())
                    summary_hour, remainder = divmod(total_seconds, 3600)
                    summary_minute, _ = divmod(remainder, 60)
                else:
                    summary_hour, summary_minute = map(int, summary_time.split(":"))
                
                # Convert summary day from database format to datetime weekday format
                summary_day_of_week = (summary_day - 1) % 7
                
                # Debug log 
                logging.debug(f"User {user_id}: Current time: {user_time.strftime('%A %H:%M')}, Summary time: {summary_hour:02}:{summary_minute:02}, Summary day: {summary_day} ({user_time.weekday()})")
                
                if user_time.weekday() == summary_day_of_week and user_time.hour == summary_hour and user_time.minute == summary_minute:
                    users_to_email.append(user_id)
            except pytz.exceptions.UnknownTimeZoneError:
                logging.error(f"Error: Invalid timezone '{timezone_str}' for user ID {user_id}")
            except Exception as e:
                logging.error(f"Error processing user {user_id}: {e}\n{traceback.format_exc()}")  
    except mysql.connector.Error as db_error:
        logging.error(f"Database error fetching users: {db_error}")
        return []
    
    return users_to_email

def command_not_in_use(ctx):
    command_name = get_function_name(ctx.command.callback)
    return not any(cmd_name == command_name for cmd_name, _ in conversation_states)


def get_function_name(func):
    function_name = func.__name__
    print(function_name)
    return function_name

def user_already_registered(user_id):
    cursor = mydb.cursor()
    query = "SELECT UserID FROM Users WHERE UserID = %s"
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    cursor.close()
    return result is not None

def check_conversation(message, command_name):
    
    user_id = message
    search_pair = (command_name, user_id)
    
    found = False

    for pair in conversation_states:
        if pair == search_pair:
            found = True
            break

    if found:
        print(f"Pair {search_pair} found in the list.")
    else:
        print(f"Pair {search_pair} not found in the list.")
    return found


async def send_email(recipient_email, subject, body):
    try:
        em = EmailMessage()
        em["From"] = email_sender
        em["To"] = recipient_email
        em["Subject"] = subject

        # Set the email content as HTML
        em.set_content(body, subtype='html')

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
            smtp.login(email_sender, email_password)
            smtp.sendmail(email_sender, recipient_email, em.as_string())
    except Exception as e:
        print(f"Error sending email: {e}")
