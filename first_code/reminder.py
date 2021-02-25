import sqlite3
import argparse
import database
from bot import bot
import datetime


parser = argparse.ArgumentParser()
parser.add_argument('--id', type=int)
reminder_id = parser.parse_args().id

db = database.ReminderBase(r'C:\Users\Erentsen\PycharmProjects\igv\olimps.db3', 'reminders')
bot.send_message(db.get_user_id(reminder_id), 'тест')

# schtasks /create /st 18:40 /tn 1073092617 /tr "C:\Users\Erentsen\PycharmProjects\igv\venv\Scripts\python.exe C:\Users\Erentsen\PycharmProjects\igv\reminder.py --id 1073092617" /sc once /ru System