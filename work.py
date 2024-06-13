from defs import *

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

work_sessions = {}
unregistered_work_sessions = {}

@bot.command(aliases=["startwork"])
async def start(ctx):
    user_id = ctx.author.id
    is_registered = user_already_registered(user_id)  
    wants_surveys = get_user_preference(user_id, "WantsMoodSurveys")  


    start_mood, start_motivation = None, None

    if is_registered:

        if user_id in work_sessions:
            await ctx.send("You've already started a work session!")
            return

        print(f"start of the start")

        if wants_surveys:
            start_mood, start_motivation = await get_mood_and_motivation(ctx, "start")

        cursor = mydb.cursor()
        try:
            query = "INSERT INTO WorkTimes (UserID, StartTime, MoodStart, MotivationStart) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (user_id, datetime.now(), start_mood, start_motivation))
            mydb.commit()
            session_id = cursor.lastrowid
        except mysql.connector.Error as err:
            mydb.rollback()
            await ctx.send(f"Failed to start work session: {err}")
            return
        finally:
            cursor.close()

        work_sessions[user_id] = {
            'start_time': datetime.now(),
            'session_id': session_id,
            'is_pomodoro': False  # Explicitly set is_pomodoro to False for regular sessions
        }
    else:

        if user_id in unregistered_work_sessions:
            await ctx.send("You've already started an unregistered work session!")
            return
        unregistered_work_sessions[user_id] = {'start_time': datetime.now()}

    await ctx.send("Work session started. Good luck!")
    if not work_sessions[user_id].get('is_pomodoro'):
        asyncio.create_task(send_reminder(user_id, ctx, is_registered))

@bot.command(aliases=["finishwork"])
async def finish(ctx):
    user_id = ctx.author.id
    finish_time = datetime.now()

    if user_id in work_sessions:
        session_info = work_sessions[user_id]

        # Check if it's a pomodoro session
        if session_info.get('is_pomodoro'):
            del work_sessions[user_id]
            await ctx.send("Pomodoro session ended.")
        else:
            # Handle regular work session
            wants_surveys = get_user_preference(user_id, "WantsMoodSurveys")  # Fetch the user's survey preference each time
            session_id = session_info.get('session_id')  # Get the session ID

            start_time = session_info['start_time']
            duration = finish_time - start_time
            duration_formatted = _format_duration(duration)

            if wants_surveys:
                end_mood, end_motivation = await get_mood_and_motivation(ctx, "end")

                cursor = mydb.cursor()
                query = "UPDATE WorkTimes SET FinishTime = %s, MoodEnd = %s, MotivationEnd = %s WHERE SessionID = %s"
                cursor.execute(query, (finish_time, end_mood, end_motivation, session_id))
            else:
                cursor = mydb.cursor()
                query = "UPDATE WorkTimes SET FinishTime = %s WHERE SessionID = %s"
                cursor.execute(query, (finish_time, session_id))

            try: 
                mydb.commit()
            except mysql.connector.Error as err:
                mydb.rollback()
                await ctx.send(f"You worked for {duration_formatted}. Great job! However, there was an error recording your time: {err}") 
            finally:
                cursor.close()


            # Check if the session ID exists to determine if the user is registered
            if session_id is None:  
                await ctx.send(f"You worked for {duration_formatted}. Great job! However, your session wasn't tracked because you're not registered.")
            else:  # Everything went well
                await ctx.send(f"Work session ended. It lasted for {duration_formatted}.")

            del work_sessions[user_id]
    else:
        await ctx.send("You haven't started a work session yet!")

async def send_reminder(user_id, ctx, is_registered):
    while True:
        await asyncio.sleep(30 * 60)  # Wait for 30 minutes
        if user_id not in work_sessions and is_registered:
            break
        if user_id not in unregistered_work_sessions and not is_registered:
            break

        session_info = work_sessions.get(user_id) or unregistered_work_sessions.get(user_id) 
        start_time = session_info['start_time']
        current_time = datetime.now()
        duration = current_time - start_time
        duration_formatted = _format_duration(duration)

        await ctx.send(f"You've been working for {duration_formatted}! Keep up the good work!")

