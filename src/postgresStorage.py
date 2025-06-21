from setting import settings
import psycopg2
from psycopg2 import sql
from datetime import datetime

class User:
    def __init__(self, id, telegram_user_id, admin_telegram_user_id, ban_date, days):
        self.id = id,
        self.telegram_user_id = telegram_user_id
        self.admin_telegram_user_id = admin_telegram_user_id
        self.ban_date = ban_date
        self.days = days

class WarnedUser:
    def __init__(self, telegram_user_id, admin_telegram_user_id, warn_date, counter):
        self.telegram_user_id = telegram_user_id
        self.admin_telegram_user_id = admin_telegram_user_id
        self.warn_date = warn_date
        self.counter = counter


class AppealRecord:
    def __init__(self, id, banId, messageId, isClosed, appealDate):
        self.id = id,
        self.banId = banId
        self.messageId = messageId
        self.isClosed = isClosed
        self.appealDate = appealDate


class PostgresStorage:
    def __init__(self, settings:settings):
        self.db_config = {
        'dbname': settings.databasename,
        'user': settings.databaseUsername,
        'password': settings.databasePassword,
        'host': settings.databaseIp,  
        'port': settings.databasePort
        }

        self.connection = psycopg2.connect(**self.db_config)
        self.cursor = self.connection.cursor()
        self.initial_migration()
        print("DB - OK")


    def initial_migration(self):
        sql_script = """
        CREATE TABLE IF NOT EXISTS ban_table (
            id SERIAL PRIMARY KEY,
            telegramUserId BIGINT NOT NULL,
            adminTelegramUserId BIGINT NOT NULL,
            banDate TIMESTAMP NOT NULL,
            days INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS warn_table (
            id SERIAL PRIMARY KEY,
            telegramUserId BIGINT NOT NULL,
            adminTelegramUserId BIGINT NOT NULL,
            warnDate TIMESTAMP NOT NULL,
            counter INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS appeal_table (
            id SERIAL PRIMARY KEY,
            banId INTEGER NOT NULL,
            messageId INTEGER NOT NULL UNIQUE,
            isClosed BOOLEAN NOT NULL DEFAULT FALSE,
            appealDate TIMESTAMP NOT NULL,
            FOREIGN KEY (banId) REFERENCES ban_table(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS appeal_approve_table (
            id SERIAL PRIMARY KEY,
            appealId INTEGER NOT NULL,
            appealApproveDate TIMESTAMP NOT NULL,
            telegramUserId BIGINT NOT NULL,
            FOREIGN KEY (appealId) REFERENCES appeal_table(id) ON DELETE CASCADE
        );


        """
        self.cursor.execute(sql_script)
        self.connection.commit()


    def get_warned_user(self, telegram_user_id):
        select_query = """
        SELECT telegramUserId, adminTelegramUserId, warnDate, counter 
        FROM warn_table 
        WHERE telegramUserId = %s;
        """
        self.cursor.execute(select_query, (telegram_user_id,))
        result = self.cursor.fetchone()
        
        if result:
            return WarnedUser(*result)  # Распаковываем результат в параметры конструктора User
        else:
            return None  # Пользователь не найден    

    def get_user(self, telegram_user_id):
        select_query = """
        SELECT id, telegramUserId, adminTelegramUserId, banDate, days 
        FROM ban_table 
        WHERE telegramUserId = %s;
        """
        self.cursor.execute(select_query, (telegram_user_id,))
        result = self.cursor.fetchone()
        
        if result:
            return User(*result)  # Распаковываем результат в параметры конструктора User
        else:
            return None  # Пользователь не найден


    def get_user_by_ban_id(self, ban_id):

        select_query = """
        SELECT id, telegramUserId, adminTelegramUserId, banDate, days 
        FROM ban_table 
        WHERE id = %s;
        """
        self.cursor.execute(select_query, (ban_id,))
        result = self.cursor.fetchone()
        
        if result:
            return User(*result)  # Распаковываем результат в параметры конструктора User
        else:
            return None  # Пользователь не найден


    def create_user_ban_time(self, telegramUserId:int, adminTelegramUserId:int, banDate:datetime= datetime.now(), days: int =1):

        insert_query = """
        INSERT INTO ban_table (telegramUserId, adminTelegramUserId, banDate, days)
        VALUES (%s, %s, %s, %s);
        """
        self.cursor.execute(insert_query, (telegramUserId, adminTelegramUserId, banDate, days))
        self.connection.commit()

    def update_user(self, telegramUserId, adminTelegramUserId=None, ban_date= datetime.now(), days=None):
        update_query = """
        UPDATE ban_table 
        SET adminTelegramUserId = %s, banDate = %s, days = %s 
        WHERE telegramUserId = %s;
        """
        
        # Заменяем None на текущие значения, чтобы не обновлять их, если не переданы новые значения
        self.cursor.execute(update_query, (
            adminTelegramUserId if adminTelegramUserId is not None else self.get_current_value_from_ban_table(telegramUserId, 'adminTelegramUserId'),
            ban_date if ban_date is not None else self.get_current_value_from_ban_table(telegramUserId, 'banDate'),
            days if days is not None else self.get_current_value_from_ban_table(telegramUserId, 'days'),
            telegramUserId
        ))
        
        self.connection.commit()

    def get_current_value_from_ban_table(self, telegramUserId, column_name):
        select_query = f"SELECT {column_name} FROM ban_table WHERE telegramUserId = %s;"
        self.cursor.execute(select_query, (telegramUserId,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def create_warned_user_ban_time(self, telegramUserId:int, adminTelegramUserId:int, warnDate:datetime= datetime.now(), counter: int =1):

        insert_query = """
        INSERT INTO warn_table (telegramUserId, adminTelegramUserId, warnDate, counter)
        VALUES (%s, %s, %s, %s);
        """
        self.cursor.execute(insert_query, (telegramUserId, adminTelegramUserId, warnDate, counter))
        self.connection.commit()
    
    def update_warned_user(self, telegramUserId, adminTelegramUserId=None, warnDate = datetime.now(), counter=None):
        update_query = """
        UPDATE warn_table 
        SET adminTelegramUserId = %s, warnDate = %s, counter = %s 
        WHERE telegramUserId = %s;
        """
        
        # Заменяем None на текущие значения, чтобы не обновлять их, если не переданы новые значения
        self.cursor.execute(update_query, (
            adminTelegramUserId if adminTelegramUserId is not None else self.get_current_value_from_warn_table(telegramUserId, 'adminTelegramUserId'),
            warnDate if warnDate is not None else self.get_current_value_from_warn_table(telegramUserId, 'warnDate'),
            counter if counter is not None else self.get_current_value_from_warn_table(telegramUserId, 'counter'),
            telegramUserId
        ))
        
        self.connection.commit()
    

    def get_current_value_from_warn_table(self, telegramUserId, column_name):
        select_query = f"SELECT {column_name} FROM warn_table WHERE telegramUserId = %s;"
        self.cursor.execute(select_query, (telegramUserId,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    # CREATE TABLE IF NOT EXISTS appeal_table (
    #         id SERIAL PRIMARY KEY,
    #         banId INTEGER NOT NULL UNIQUE,
    #         messageId INTEGER NOT NULL UNIQUE,
    #         isClosed BOOLEAN NOT NULL DEFAULT FALSE,
    #         appealDate TIMESTAMP NOT NULL,
    #         FOREIGN KEY (banId) REFERENCES ban_table(id) ON DELETE CASCADE
    #     );

    #     CREATE TABLE IF NOT EXISTS appeal_approve_table (
    #         id SERIAL PRIMARY KEY,
    #         appealId INTEGER NOT NULL UNIQUE,
    #         appealApproveDate TIMESTAMP NOT NULL,
    #         telegramUserId BIGINT NOT NULL,
    #         FOREIGN KEY (appealId) REFERENCES appeal_table(id) ON DELETE CASCADE
    #     );

    def create_appeal(self, banId:int, messageId:int, appealDate:datetime= datetime.now()):

        insert_query = """
        INSERT INTO appeal_table (banId, messageId, appealDate)
        VALUES (%s, %s, %s);
        """
        self.cursor.execute(insert_query, (banId, messageId, appealDate))
        self.connection.commit()

    def get_appeal(self, messageId):
        select_query = """
        SELECT id, banId, messageId, isClosed, appealDate
        FROM appeal_table 
        WHERE messageId = %s;
        """
        self.cursor.execute(select_query, (messageId,))
        result = self.cursor.fetchone()
        
        if result:
            return AppealRecord(*result)
        else:
            return None

    def get_appeal_by_ban_id(self, banId):
        select_query = """
        SELECT id, banId, messageId, isClosed, appealDate
        FROM appeal_table 
        WHERE banId = %s;
        """
        self.cursor.execute(select_query, (banId,))
        result = self.cursor.fetchone()
        
        if result:
            return AppealRecord(*result)
        else:
            return None
    

    def close_appeal_by_id(self, appeal_id: int) -> bool:
        update_query = """
        UPDATE appeal_table 
        SET isClosed = TRUE 
        WHERE id = %s 
        RETURNING *;
        """
        
        self.cursor.execute(update_query, (appeal_id,))
        updated_appeal = self.cursor.fetchone()
        
        if updated_appeal:
            return True
        else:
            return False


    def create_appeal_approve(self, appealId:int, telegramUserId:int, appealApproveDate:datetime= datetime.now()):
        insert_query = """
        INSERT INTO appeal_approve_table (appealId, appealApproveDate, telegramUserId)
        VALUES (%s, %s, %s);
        """
        self.cursor.execute(insert_query, (appealId, appealApproveDate, telegramUserId))
        self.connection.commit()


    def is_appeal_approved_by_the_user(self, appealId: int, telegramUserId: int) -> bool:
        check_query = """
        SELECT EXISTS (
            SELECT 1 
            FROM appeal_approve_table 
            WHERE appealId = %s AND telegramUserId = %s
        );
        """
        self.cursor.execute(check_query, (appealId, telegramUserId))
        result = self.cursor.fetchone()
        
        return result[0]

    def count_appeals_by_id(self, appealId: int) -> int:
        count_query = """
        SELECT COUNT(*) 
        FROM appeal_approve_table 
        WHERE appealId = %s;
        """
        self.cursor.execute(count_query, (appealId,))
        result = self.cursor.fetchone()
        
        # result[0] содержит количество записей с заданным appealId
        return result[0]



if __name__ == "__main__":
    my_settings = settings()
    my_storage = PostgresStorage(my_settings)

    my_storage.create_user_ban_time(telegramUserId=5, adminTelegramUserId = 8,days = 5)
    my_storage.update_user(telegramUserId=5, adminTelegramUserId = 8,days = 102)

    print(my_storage.get_user(5).days)