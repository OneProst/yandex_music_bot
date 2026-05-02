import requests
import re
import time
import os

BOT_TOKEN = "8467280621:AAEYQObUyv3jJjtM2n0nY4YPwSD9hLNWAOk"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
LAST_UPDATE_ID = 0
START_TIME = time.time()

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def extract_login_from_html(html):
    patterns = [
        r'"owner"\s*:\s*\{[^{}]*"login"\s*:\s*"([^"]+)"',
        r'"login"\s*:\s*"([^"]+)"\s*,\s*"name"',
        r'preloadedPlaylistByUuid[^}]*"login"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            login = match.group(1)
            log(f"Найден логин: {login}")
            return login
    return None

def convert_playlist(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'ru-RU,ru;q=0.9'
    }
    try:
        clean_url = re.sub(r'\?.*$', '', url)
        log(f"Запрос к Яндекс: {clean_url[:80]}...")
        
        response = requests.get(clean_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        login = extract_login_from_html(response.text)
        
        if login:
            result = f"https://music.yandex.ru/users/{login}/playlists/3"
            return result, None
        else:
            return None, "❌ Не удалось найти логин. Убедись, что плейлист публичный."
            
    except requests.exceptions.Timeout:
        return None, "⏰ Таймаут. Попробуй позже."
    except requests.exceptions.ConnectionError:
        return None, "❌ Ошибка соединения."
    except Exception as e:
        return None, f"❌ Ошибка: {str(e)[:100]}"

def send_message(chat_id, text, reply_to=None):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    if reply_to:
        payload['reply_to_message_id'] = reply_to
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            log(f"Ошибка отправки: {response.status_code}")
        return response
    except Exception as e:
        log(f"Ошибка отправки сообщения: {e}")
        return None

def send_typing(chat_id):
    try:
        requests.post(f"{TELEGRAM_API}/sendChatAction", json={
            'chat_id': chat_id,
            'action': 'typing'
        }, timeout=5)
    except:
        pass

def handle_start(chat_id):
    log(f"Start команда от {chat_id}")
    send_message(chat_id, """🎵 *Конвертер Яндекс Музыки*

Отправь мне ссылку на плейлист, например:
`https://music.yandex.ru/playlists/lk.4c673eff-...`

А я пришлю ссылку старого формата:
`https://music.yandex.ru/users/логин/playlists/3`

💡 *Важно:* плейлист должен быть публичным
""")

def handle_help(chat_id):
    send_message(chat_id, """📖 *Как пользоваться*

1. Открой плейлист в Яндекс Музыке
2. Нажми «Поделиться» → «Копировать ссылку»
3. Отправь эту ссылку боту
4. Получи готовую ссылку старого формата

*Пример:*
`https://music.yandex.ru/playlists/lk.4c673eff-d89f-429b-9086-e94519a0021a`
""")

def handle_url(chat_id, text, message_id):
    log(f"Обработка URL от {chat_id}: {text[:60]}...")
    
    # Ищем ссылку в тексте
    match = re.search(r'(https?://)?(music\.yandex\.(ru|by|kz|ua))/playlists?/[a-f0-9\.-]+', text, re.IGNORECASE)
    
    if not match:
        send_message(chat_id, "❌ Это не похоже на ссылку плейлиста Яндекс Музыки.\n\nСсылка должна содержать `music.yandex.ru/playlists/...`", reply_to=message_id)
        return
    
    full_url = match.group(0)
    if not full_url.startswith('http'):
        full_url = 'https://' + full_url
    
    send_typing(chat_id)
    result, error = convert_playlist(full_url)
    
    if error:
        send_message(chat_id, error, reply_to=message_id)
    else:
        send_message(chat_id, f"✅ *Готово!*\n\n🔗 {result}\n\n📋 Нажми на ссылку, чтобы скопировать", reply_to=message_id)

def main():
    global LAST_UPDATE_ID, START_TIME
    log("🚀 Бот запущен!")
    log(f"Токен: {BOT_TOKEN[:15]}...")
    
    # Проверяем подключение к Telegram API
    try:
        test = requests.get(f"{TELEGRAM_API}/getMe", timeout=10)
        if test.status_code == 200:
            log("✅ Подключение к Telegram API работает", "success")
            bot_info = test.json()
            if bot_info.get('ok'):
                log(f"✅ Бот: @{bot_info['result']['username']}", "success")
        else:
            log(f"⚠️ Проблема с API: {test.status_code}")
    except Exception as e:
        log(f"⚠️ Не удалось проверить API: {e}")
    
    log("🔄 Запускаю polling цикл...")
    
    while True:
        try:
            url = f"{TELEGRAM_API}/getUpdates"
            params = {
                'offset': LAST_UPDATE_ID + 1,
                'timeout': 30,
                'allowed_updates': ['message']
            }
            
            response = requests.get(url, params=params, timeout=35)
            data = response.json()
            
            if data.get('ok') and data.get('result'):
                for update in data['result']:
                    LAST_UPDATE_ID = update['update_id']
                    
                    if 'message' in update:
                        msg = update['message']
                        chat_id = msg['chat']['id']
                        text = msg.get('text', '')
                        message_id = msg['message_id']
                        
                        # Игнорируем старые сообщения (старше 10 секунд)
                        msg_date = msg.get('date', 0)
                        
                        if text.startswith('/start'):
                            handle_start(chat_id)
                        elif text.startswith('/help'):
                            handle_help(chat_id)
                        elif text.startswith('/'):
                            send_message(chat_id, "❌ Неизвестная команда. Используй /start или /help", reply_to=message_id)
                        else:
                            handle_url(chat_id, text, message_id)
            
        except requests.exceptions.Timeout:
            pass  # Нормально, просто ждем дальше
        except Exception as e:
            log(f"Ошибка в polling: {e}")
            time.sleep(5)
        
        time.sleep(1)

if __name__ == "__main__":
    main()