def _format_duration(duration):
    duration_seconds = duration.seconds
    duration_minutes = duration_seconds // 60
    duration_hours = duration_minutes // 60
    duration_minutes %= 60
    duration_seconds %= 60

    duration_parts = []
    if duration_hours > 0:
        duration_parts.append(f"{duration_hours}h")
    if duration_minutes > 0 or duration_hours > 0: 
        duration_parts.append(f"{duration_minutes}m")
    duration_parts.append(f"{duration_seconds}s")
    duration_formatted = " ".join(duration_parts)
    return duration_formatted

@bot.command()
async def howlong(ctx):
    user_id = ctx.author.id

    if user_id in work_sessions:
        session_info = work_sessions[user_id]
        start_time = session_info['start_time']
        current_time = datetime.now()
        duration = current_time - start_time

        duration_formatted = _format_duration(duration)

        if session_info.get('is_pomodoro'):

            remaining_time = timedelta(minutes=25) - duration
            remaining_seconds = remaining_time.seconds
            remaining_minutes = remaining_seconds // 60
            remaining_seconds %= 60
            remaining_formatted = f"{remaining_minutes}m {remaining_seconds}s"

            await ctx.send(f"Pomodoro in progress. Time worked: {duration_formatted}. Time remaining: {remaining_formatted}")
        else:

            await ctx.send(f"Time worked: {duration_formatted}")
    else:
        await ctx.send("You haven't started a work session yet!")

@bot.command()
async def pomodoro(ctx):
    user_id = ctx.author.id
    is_registered = user_already_registered(user_id)

    if user_id in work_sessions:
        # Check if it's already a pomodoro session
        if work_sessions[user_id].get('is_pomodoro'):
            await ctx.send("You're already in a pomodoro session. Wait for it to end.")
            return
        else:  
            await ctx.send("You're already in a work session. Finish it first.")
            return

    # Store necessary information in work_sessions
    work_sessions[user_id] = {'start_time': datetime.now(), 'is_registered': is_registered, 'is_pomodoro': True}
    await ctx.send(f"Pomodoro session started. Focus for 25 minutes!")

    asyncio.create_task(end_pomodoro(user_id, ctx))



async def end_pomodoro(user_id, ctx):
    await asyncio.sleep(25 * 60)  # Wait for 25 minutes
    if user_id in work_sessions and work_sessions[user_id].get('is_pomodoro'):
        finish_time = datetime.now()

        # Handle survey
        if work_sessions[user_id]['is_registered'] and get_user_preference(user_id, "WantsMoodSurveys"):
            end_mood, end_motivation = await get_mood_and_motivation(ctx, "end")
            await _store_work_session(ctx, user_id, work_sessions[user_id]['start_time'], finish_time, mood_end=end_mood, motivation_end=end_motivation)
        else:
            await _store_work_session(ctx, user_id, work_sessions[user_id]['start_time'], finish_time)

        del work_sessions[user_id]
        await ctx.send(f"Pomodoro session ended at {finish_time}. Time for a break!")


@bot.command()
async def togglesurveys(ctx):
    user_id = ctx.author.id
    if not user_already_registered(user_id):
        await ctx.send("You need to be registered to use this feature. Use !register to get started.")
        return

    try:
        cursor = mydb.cursor()
        query = "SELECT WantsMoodSurveys FROM Users WHERE UserID = %s"
        cursor.execute(query, (user_id,))
        current_preference = cursor.fetchone()[0]

        new_preference = not current_preference
        query = "UPDATE Users SET WantsMoodSurveys = %s WHERE UserID = %s"
        cursor.execute(query, (new_preference, user_id))
        mydb.commit()

        message = "Mood and motivation surveys are now **enabled**." if new_preference else "Mood and motivation surveys are now **disabled**."
        await ctx.send(message)
    except mysql.connector.Error as err:
        await ctx.send(f"An error occurred while updating your preferences: {err}")
    finally:
        cursor.close()
