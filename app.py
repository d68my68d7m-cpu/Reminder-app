from flask import Flask, request, jsonify
import sqlite3
import datetime
import time
import threading
import requests
import os

app = Flask(__name__)

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8687939395:AAH2MMp3YHeRHLG9kIfX3iJoG6R4SlgMuPg')  # Замените на ваш токен, либо задайте переменную окружения
# ------------------------------

# Создаём базу данных и таблицу, если её нет
def init_db():
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            datetime TEXT NOT NULL,
            sent INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Функция отправки сообщения через бота
def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': '🔔 Напоминание: ' + text,
        'parse_mode': 'HTML'
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
        return r.ok
    except:
        return False

# Эндпоинт для добавления напоминания
@app.route('/add_reminder', methods=['POST'])
def add_reminder():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400

    chat_id = data.get('chat_id')
    text = data.get('text')
    datetime_str = data.get('datetime')  # ожидается ISO-строка, например "2025-08-27T14:30:00"

    if not all([chat_id, text, datetime_str]):
        return jsonify({'error': 'Missing fields'}), 400

    # Проверяем, что дата корректна
    try:
        dt = datetime.datetime.fromisoformat(datetime_str)
    except:
        return jsonify({'error': 'Invalid datetime format'}), 400

    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute('INSERT INTO reminders (chat_id, text, datetime) VALUES (?, ?, ?)',
              (chat_id, text, datetime_str))
    conn.commit()
    conn.close()

    return jsonify({'status': 'ok'}), 200

# Фоновый поток, который раз в минуту проверяет напоминания
def reminder_checker():
    while True:
        try:
            conn = sqlite3.connect('reminders.db')
            c = conn.cursor()
            now = datetime.datetime.now().isoformat(timespec='seconds')
            # Выбираем напоминания, у которых время <= текущее и они ещё не отправлены
            c.execute('SELECT id, chat_id, text, datetime FROM reminders WHERE datetime <= ? AND sent = 0', (now,))
            rows = c.fetchall()
            for row in rows:
                id_, chat_id, text, dt = row
                success = send_telegram_message(chat_id, text)
                if success:
                    # Помечаем как отправленное
                    c.execute('UPDATE reminders SET sent = 1 WHERE id = ?', (id_,))
                    conn.commit()
                else:
                    # Если не удалось отправить, можно попробовать позже (не помечаем)
                    pass
            conn.close()
        except Exception as e:
            print('Ошибка в checker:', e)
        time.sleep(60)  # проверяем каждую минуту

# Запускаем фоновый поток
thread = threading.Thread(target=reminder_checker, daemon=True)
thread.start()

@app.route('/')
def index():
    return 'Сервер напоминаний работает!'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)