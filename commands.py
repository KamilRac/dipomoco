from defs import *

@bot.event
async def on_command(ctx):
    user_id = ctx.author.id
    command_name = get_function_name(ctx.command.callback)
    conversation_states.append((command_name, user_id))

@bot.event
async def on_command_error(ctx, error):
    allowed_commands = ['start', 'startwork', 'pomodoro', 'finish', 'finishwork']
    if isinstance(error, commands.CheckFailure):
        if ctx.command.name not in allowed_commands:
            await ctx.send(f"Sorry, {ctx.command.name} is currently being used. Please wait.")

@bot.event
async def on_command_completion(ctx):
    user_id = ctx.author.id
    user_id_to_remove = user_id

    # Find the index of the pair to remove
    index_to_remove = -1
    for index, pair in enumerate(conversation_states):
        if pair[1] == user_id_to_remove:
            index_to_remove = index
            break

    # Remove the pair if found
    if index_to_remove != -1:
        removed_pair = conversation_states.pop(index_to_remove)
        print(f"Removed pair: {removed_pair}")
    else:
        print(f"No pair found with user_id {user_id_to_remove}")

@bot.event
async def on_ready():
    
    print("Hello! I work today!")
    channel = bot.get_channel(CHANNEL_ID)
    await channel.send("Hello! I work on the discord now too!")

    # Start the email task
    if not hasattr(bot, "email_task"):
        bot.email_task = bot.loop.create_task(check_and_send_summaries())
    else:
        print("Email task is already running")

async def setup_hook():
	pass





bot.remove_command('help')  # Remove default help command
@bot.command(name='help')
async def custom_help(ctx):
    help_text = """
**Available Commands:**

**Registration and Account Management:**

* `!register`: Registers a new user by guiding you through a series of questions.
* `!deleteaccount`: Deletes your user account after a verification process.
* `!changetimezone`: Changes your timezone for accurate summary reports.
* `!changenickname`: Changes your nickname associated with the bot.
* `!changeemail`: Changes your email address for notifications.
* `!changesummarysettings`: Adjusts the day and time for your weekly summary emails.
* `!togglesurveys`: Enables or disables the mood and motivation surveys at the start and end of work sessions.

**Work Session Tracking:**

* `!start` or `!startwork`: Starts a new work session.
* `!finish` or `!finishwork`: Ends the current work session and records the duration.
* `!pomodoro`: Starts a 25-minute pomodoro session with a short break afterwards.

**Other Commands:**

* `!testsummary [email]`: (Optional) Sends a test summary email to the specified address or your registered email by default.
* `!hello`: The bot greets you.
* `!help`: Shows this help message. 
    """
    await ctx.send(help_text)

