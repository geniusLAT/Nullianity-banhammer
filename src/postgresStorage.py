from setting import settings
import psycopg2
from psycopg2 import sql
from datetime import datetime

class User:
    def __init__(self, telegram_user_id, admin_telegram_user_id, ban_date, days):
        self.telegram_user_id = telegram_user_id
        self.admin_telegram_user_id = admin_telegram_user_id
        self.ban_date = ban_date
        self.days = days

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

        """
        self.cursor.execute(sql_script)
        self.connection.commit()
        

    def get_user(self, telegram_user_id):
        select_query = """
        SELECT telegramUserId, adminTelegramUserId, banDate, days 
        FROM ban_table 
        WHERE telegramUserId = %s;
        """
        self.cursor.execute(select_query, (telegram_user_id,))
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

    def update_user(self, telegramUserId, adminTelegramUserId=None, ban_date=None, days=None):
        update_query = """
        UPDATE ban_table 
        SET adminTelegramUserId = %s, banDate = %s, days = %s 
        WHERE telegramUserId = %s;
        """
        
        # Заменяем None на текущие значения, чтобы не обновлять их, если не переданы новые значения
        self.cursor.execute(update_query, (
            adminTelegramUserId if adminTelegramUserId is not None else self.get_current_value(telegramUserId, 'adminTelegramUserId'),
            ban_date if ban_date is not None else self.get_current_value(telegramUserId, 'banDate'),
            days if days is not None else self.get_current_value(telegramUserId, 'days'),
            telegramUserId
        ))
        
        self.connection.commit()

    def get_current_value(self, telegramUserId, column_name):
        select_query = f"SELECT {column_name} FROM ban_table WHERE telegramUserId = %s;"
        self.cursor.execute(select_query, (telegramUserId,))
        result = self.cursor.fetchone()
        return result[0] if result else None

if __name__ == "__main__":
    my_settings = settings()
    my_storage = PostgresStorage(my_settings)

    my_storage.create_user_ban_time(telegramUserId=5, adminTelegramUserId = 8,days = 5)
    my_storage.update_user(telegramUserId=5, adminTelegramUserId = 8,days = 102)

    print(my_storage.get_user(5).days)