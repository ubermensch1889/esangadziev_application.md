import telebot
import sqlite3
import config
import datetime
import database
import os

rb = database.ReminderBase(r'C:\Users\Erentsen\PycharmProjects\igv\olimps.db3', 'reminders')
bot = telebot.TeleBot(config.token)

if __name__ == '__main__':
    con = sqlite3.connect("olimps.db3")
    cur = con.cursor()


    def error_message(id):
        bot.send_message(id, 'Ошибка')


    @bot.message_handler(commands=['start'])
    def start_message(message):
        bot.send_message(message.chat.id, 'Привет, ты написал мне /start')


    @bot.message_handler(content_types=['text'])
    def add(message):
        dt = datetime.datetime(*[int(i) for i in message.text.split()])
        rb.insert_into_base(message.chat.id, 0, dt.strftime("%Y-%m-%d %H:%M%S"), 'Биология', 'Олимпиада СПбГУ по биологии')
        reminder_id = rb.get_last_id()
        print(reminder_id)
        path = r"C:\Users\Erentsen\PycharmProjects\igv\venv\Scripts\python.exe" + " " + r"C:\Users\Erentsen\PycharmProjects\igv\reminder.py" + " --id " + str(reminder_id)
        print(dt.strftime("%Y-%m-%d %H:%M:%S"))
        command = f"""schtasks /create /tn {str(reminder_id)} /tr "{path}" /sd {dt.strftime("%d/%m/%Y")} /st {str(dt.time())[:-3]} /sc once /ru System"""
        print(command)
        os.system(command)


    @bot.message_handler(commands=['id'])
    def id(message):
        print(message.chat)


    bot.polling()