@bot.command()
async def testsummary(ctx, recipient_email=test_emailex):  
    """Sends a test summary email with random data."""
    try:
        user_id = ctx.author.id 

        # Simulate user data for the test
        test_user_data = {
            'UserNickname': 'Test User',
            'Email': recipient_email,
            'Timezone': 'Europe/Warsaw', 
            'SummaryIsSundayIncluded': True,
            'SummaryDayOfWeek': 2,
            'SummaryTime': '07:00'         
        }

        
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        daily_work = {day: random.randint(30, 120) for day in day_names if test_user_data['SummaryIsSundayIncluded'] or day != 'Sunday'}

        # (dummy value)
        total_minutes = random.randint(1000, 5000)

        
        chart_data = {
            'type': 'bar',
            'data': {
                'labels': list(daily_work.keys()),
                'datasets': [{
                    'label': 'Work Minutes (Test Data)',
                    'data': list(daily_work.values())
                }]
            }
        }
        encoded_config = quote(json.dumps(chart_data))
        chart_url = f'https://quickchart.io/chart?c={encoded_config}'

        subject = "Dipomoco Test Weekly Work Summary"
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
            width: 80%;  /* Adjust chart width here */
            margin: 20px auto;
        }}
		</style>
        </head>
        <body>
            <div class="container">
                <h2>Hi {test_user_data['UserNickname']},</h2>
                <p>Here's your weekly work summary for the week ending on {datetime.now(pytz.timezone(test_user_data['Timezone'])).strftime('%A, %B %d, %Y')}:</p>

                <div class="chart-container">
                    <img src="{chart_url}" alt="Weekly Work Chart" style="width:100%;"/>
                </div>

                <p>You've worked a total of {total_minutes} minutes since joining Dipomoco.</p>
            </div>
        </body>
        </html>
        """

        await send_email(recipient_email, subject, email_body)
        await ctx.send("Test summary email sent successfully!")
    except Exception as e:
        await ctx.send(f"An error occurred while sending the test email: {e}")

@bot.command()
async def hello(ctx):
    await ctx.send("Haia!")

@bot.command()
@commands.check(command_not_in_use)
async def register(ctx):
    if user_already_registered(ctx.author.id):
        await ctx.send("You are already registered!")
        return
    command_name=get_caller_function_name()
    user_id = ctx.author.id
    
    def store_user_data(user_id, nickname, email, timezone, sunday_included, summary_day_of_week):
        try:
            cursor = mydb.cursor()
            query = "INSERT INTO Users (UserID, UserNickname, Email, Timezone, SummaryIsSundayIncluded, SummaryDayOfWeek) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(query, (user_id, nickname, email, timezone, sunday_included, summary_day_of_week))
            mydb.commit()
            print(f"User data stored for ID: {user_id}")
        except mysql.connector.Error as err:
            print(f"Error storing user data: {err}")
            
    
    await ctx.send("Hello! Let's get you registered.")

    try:
        # Ask for nickname
        await ctx.send("What's your nickname?")
        new_nickname_msg = await bot.wait_for('message', timeout=30.0)
        user_id = new_nickname_msg.author.id
        print(f"The new nickname in the console: {new_nickname_msg.content}")
        anw=check_conversation(user_id, command_name)
        if anw == True:
            pass
        else:
            while True:
                new_nickname_msg = await bot.wait_for('message', timeout=30.0)
                user_id = new_nickname_msg.author.id
                anw=check_conversation(user_id, command_name)
                if anw == True:
                    break
        new_nickname = new_nickname_msg.content
		
        
        
        # Ask for email
        while True:
            await ctx.send("What's your email address?")
            new_email_msg = await bot.wait_for('message', timeout=30.0)
            user_id = new_email_msg.author.id
            print(f"The new email in the console: {new_email_msg.content}")
            anw=check_conversation(user_id, command_name)
            if anw == True:
                pass
            else:
                while True:
                    new_email_msg = await bot.wait_for('message', timeout=30.0)
                    user_id = new_email_msg.author.id
                    anw=check_conversation(user_id, command_name)
                    if anw == True:
                        break
            new_email = new_email_msg.content.strip()

            if re.match(r"[^@]+@[^@]+\.[^@]+", new_email):
                if not email_already_exists(new_email):
                    break
                else:
                    await ctx.send("This email is already registered. Please use a different email address.")
            else:
                await ctx.send("Invalid email format. Please enter a valid email address (e.g., example@email.com)")
                
        

        # Ask for timezone
        while True:
            await ctx.send("What's your timezone? (e.g. GMT+0, GMT-5, GMT+12)")  
            new_timezone_msg = await bot.wait_for('message', timeout=30.0)
            user_id = new_timezone_msg.author.id
            anw=check_conversation(user_id, command_name)
            if anw == True:
                pass
            else:
                while True:
                    new_timezone_msg = await bot.wait_for('message', timeout=30.0)
                    print(f"The new timezone in the console: {new_timezone_msg.content}")
                    user_id = new_timezone_msg.author.id
                    anw=check_conversation(user_id, command_name)
                    if anw == True:
                        break
            new_timezone = new_timezone_msg.content.strip()  # Strip extra spaces

            if re.fullmatch(r"^GMT([+-]1[0-2]|[+]?1[3-4]|[+]?[1-9]|[+-]0)$", new_timezone):
                break
            else:
                await ctx.send("Invalid timezone format. Please use GMT followed by the offset (e.g., GMT-5).")
        
        # Ask for Sunday 
        while True:
            await ctx.send("Do you want Sundays included in your weekly summaries? (yes/no)")
            sunday_included_msg = await bot.wait_for('message', timeout=30.0)
            print(f"The new Sunday status in the console: {sunday_included_msg.content}")
            user_id = sunday_included_msg.author.id
            anw=check_conversation(user_id, command_name)
            if anw == True:
                pass
            else:
                while True:
                    sunday_included_msg = await bot.wait_for('message', timeout=30.0)
                    user_id = sunday_included_msg.author.id
                    anw=check_conversation(user_id, command_name)
                    if anw == True:
                        break
            sunday_included_str = sunday_included_msg.content.lower()

            if sunday_included_str in ["yes", "y"]:
                summary_is_sunday_included = True
                break
            elif sunday_included_str in ["no", "n"]:
                summary_is_sunday_included = False
                break
            else:
                await ctx.send("Invalid response. Please enter 'yes' or 'no'.")

        # Ask for verification code
        
        verification_code = ''.join(random.choices(string.ascii_letters + string.digits, k=6)).upper()

        try:
            em = EmailMessage()
            em["From"] = email_sender
            em["To"] = new_email 
            em["Subject"] = "Your Verification Code for Dipomoco"
            em.set_content(f"Your verification code is: {verification_code}")

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
                smtp.login(email_sender, email_password)
                smtp.sendmail(email_sender, new_email, em.as_string())
        except Exception as e:
            await ctx.send(f"There was an error sending the verification email. Please try again later.")
            return

        
        await ctx.send("We've sent a verification code to your email. Please enter it below:") 

        # Verification loop
        max_attempts = 3
        attempts = 0
        while attempts < max_attempts:
            verification_code_msg = await bot.wait_for('message', timeout=120.0)
            anw=check_conversation(user_id, command_name)
            if anw == True:
                pass
            else:
                while True:
                    verification_code_msg = await bot.wait_for('message', timeout=30.0)
                    user_id = verification_code_msg.author.id
                    anw=check_conversation(user_id, command_name)
                    if anw == True:
                        break
            entered_code = verification_code_msg.content
  
            if entered_code == verification_code:
            
                summary_day_of_week = 6  # Default to Saturday
                if summary_is_sunday_included:
                    summary_day_of_week = 7  # Sunday

            
                store_user_data(ctx.author.id, new_nickname, new_email, new_timezone, summary_is_sunday_included, summary_day_of_week)
                await ctx.send("Registration successful!")
                return   

            attempts += 1
            await ctx.send(f"Invalid code. You have {max_attempts - attempts} attempts remaining.")

        await ctx.send("You've reached the maximum number of attempts. Registration failed.")

    except asyncio.TimeoutError:
        await ctx.send("Sorry, you took too long to respond.")
        
@bot.command()
@commands.check(command_not_in_use)
async def deleteaccount(ctx):
    user_id = ctx.author.id
    command_name=get_caller_function_name()
    if not user_already_registered(user_id):
        await ctx.send("You are not registered yet!")
        return

    # Fetch user's email
    cursor = mydb.cursor()
    query = "SELECT Email FROM Users WHERE UserID = %s"
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()

    if not result:
        await ctx.send("Error fetching your email address.")
        cursor.close()
        return

    user_email = result[0]
    cursor.close()

    # Generate verification code
    verification_code = ''.join(random.choices(string.ascii_letters + string.digits, k=6)).upper()

    
    await send_email(user_email, "Account Deletion Verification", f"Your verification code is: {verification_code}")

    await ctx.send("We've sent a verification code to your email. Please enter it below to confirm deletion:")

    # Verification loop
    max_attempts = 3
    attempts = 0
    while attempts < max_attempts:
        verification_code_msg = await bot.wait_for('message', timeout=120.0)
        anw=check_conversation(user_id, command_name)
        if anw == True:
            pass
        else:
            while True:
                verification_code_msg = await bot.wait_for('message', timeout=30.0)
                user_id = verification_code_msg.author.id
                anw=check_conversation(user_id, command_name)
                if anw == True:
                    break
        entered_code = verification_code_msg.content

        if entered_code == verification_code:
            # Delete user data
            try:
                cursor = mydb.cursor()
                query = "DELETE FROM Users WHERE UserID = %s"
                cursor.execute(query, (user_id,))
                mydb.commit()
                await ctx.send("Your account has been deleted.")
            except mysql.connector.Error as err:
                await ctx.send(f"An error occurred while deleting your account: {err}")
            finally:
                cursor.close()
            return

        attempts += 1
        await ctx.send(f"Invalid code. You have {max_attempts - attempts} attempts remaining.")

    await ctx.send("You've reached the maximum number of attempts. Account deletion cancelled.")

@bot.command()
@commands.check(command_not_in_use)
async def changetimezone(ctx):
    user_id = ctx.author.id
    command_name=get_caller_function_name()
    if not user_already_registered(user_id):
        await ctx.send("You are not registered yet!")
        return

    try:

        while True:
            await ctx.send("Enter your new timezone (e.g. GMT+0, GMT-5, GMT+12):")
            command_name=get_caller_function_name()
            
            new_timezone_msg = await bot.wait_for('message', timeout=30.0)
            user_id = new_timezone_msg.author.id
            anw=check_conversation(user_id, command_name)
            if anw == True:
                pass
            else:
                while True:
                    new_timezone_msg = await bot.wait_for('message', timeout=30.0)
                    user_id = new_timezone_msg.author.id
                    anw=check_conversation(user_id, command_name)
                    if anw == True:
                        break
            new_timezone = new_timezone_msg.content.strip()

            if re.fullmatch(r"^GMT([+-]1[0-2]|[+]?1[3-4]|[+]?[1-9]|[+-]0)$", new_timezone):
                break
            else:
                await ctx.send("Invalid timezone format. Please use GMT followed by the offset (e.g., GMT-5).")


        try:
            cursor = mydb.cursor()
            query = "UPDATE Users SET Timezone = %s WHERE UserID = %s"
            cursor.execute(query, (new_timezone, user_id))
            mydb.commit()
            await ctx.send(f"Your timezone has been updated to {new_timezone}.")
        except mysql.connector.Error as err:
            await ctx.send(f"An error occurred while updating your timezone: {err}")
        finally:
            cursor.close()
    except asyncio.TimeoutError:
        await ctx.send("Sorry, you took too long to respond.")

@bot.command()
@commands.check(command_not_in_use)
async def changenickname(ctx):
    command_name=get_caller_function_name()
    user_id = ctx.author.id

    if not user_already_registered(user_id):
        await ctx.send("You are not registered yet!")
        return

    try:
        await ctx.send("Enter your new nickname:")
        new_nickname_msg = await bot.wait_for('message', timeout=30.0)
        user_id = new_nickname_msg.author.id
        anw=check_conversation(user_id, command_name)
        if anw == True:
            pass
        else:
            while True:
                new_nickname_msg = await bot.wait_for('message', timeout=30.0)
                user_id = new_nickname_msg.author.id
                anw=check_conversation(user_id, command_name)
                if anw == True:
                    break
        print("test3")
        new_nickname = new_nickname_msg.content.strip()
        print("test4")

        try:
            cursor = mydb.cursor()
            query = "UPDATE Users SET UserNickname = %s WHERE UserID = %s"
            cursor.execute(query, (new_nickname, user_id))
            mydb.commit()


            await ctx.send(f"Your nickname has been changed to {new_nickname}.")  
        except mysql.connector.Error as err:
            await ctx.send(f"An error occurred while updating your nickname: {err}")
        finally:
            cursor.close()
    except asyncio.TimeoutError:
        await ctx.send("Sorry, you took too long to respond.")

@bot.command()
@commands.check(command_not_in_use)
async def changeemail(ctx):
    user_id = ctx.author.id
    command_name=get_caller_function_name()
    try:

        while True:
            await ctx.send("Enter your new email address:")
            new_email_msg = await bot.wait_for('message', timeout=30.0)
            user_id = new_email_msg.author.id
            anw=check_conversation(user_id, command_name)
            if anw == True:
                pass
            else:
                while True:
                    new_email_msg = await bot.wait_for('message', timeout=30.0)
                    user_id = new_email_msg.author.id
                    anw=check_conversation(user_id, command_name)
                    if anw == True:
                        break
            new_email = new_email_msg.content.strip()

            if re.match(r"[^@]+@[^@]+\.[^@]+", new_email):
                if not email_already_exists(new_email):
                    break
                else:
                    await ctx.send("This email is already registered. Please use a different email address.")
            else:
                await ctx.send("Invalid email format. Please enter a valid email address (e.g., example@email.com)")


        verification_code = ''.join(random.choices(string.ascii_letters + string.digits, k=6)).upper()

        try:
            await send_email(new_email, "Email Change Verification for Dipomoco", f"Your verification code is: {verification_code}")
        except Exception as e:
            await ctx.send(f"There was an error sending the verification email. Please try again later.")
            return


        await ctx.send("We've sent a verification code to your new email. Please enter it below:")
        max_attempts = 3
        attempts = 0
        while attempts < max_attempts:
            verification_code_msg = await bot.wait_for('message', timeout=120.0)
            user_id = new_verification_msg.author.id
            anw=check_conversation(user_id, command_name)
            if anw == True:
                pass
            else:
                while True:
                    new_verification_msg = await bot.wait_for('message', timeout=30.0)
                    user_id = new_verification_msg.author.id
                    anw=check_conversation(user_id, command_name)
                    if anw == True:
                        break
            entered_code = verification_code_msg.content

            if entered_code == verification_code:

                try:
                    cursor = mydb.cursor()
                    query = "UPDATE Users SET Email = %s WHERE UserID = %s"
                    cursor.execute(query, (new_email, user_id))
                    mydb.commit()
                    await ctx.send("Your email has been updated successfully!")
                except mysql.connector.Error as err:
                    await ctx.send(f"An error occurred while updating your email: {err}")
                finally:
                    cursor.close()
                return

            attempts += 1
            await ctx.send(f"Invalid code. You have {max_attempts - attempts} attempts remaining.")
            
        cursor = mydb.cursor()
        query = "SELECT Email FROM Users WHERE UserID = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        if result:
            original_email = result[0]
            await send_email(original_email, "Email Change Attempt Failed",
                             f"Someone tried to change the email address on your Dipomoco account on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. "
                             "If this was not you, please take precautions to secure your account.")
        await ctx.send("You've reached the maximum number of attempts. Email change failed.")

    except asyncio.TimeoutError:
        await ctx.send("Sorry, you took too long to respond.")

@bot.command()
@commands.check(command_not_in_use)
async def changesummarysettings(ctx):
    command_name=get_caller_function_name()
    user_id = ctx.author.id

    if not user_already_registered(user_id):
        await ctx.send("You are not registered yet!")
        return

    try:

        while True:
            await ctx.send("Enter the new day for your weekly summary (e.g., Monday or 1, Tuesday or 2 etc.):")
            new_day_msg = await bot.wait_for('message', timeout=30.0)
            anw=check_conversation(user_id, command_name)
            if anw == True:
                pass
            else:
                while True:
                    new_day_msg = await bot.wait_for('message', timeout=30.0)
                    user_id = new_day_msg.author.id
                    anw=check_conversation(user_id, command_name)
                    if anw == True:
                        break
            day_input = new_day_msg.content.strip().lower()

            # Try to convert day name to number
            day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            if day_input in day_names:
                new_day_of_week = day_names.index(day_input) + 1
                break
            
            try:
                new_day_of_week = int(day_input)
                if 1 <= new_day_of_week <= 7:
                    break
                else:
                    await ctx.send("Invalid input. Please enter a day name or a number between 1 and 7.")
            except ValueError:
                await ctx.send("Invalid input. Please enter a day name or a number.")


        while True:
            await ctx.send("Enter the new time for your weekly summary (full hour, 24-hour clock, e.g., 14):")
            new_time_msg = await bot.wait_for('message', timeout=30.0)
            anw=check_conversation(user_id, command_name)
            if anw == True:
                pass
            else:
                while True:
                    new_time_msg = await bot.wait_for('message', timeout=30.0)
                    user_id = new_time_msg.author.id
                    anw=check_conversation(user_id, command_name)
                    if anw == True:
                        break
            try:
                new_hour = int(new_time_msg.content.strip())
                if 0 <= new_hour <= 23:
                    new_summary_time = f"{new_hour:02}:00"  # Format as HH:MM
                    break
                else:
                    await ctx.send("Invalid hour. Please enter a number between 0 and 23.")
            except ValueError:
                await ctx.send("Invalid input. Please enter a number.")


        try:
            cursor = mydb.cursor()
            query = "UPDATE Users SET SummaryDayOfWeek = %s, `SummaryTime` = %s WHERE UserID = %s"
            cursor.execute(query, (new_day_of_week, new_summary_time, user_id))
            mydb.commit()


            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            await ctx.send(
                f"Your weekly summary settings have been updated to {day_names[new_day_of_week - 1]} at {new_summary_time}. Please note that summaries are being checked for hourly."
            )
        except mysql.connector.Error as err:
            await ctx.send(f"An error occurred while updating your summary settings: {err}")
        finally:
            cursor.close()
    except asyncio.TimeoutError:
        await ctx.send("Sorry, you took too long to respond.")