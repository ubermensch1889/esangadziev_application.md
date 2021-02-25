import requests
import sqlite3
from bs4 import BeautifulSoup


def translate_date(d):
    d = d.replace('До ', '')
    if '...' not in d:
        d = d.split()
        return d[0].rjust(2, '0') + '.' + str(months.index(d[1]) + 1).rjust(2, '0')
    d = list(map(lambda x: x.split(), d.split('...')))
    if len(d[0]) == 1:
        d[0].append(d[1][1])
    return d[0][0].rjust(2, '0') + '.' + str(months.index(d[0][1]) + 1).rjust(2, '0') + '-' + \
           d[1][0].rjust(2, '0') + '.' + str(months.index(d[1][1]) + 1).rjust(2, '0')


def get_age(age):
    age = age[:-7]
    if '–' in age:
        age = age.split('–')
        return ' '.join([str(cl) for cl in range(int(age[0]), int(age[1]) + 1)])
    return age


con = sqlite3.connect("olimps.db3")
cur = con.cursor()
cur.execute("DELETE FROM olimps")
cur.execute("DELETE FROM subjects")
months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
url = 'https://olimpiada.ru/article/942#iikt'
response = requests.get(url)
soup = BeautifulSoup(response.text, 'lxml')
quotes = soup.find_all('a', {'class': 'slim_dec'})
l = []
album = []
dates = []

for quote in quotes:
    l.append('https://olimpiada.ru' + str(quote.get('href')))

for curr_url in l[1:50]:
    if '#' not in curr_url and 'None' not in curr_url:
        response = requests.get(curr_url)
        soup = BeautifulSoup(response.text, 'lxml')
        quotes = soup.find_all('a')
        name = soup.find('h1').text
        classes = soup.find('span', {'class': 'classes_types_a'}).text
        level = soup.find_all('div', {'class': 'f_blocks'})[-1].text
        subject = soup.find('span', {'class': 'subject_tag'}).text
        for i in quotes:
            if i.text[-3:] in months:
                dates.append(translate_date(i.text))
        album.append((name, level[level.find('уровень') + 8], ' '.join(dates), get_age(classes), subject))
        dates = []
cur.executemany("INSERT INTO olimps VALUES (?,?,?,?,?)", album)
subjects = sorted(list(set(cur.execute("SELECT subject FROM olimps").fetchall())))
cur.executemany("INSERT INTO subjects VALUES (?)", subjects)

con.commit()