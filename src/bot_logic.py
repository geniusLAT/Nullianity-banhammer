import telebot
import setting
from postgresStorage import PostgresStorage
from datetime import datetime, timedelta
import time

WARNS_TO_BAN = 3
APPROVES_TO_SATISFY_APPEAL = 3
DAYS_BEFORE_WARN_EXPIRE = 7
DEVELOPER_MODE = True

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
        log = "Невозможно замутить администратора."
        #bot.reply_to(message, log)
        return log

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
    mute_user_for_log = mute_user_for(message, ban_time)
    if mute_user_for_log != "" and not DEVELOPER_MODE:
        return ban_time, mute_user_for_log
    if user:
        storage.update_user(message.from_user.id, admin_telegram_user_id, days = ban_time)
    else:
        storage.create_user_ban_time(message.from_user.id, admin_telegram_user_id)
    return ban_time, mute_user_for_log


def warn_user(message, admin_telegram_user_id:int = bot.get_me().id):
    global storage
    warn_log = ""
    user = storage.get_warned_user(message.from_user.id)
    if user:
        now = datetime.now()
        spent_time = now - user.warn_date
        print(f"spent_time {spent_time}")
        warn_log = f"Предыдушее предупреждение было получено пользователем {user.warn_date}."
        warn_log += f"\nСейчас {now}"
        warn_log += f"\n прошло {spent_time},"
        if  spent_time > timedelta(days=DAYS_BEFORE_WARN_EXPIRE):
            warn_log += f"это более {DAYS_BEFORE_WARN_EXPIRE} суток. Предыдушее предупреждение утратило силу, так что текущее предупреждение считается первым"
            print(warn_log)
            user.counter=0
        if user.counter+1 >= WARNS_TO_BAN:
            storage.update_warned_user(message.from_user.id, admin_telegram_user_id, counter = 0)
            return 0, warn_log
        storage.update_warned_user(message.from_user.id, admin_telegram_user_id, counter = user.counter + 1)
        return user.counter+1, warn_log
    else:
        warn_log += f"Данный пользователь никогда ранее не получал предупреждений"
        storage.create_warned_user_ban_time(message.from_user.id, admin_telegram_user_id)
        return 1, warn_log


@bot.message_handler(commands=["start"])
def start_message(message):
    start_message = ""
    start_message += f"Количество предупреждений для получения мута: {WARNS_TO_BAN}\n"
    start_message += f"Количество одобрений для принятия апелляции: {APPROVES_TO_SATISFY_APPEAL}\n"
    start_message += f"Режим разработчика: {DEVELOPER_MODE}"
    if DEVELOPER_MODE:
        start_message += "\n\n В режиме разработчика бот по прежнему показывает время банов для администраторов, хотя фактически не лишает их прав. Но заносит их в базу данных.\n"
    bot.send_message(message.chat.id, start_message)


