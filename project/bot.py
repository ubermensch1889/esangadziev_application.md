import telebot
import sqlite3
import config
import datetime
import database
import requests
import os
from backports import zoneinfo
from telebot import types
import logging
import random

# создаем объекты для работы с базой данных
rb = database.ReminderBase('reminders')
ub = database.UserBase('users')
sb = database.SubjectsBase('subjects')
ob = database.OlimpsBase('olimps')
qb = database.QuestionsBase('questions')

bot = telebot.TeleBot(config.token, threaded=False)
bot.remove_webhook()

logger = telebot.logger
logging.basicConfig(
    filename='log.txt', level=logging.INFO, format=' %(asctime)s - %(levelname)s - %(message)s'
)


def main():
    bot.infinity_polling()


@bot.message_handler(commands=['start'])
def start_message(message):
    user_id = message.chat.id

    try:
        # вносим id пользователя в базу, если оно уже там, то удаляем его сообщение
        ub.create_user(user_id)

        markup = types.InlineKeyboardMarkup(row_width=2)
        button1 = types.InlineKeyboardButton('По местоположению', callback_data='send_location')
        button2 = types.InlineKeyboardButton('Выбрать из списка', callback_data='send_tz')
        markup.add(button1, button2)

        bot_message_id = bot.send_message(
            user_id,
            '*Привет*, для начала работы нужно пройти небольшую регистрацию\.'
            ' Все данные в дальнейшем можно будет изменить\.\n'
            'Сначала выберите способ задания часового пояса\.',
            reply_markup=markup,
            parse_mode='MarkdownV2'
        ).id
        bot.delete_message(user_id, message.id)
        ub.set_last_bot_message(user_id, bot_message_id)
    except sqlite3.IntegrityError:
        if ub.exist(user_id):
            button = types.InlineKeyboardButton('В меню', callback_data='to_menu')
            markup = types.InlineKeyboardMarkup()
            markup.add(button)
            # отправляем сообщение, чтобы если пользователь
            # случайно удалил сообшение бота, то он смог бы вернуться в меню
            bot_message_id = bot.send_message(user_id,
                                              'Вы уже зарегистрированы.', reply_markup=markup).id
            bot.delete_message(user_id, ub.get_last_bot_message(user_id))
            ub.set_last_bot_message(user_id, bot_message_id)
            bot.delete_message(user_id, message.id)
        else:
            aborted_start(message)


def aborted_start(message):
    user_id = message.chat.id
    markup = types.InlineKeyboardMarkup(row_width=2)
    button1 = types.InlineKeyboardButton('По местоположению', callback_data='send_location')
    button2 = types.InlineKeyboardButton('Выбрать из списка', callback_data='send_tz')
    markup.add(button1, button2)
    bot_message_id = bot.send_message(
        user_id,
        'Вы нарушили порядок регистрации. Вам придется начать заново.',
        reply_markup=markup,
    ).id
    bot.delete_message(user_id, ub.get_last_bot_message(user_id))
    bot.delete_message(user_id, message.id)
    ub.set_last_bot_message(user_id, bot_message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'send_location')
def ask_for_location(call):
    user_id = call.message.chat.id

    bot.delete_message(user_id, ub.get_last_bot_message(user_id))
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button_geo = types.KeyboardButton(text='Передать местоположение',
                                      request_location=True)
    button_rejection = types.KeyboardButton(text='Откажусь')
    keyboard.add(button_geo, button_rejection)
    ub.set_status(user_id, 'rejection')
    bot_message_id = bot.send_message(
        call.message.chat.id,
        'Прекрасно\! Нажмите _Передать местоположение_\.\nЕсли Вы все '
        'же не хотите, то нажмите _Откажусь_\.',
        reply_markup=keyboard,
        parse_mode='MarkdownV2'
    ).id
    ub.set_last_bot_message(user_id, bot_message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'send_tz')
def ask_for_tz(call):
    # отправляем пользователю сообщение с выбором часового пояса в формате UTC
    markup = types.InlineKeyboardMarkup()
    for time_zone in config.time_zones_utc:
        button = types.InlineKeyboardButton(time_zone,
                                            callback_data=f'time_zone_choice_{time_zone}')
        markup.add(button)
    bot.edit_message_text(
        'Выберите свой часовой пояс.', call.message.chat.id,
        call.message.id, reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: 'time_zone_choice' in call.data)
def get_time_zone(call):
    ask_for_grade(call.message, config.time_zones_utc[call.data[17:]])
    # срез, чтобы передать только зону без идентификатора


