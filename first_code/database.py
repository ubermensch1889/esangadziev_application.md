import sqlite3


class Base:
    def __init__(self, db_name, table_name):
        self.db = sqlite3.connect(db_name, check_same_thread=False)
        self.cur = self.db.cursor()
        self.table_name = table_name


class UserBase(Base):
    def __init__(self, db_name, table_name):
        super().__init__(db_name, table_name)

    def create_user(self, user_id, tz, grade):
        self.cur.execute(f"INSERT INTO {self.table_name} VALUES (?, ?, ?)", (user_id, tz, grade))
        self.db.commit()

    def change_grade(self, user_id, new_grade):
        self.cur.execute(f"UPDATE {self.table_name} SET grade = ? WHERE user_id = {user_id}",
                         new_grade)
        self.db.commit()

    def change_tz(self, user_id, new_tz):
        self.cur.execute(f"UPDATE {self.table_name} SET tz = ? WHERE user_id = {user_id}",
                         new_tz)
        self.db.commit()


class ReminderBase(Base):
    def __init__(self, db_name, table_name):
        super().__init__(db_name, table_name)

    def insert_into_base(self, user_id, tz, dt, subject, olimp_name):
        self.cur.execute(f"INSERT INTO {self.table_name} VALUES (?, ?, ?, ?, ?, NULL)", (user_id, tz, dt, subject, olimp_name))
        self.db.commit()

    def exist_in_base(self, user_id, subject, olimp_name):
        return bool(self.cur.execute(f"SELECT * FROM {self.table_name} "
                                     f"WHERE (user_id = {user_id} AND subject ="
                                     f" {subject} AND olimp_name = {olimp_name})").fetchone())

    def get_user_id(self, reminder_id):
        return self.cur.execute(f"SELECT user_id FROM"
                                f" {self.table_name} WHERE id = {reminder_id}").fetchone()[0]

    def get_last_id(self):
        return self.cur.execute(f"SELECT id FROM {self.table_name} WHERE rowid=last_insert_rowid()").fetchone()[0]


class QuestionsBase(Base):
    def __init__(self, db_name, table_name):
        super().__init__(db_name, table_name)

    def get_questions(self, user_id):
        return self.cur.execute(f"SELECT * FROM {self.table_name} WHERE questioner_id = {user_id}")

    def ask(self, user_id, subject, grade, text):
        questions = self.get_questions(user_id)
        number = len(questions) + 1 if questions else 1
        self.cur.execute(f"INSERT INTO {self.table_name} VALUES "
                         f"({user_id}, {subject}, {grade}, {text}, {number})")
        self.db.commit()

    def delete_question(self, user_id, number):
        self.cur.execute(f"DELETE FROM {self.table_name} WHERE "
                         f"(questioner_id = {user_id} AND number = {number})")
        self.cur.execute(f"UPDATE {user_id} SET number = number - 1 WHERE number > {number}")
        self.db.commit()