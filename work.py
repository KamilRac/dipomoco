from defs import *

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
            'session_id': session_id
        }
    else:

        if user_id in unregistered_work_sessions:
            await ctx.send("You've already started an unregistered work session!")
            return
        unregistered_work_sessions[user_id] = {'start_time': datetime.now()}

    await ctx.send("Work session started. Good luck!")



    asyncio.create_task(end_pomodoro())

@bot.command(aliases=["finishwork"])
async def finish(ctx):
    user_id = ctx.author.id
    finish_time = datetime.now()

    if user_id in work_sessions:
        # registered users
        wants_surveys = get_user_preference(user_id, "WantsMoodSurveys")
        is_registered = user_already_registered(user_id)
        session_id = work_sessions[user_id]['session_id']
        start_time = work_sessions[user_id]['start_time'] 
        duration = finish_time - start_time 

        # Calculate and format
        duration_seconds = duration.seconds
        duration_minutes = duration_seconds // 60
        duration_hours = duration_minutes // 60
        duration_minutes %= 60
        duration_seconds %= 60


        duration_parts = []
        if duration_hours > 0:
            duration_parts.append(f"{duration_hours}h")
        if duration_minutes > 0:
            duration_parts.append(f"{duration_minutes}m")
        duration_parts.append(f"{duration_seconds}s")
        duration_formatted = " ".join(duration_parts)

        if is_registered and wants_surveys:
            end_mood, end_motivation = await get_mood_and_motivation(ctx, "end")


            cursor = mydb.cursor()
            query = "UPDATE WorkTimes SET FinishTime = %s, MoodEnd = %s, MotivationEnd = %s WHERE SessionID = %s"
            cursor.execute(query, (finish_time, end_mood, end_motivation, session_id))
            mydb.commit()
            cursor.close()
        else:

            cursor = mydb.cursor()
            query = "UPDATE WorkTimes SET FinishTime = %s WHERE SessionID = %s"
            cursor.execute(query, (finish_time, session_id))
            mydb.commit()
            cursor.close()  

        del work_sessions[user_id]
        await ctx.send(f"Work session ended. It lasted for {duration_formatted}.")

    elif user_id in unregistered_work_sessions:

        start_time = unregistered_work_sessions[user_id]['start_time']
        duration = finish_time - start_time


        duration_seconds = duration.seconds
        duration_minutes = duration_seconds // 60
        duration_hours = duration_minutes // 60
        duration_minutes %= 60
        duration_seconds %= 60

        duration_parts = []
        if duration_hours > 0:
            duration_parts.append(f"{duration_hours}h")
        if duration_minutes > 0:
            duration_parts.append(f"{duration_minutes}m")
        duration_parts.append(f"{duration_seconds}s")
        duration_formatted = " ".join(duration_parts)

        del unregistered_work_sessions[user_id]
        await ctx.send(f"Unregistered work session ended. It lasted for {duration_formatted}.") 

    else:
        await ctx.send("You haven't started a work session yet!")

@bot.command()
async def pomodoro(ctx):
    user_id = ctx.author.id
    is_registered = user_already_registered(user_id)

    if user_id in work_sessions:
        await ctx.send("You're already in a work session. Finish it first or wait for the pomodoro to end.")
        return

    work_sessions[user_id] = {'start_time': datetime.now(), 'is_registered': is_registered, 'is_pomodoro': True}
    await ctx.send(f"Pomodoro session started. Focus for 25 minutes!")


    async def end_pomodoro():
        await asyncio.sleep(25 * 60)  # Wait for 25 minutes
        if user_id in work_sessions and work_sessions[user_id]['is_pomodoro']:
            finish_time = datetime.now()
            await _store_work_session(ctx, user_id, work_sessions[user_id]['start_time'], finish_time)
            del work_sessions[user_id]
            await ctx.send(f"Pomodoro session ended at {finish_time}. Time for a break!")

    asyncio.create_task(end_pomodoro())

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