def check_for_command(message):
    global storage
    status = check_status(message)
    if message.reply_to_message == None:
        return
    if not status:
        return

    text_commandless = "".join(message.text.split(" ")[1:])

    if message.text.startswith("/ban"):
        ban_time, mute_user_log = mute_user(message.reply_to_message, message.from_user.id)
        log = f"Мут на {ban_time} дней выдан модератором {message.from_user.username} ({message.from_user.id})"
        log += f" пользователю {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id})\n"
        log +=  mute_user_log
        log += f"\nКомментарий модератора: {text_commandless}"
        if mute_user_log == "" or DEVELOPER_MODE:
            bot.reply_to(
                message.reply_to_message, f"Мут наложен модератором {message.from_user.username} на {ban_time} дней"
            )
        else:
            bot.reply_to(
                message.reply_to_message, f"Попытка замутить предпринята модератором {message.from_user.username} на {ban_time} дней\n Попытка неудачна. Невозможно замутить администратора."
            )
        publish_log(log)
        return
    if message.text.startswith("/warn"):
        print("warn command")
        warn_time, warn_log = warn_user(message.reply_to_message, message.from_user.id)
        print("warn command 1")
        if warn_time == 0:
            print("warn command 2")
            ban_time, mute_user_log = mute_user(message.reply_to_message, message.from_user.id)
            
            log = f"Предупреждение {warn_time} выдано модератором {message.from_user.username} ({message.from_user.id})"
            log += f" пользователю {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id})"
            log +=  f" Достигнут лимит в {WARNS_TO_BAN}. Пользователь был забанен на {ban_time} дней"
            log +=  warn_log + mute_user_log
            log += f"\nКомментарий модератора: {text_commandless}\n\n"
            publish_log(log)
            if mute_user_log != "":
                bot.reply_to(
                message.reply_to_message, f"Предупреждение {WARNS_TO_BAN} выдано модератором {message.from_user.username}. Вы достигли лимита в {WARNS_TO_BAN}. Вы забанены модератором {message.from_user.username} на {ban_time} дней"
                )
            return
        print("warn command 3")
        log = f"Предупреждение {warn_time} выдано модератором {message.from_user.username} ({message.from_user.id})"
        log += f" пользователю {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id})"
        log += f"\nКомментарий модератора: {text_commandless}\n\n"
        log +=  warn_log
        publish_log(log)
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
        log = ""
        chat_id = special_chat
        user_id = message.reply_to_message.from_user.id
        
        log += f"Снятие мута с пользователя {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id}) "
        log += f"модератором {message.from_user.username} ({message.from_user.id}) "
        log += f"\nКомментарий модератора: {text_commandless}"
        user_status = bot.get_chat_member(message.chat.id, user_id).status
        if user_status == "administrator" or user_status == "creator":
            bot.reply_to(message, "Невозможно лишить прав администратора. Так что и вернуть ему права невозможно.")
            log += f"Ошибка: Невозможно лишить прав администратора. Так что и вернуть ему права невозможно. "
            if not DEVELOPER_MODE:
                publish_log(log)
                return
            else:
                log += f"\n(Ошибка будет проигнорирована так как вызвана в режиме разработчика)"
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
                log += "Снятие мута не завершено"
                reason = f"Пользователь {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id}) уже был реабилитирован за все нарушения."
                log += reason
                bot.reply_to(message,reason)
            else:
                if last_ban_time == 1:
                    storage.update_user(message.reply_to_message.from_user.id, days = 0)
                    reason = f"Пользователь {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id}) реабилитирован по последнему нарушению"
                    log += reason
                    bot.reply_to(message, reason)
                else:
                    storage.update_user(message.reply_to_message.from_user.id, days = int(last_ban_time / 2))
                    reason = f"Пользователь {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id}) реабилитирован"
                    log += reason
                    bot.reply_to(message, reason)
        else:
            log += "Снятие мута не завершено"
            reason = f"Пользователь {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id}) не отмечен в базе как ранее привлекавщийся. Его нельзя реабилтировать, пока он не получит свой первый мут",
            log += reason
            bot.reply_to(message,reason)
        publish_log(log)
    #
    if message.text.startswith("/unwarn"):
        log = ""
        chat_id = special_chat
        user_id = message.reply_to_message.from_user.id
        
        log += f"Снятие предупреждения с пользователя {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id}) "
        log += f"модератором {message.from_user.username} ({message.from_user.id}) "
        #user_status = bot.get_chat_member(message.chat.id, user_id).status
        log += f"\nКомментарий модератора: {text_commandless}"
        user = storage.get_warned_user(message.reply_to_message.from_user.id)
        if user:
            warn_counter = user.counter

            now = datetime.now()
            spent_time = now - user.warn_date
            log += f"\nПредыдушее предупреждение было получено пользователем {user.warn_date}."
            log += f"\nСейчас {now}"
            log += f"\n прошло {spent_time},"
            if  spent_time > timedelta(days=DAYS_BEFORE_WARN_EXPIRE):
                log += f" это более {DAYS_BEFORE_WARN_EXPIRE} суток. Предыдушее предупреждение утратило силу."
                warn_counter = 0
            else: 
                log += f" это не более {DAYS_BEFORE_WARN_EXPIRE} суток. Предыдушее предупреждение не утратило силу."

            if warn_counter == 0:
                log += "\nСнятие предупреждения не завершено\n"
                reason = f"Пользователь {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id}) имеет 0 не истёкших предупреждений"
                log += reason
                bot.reply_to(message,reason)
            else:
                storage.update_warned_user(message.reply_to_message.from_user.id, user.admin_telegram_user_id, user.warn_date, counter = warn_counter - 1)
                reason = f"Пользователь {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id}) реабилитирован по предупреждению {warn_counter}"
                log += reason
                bot.reply_to(message, reason)
        else:
            log += "\nСнятие предупреждения не завершено \n"
            reason = f"Пользователь {message.reply_to_message.from_user.username} ({message.reply_to_message.from_user.id}) не отмечен в базе как ранее получавщий предупреждение. Нельзя пытаться снять предупреждение с того, кто их не получал."
            log += reason
            bot.reply_to(message,reason)
        publish_log(log)
    

