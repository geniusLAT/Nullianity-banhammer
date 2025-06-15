import telebot
import setting
from postgresStorage import PostgresStorage
from datetime import datetime, timedelta
import time

my_setting = setting.settings()
logger_chat = my_setting.logger_chat
special_chat = my_setting.special_chat
token = my_setting.token
toxicity_threshold = my_setting.toxicity_threshold

bot = telebot.TeleBot(token)

bot_name = bot.get_me().username
bot_tag = f"@{bot_name}"

storage = PostgresStorage(my_setting)

def check_status(message):
    user_status = bot.get_chat_member(message.chat.id, message.from_user.id).status
    return user_status == "administrator" or user_status == "creator"


def next_midnight():
    now = datetime.now()
    midnight_today = datetime(now.year, now.month, now.day)
    #from UTC+5 to UTC+0
    #TODO do it correct
    midnight_today = midnight_today - timedelta(hours=5)
    if now >= midnight_today:
        midnight_today += timedelta(days=1)

    return midnight_today 


def mute_user_for(message, duration_in_days=1):
    user_status = bot.get_chat_member(message.chat.id, message.from_user.id).status
    if user_status == "administrator" or user_status == "creator":
        bot.reply_to(message, "Невозможно замутить администратора.")
        return

    bot.restrict_chat_member(
        message.chat.id,
        message.from_user.id,
        until_date=next_midnight() + timedelta(days=duration_in_days),
    )

def choose_ban_time(message,user) -> int:
    global storage
    user = storage.get_user(message.from_user.id)
    if user:
        last_ban_time = user.days
        if last_ban_time == 0:
            return 1
        return last_ban_time * 2
    else:
        return 1

def mute_user(message, admin_telegram_user_id:int = bot.get_me().id):
    global storage
    user = storage.get_user(message.from_user.id)
    ban_time = choose_ban_time(message, user)
    print(f"Chosen: {ban_time} days")
    mute_user_for(message, ban_time)
    if user:
        storage.update_user(message.from_user.id, admin_telegram_user_id, days = ban_time)
    else:
        storage.create_user_ban_time(message.from_user.id, admin_telegram_user_id)
    return ban_time


@bot.message_handler(commands=["start"])
def start_message(message):
    bot.send_message(message.chat.id, "Привет ✌️ ")


def check_for_command(message):
    global storage
    status = check_status(message)
    if message.reply_to_message == None:
        return
    if not status:
        return

    if message.text.startswith("/ban"):
        ban_time = mute_user(message.reply_to_message, message.from_user.id)
        bot.reply_to(
            message.reply_to_message, f"Забанен модератором {message.from_user.username} на {ban_time} дней"
        )
        return
    if message.text.startswith("/set_ban"):
        words = message.text.split(" ")
        days = 0
        if len(words) < 2:
            bot.reply_to(message, f"Неверный синтаксис. \nПример: /set_ban 10")
            return
        try:
            days = int(words[1])
        except:
            bot.reply_to(
                message,
                f"Неверный синтаксис. \n {words[1]} не является целым числом \nПример: /set_ban 10",
            )
            return
        #tracker.update_user(message.reply_to_message.from_user.id, days)
        bot.reply_to(
            message,
            f"Время последнего бана перезаписано для {message.reply_to_message.from_user.username} на {days} дней",
        )
        return
    if message.text.startswith("/unban"):
        chat_id = special_chat
        user_id = message.reply_to_message.from_user.id
        print(user_id)
        user_status = bot.get_chat_member(message.chat.id, user_id).status
        if user_status == "administrator" or user_status == "creator":
            bot.reply_to(message, "Невозможно лишить прав администратора. Так что и вернуть ему права невозможно.")
        else:
            bot.restrict_chat_member(
                chat_id,
                user_id,
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )


        user = storage.get_user(message.from_user.id)
        if user:
            last_ban_time = user.days
            if last_ban_time == 0:
                 bot.reply_to(
                    message,
                    f"Пользователь {message.reply_to_message.from_user.username} уже был реабилитирован за все нарушения.",
                )
            else:
                if last_ban_time == 1:
                    storage.update_user(message.from_user.id, days = 0)
                    bot.reply_to(
                        message,
                        f"Пользователь {message.reply_to_message.from_user.username} реабилитирован по последнему нарушению",
                    )
                else:
                    storage.update_user(message.from_user.id, days = int(last_ban_time / 2))
                    bot.reply_to(
                        message,
                        f"Пользователь {message.reply_to_message.from_user.username} реабилитирован .",
                    )
        else:
             bot.reply_to(
                    message,
                    f"Пользователь {message.reply_to_message.from_user.username} не отмечен в базе как ранее привлекавщийся. Его нельзя реабилтировать, пока он не получит свой первый бан",
                )

#TODO add handler for commands
@bot.message_handler(content_types="text")
def message_reply(message):
    print("msg :", message.chat.id)
    try:
        check_for_command(message)
    except Exception as e:
        print(e)


bot.infinity_polling()
