import requests
import sqlite3
from bs4 import BeautifulSoup

STUDY_YEAR = ('.2020', '.2021')


def translate_date(d):
    d = d.replace('До ', '')
    if '...' not in d:
        d = d.split()
        if int(str(months.index(d[1]) + 1).rjust(2, '0')) >= 9:
            year = STUDY_YEAR[0]
        else:
            year = STUDY_YEAR[1]
        return d[0].rjust(2, '0') + '.' + str(months.index(d[1]) + 1).rjust(2, '0') + year
    d = list(map(lambda x: x.split(), d.split('...')))
    if len(d[0]) == 1:
        d[0].append(d[1][1])
    if int(str(months.index(d[0][1]) + 1).rjust(2, '0')) >= 9:
        year_1 = STUDY_YEAR[0]
    else:
        year_1 = STUDY_YEAR[1]
    if int(str(months.index(d[1][1]) + 1).rjust(2, '0')) >= 9:
        year_2 = STUDY_YEAR[0]
    else:
        year_2 = STUDY_YEAR[1]
    return d[0][0].rjust(2, '0') + '.' + str(months.index(d[0][1]) + 1).rjust(2, '0') + year_1 + '-' + \
           d[1][0].rjust(2, '0') + '.' + str(months.index(d[1][1]) + 1).rjust(2, '0') + year_2


def get_age(age):
    age = age[:-7]
    if '–' in age:
        age = age.split('–')
        return ' '.join([str(cl) for cl in range(int(age[0]), int(age[1]) + 1)])
    return age


con = sqlite3.connect("olimps.db3")
cur = con.cursor()
months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
url = 'https://olimpiada.ru/article/942#iikt'  # ссылка на сайт с списком перечневых олимпиад
response = requests.get(url)
soup = BeautifulSoup(response.text, 'lxml')
quotes = soup.find_all('a', {'class': 'slim_dec'})
urls = []


for quote in quotes:
    link = str(quote.get('href'))
    if 'activity' in link:
        urls.append('https://olimpiada.ru' + link)

url = 'https://olimpiada.ru/activity/43'  # ссылка на сайт с списком Всероссийских олимпиад
response = requests.get(url)
soup = BeautifulSoup(response.text, 'lxml')
quotes = soup.find_all('a', {'class': 'none_a'})

for quote in quotes:
    link = 'https://olimpiada.ru' + str(quote.get('href'))
    if 'activity' in link and link not in urls:
        urls.append(link)
for curr_url in urls:
    try:
        dates = []
        response = requests.get(curr_url)
        soup = BeautifulSoup(response.text, 'lxml')
        table = soup.find_all('tr', {'class': 'grey'})
        name = soup.find('h1').text
        classes = soup.find('span', {'class': 'classes_types_a'}).text
        level = soup.find_all('div', {'class': 'f_blocks'})[2].text
        level = level[level.find('уровень') + 8]
        try:
            int(level)
        except ValueError:
            level = 'зависит от профиля'
        subjects = soup.find('div', {'class': 'subject_tags_full'}).find_all(
            'span', {'class': 'subject_tag'})
        for row in table:
            stage = row.find('div', {'class': 'event_name'}).text
            date = row.find_next('a').find_next('a').text
            dates.append(stage + '/gap/' + translate_date(date))
        dates = '/sep/'.join(dates)
        for subject in subjects:
            subject = subject.text[1:]
            album = (name, level, dates, get_age(classes), subject, curr_url)
            if all(album):
                if cur.execute("SELECT EXISTS (SELECT * FROM olimps WHERE link = "
                               "? AND subject = ?)", (curr_url, subject)).fetchone()[0]:
                    cur.execute("UPDATE olimps SET level = ?, dates = ?, classes = ? WHERE link "
                                "= ? AND subject = ?", (level, dates, get_age(classes), curr_url,
                                                        subject))
                else:
                    cur.execute("INSERT INTO olimps VALUES (?,?,?,?,?,?,NULL)", album)

            con.commit()

    except Exception as e:
        pass


subjects = list(set(cur.execute("SELECT subject "
                                "FROM olimps").fetchall())) + [('Внепредметная область',)]
for subject in subjects:
    if not cur.execute("SELECT EXISTS (SELECT * FROM "
                       "subjects WHERE subject = ?)", subject).fetchone()[0]:
        cur.execute("INSERT INTO subjects VALUES (?, NULL)", subject)

con.commit()