def publish_log(text:str):
    print(text)
    bot.send_message(chat_id=my_setting.logger_chat, text=text) 

##segment about mute appeals

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


def public_appeal(message, banned_user):
    day_word_form = "дней"
    r = banned_user.days % 10
    if r == 1 and banned_user.days % 100 != 11:
        day_word_form = "дней"
    if r > 1 and r < 5 and (banned_user.days % 100) - r != 10 :
        day_word_form = "дня"
    interval_message = f"{banned_user.days} {day_word_form}"
    log = f"Апелляция на мут\n\n[{message.from_user.username}](tg://user?id={message.from_user.id}) \\({message.from_user.id}\\) получил\\(a\\) свой последний мут на {interval_message}."
    log += f"\nДата наложения последнего бана {banned_user.ban_date}"
    admin = bot.get_chat_member(my_setting.special_chat, banned_user.admin_telegram_user_id).user 
    log += f"\nАдминистратор наложивший бан: [{admin.username}](tg://user?id={banned_user.admin_telegram_user_id}) \\({banned_user.admin_telegram_user_id}\\)"


    text_commandless = " ".join(message.text.split(" ")[1:], )
    if text_commandless == "":
        bot.reply_to(
                        message,
                        f"Вы, вероятно, по ошибке пытаетесь отправить пустой текст апелляции. Пожалуйста, кроме команды через пробел укажите почему вы считаете мут несправедливым",
                    )
        raise Exception(f"Empty mute appeal text by {message.from_user.username} ({message.from_user.id})")
    text_commandless = text_commandless.replace('(','\\(').replace(')','\\)').replace('=','\\=')

    post_text = f"{log}\n\nТекст апелляции: {text_commandless}"
    post_text = post_text.replace('-','\\-').replace('.','\\.').replace('!','\\!')
    print(post_text)
    publish_log(post_text)
    mes = bot.send_message(chat_id=my_setting.appeal_channel, text=post_text, parse_mode="MarkdownV2") # 
    print(f"published appeal id {mes.id}")
    return mes


