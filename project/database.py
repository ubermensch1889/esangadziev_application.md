import sqlite3
from config import path_to_base

DB = sqlite3.connect(path_to_base, check_same_thread=False)
CURSOR = DB.cursor()


class Base:
    def __init__(self, table_name):
        self.cur = CURSOR
        self.db = DB
        self.table_name = table_name


class OlimpsBase(Base):
    def __init__(self, table_name):
        super().__init__(table_name)

    def get_olimps(self, subject, age):
        olimps = self.cur.execute(
            f"SELECT * FROM {self.table_name} WHERE subject = ? "
            f" and classes LIKE '%{age}%' ORDER BY level, name",
            (subject,)).fetchall()
        return sorted(olimps, key=lambda x: x[0])

    def get_dates(self, olimp_id):
        dates = self.cur.execute(f"SELECT dates FROM {self.table_name} WHERE id = ?",
                                 (olimp_id,)).fetchone()[0].split('/sep/')
        return dates

    def get_olimp(self, olimp_id):
        return self.cur.execute(f"SELECT * FROM {self.table_name} WHERE id = ?",
                                (olimp_id,)).fetchone()


class UserBase(Base):
    def __init__(self, table_name):
        super().__init__(table_name)

    def exist(self, user_id):
        return self.cur.execute(
            f"SELECT EXISTS (SELECT * FROM {self.table_name} WHERE user_id = ? AND not tz "
            f"is NULL AND not grade is NULL)",
            (user_id,)).fetchone()[0]

    def create_user(self, user_id):
        self.cur.execute(f"INSERT INTO {self.table_name} (user_id) VALUES (?)",
                         (user_id,))
        self.db.commit()

    def set_grade(self, user_id, new_grade):
        self.cur.execute(f"UPDATE {self.table_name} SET grade = ? WHERE user_id = {user_id}",
                         (new_grade,))
        self.db.commit()

    def set_tz(self, user_id, new_tz):
        self.cur.execute(f"UPDATE {self.table_name} SET tz = ? WHERE user_id = {user_id}",
                         (new_tz,))
        self.db.commit()

    def get_tz(self, user_id):
        table = self.cur.execute(
            f"SELECT tz FROM {self.table_name} WHERE user_id = {user_id}").fetchone()
        return table[0]

    def get_grade(self, user_id):
        table = self.cur.execute(
            f"SELECT grade FROM {self.table_name} WHERE user_id = {user_id}").fetchone()
        return table[0]

    def get_last_bot_message(self, user_id):
        table = self.cur.execute(
            f"SELECT last_bot_message FROM {self.table_name} WHERE user_id = {user_id}").fetchone()
        return table[0]

    def set_last_bot_message(self, user_id, message_id):
        self.cur.execute(
            f"UPDATE {self.table_name} SET last_bot_message = ? WHERE user_id = {str(user_id)}",
            (str(message_id),))
        self.db.commit()

    def set_ids(self, user_id, ids):
        self.cur.execute(
            f"UPDATE {self.table_name} SET ids = ? WHERE user_id = {user_id}",
            (ids,))
        self.db.commit()

    def get_ids(self, user_id):
        table = self.cur.execute(
            f"SELECT ids FROM {self.table_name} WHERE user_id = {user_id}").fetchone()
        if type(table[0]) == int:
            return [str(table[0])]
        elif not table[0] or table[0] == 'none':
            return []
        return table[0].split()

    def get_status(self, user_id):
        table = self.cur.execute(
            f"SELECT status FROM {self.table_name} WHERE user_id = {user_id}").fetchone()
        return table[0]

    def set_status(self, user_id, status):
        # статус - состояние ввода
        self.cur.execute(
            f"UPDATE {self.table_name} SET status = ? WHERE user_id = {user_id}",
            (status,))
        self.db.commit()


class ReminderBase(Base):
    def __init__(self, table_name):
        super().__init__(table_name)

    def insert_into_base(self, user_id, dt, olimp_id):
        self.cur.execute(f"INSERT INTO {self.table_name} VALUES (?, ?, ?, NULL)",
                         (user_id, dt, olimp_id))
        self.db.commit()

    def exist_in_base(self, user_id, olimp_id):
        return bool(self.cur.execute(f"SELECT * FROM {self.table_name} "
                                     f"WHERE user_id = ? AND olimp_id = ?",
                                     (user_id, olimp_id)).fetchone())

    def get_user_id(self, reminder_id):
        return self.cur.execute(f"SELECT user_id FROM"
                                f" {self.table_name} WHERE id = {reminder_id}").fetchone()[0]

    def get_last_id(self):
        return self.cur.execute(
            f"SELECT id FROM {self.table_name} WHERE rowid=last_insert_rowid()").fetchone()[0]

    def get_reminders(self, user_id):
        return self.cur.execute(
            f"SELECT * FROM {self.table_name} WHERE user_id = {user_id}").fetchall()

    def delete_reminder(self, user_id, reminder_id):
        self.cur.execute(f"DELETE FROM {self.table_name} WHERE "
                         f"(user_id = {user_id} AND id = {reminder_id})")
        self.db.commit()

    def get_olimp_id(self, reminder_id):
        return self.cur.execute(
            f"SELECT olimp_id FROM {self.table_name} WHERE id=?", (reminder_id,)).fetchone()[0]


class QuestionsBase(Base):
    def __init__(self, table_name):
        super().__init__(table_name)

    def get_questions(self, user_id):
        return self.cur.execute(
            f"SELECT * FROM {self.table_name} WHERE questioner_id = {user_id}").fetchall()

    def ask(self, user_id, subject, text):
        self.cur.execute(f"INSERT INTO {self.table_name} VALUES "
                         f"(?, ?, ?, NULL)", (user_id, subject, text))
        self.db.commit()

    def delete_question(self, user_id, question_id):
        self.cur.execute(f"DELETE FROM {self.table_name} WHERE "
                         f"(questioner_id = {user_id} AND id = {question_id})")
        self.db.commit()

    def get_first_questions(self, subject, start):
        table = self.cur.execute(
            f"SELECT id, text FROM {self.table_name} WHERE id > ? AND subject = ? LIMIT 10",
            (start, subject)).fetchall()
        return table

    def get_question(self, question_id):
        table = self.cur.execute(
            f"SELECT * FROM {self.table_name} WHERE id = ?", (question_id,)).fetchone()
        return table


class SubjectsBase(Base):
    def __init__(self, table_name):
        super().__init__(table_name)

    def get_subjects(self):
        table = self.cur.execute(f"SELECT id, subject FROM subjects").fetchall()
        return sorted(table[:-1], key=lambda x: x[1]) + [table[-1]]  # сортируем по предмету

    def get_subject(self, subject_id):
        table = self.cur.execute(f"SELECT subject FROM subjects WHERE id = {subject_id}").fetchone()
        return table[0]
