import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name: str = "birthdays.db"):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        with self.get_connection() as conn:
            # Пользователи
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    birthday DATE,
                    participation_type TEXT CHECK(participation_type IN ('give_only', 'give_and_receive')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Адреса ПВЗ
            conn.execute("""
                CREATE TABLE IF NOT EXISTS addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    service TEXT CHECK(service IN ('ozon', 'yandex', 'wildberries')),
                    address TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            
            # Пожелания к подаркам
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wishes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    wishes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            
            # Отложенные рассылки
            conn.execute("""
                CREATE TABLE IF NOT EXISTS delays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    birthday_user_id INTEGER,
                    delay_days INTEGER DEFAULT 0,
                    delay_until DATE,
                    year INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (birthday_user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            
            # Отправленные уведомления
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    birthday_user_id INTEGER,
                    notified_user_id INTEGER,
                    notification_type TEXT,
                    year INTEGER,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (birthday_user_id) REFERENCES users(user_id),
                    FOREIGN KEY (notified_user_id) REFERENCES users(user_id)
                )
            """)
            
            # Штрих-коды
            conn.execute("""
                CREATE TABLE IF NOT EXISTS barcodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER,
                    receiver_id INTEGER,
                    photo_file_id TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    delivered BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (sender_id) REFERENCES users(user_id),
                    FOREIGN KEY (receiver_id) REFERENCES users(user_id)
                )
            """)
            
            # Создаем индексы для оптимизации запросов
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_birthday_year_type 
                ON notifications(birthday_user_id, year, notification_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_delays_birthday_user 
                ON delays(birthday_user_id, user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_addresses_user_id 
                ON addresses(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_birthday 
                ON users(birthday)
            """)
            
            conn.commit()
    
    # Методы для работы с пользователями
    def add_user(self, user_id: int, username: str, full_name: str, birthday: str, participation_type: str):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO users (user_id, username, full_name, birthday, participation_type, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, username, full_name, birthday, participation_type))
            conn.commit()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_user(self, user_id: int, **kwargs):
        if not kwargs:
            return
        
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        
        with self.get_connection() as conn:
            conn.execute(f"""
                UPDATE users SET {set_clause} WHERE user_id = ?
            """, list(kwargs.values()) + [user_id])
            conn.commit()
    
    def get_all_users(self) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users ORDER BY full_name")
            return [dict(row) for row in cursor.fetchall()]
    
    # Методы для работы с адресами
    def set_address(self, user_id: int, service: str, address: str):
        with self.get_connection() as conn:
            # Удаляем старый адрес для этого сервиса
            conn.execute("DELETE FROM addresses WHERE user_id = ? AND service = ?", (user_id, service))
            # Добавляем новый
            if address.strip():  # Добавляем только если адрес не пустой
                conn.execute("""
                    INSERT INTO addresses (user_id, service, address)
                    VALUES (?, ?, ?)
                """, (user_id, service, address))
            conn.commit()
    
    def get_user_addresses(self, user_id: int) -> Dict[str, str]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT service, address FROM addresses WHERE user_id = ?", (user_id,))
            return {row['service']: row['address'] for row in cursor.fetchall()}
    
    def get_all_addresses(self) -> Dict[int, Dict[str, str]]:
        """Получает все адреса всех пользователей (для оптимизации N+1 запросов)"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT user_id, service, address FROM addresses")
            result = {}
            for row in cursor.fetchall():
                user_id = row['user_id']
                if user_id not in result:
                    result[user_id] = {}
                result[user_id][row['service']] = row['address']
            return result
    
    def get_all_wishes(self) -> Dict[int, str]:
        """Получает все пожелания всех пользователей (для оптимизации N+1 запросов)"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT user_id, wishes FROM wishes")
            return {row['user_id']: row['wishes'] for row in cursor.fetchall()}
    
    # Методы для работы с пожеланиями
    def set_wishes(self, user_id: int, wishes: str):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO wishes (user_id, wishes)
                VALUES (?, ?)
            """, (user_id, wishes))
            conn.commit()
    
    def get_wishes(self, user_id: int) -> Optional[str]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT wishes FROM wishes WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row['wishes'] if row else None
    
    # Методы для работы с отложенными рассылками
    def set_delay(self, user_id: int, birthday_user_id: int, delay_days: int, year: int):
        """Устанавливает отложенное напоминание о дне рождения"""
        delay_until = (datetime.now() + timedelta(days=delay_days)).date()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO delays (user_id, birthday_user_id, delay_days, delay_until, year)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, birthday_user_id, delay_days, delay_until, year))
            conn.commit()
    
    def get_delay(self, user_id: int, birthday_user_id: int = None) -> Optional[Dict]:
        """Получает отложенное напоминание. Если birthday_user_id не указан, возвращает все напоминания для пользователя"""
        with self.get_connection() as conn:
            if birthday_user_id:
                cursor = conn.execute(
                    "SELECT * FROM delays WHERE user_id = ? AND birthday_user_id = ?", 
                    (user_id, birthday_user_id)
                )
            else:
                cursor = conn.execute("SELECT * FROM delays WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_delays(self) -> List[Dict]:
        """Получает все отложенные напоминания"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM delays")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_delays_by_birthday_user(self, birthday_user_id: int) -> List[Dict]:
        """Получает все отложенные напоминания для конкретного именинника (оптимизированный запрос)"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM delays WHERE birthday_user_id = ?",
                (birthday_user_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_delay(self, user_id: int, birthday_user_id: int):
        """Удаляет отложенное напоминание"""
        with self.get_connection() as conn:
            conn.execute(
                "DELETE FROM delays WHERE user_id = ? AND birthday_user_id = ?",
                (user_id, birthday_user_id)
            )
            conn.commit()
    
    # Методы для работы с уведомлениями
    def add_notification(self, birthday_user_id: int, notified_user_id: int, notification_type: str, year: int):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO notifications (birthday_user_id, notified_user_id, notification_type, year)
                VALUES (?, ?, ?, ?)
            """, (birthday_user_id, notified_user_id, notification_type, year))
            conn.commit()
    
    def is_notification_sent(self, birthday_user_id: int, year: int, notification_type: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 1 FROM notifications 
                WHERE birthday_user_id = ? AND year = ? AND notification_type = ?
                LIMIT 1
            """, (birthday_user_id, year, notification_type))
            return cursor.fetchone() is not None
    
    def has_notify_members_clicked(self, birthday_user_id: int, year: int) -> bool:
        """Проверяет, нажал ли именинник кнопку 'уведомить участников'"""
        return self.is_notification_sent(birthday_user_id, year, "notify_members_button_clicked")
    
    def mark_notify_members_clicked(self, birthday_user_id: int, year: int):
        """Отмечает, что именинник нажал кнопку 'уведомить участников'"""
        self.add_notification(birthday_user_id, birthday_user_id, "notify_members_button_clicked", year)
    
    def has_ready_receive_notification_sent(self, birthday_user_id: int, year: int) -> bool:
        """Проверяет, отправлено ли уведомление 'готов принимать подарки'"""
        return self.is_notification_sent(birthday_user_id, year, "ready_receive_notification")
    
    def mark_ready_receive_notification_sent(self, birthday_user_id: int, year: int):
        """Отмечает, что отправлено уведомление 'готов принимать подарки'"""
        self.add_notification(birthday_user_id, birthday_user_id, "ready_receive_notification", year)
    
    def get_notifications_history(self, birthday_user_id: int = None, year: int = None) -> List[Dict]:
        """
        Получает историю уведомлений
        Если birthday_user_id указан - фильтрует по имениннику
        Если year указан - фильтрует по году
        """
        with self.get_connection() as conn:
            query = """
                SELECT 
                    n.id,
                    n.birthday_user_id,
                    n.notified_user_id,
                    n.notification_type,
                    n.year,
                    n.sent_at,
                    bd_user.full_name as birthday_user_name,
                    notified_user.full_name as notified_user_name
                FROM notifications n
                LEFT JOIN users bd_user ON n.birthday_user_id = bd_user.user_id
                LEFT JOIN users notified_user ON n.notified_user_id = notified_user.user_id
            """
            params = []
            conditions = []
            
            if birthday_user_id:
                conditions.append("n.birthday_user_id = ?")
                params.append(birthday_user_id)
            
            if year:
                conditions.append("n.year = ?")
                params.append(year)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY n.sent_at DESC"
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # Методы для работы со штрих-кодами
    def add_barcode(self, sender_id: int, receiver_id: int, photo_file_id: str):
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO barcodes (sender_id, receiver_id, photo_file_id)
                VALUES (?, ?, ?)
            """, (sender_id, receiver_id, photo_file_id))
            conn.commit()
            return cursor.lastrowid
    
    def get_undelivered_barcodes(self, receiver_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT b.*, u.full_name as sender_name 
                FROM barcodes b
                JOIN users u ON b.sender_id = u.user_id
                WHERE b.receiver_id = ? AND b.delivered = FALSE
                ORDER BY b.sent_at
            """, (receiver_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_barcode_delivered(self, barcode_id: int):
        with self.get_connection() as conn:
            conn.execute("UPDATE barcodes SET delivered = TRUE WHERE id = ?", (barcode_id,))
            conn.commit()
    
    # Методы для администратора
    def delete_user(self, user_id: int):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
    
    # Методы для получения дней рождений
    def get_all_birthdays(self, sort_by: str = "month_day") -> List[Dict]:
        """
        Получает все дни рождения
        """
        with self.get_connection() as conn:
            # Получаем всех пользователей с датой рождения
            if sort_by == "month_day":
                # Более простая сортировка по месяцу и дню
                query = """
                    SELECT * FROM users 
                    WHERE birthday IS NOT NULL 
                        AND birthday != ''
                    ORDER BY 
                        substr(birthday, 6, 2),  -- месяц
                        substr(birthday, 9, 2)   -- день
                """
            elif sort_by == "alphabetical":
                query = """
                    SELECT * FROM users 
                    WHERE birthday IS NOT NULL 
                        AND birthday != ''
                    ORDER BY full_name
                """
            elif sort_by == "date_added":
                query = """
                    SELECT * FROM users 
                    WHERE birthday IS NOT NULL 
                        AND birthday != ''
                    ORDER BY created_at DESC
                """
            else:
                query = """
                    SELECT * FROM users 
                    WHERE birthday IS NOT NULL 
                        AND birthday != ''
                    ORDER BY birthday
                """
            
            cursor = conn.execute(query)
            users = [dict(row) for row in cursor.fetchall()]
            
            return users