@bot.message_handler(content_types=['location'])
def get_location(message):
    bot.delete_message(message.chat.id, message.id)
    ask_for_grade(message, request_tz(message.location.latitude, message.location.longitude), True)


def ask_for_grade(message, time_zone, from_loc=False):
    ub.set_tz(message.chat.id, time_zone)
    markup = types.InlineKeyboardMarkup()
    user_id = message.chat.id
    answer = 'Прекрасно! Теперь мне нужно узнать, в каком Вы классе, чтобы я смог понять, какие' \
             ' олимпиады Вам подходят.'

    for grade in range(5, 12):
        button = types.InlineKeyboardButton(str(grade), callback_data='grade_' + str(grade))
        markup.add(button)

    if from_loc:
        # изменить сообщение с клавиатурой нельзя, поэтому вот так
        bot.delete_message(user_id, ub.get_last_bot_message(user_id))
        bot_message_id = bot.send_message(user_id, answer, reply_markup=markup).id
        ub.set_last_bot_message(message.chat.id, bot_message_id)
    else:
        bot.edit_message_text(answer, user_id, message.id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: 'grade' in call.data)
def get_grade(call):
    grade = call.data[6:]
    ub.set_grade(call.message.chat.id, grade)
    send_menu(call.message)


@bot.callback_query_handler(func=lambda call: 'to_menu' == call.data)
def to_menu(call):
    send_menu(call.message)
    ub.set_status(call.message.chat.id, 'none')


def send_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    user_id = message.chat.id

    button_create_reminder = types.InlineKeyboardButton('Создать напоминание',
                                                        callback_data='create_reminder')
    button_create_question = types.InlineKeyboardButton('Задать вопрос',
                                                        callback_data='create_question')
    button_answer = types.InlineKeyboardButton('Посмотреть вопросы', callback_data='get_questions')
    button_delete_reminder = types.InlineKeyboardButton('Удалить напоминание',
                                                        callback_data='delete_reminder')
    button_delete_question = types.InlineKeyboardButton('Удалить вопрос',
                                                        callback_data='delete_question')
    button_update_data = types.InlineKeyboardButton('Изменить данные о себе',
                                                    callback_data='update_data')
    markup.add(button_create_reminder, button_create_question,
               button_answer, button_delete_reminder,
               button_delete_question, button_update_data)
    bot.edit_message_text('Отлично! Что будуте делать?', user_id,
                          message.id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: 'update_data' == call.data)
