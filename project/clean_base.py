import sqlite3

db = sqlite3.connect('olimps.db3', check_same_thread=False)
cur = db.cursor()

cur.execute('DELETE FROM reminders')
cur.execute('DELETE FROM questions')
cur.execute('DELETE FROM users')

db.commit()