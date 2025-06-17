import telebot
import setting
from postgresStorage import PostgresStorage
from datetime import datetime, timedelta
import time

WARNS_TO_BAN = 3
APPROVES_TO_SATISFY_APPEAL = 3

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
    user_status = bot.get_chat_member(my_setting.special_chat, message.from_user.id).status
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


def warn_user(message, admin_telegram_user_id:int = bot.get_me().id):
    global storage
    user = storage.get_warned_user(message.from_user.id)
    if user:
        if user.counter+1 >= WARNS_TO_BAN:
            storage.update_warned_user(message.from_user.id, admin_telegram_user_id, counter = 0)
            return 0
        storage.update_warned_user(message.from_user.id, admin_telegram_user_id, counter = user.counter + 1)
        return user.counter+1
    else:
        storage.create_warned_user_ban_time(message.from_user.id, admin_telegram_user_id)
        return 1


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
    if message.text.startswith("/warn"):
        warn_time = warn_user(message.reply_to_message, message.from_user.id)
        if warn_time == 0:
            ban_time = mute_user(message.reply_to_message, message.from_user.id)
            bot.reply_to(
                message.reply_to_message, f"Предупреждение {WARNS_TO_BAN} выдано модератором {message.from_user.username}. Вы достигли лимита в {WARNS_TO_BAN}. Вы забанены модератором {message.from_user.username} на {ban_time} дней"
            )
            return
        bot.reply_to(
            message.reply_to_message, f"Предупреждение {warn_time} выдано модератором {message.from_user.username}"
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


        user = storage.get_user(message.reply_to_message.from_user.id)
        if user:
            last_ban_time = user.days
            if last_ban_time == 0:
                 bot.reply_to(
                    message,
                    f"Пользователь {message.reply_to_message.from_user.username} уже был реабилитирован за все нарушения.",
                )
            else:
                if last_ban_time == 1:
                    storage.update_user(message.reply_to_message.from_user.id, days = 0)
                    bot.reply_to(
                        message,
                        f"Пользователь {message.reply_to_message.from_user.username} реабилитирован по последнему нарушению",
                    )
                else:
                    storage.update_user(message.reply_to_message.from_user.id, days = int(last_ban_time / 2))
                    bot.reply_to(
                        message,
                        f"Пользователь {message.reply_to_message.from_user.username} реабилитирован .",
                    )
        else:
             bot.reply_to(
                    message,
                    f"Пользователь {message.reply_to_message.from_user.username} не отмечен в базе как ранее привлекавщийся. Его нельзя реабилтировать, пока он не получит свой первый бан",
                )


def check_right_for_appeal(message, user):
    if not user:
        bot.reply_to(
            message,
            f"Апелляция отклонена. Вы не отмечены в базе как нарушитель. Вы не можете апеллировать решению о нарушении без такого решения.",
        )
        return False

    if user.days == 0:
        bot.reply_to(
            message,
            f"Апелляция отклонена. Вы реабилитированы по всем пунктам.",
        )
        return False

    # appeal = storage.get_appeal_by_ban_id(user.id)
    # if appeal:
    #     if not appeal.isClosed:
    #         bot.reply_to(
    #             message,
    #             f"Вы уже подавали апелляцию {appeal.appealDate}. Вы не можете ",
    #         )
    #         return False

    if datetime.now() - user.ban_date > timedelta(hours = 72):
        bot.reply_to(
            message,
            f"Апелляция отклонена. Срок подачи апелляции истёк",
        )
        return False

    return True


def public_appeal(message):
    post_text = f"Автор {message.from_user.username}\nАпелляция: {message.text}"
    mes = bot.send_message(chat_id=my_setting.appeal_channel, text=post_text) 
    print(f"published appeal id {mes.id}")
    return mes.id


def register_appeal(message):
    user = storage.get_user(message.from_user.id)
    if not check_right_for_appeal(message, user):
        return
    appeal_message_id = public_appeal(message)
    print("creating appeal")
    storage.create_appeal(user.id, appeal_message_id)
    print("created appeal")
    bot.reply_to(
                        message,
                        f"Апелляция зарегестрирована.",
                    )
                    
def connect_appeal(message):
    if message.from_user.id == 777000:
        print("Caught message")
        print(f"caught appeal id {message.forward_origin.message_id}")
        #print(message)
        bot.reply_to(
                    message,
                    f"Началось рассмотрение апелляции. Модераторы, кроме того, чьё решение обсуждается, имеют право проголосовать за одобрение апелляции командой /approve. Для одобрения необходимо голосов:{APPROVES_TO_SATISFY_APPEAL}",
                )
        return True
    return False
                    

def check_for_appeal_command(message):
    if message.chat.id != my_setting.appeal_channel_discussion:
        return
    connect = connect_appeal(message)
    if not connect:
        print(f"replied for: {message.reply_to_message.text}")
        print(f"replied for ID: {message.reply_to_message.forward_origin.message_id}")
        appeal = storage.get_appeal(message.reply_to_message.forward_origin.message_id)
        print(appeal)
        if message.text.startswith("/approve"):
            if not appeal:
                bot.reply_to(
                    message,
                    f"Ошибка одобрения апелляции",
                )
                return False
            if appeal.isClosed:
                bot.reply_to(
                    message,
                    f"Данная апелляция уже была одобрена. Дополнительное одобрение избыточно.",
                )
                return False
            if datetime.now() - appeal.appealDate > timedelta(days = 7):
                bot.reply_to(
                    message,
                    f"Одобрение данной апелляции идёт с опозданием, она была размещена более 7 дней назад",
                )
            banned_user = storage.get_user_by_ban_id(appeal.banId)
            if not banned_user:
                bot.reply_to(
                    message,
                    f"Апелляция создана на несуществующего пользователя. Записи в БД пропали. Это странно. Вам стоит задуматься...",
                )
                return False
            if banned_user.admin_telegram_user_id == message.from_user.id:
                bot.reply_to(
                    message,
                    f"Вы являетесь тем администратором, который забанил юзера, подавшего апелляцию. Вы не имеете права голоса в рамках этой апелляции",
                )
                #return False
            if banned_user.telegram_user_id == message.from_user.id:
                bot.reply_to(
                    message,
                    f"Вы являетесь пользователем, чья апелляция сейчас рассматривается. Вы не имеете права голоса в рамках этой апелляции",
                )
                #return False
            if not check_status(message):
                bot.reply_to(
                    message,
                    f"Одобрить апелляцию способен только администратор",
                )
                # return False
            if storage.is_appeal_approved_by_the_user(appeal.id, message.from_user.id):
                bot.reply_to(
                    message,
                    f"Вы уже одобрили данную апелляцию",
                )
                #return False

            approve_appeal(message, appeal, banned_user)


def approve_appeal(message, appeal, user):
    storage.create_appeal_approve(appeal.id, message.from_user.id )

    satisfaction_message = ""
    approve_counter = storage.count_appeals_by_id(appeal.id)
    if approve_counter == APPROVES_TO_SATISFY_APPEAL:
        print("Appeal was satisfied")
        storage.close_appeal_by_id(appeal.id)
        satisfaction_message = f"Апелляция получила необходимое количество одобрений и считается удовлетворённой. Вы как последний член апелляционной комиссии должны её удовлетоворить."
    bot.reply_to(
                    message,
                    f"Аппеляция одобрена модератором {message.from_user.username}.\n {satisfaction_message}",
                )



#TODO add handler for commands
@bot.message_handler(content_types="text")
def message_reply(message):
    print("msg :", message.chat.id)
   
    #print(message)
    try:
        check_for_appeal_command(message)
        check_for_command(message)

        if message.chat.type == 'private':
            register_appeal(message)
    except Exception as e:
        print(e)


bot.infinity_polling()