def start_updating_data(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    button1 = types.InlineKeyboardButton('По местоположению', callback_data='send_location')
    button2 = types.InlineKeyboardButton('Выбрать из списка', callback_data='send_tz')
    markup.add(button1, button2)
    bot.edit_message_text('Хорошо, сначала обновим часовой пояс. '
                          'Пожалуйста, выберите способ.',
                          call.message.chat.id,
                          call.message.id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: 'delete_reminder' == call.data)
def ask_for_reminder_to_delete(call):
    # отправляем пользователю его напоминания, если они есть
    user_id = call.message.chat.id
    reminders = rb.get_reminders(user_id)
    button = types.InlineKeyboardButton('Назад', callback_data='to_menu')
    markup = types.InlineKeyboardMarkup()
    markup.add(button)

    if reminders:
        ids = []
        answer = 'Вот Ваши напоминания, введите номер того, который хотите удалить.\n'

        for number, reminder in enumerate(reminders):
            olimp_id = reminder[2]
            data = ob.get_olimp(olimp_id)
            name = data[0]
            time = reminder[1][:-2]
            subject = data[4]
            answer += f'{str(number + 1)}. Олимпиада: {name}\n' \
                      f'Предмет: {subject}\n' \
                      f'Время: {time}\n'
            ids.append(str(reminder[-1]))

        ub.set_ids(user_id, ' '.join(ids))
        ub.set_status(user_id, 'choosing_reminder_to_delete')
        bot.edit_message_text(answer, user_id,
                              call.message.id,
                              reply_markup=markup)
        return
    bot.edit_message_text('У вас нет активных напоминаний.', user_id,
                          call.message.id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: 'delete_question' == call.data)
def ask_for_question_to_delete(call):
    # аналогично удалению напоминаний, выдаем список вопросов, если они есть
    user_id = call.message.chat.id
    questions = qb.get_questions(user_id)
    button = types.InlineKeyboardButton('В меню', callback_data='to_menu')
    markup = types.InlineKeyboardMarkup()
    markup.add(button)

    if questions:
        answer = 'Вот ваши вопросы, введите номер того, который хотите удалить.\n'
        ids = []
        for number, question in enumerate(questions):
            text = question[2]
            subject = question[1]
            answer += f'{str(number + 1)}. Вопрос: "{text}"\n' \
                      f'Предмет: {subject}\n'
            ids.append(str(question[-1]))

        ub.set_ids(user_id, ' '.join(ids))
        ub.set_status(user_id, 'choosing_question_to_delete')
        bot.edit_message_text(answer, user_id,
                              call.message.id,
                              reply_markup=markup)
    else:
        bot.edit_message_text('У вас нет активных вопросов.', user_id,
                              call.message.id,
                              reply_markup=markup)


@bot.callback_query_handler(func=lambda call: 'create_reminder' == call.data or
                                              'create_question' == call.data or
                                              'get_questions' == call.data)
def ask_for_subject(call):
    # отправляем пользователю предметы, по которым он выберет олимпиады или вопросы
    if call.data == 'create_reminder':
        subjects = sb.get_subjects()[:-1]
        # в конце списка лежит Внепредметная область, но, естественно, олимпиад по ней нет
        answer = 'Вот школьные предметы, введите номер того, ' \
                 'по которому Вы хотите увидеть олимпиады:\n\n'
    elif call.data == 'create_question':
        subjects = sb.get_subjects()
        answer = 'Вот школьные предметы, введите номер того, ' \
                 'по которому Вы хотите задать вопрос:\n\n'
    else:
        subjects = sb.get_subjects()
        answer = 'Вот школьные предметы, введите номер того, ' \
                 'по которому Вы хотите увидеть вопросы:\n\n'

    user_id = call.message.chat.id
    ids = []
    ub.set_status(user_id, call.data)

    for number, subject in enumerate(subjects):
        subject_id, name = subject
        answer += f'{str(number + 1)}. {name}\n'
        ids.append(str(subject_id))

    ub.set_ids(user_id, ' '.join(ids))
    button = types.InlineKeyboardButton('В меню', callback_data='to_menu')
    markup = types.InlineKeyboardMarkup()
    markup.add(button)
    bot.edit_message_text(answer, user_id,
                          call.message.id,
                          reply_markup=markup)


def error(chat_id):
    # уведомеляем пользователя об ошибке, это непредвиденный или неправильный ввод
    answer = f'Некорректный ввод.\n' \
             f'Просто число: {str(random.randint(-1000, 1000))}.'
    # число небходимо, чтобы при спаме телеграмм апи не ругался на уникальность сообщения
    button = types.InlineKeyboardButton('В меню', callback_data='to_menu')
    markup = types.InlineKeyboardMarkup()
    markup.add(button)
    bot.edit_message_text(answer, chat_id,
                          ub.get_last_bot_message(chat_id),
                          reply_markup=markup)


@bot.message_handler(content_types=['text'])
def process_text(message):
    # обработчик всех текстовых сообщений пользователя
    user_id = message.chat.id
    status = ub.get_status(user_id)
    bot.delete_message(user_id, message.id)

    if not ub.exist(user_id) and status != 'rejection' and message.text != 'Откажусь':
        # случай, когда ползьзователь не завершил регистрацию и сделал непредвиденный ввод,
        # вернуть его к предыдущему шагу проблематично, поэтому просто удаляем его сообщение
        aborted_start(message)
        return

    if 'choosing_olimp' == status:
        # пользователь выбирает номер олимпиады при создании напоминания
        ub.set_status(message.chat.id, 'none')
        try:
            # обрабатываем случай, когда пользователь ввел не число
            # или несуществующий номер олимпиады
            number = int(message.text)
            if number > len(ub.get_ids(user_id)) or number <= 0:
                raise ValueError
        except ValueError:
            error(user_id)
        else:
            get_olimp(message)

    elif 'create_reminder' == status:
        # пользователь выбирает номер предмета при создании напоминания
        ub.set_status(user_id, 'none')
        try:
            number = int(message.text)
            if 0 >= number or number > len(sb.get_subjects()) - 1:
                raise ValueError
        except ValueError:
            error(user_id)
        else:
            ask_for_olimp(message)

    elif 'choosing_date' in status:
        # пользователь выбирает дату при создании напоминания
        data = status
        ub.set_status(user_id, 'none')
        try:
            # обрабатываем случай, когда пользователь ввел дату в неверном формате или дату,
            # которая раньше, чем сегодня
            olimp_id = data.split('_')[2]
            tmp = [int(i) for i in message.text.split('.')]
            date_reminder = datetime.date(tmp[2], tmp[1], tmp[0])
            if date_reminder < datetime.date.today():
                raise ValueError
        except (ValueError, IndexError):
            button_back = types.InlineKeyboardButton('Повторить', callback_data=data)
            button_menu = types.InlineKeyboardButton('В меню', callback_data='to_menu')
            markup = types.InlineKeyboardMarkup()
            markup.add(button_menu, button_back)
            bot.edit_message_text(
                'Некорректный ввод, дата должна быть в формате ДД.ММ.ГГГГ, '
                'самая ранняя дата - сегодня.', user_id, ub.get_last_bot_message(user_id),
                reply_markup=markup
            )
        else:
            ask_for_time(ub.get_last_bot_message(user_id), user_id, olimp_id, date_reminder)

    elif 'choosing_interval' in status:
        # пользователь выбирает промежуток в днях, за который нужно его оповестить
        data = status
        ub.set_status(user_id, 'none')
        try:
            data = data.split('_')
            olimp_id = data[2]
            tmp = [int(i) for i in data[-1].split('.')]
            date_olimp = datetime.date(tmp[2], tmp[1], tmp[0])
            interval = int(message.text)
            if interval < 0:
                raise ValueError
            date_reminder = date_olimp - datetime.timedelta(days=interval)
            if date_reminder < datetime.date.today():
                raise ValueError
        except ValueError:
            button_back = types.InlineKeyboardButton('Назад', callback_data=status)
            button_menu = types.InlineKeyboardButton('В меню', callback_data='to_menu')
            markup = types.InlineKeyboardMarkup()
            markup.add(button_menu, button_back)
            bot.edit_message_text(
                'Некорректный ввод, число должно быть целым неотрицательным, а также '
                'быть меньше, чем количество дней от сегодняшней даты до даты проведения этапа.',
                user_id, ub.get_last_bot_message(user_id), reply_markup=markup
            )
        else:
            ask_for_time(ub.get_last_bot_message(user_id), user_id, olimp_id, date_reminder)

    elif 'choosing_time' in status:
        # пользователь вводит время
        data = f'tm_{message.text}_{status[14:]}'
        ub.set_status(user_id, 'none')
        create_reminder(user_id, data, status)

    elif 'create_question' == status:
        # пользователь вводит номер предмета для создания вопроса
        try:
            number = int(message.text)
            if number > len(sb.get_subjects()) or number < 1:
                raise ValueError
        except ValueError:
            error(user_id)
        else:
            bot.edit_message_text('Хорошо! Введите вопрос.', user_id,
                                  ub.get_last_bot_message(user_id))
            ub.set_status(user_id, f'asking_question_{message.text}')

    elif 'asking_question' in status:
        # пользователь вводит текст вопроса
        subject_id = ub.get_ids(user_id)[int(status.split('_')[2]) - 1]

        button_menu = types.InlineKeyboardButton('Отмена', callback_data='to_menu')
        button_ask = types.InlineKeyboardButton('Задать',
                                                callback_data=f'ask_{subject_id}')
        ub.set_ids(user_id, message.text)
        markup = types.InlineKeyboardMarkup()
        markup.add(button_ask, button_menu)
        bot.edit_message_text(f'Вот ваш вопрос: "{message.text}". '
                              f'Обратите внимание, любой пользователь бота '
                              f'сможет получить ссылку на Ваш Telegram аккаунт.',
                              user_id,
                              ub.get_last_bot_message(user_id),
                              reply_markup=markup)
        ub.set_status(user_id, 'none')

    elif 'get_questions' == status:
        # пользователь выбирает предмет, на вопрос по которому он хочет ответить
        try:
            number = int(message.text)
            subject_id = ub.get_ids(user_id)[number - 1]
        except (ValueError, IndexError):
            error(user_id)
        else:
            show_questions(ub.get_last_bot_message(user_id), user_id, subject_id)

    elif 'choosing_questions' == status:
        # пользователь выбирает вопрос, на который хочет ответить
        button_menu = types.InlineKeyboardButton('В меню', callback_data='to_menu')
        markup = types.InlineKeyboardMarkup()
        markup.add(button_menu)
        ub.set_status(user_id, 'none')

        try:
            question_id = ub.get_ids(user_id)[int(message.text) - 1]
        except (ValueError, IndexError):
            error(user_id)
        else:
            data = qb.get_question(question_id)
            try:
                author = int(data[0])
            except TypeError:
                button_menu = types.InlineKeyboardButton('В меню', callback_data='to_menu')
                markup = types.InlineKeyboardMarkup()
                markup.add(button_menu)
                bot.edit_message_text('Ой. Возможно этот вопрос уже удален.',
                                      user_id, ub.get_last_bot_message(user_id),
                                      reply_markup=markup)
            else:
                if author == user_id:
                    bot.edit_message_text('Этот вопрос задали Вы.', user_id,
                                          ub.get_last_bot_message(user_id),
                                          reply_markup=markup)
                    ub.set_status(user_id, 'none')
                else:
                    usr_info = bot.get_chat_member(author, author).user
                    bot.edit_message_text(
                        f'[{usr_info.first_name}](tg://user?id={author}) задал\(а\) этот вопрос\. '
                        f'Пожалуйста, будьте вежливы\.',
                        user_id, ub.get_last_bot_message(user_id),
                        parse_mode='MarkdownV2',
                        reply_markup=markup
                    )

                    text = data[2]
                    subject = data[1]

                    button_delete = types.InlineKeyboardButton(
                        'Удалить вопрос',
                        callback_data=f'remove_quest_{question_id}'
                    )
                    markup.add(button_delete)

                    bot.delete_message(author, ub.get_last_bot_message(author))

                    bot_message_id = bot.send_message(author,
                                                      f'[{message.chat.first_name}]'
                                                      f'(tg://user?id={message.chat.id}) '
                                                      f'хочет ответить на ваш вопрос\! Пожалуйста, '
                                                      f'будьте вежливы\.\n'
                                                      f'Вопрос: "{text}"\n'
                                                      f'Предмет: {subject}',
                                                      parse_mode='MarkdownV2',
                                                      reply_markup=markup).id
                    ub.set_last_bot_message(author, bot_message_id)

    elif 'choosing_question_to_delete' == status:
        # пользователь выбирает вопрос, который он хочет удалить
        ub.set_status(user_id, 'none')

        try:
            question_id = ub.get_ids(message.chat.id)[int(message.text) - 1]
            if int(message.text) < 1:
                raise IndexError
        except (IndexError, ValueError):
            error(user_id)
        else:
            button_remove = types.InlineKeyboardButton(
                'Да',
                callback_data=f'remove_quest_{str(question_id)}'
            )
            button_menu = types.InlineKeyboardButton('Отмена', callback_data='to_menu')
            markup = types.InlineKeyboardMarkup()
            markup.add(button_remove, button_menu)

            bot.edit_message_text('Вы уверены?', user_id,
                                  ub.get_last_bot_message(user_id),
                                  reply_markup=markup)

    elif 'choosing_reminder_to_delete' == status:
        # пользователь выбирает напоминание, которое хочет удалить
        ub.set_status(user_id, 'none')

        try:
            reminder_id = ub.get_ids(user_id)[int(message.text) - 1]
            if int(message.text) < 1:
                raise IndexError
        except (IndexError, ValueError):
            error(user_id)
        else:
            button_remove = types.InlineKeyboardButton(
                'Да', callback_data=f'remove_rem_{str(reminder_id)}'
            )
            button_menu = types.InlineKeyboardButton('Отмена', callback_data='to_menu')
            markup = types.InlineKeyboardMarkup()
            markup.add(button_remove, button_menu)

            bot.edit_message_text('Вы уверены?', user_id,
                                  ub.get_last_bot_message(user_id),
                                  reply_markup=markup)

    elif 'rejection' == status and message.text == 'Откажусь':
        # если пользователь отказался отправить местоположение
        button = types.InlineKeyboardButton('Выбрать', callback_data='send_tz')
        markup = types.InlineKeyboardMarkup()
        markup.add(button)
        bot.delete_message(user_id, ub.get_last_bot_message(user_id))
        bot_message_id = bot.send_message(user_id,
                                          'Тогда вам нужно выбрать часовой пояс из списка.',
                                          reply_markup=markup).id
        ub.set_last_bot_message(user_id, bot_message_id)
        ub.set_status(user_id, 'none')

    elif 'choosing_stage' in status:
        olimp_id = status.split('_')[2]
        try:
            number = int(message.text)
            stage_date = ob.get_dates(olimp_id)[number - 1].split('/gap/')[1].split('-')[0]
            if number < 1:
                raise ValueError
            ask_for_interval(user_id, stage_date, olimp_id)
        except (ValueError, IndexError):
            error(user_id)

    else:
        # непредвиденное сообщение
        button = types.InlineKeyboardButton('В меню', callback_data='to_menu')
        markup = types.InlineKeyboardMarkup()
        markup.add(button)
        bot.edit_message_text(f'Извините, я Вас не понимаю.\n'
                              f'Просто число: {str(random.randint(-1000, 1000))}.', user_id,
                              ub.get_last_bot_message(user_id),
                              reply_markup=markup)
        # число небходимо, чтобы при спаме телеграмм апи не ругался на уникальность сообщения
        ub.set_status(user_id, 'none')


@bot.callback_query_handler(func=lambda call: 'remove_rem' in call.data)
def remove_reminder(call):
    # удаляем из напоминание из базы данных и из schtasks
    reminder_id = call.data.split('_')[-1]
    user_id = call.message.chat.id
    command = f'schtasks /delete /tn {reminder_id} -f'

    os.system(command)

    rb.delete_reminder(user_id, reminder_id)

    button = types.InlineKeyboardButton('В меню', callback_data='to_menu')
    markup = types.InlineKeyboardMarkup()
    markup.add(button)

    bot.edit_message_text('Напоминание успешно удалено.', user_id,
                          call.message.id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: 'remove_quest' in call.data)
def remove_question(call):
    # удаляем вопрос из базы данных
    user_id = call.message.chat.id
    question_id = call.data.split('_')[-1]
    qb.delete_question(user_id, question_id)

    button = types.InlineKeyboardButton('В меню', callback_data='to_menu')
    markup = types.InlineKeyboardMarkup()
    markup.add(button)

    bot.edit_message_text('Вопрос успешно удален.', user_id,
                          call.message.id,
                          reply_markup=markup)


def show_questions(message_id, user_id, subject_id, start=0, count=0):
    # показываем пользователю 10 вопросов по заданному предмету
    try:
        subject = sb.get_subject(subject_id)
    except TypeError:
        error(user_id)
    else:
        questions = qb.get_first_questions(subject, start)
        if questions:
            ids = []
            answer = ''
            for number, question in enumerate(questions):
                q_id, text = question
                answer += f'{str(count * 10 + number + 1)}. {text}\n'
                ids.append(str(q_id))

            ub.set_ids(user_id, ' '.join(['none'] * count * 10) + ' ' + ' '.join(ids))
            ub.set_status(user_id, 'choosing_questions')
            button = types.InlineKeyboardButton(
                'Дальше',
                callback_data=f'next_{str(ids[-1])}_{subject_id}_{str(count + 1)}'
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(button)
            bot.edit_message_text(answer, user_id, message_id, reply_markup=markup)
        else:
            button_back = types.InlineKeyboardButton('Вернуться к выбору предмета',
                                                     callback_data='get_questions')
            markup = types.InlineKeyboardMarkup()
            markup.add(button_back)
            if count == 0:
                answer = 'Нет активных вопросов по данному предмету.'
            else:
                answer = 'Вопросы по данному предмету закончились.'
            bot.edit_message_text(answer, user_id, message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: 'next' in call.data)
def next_questions(call):
    subject_id = call.data.split('_')[2]
    count = int(call.data.split('_')[3])
    start = int(call.data.split('_')[1])
    show_questions(call.message.id, call.message.chat.id, subject_id, start, count)


@bot.callback_query_handler(func=lambda call: 'ask' in call.data)
def ask(call):
    # добавляем вопрос в базу данных
    user_id = call.message.chat.id
    subject_id = call.data.split('_')[1]
    text = ' '.join(ub.get_ids(user_id))
    subject = sb.get_subject(subject_id)
    qb.ask(user_id, subject, text)
    button = types.InlineKeyboardButton('В меню', callback_data='to_menu')
    markup = types.InlineKeyboardMarkup()
    markup.add(button)
    bot.edit_message_text('Отлично! Вопрос задан.', user_id,
                          call.message.id,
                          reply_markup=markup)


def ask_for_olimp(message):
    # выдаем пользователю олимпиады по предмету
    user_id = message.chat.id
    try:
        subject_id = ub.get_ids(message.chat.id)[int(message.text) - 1]
        subject = sb.get_subject(subject_id)
    except IndexError:
        error(user_id)
    else:
        ub.set_status(user_id, 'choosing_olimp')
        olimps = ob.get_olimps(subject, ub.get_grade(message.chat.id))
        button = types.InlineKeyboardButton('В меню', callback_data='to_menu')
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(button)
        if olimps:
            answer = 'Выберите олимпиаду из списка и введите ее номер.\n\n' + '\n'.join(
                [str(number + 1) + '. ' + olimp[0] for number, olimp in enumerate(olimps)])
            ids = ' '.join([str(olimp[-1]) for olimp in olimps])
            ub.set_ids(user_id, ids)
        else:
            answer = 'Похоже, что олимпиад по данному предмету для Вашего возраста нет.'
        bot.edit_message_text(answer, user_id,
                              ub.get_last_bot_message(user_id),
                              reply_markup=markup)


def get_olimp(message):
    # пользователь получает информацию об олимпиаде и ему предлагается записаться или перейти в меню
    user_id = message.chat.id
    try:
        olimp_id = ub.get_ids(message.chat.id)[int(message.text) - 1]
    except IndexError:
        error(user_id)
    else:
        if rb.exist_in_base(user_id, olimp_id):
            # предложить перезаписать
            answer = 'У Вас уже есть напоминание по этой олимпиаде\.'
            button_add = types.InlineKeyboardButton('Добавить еще одно',
                                                    callback_data=f'add_{olimp_id}')
            button_cancel = types.InlineKeyboardButton('В меню', callback_data='to_menu')
            markup = types.InlineKeyboardMarkup()
            markup.add(button_add, button_cancel)
        else:
            markup = types.InlineKeyboardMarkup(row_width=1)
            button_sigh = types.InlineKeyboardButton('Записаться',
                                                     callback_data=f'add_{olimp_id}')
            button_cancel = types.InlineKeyboardButton('В меню', callback_data='to_menu')
            markup.add(button_sigh, button_cancel)
            data = ob.get_olimp(olimp_id)
            answer = f'{data[0]}\nУровень: {str(data[1])}\nБольше информации [здесь]({data[5]})\.'
        bot.edit_message_text(answer, user_id,
                              ub.get_last_bot_message(user_id),
                              reply_markup=markup,
                              parse_mode='MarkdownV2')


@bot.callback_query_handler(func=lambda call: 'add' in call.data)
def ask_for_stage(call):
    # выводим этапы выбранной олимпиады
    user_id = call.message.chat.id
    olimp_id = call.data[4:]
    dates = ob.get_dates(olimp_id)
    markup = types.InlineKeyboardMarkup()
    answer = 'Выберите этап олимпиады из списка и введите его номер.\n'

    for number, date in enumerate(dates):
        name, time = date.split('/gap/')
        answer += f'\n{str(number + 1)}. {name}\nДата проведения: {time}'
    button_back = types.InlineKeyboardButton('В меню',
                                             callback_data='to_menu')
    markup.add(button_back)
    bot.edit_message_text(answer, user_id,
                          call.message.id,
                          reply_markup=markup)
    ub.set_status(user_id, f'choosing_stage_{olimp_id}')


def ask_for_interval(user_id, date, olimp_id):
    # выводим промежутки, за которые нужно оповестить пользователя
    list_date = date.split('.')

    if datetime.date(int(list_date[2]), int(list_date[1]),
                     int(list_date[0])) < datetime.date.today():
        button = types.InlineKeyboardButton('Назад', callback_data=f'add_{olimp_id}')
        markup = types.InlineKeyboardMarkup()
        markup.add(button)
        bot.edit_message_text('Выбранный этап уже проходит или прошел.',
                              user_id,
                              ub.get_last_bot_message(user_id),
                              reply_markup=markup)
        return

    markup = types.InlineKeyboardMarkup()
    button_month = types.InlineKeyboardButton('месяц',
                                              callback_data=f'gap_30_{olimp_id}_{date}')
    button_2_weeks = types.InlineKeyboardButton('2 недели',
                                                callback_data=f'gap_14_{olimp_id}_{date}')
    button_week = types.InlineKeyboardButton('неделя',
                                             callback_data=f'gap_7_{olimp_id}_{date}')
    button_choice_date = types.InlineKeyboardButton(
        'Выбрать дату',
        callback_data=f'choosing_date_{olimp_id}_{date}'
    )
    button_choice_gap = types.InlineKeyboardButton(
        'Выбрать промежуток',
        callback_data=f'choosing_interval_{olimp_id}_{date}'
    )
    markup.add(button_month, button_2_weeks, button_week, button_choice_gap, button_choice_date)
    bot.edit_message_text('Выберите промежуток, '
                          'за который Вам придет уведомление.', user_id,
                          ub.get_last_bot_message(user_id),
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: 'choosing_interval' in call.data)
def manual_interval_selection(call):
    # просим пользователя отправить промежуток
    user_id = call.message.chat.id
    ub.set_status(user_id, call.data)
    bot.edit_message_text('Введите интервал в днях.', user_id,
                          call.message.id)


@bot.callback_query_handler(func=lambda call: 'choosing_date' in call.data)
def ask_for_date(call):
    # просим пользователя отправить дату
    user_id = call.message.chat.id
    data = call.data.split('_')
    olimp_date = data[3]
    ub.set_status(user_id, call.data)
    bot.edit_message_text(
        f'Введите дату в формате ДД.ММ.ГГ (она должна быть не позднее {olimp_date}).',
        user_id,
        call.message.id
    )


@bot.callback_query_handler(func=lambda call: 'gap' in call.data)
def get_interval(call):
    # получаем от пользователя интервал и спрашиваем время
    data = call.data.split('_')
    olimp_id = data[2]
    tmp = [int(i) for i in data[-1].split('.')]
    date_olimp = datetime.date(tmp[2], tmp[1], tmp[0])
    gap = int(data[1])
    date_reminder = date_olimp - datetime.timedelta(days=gap)
    ask_for_time(call.message.id, call.message.chat.id, olimp_id, date_reminder)


def ask_for_time(message_id, user_id, olimp_id, date_reminder):
    # спрашиваем время
    markup = types.InlineKeyboardMarkup()
    button_9 = types.InlineKeyboardButton(
        '⏰ 9:00',
        callback_data=f'tm_9:00_{str(date_reminder)}_{olimp_id}'
    )
    button_12 = types.InlineKeyboardButton(
        '⏰ 12:00',
        callback_data=f'tm_12:00_{str(date_reminder)}_{olimp_id}'
    )
    button_15 = types.InlineKeyboardButton(
        '⏰ 15:00',
        callback_data=f'tm_15:00_{str(date_reminder)}_{olimp_id}'
    )
    button_choice_time = types.InlineKeyboardButton(
        '⏰ Выбрать самостоятельно',
        callback_data=f'choosing_time_{str(date_reminder)}_{olimp_id}'
    )
    markup.add(button_9, button_12, button_15, button_choice_time)
    bot.edit_message_text('Выберите время.', user_id,
                          message_id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: 'choosing_time' in call.data)
def manual_time_selection(call):
    # просим в ручную ввести время
    user_id = call.message.chat.id
    ub.set_status(user_id, call.data)
    bot.edit_message_text('Введите время в формате ЧЧ:ММ.', user_id,
                          call.message.id)


@bot.callback_query_handler(func=lambda call: 'tm' in call.data)
def get_time(call):
    data = call.data
    create_reminder(call.message.chat.id, data)


def create_reminder(user_id, data, status='choosing_time'):
    # наконец-то создаем напоминание в базе и в schtasks
    render_data = data.split('_')
    olimp_id = render_data[-1]
    try:
        time = [int(i) for i in render_data[1].split(':')]
        date = [int(i) for i in render_data[2].split('-')]
        tz = zoneinfo.ZoneInfo(ub.get_tz(user_id))
        local_tz = zoneinfo.ZoneInfo(config.local_time_zone)
        dt_local = datetime.datetime(year=date[0], month=date[1], day=date[2], hour=time[0],
                                     minute=time[1], tzinfo=tz).astimezone(local_tz)
        if dt_local < datetime.datetime.now(tz=local_tz):
            # случай, если пользователь ввел тот же день, но раньше по времени
            raise ValueError
    except (ValueError, IndexError):
        button = types.InlineKeyboardButton('Назад', callback_data=status)
        button_menu = types.InlineKeyboardButton('В меню', callback_data='to_menu')
        markup = types.InlineKeyboardMarkup()
        markup.add(button_menu, button)
        bot.edit_message_text('Некорректный ввод, возможно это время уже прошло.', user_id,
                              ub.get_last_bot_message(user_id),
                              reply_markup=markup)
    else:
        rb.insert_into_base(user_id, dt_local.strftime("%Y-%m-%d %H:%M%S"), olimp_id)
        reminder_id = rb.get_last_id()
        path = f'{config.path_to_python} "{config.path_to_reminder}" --id {str(reminder_id)}'
        # дата на сервере нужна в формате ММ/ДД/ГГГГ
        command = f"""schtasks /create /tn {str(reminder_id)} /tr "{path}" /sd {dt_local.strftime("%m/%d/%Y")} /st {str(dt_local.time())[:-3]} /sc once /ru System -f"""
        button_menu = types.InlineKeyboardButton('В меню', callback_data='to_menu')
        markup = types.InlineKeyboardMarkup()
        markup.add(button_menu)
        bot.edit_message_text('Напоминание создано!', user_id,
                              ub.get_last_bot_message(user_id),
                              reply_markup=markup)
        os.system(command)


def request_tz(lat, lon):
    # делаем запрос к сервису и получаем json файл, откуда берем часовой пояс
    url = f'http://api.geonames.org/timezoneJSON?formatted=' \
          f'true&lat={lat}&lng={lon}&username={config.user_name_geonames}'
    data = requests.get(url)
    return data.json()['timezoneId']


if __name__ == '__main__':
    main()