def register_appeal(message):
    user = storage.get_user(message.from_user.id)
    if not check_right_for_appeal(message, user):
        return
    appeal_message = public_appeal(message, user)
    print("creating appeal")
    storage.create_appeal(user.id, appeal_message.id)
    print("created appeal")

    post_channel_id =  -1 * appeal_message.chat.id -1000000000000
    print(appeal_message.chat.id)
    print(post_channel_id)
    answer = f"[Апелляция](https://t.me/c/{post_channel_id}/{appeal_message.id}) зарегестрирована\\."
    publish_log(answer)
    bot.reply_to(
                        message,
                        answer,
                        parse_mode="MarkdownV2"
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
                warn_appeal = storage.get_warn_appeal(message.reply_to_message.forward_origin.message_id)
                if warn_appeal:
                    return check_for_warn_appeal_command(message, warn_appeal)
                else:
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
                return False
            if banned_user.telegram_user_id == message.from_user.id:
                bot.reply_to(
                    message,
                    f"Вы являетесь пользователем, чья апелляция сейчас рассматривается. Вы не имеете права голоса в рамках этой апелляции",
                )
                return False
            if not check_status(message):
                bot.reply_to(
                    message,
                    f"Одобрить апелляцию способен только администратор",
                )
                return False
            if storage.is_appeal_approved_by_the_user(appeal.id, message.from_user.id):
                bot.reply_to(
                    message,
                    f"Вы уже одобрили данную апелляцию",
                )
                return False

            approve_appeal(message, appeal, banned_user)


def approve_appeal(message, appeal, user):
    storage.create_appeal_approve(appeal.id, message.from_user.id )

    satisfaction_message = ""
    approve_counter = storage.count_appeals_by_id(appeal.id)
    if approve_counter == APPROVES_TO_SATISFY_APPEAL:
        print("Appeal was satisfied")
        storage.close_appeal_by_id(appeal.id)
        satisfaction_message = f"Апелляция получила необходимое количество одобрений и считается удовлетворённой. Вы как последний член апелляционной комиссии должны её удовлетоворить."
    answer = f"Аппеляция одобрена модератором {message.from_user.username}.\n {satisfaction_message}",
    publish_log(f" {answer} ")
    bot.reply_to(
                    message,
                    answer
                )


##segment about warn appeals

def check_right_for_warn_appeal(message, user):
    if not user:
        bot.reply_to(
            message,
            f"Апелляция отклонена. Вы не отмечены в базе как нарушитель. Вы не можете апеллировать решению о нарушении без такого решения.",
        )
        return False

    if user.counter == 0:
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

    if datetime.now() - user.warn_date > timedelta(hours = 72):
        bot.reply_to(
            message,
            f"Апелляция отклонена. Срок подачи апелляции истёк",
        )
        return False

    return True


def public_warn_appeal(message, warnned_user):
    log = f"Апелляция на предупреждение\n\n[{message.from_user.username}](tg://user?id={message.from_user.id}) \\({message.from_user.id}\\) получил\\(a\\) своё последнее предупреждение"
    log += f"\nДата наложения последнего предупреждения {warnned_user.warn_date}"
    admin = bot.get_chat_member(my_setting.special_chat, warnned_user.admin_telegram_user_id).user 
    log += f"\nАдминистратор наложивший прдупреждение: [{admin.username}](tg://user?id={warnned_user.admin_telegram_user_id}) \\({warnned_user.admin_telegram_user_id}\\)"


    text_commandless = " ".join(message.text.split(" ")[1:], )
    if text_commandless == "":
        bot.reply_to(
                        message,
                        f"Вы, вероятно, по ошибке пытаетесь отправить пустой текст апелляции. Пожалуйста, кроме команды через пробел укажите почему вы считаете мут несправедливым",
                    )
        raise Exception(f"Empty warn appeal text by {message.from_user.username} ({message.from_user.id})")
    text_commandless = text_commandless.replace('(','\\(').replace(')','\\)').replace('=','\\=')

    post_text = f"{log}\n\nТекст апелляции: {text_commandless}"
    post_text = post_text.replace('-','\\-').replace('.','\\.').replace('!','\\!')
    print(post_text)
    publish_log(post_text)
    mes = bot.send_message(chat_id=my_setting.appeal_channel, text=post_text, parse_mode="MarkdownV2") # 
    print(f"published appeal id {mes.id}")
    return mes


def register_warn_appeal(message):
    user = storage.get_warned_user(message.from_user.id)
    if not check_right_for_warn_appeal(message, user):
        return
    appeal_message = public_warn_appeal(message, user)
    print("creating warn appeal")
    storage.create_warn_appeal(user.id, appeal_message.id)
    print("created warn appeal")

    post_channel_id =  -1 * appeal_message.chat.id -1000000000000
    print(appeal_message.chat.id)
    print(post_channel_id)
    answer = f"[Апелляция на предупреждение](https://t.me/c/{post_channel_id}/{appeal_message.id}) зарегестрирована\\."
    publish_log(answer)
    bot.reply_to(
                        message,
                        answer,
                        parse_mode="MarkdownV2"
                    )

def check_for_warn_appeal_command(message, appeal):
    print(appeal)
    if message.text.startswith("/approve"):
        if not appeal:
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
        warned_user = storage.get_warned_user_by_warn_id(appeal.warnId)
        if not warned_user:
            bot.reply_to(
                message,
                f"Апелляция создана на несуществующего пользователя. Записи в БД пропали. Это странно. Вам стоит задуматься...",
            )
            return False
        if warned_user.admin_telegram_user_id == message.from_user.id:
            bot.reply_to(
                message,
                f"Вы являетесь тем администратором, который дал предупреждение юзеру, подавшему апелляцию. Вы не имеете права голоса в рамках этой апелляции",
            )
            return False
        if warned_user.telegram_user_id == message.from_user.id:
            bot.reply_to(
                message,
                f"Вы являетесь пользователем, чья апелляция сейчас рассматривается. Вы не имеете права голоса в рамках этой апелляции",
            )
            return False
        if not check_status(message):
            bot.reply_to(
                message,
                f"Одобрить апелляцию способен только администратор",
            )
            return False
        if storage.is_warn_appeal_approved_by_the_user(appeal.id, message.from_user.id):
            bot.reply_to(
                message,
                f"Вы уже одобрили данную апелляцию",
            )
            return False

        approve_warn_appeal(message, appeal, banned_user)
        return True


def approve_warn_appeal(message, appeal, user):
    storage.create_warn_appeal_approve(appeal.id, message.from_user.id )

    satisfaction_message = ""
    approve_counter = storage.count_warn_appeals_by_id(appeal.id)
    if approve_counter == APPROVES_TO_SATISFY_APPEAL:
        print("Appeal was satisfied")
        storage.close_warn_appeal_by_id(appeal.id)
        satisfaction_message = f"Апелляция получила необходимое количество одобрений и считается удовлетворённой. Вы как последний член апелляционной комиссии должны её удовлетоворить."
    answer = f"Аппеляция одобрена модератором {message.from_user.username}.\n {satisfaction_message}",
    publish_log(f" {answer} ")
    bot.reply_to(
                    message,
                    answer
                )

## private message processing

def show_statistics_for_user(message):
    print("showing statistics")

    user_id = message.from_user.id
    
    status_message = ""

    try:
        status = bot.get_chat_member(my_setting.special_chat, user_id).status
        if status == "creator":
            status_message = "создатель"
        if status == "administrator":
            status_message = "администратор"
        if status == "member":
            status_message = "обычный участник"
    except Exception as e:
        print(e)

    if status_message == "":
        bot.reply_to(message, "Вы не являетесь участником чата")
        return
    
    activity_message = ""
    if storage.is_active_admin(message.from_user.id):
        activity_message += ", вы в списке активных админов"

    log = f"Вы {message.from_user.username} ({message.from_user.id}), {status_message} чата, в котором работает бот{activity_message}."

    banned_user = storage.get_user(user_id)

    if banned_user:
        day_word_form = "дней"
        r = banned_user.days % 10
        if r == 1 and banned_user.days % 100 != 11:
            day_word_form = "дней"
        if r > 1 and r < 5 and (banned_user.days % 100) - r != 10 :
            day_word_form = "дня"
        interval_message = f"{banned_user.days} {day_word_form}"
        log += f"\nВы получили свой последний мут на {interval_message} ."
        log += f"\nДата наложения последнего бана {banned_user.ban_date}"
        admin = bot.get_chat_member(my_setting.special_chat, banned_user.admin_telegram_user_id).user 
        log += f"\nАдминистратор наложивший бан: {admin.username} {banned_user.admin_telegram_user_id}"

        if banned_user.days != 0:
            if datetime.now() - banned_user.ban_date > timedelta(hours = 72):
                log += f"\nСрок подачи (72 часа) апелляции истёк"
            else:
                log += f"\nВы можете подать апелляцию (напишите /help чтобы узнать подробнее)"
        else:
            log += f"\nВы не имеете права подавать апелляцию о муте, так как реабилитированы по всем пунктам."
    else:
         log += f"\nНе обнаружено записей о выдаче вам мутов со стороны администрации"
    mute_appeals = storage.get_appeals_by_telegram_user_id(user_id)
    log += f"\nВы подали апелляций на муты: {len(mute_appeals)} "
    for appeal in mute_appeals:
        closed_msg = "на рассмотрении" 
        if appeal.isClosed:
            closed_msg = "закрыта"
        count = storage.count_appeals_by_id(appeal.id)
        log += f"\nАпелляция подана {appeal.appealDate}, она {closed_msg}, получила {count}/{APPROVES_TO_SATISFY_APPEAL} одобрений"

    log += f"\n"

    warned_user = storage.get_warned_user(user_id)
    if warned_user:
        
        log += f"\nУ вас есть {warned_user.counter} предупреждений."
        log += f"\nДата наложения последнего предупреждения {warned_user.warn_date}"
        
        now = datetime.now()
        spent_time = now - warned_user.warn_date
        log += f"\nСейчас {now}"
        log += f"\n прошло {spent_time},"
        if  spent_time > timedelta(days=DAYS_BEFORE_WARN_EXPIRE):
            log += f"это более {DAYS_BEFORE_WARN_EXPIRE} суток. Предыдушее предупреждение утратило силу, так что считается, что у вас 0 предупреждений"
            print(log)
            warned_user.counter=0

        admin = bot.get_chat_member(my_setting.special_chat, warned_user.admin_telegram_user_id).user 
        log += f"\nАдминистратор наложивший предупреждение: {admin.username} {warned_user.admin_telegram_user_id}"

        if warned_user.counter > 0:
            if datetime.now() - warned_user.warn_date > timedelta(hours = 72):
                log += f"\nСрок подачи (72 часа) апелляции истёк"
            else:
                log += f"\nВы можете подать апелляцию (напишите /help чтобы узнать подробнее)"
        else:
            log += f"\nВы не имеете права подавать на аппеляцию о предупреждениях, так как количество активных предупреждений равно нулю."
    else:
         log += f"\nНе обнаружено записей о выдаче вам предупреждений со стороны администрации"
    warn_appeals = storage.get_warn_appeals_by_telegram_user_id(user_id)
    log += f"\nВы подали апелляций на варны: {len(warn_appeals)} "
    for appeal in warn_appeals:
        closed_msg = "на рассмотрении" 
        if appeal.isClosed:
            closed_msg = "закрыта"
        count = storage.count_appeals_by_id(appeal.id)
        log += f"\nАпелляция подана {appeal.appealDate}, она {closed_msg}, получила {count}/{APPROVES_TO_SATISFY_APPEAL} одобрений"


    bot.reply_to(message, log)


def subscribe_active_admin(message):
    print('adding new active admin')
    if not check_status(message):
        bot.reply_to(message, "Вы не админ, так что вы не можете быть добавлены в список")
        return False

    if storage.is_active_admin(message.from_user.id):
        bot.reply_to(message, "Вы уже добавлены в список активных админов, вы не можете присутствовать в нём дважды")
        return False
    storage.create_active_admin(message.from_user.id)
    bot.reply_to(message, "Вы были добавлены в список активных админов")
    return True

def unsubscribe_active_admin(message):
    if not storage.is_active_admin(message.from_user.id):
        bot.reply_to(message, "Вы не присутствуете в списке, так что вас нельзя оттуда удалить")
        return False
    storage.delete_active_admin(message.from_user.id)
    print('removing active admin')
    bot.reply_to(message, "Вы удалены из списка")
    return True

def show_help(message):
    answer = '''
    Бот поддерживает следующие команды
    /help - позволяет узнать список команд
    /subscribe - добавляет вас в список активных админов, вам потребуется быть админом. В беседе появится возможность применять команду /tag_admins, чтобы призвать всех активных админов
    /unsubscribe - удаляет вас из списка активных админов, вам потребуется быть админом.
    /statistics - позволяет узнать ваш статус в системе, количество мутов, предупреждений, апелляций и прочие сведения.
    /appeal_mute - позволяет подать апелляцию на наложенный на вас мут. Пожалуйста укажите как можно больше подробностей, в своём сообщении. 
    После публикации апелляции она будет размещена в канале для апелляций, где апелляционная комиссия сможет рассмотреть её согласно правилам.
    Если вы не согласны с несколькими мутами, полученными в последнее время, пожалуйста, уложите ваши пожелания в рамках одной апелляции и в тексте опишите
    все случаи, с которыми не согласны. У вас есть возможность отправить несколько апелляций, но это не рекомендуется.

    Пример: /appeal_mute мне был выдан мут администратором IvanFedorov за то, что я ругаюсь матом. Администратор не указал, какой именно пункт правил я 
    нарушаю. А ругаться матом не запрещено. Считаю мут несправедливым и незаконным.

    /appeal_warn - позволяет подать апелляцию на наложенный на вас мут. Пожалуйста укажите как можно больше подробностей, в своём сообщении. 
    После публикации апелляции она будет размещена в канале для апелляций, где апелляционная комиссия сможет рассмотреть её согласно правилам.
    Если вы не согласны с несколькими варнами (предупреждениями), полученными в последнее время, пожалуйста, уложите ваши пожелания в рамках одной апелляции и в тексте опишите
    все случаи, с которыми не согласны. У вас есть возможность отправить несколько апелляций, но это не рекомендуется.

    Пример: /appeal_warn мне был выдан варн администратором IvanFedorov за то, что я ругаюсь матом. Администратор не указал, какой именно пункт правил я 
    нарушаю. А ругаться матом не запрещено. Считаю варн несправедливым и незаконным.
    '''
    bot.reply_to(message, answer)

def process_private_chat_message(message):
    if message.text.startswith("/statistics"):
        show_statistics_for_user(message)
        return
    if message.text.startswith("/help"):
        show_help(message)
        return
    if message.text.startswith("/appeal_mute"):
        register_appeal(message)
        return
    if message.text.startswith("/appeal_warn"):
        register_warn_appeal(message)
        return
    if message.text.startswith("/subscribe"):
        subscribe_active_admin(message)
        return
    if message.text.startswith("/unsubscribe"):
        unsubscribe_active_admin(message)
        return
    bot.reply_to(message, "Напишите /help чтобы узнать подробнее")
    

#TODO add handler for commands
@bot.message_handler(content_types="text")
def message_reply(message):
    print("msg :", message.chat.id)
   
    #print(message)
    try:
        check_for_appeal_command(message)
        check_for_command(message)

        if message.chat.type == 'private':
            process_private_chat_message(message)
            #register_appeal(message)
    except Exception as e:
        print(e)


bot.infinity_polling()
