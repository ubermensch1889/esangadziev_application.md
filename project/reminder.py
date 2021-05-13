import argparse
import os
from bot import bot, ub, ob, rb
from telebot import types


parser = argparse.ArgumentParser()
parser.add_argument('--id', type=int)
reminder_id = parser.parse_args().id

olimp_id = rb.get_olimp_id(reminder_id)
user_id = rb.get_user_id(reminder_id)

data = ob.get_olimp(olimp_id)
name = data[0]
subject = data[4]
link = data[5]

command = f"""schtasks /delete /tn {reminder_id} -f"""
os.system(command)  # удаляем напоминание из журнала задач

rb.delete_reminder(user_id, reminder_id)  # удаляем напоминание их базы

button_reschedule = types.InlineKeyboardButton('Перенести', callback_data=f'add_{str(olimp_id)}')
button_cancel = types.InlineKeyboardButton('В меню', callback_data='to_menu')
markup = types.InlineKeyboardMarkup()
markup.add(button_reschedule, button_cancel)
bot.delete_message(user_id, ub.get_last_bot_message(user_id))
bot_message = bot.send_message(user_id, f'Вы просили меня напомнить вам о проведении "{name}" '
                                        f'по предмету {subject}\. Больше информации '
                                        f'[здесь]({link})\.', reply_markup=markup,
                               parse_mode='MarkdownV2')
ub.set_status(user_id, 'none')
ub.set_last_bot_message(user_id, bot_message.id)
