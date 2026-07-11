"""
Основной бот Lexaz — с админ-командами, двойной защитой и логированием.
Работает локально (с .env) и на Render (с Environment Variables).
"""

import telebot
import os
import re
import requests
from bs4 import BeautifulSoup

import ai_manager
import lexaz_memory
import lexaz_personality

# ═══════════════════════════════════════════════════════════════
# ЗАГРУЗКА КЛЮЧЕЙ
# ═══════════════════════════════════════════════════════════════

def load_env():
    """Загружает переменные из .env если файл есть (локально), 
    или использует переменные окружения (на Render)"""
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print("Загружены переменные из .env")
    else:
        print("Файл .env не найден — использую переменные окружения (Render)")

load_env()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '0'))

if not TELEGRAM_TOKEN:
    print("TELEGRAM_TOKEN не найден!")
    print("Локально: создайте .env файл")
    print("На Render: добавьте TELEGRAM_TOKEN в Environment Variables")
    exit()

bot = telebot.TeleBot(TELEGRAM_TOKEN)

LEX_UZ_BASE = "https://lex.uz"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}

user_states = {}

# ═══════════════════════════════════════════════════════════════
# СЕКРЕТНЫЙ КОД ДЛЯ РАССЫЛОК
# ═══════════════════════════════════════════════════════════════

SECRET_CODE = "lexazimaz"

# ═══════════════════════════════════════════════════════════════
# ПРОВЕРКА АДМИНА
# ═══════════════════════════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID

# ═══════════════════════════════════════════════════════════════
# ПОИСК НА LEX.UZ
# ═══════════════════════════════════════════════════════════════

def search_on_lexuz(query: str) -> dict:
    try:
        search_url = f"{LEX_UZ_BASE}/ru/search/all"
        params = {'lang': '1', 'searchtitle': query}
        response = requests.get(search_url, params=params, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return {'found': False}
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=re.compile(r'/docs/-?\d+'))
        if not links:
            return {'found': False}
        first_link = links[0]
        href = first_link.get('href')
        title = first_link.get_text(strip=True)
        if not href:
            return {'found': False}
        doc_url = href if href.startswith('http') else f"{LEX_UZ_BASE}{href}"
        doc_response = requests.get(doc_url, headers=HEADERS, timeout=30)
        if doc_response.status_code != 200:
            return {'found': True, 'title': title, 'url': doc_url, 'text': ''}
        doc_soup = BeautifulSoup(doc_response.text, 'html.parser')
        text = ""
        for selector in ['.doc_body', '.document_body', '#document_body', 'article', 'main']:
            content = doc_soup.select_one(selector)
            if content:
                text = content.get_text(separator='\n', strip=True)
                if len(text) > 200:
                    break
        if len(text) < 200:
            body = doc_soup.find('body')
            if body:
                text = body.get_text(separator='\n', strip=True)
        if len(text) > 5000:
            text = text[:5000] + "\n[...текст обрезан...]"
        return {'found': True, 'title': title, 'url': doc_url, 'text': text}
    except Exception as e:
        print(f"[Lex.uz] Ошибка: {e}")
        return {'found': False}

# ═══════════════════════════════════════════════════════════════
# ОБЫЧНЫЕ КОМАНДЫ
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=['start', 'help'])
def start_message(message):
    user_id = message.from_user.id
    lexaz_memory.register_user(user_id, message.from_user.username, message.from_user.first_name)
    
    text = """Здравствуйте! Я — Lexaz, ваш юридический ассистент.

Помогаю с вопросами по законодательству Республики Узбекистан.

*Бот работает на базе ИИ. Ответы могут содержать неточности.*

Команды:
/review — оставить отзыв
/clear — очистить историю
/name [имя] — как к вам обращаться
/style [formal/casual] — стиль общения

Задайте ваш вопрос."""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['clear'])
def clear_history_cmd(message):
    lexaz_memory.clear_history(message.from_user.id)
    bot.reply_to(message, "История диалога очищена.")

@bot.message_handler(commands=['name'])
def set_name_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /name [ваше имя]")
        return
    name = parts[1].strip()
    lexaz_memory.set_custom_name(message.from_user.id, name)
    lexaz_memory.set_use_name(message.from_user.id, True)
    bot.reply_to(message, f"Хорошо, буду обращаться к вам: {name}")

@bot.message_handler(commands=['style'])
def set_style_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /style [formal/casual/friendly]")
        return
    style = parts[1].strip().lower()
    if style not in ['formal', 'casual', 'friendly']:
        bot.reply_to(message, "Доступные стили: formal, casual, friendly")
        return
    lexaz_memory.set_communication_style(message.from_user.id, style)
    bot.reply_to(message, f"Стиль общения изменён на: {style}")

@bot.message_handler(commands=['review'])
def start_review_cmd(message):
    user_states[message.from_user.id] = 'waiting_review'
    bot.reply_to(message, "Напишите ваш отзыв одним сообщением.")

# ═══════════════════════════════════════════════════════════════
# АДМИН-КОМАНДЫ С ДВОЙНОЙ ЗАЩИТОЙ
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Эта команда доступна только администратору.")
        return
    
    stats = lexaz_memory.get_stats()
    text = f"""📊 *Статистика Lexaz*

*Всего пользователей:* {stats['total_users']}
*Всего сообщений:* {stats['total_messages']}

*Активность:*
— за 24 часа: {stats['active_24h']}
— за 7 дней: {stats['active_7d']}
— за 30 дней: {stats['active_30d']}

*Отзывов получено:* {stats['total_reviews']}

*Топ-10 пользователей:*"""
    
    for i, user in enumerate(stats['top_users'], 1):
        user_id, first_name, username, msg_count, last_seen = user
        name = first_name or 'Неизвестно'
        uname = f"@{username}" if username else 'нет username'
        text += f"\n{i}. {name} ({uname}) — {msg_count} сообщ."
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['feedbacks'])
def feedbacks_cmd(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Эта команда доступна только администратору.")
        return
    
    reviews = lexaz_memory.get_reviews(limit=10)
    
    if not reviews:
        bot.reply_to(message, "Отзывов пока нет.")
        return
    
    text = " *Последние отзывы:*\n\n"
    for r in reviews:
        name = r['first_name'] or 'Неизвестно'
        uname = f"@{r['username']}" if r['username'] else 'нет username'
        date = r['timestamp'][:10] if r['timestamp'] else 'неизвестно'
        text += f"*{name}* ({uname}) — {date}\n"
        text += f"_{r['review_text']}_\n\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Эта команда доступна только администратору.")
        return
    
    parts = message.text.split(maxsplit=2)
    
    if len(parts) < 3:
        bot.reply_to(message, f"Использование: /broadcast {SECRET_CODE} [текст рассылки]\n\nПример:\n/broadcast {SECRET_CODE} Здравствуйте! Бот обновился.")
        return
    
    code = parts[1]
    text = parts[2]
    
    if code != SECRET_CODE:
        bot.reply_to(message, "Неверный секретный код. Доступ запрещён.")
        print(f"[БЕЗОПАСНОСТЬ] Попытка рассылки с неверным кодом от пользователя {message.from_user.id} (@{message.from_user.username})")
        return
    
    send_broadcast(message, text)

@bot.message_handler(commands=['users'])
def users_cmd(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Эта команда доступна только администратору.")
        return
    
    user_ids = lexaz_memory.get_all_user_ids()
    text = f"👥 *Всего пользователей:* {len(user_ids)}\n\n"
    text += "Первые 50 пользователей:\n"
    
    for uid in user_ids[:50]:
        user = lexaz_memory.get_user(uid)
        if user:
            name = user['first_name'] or 'Неизвестно'
            uname = f"@{user['username']}" if user['username'] else ''
            text += f"• `{uid}` — {name} {uname} ({user['messages_count']} сообщ.)\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

def send_broadcast(message, text: str):
    user_ids = lexaz_memory.get_all_user_ids()
    if not user_ids:
        bot.reply_to(message, "Нет пользователей для рассылки.")
        return
    
    sent = 0
    failed = 0
    status_msg = bot.reply_to(message, f"Начинаю рассылку для {len(user_ids)} пользователей...")
    
    for uid in user_ids:
        try:
            bot.send_message(uid, f"📢 *Сообщение от администратора Lexaz:*\n\n{text}", parse_mode='Markdown')
            sent += 1
        except:
            failed += 1
    
    bot.edit_message_text(
        f"✅ Рассылка завершена.\n\nОтправлено: {sent}\nОшибок: {failed}",
        status_msg.chat.id,
        status_msg.message_id
    )

# ═══════════════════════════════════════════════════════════════
# ГЛАВНЫЙ ОБРАБОТЧИК С ЛОГИРОВАНИЕМ
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    username = message.from_user.username or 'нет username'
    first_name = message.from_user.first_name or 'Неизвестно'
    user_query = message.text
    
    # ЛОГИРОВАНИЕ В ТЕРМИНАЛ
    print(f"\n[User: {user_id} | @{username} | {first_name}] {user_query}")
    
    if not user_query or not user_query.strip():
        bot.reply_to(message, "Пожалуйста, сформулируйте ваш вопрос.")
        return
    
    lexaz_memory.register_user(user_id, message.from_user.username, message.from_user.first_name)
    
    # Режим ожидания отзыва
    if user_states.get(user_id) == 'waiting_review':
        handle_review(message)
        return
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Пасхалки (проверяем ПЕРВЫМИ)
        easter_egg = lexaz_personality.check_easter_egg(user_query)
        if easter_egg:
            bot.reply_to(message, easter_egg)
            lexaz_memory.add_to_history(user_id, 'user', user_query)
            lexaz_memory.add_to_history(user_id, 'assistant', easter_egg)
            print(f"[Ответ: пасхалка]")
            return
        
        # Анализ сообщения
        analysis = lexaz_personality.analyze_message(user_query)
        category = analysis.get('category', 'other')
        preference = analysis.get('preference')
        
        print(f"[Категория: {category}]")
        
        # Представление
        if category == 'name_request' and analysis.get('extracted_name'):
            name = analysis['extracted_name']
            lexaz_memory.set_custom_name(user_id, name)
            lexaz_memory.set_use_name(user_id, True)
            reply = f"Приятно познакомиться, {name}! Буду рад помочь."
            bot.reply_to(message, reply)
            lexaz_memory.add_to_history(user_id, 'user', user_query)
            lexaz_memory.add_to_history(user_id, 'assistant', reply)
            return
        
        # Смена стиля
        if category == 'style_request' and analysis.get('requested_style'):
            style = analysis['requested_style']
            lexaz_memory.set_communication_style(user_id, style)
            reply = f"Хорошо, перейдём на стиль: {style}."
            bot.reply_to(message, reply)
            lexaz_memory.add_to_history(user_id, 'user', user_query)
            lexaz_memory.add_to_history(user_id, 'assistant', reply)
            return
        
        # Просьбы изменить поведение
        if category == 'preference_request' and preference:
            if preference == 'use_name_off':
                lexaz_memory.set_use_name(user_id, False)
            elif preference == 'use_name_on':
                lexaz_memory.set_use_name(user_id, True)
            elif preference == 'emoji_off':
                lexaz_memory.set_use_emoji(user_id, False)
            elif preference == 'emoji_on':
                lexaz_memory.set_use_emoji(user_id, True)
            
            reply = lexaz_personality.generate_preference_answer(preference)
            bot.reply_to(message, reply)
            lexaz_memory.add_to_history(user_id, 'user', user_query)
            lexaz_memory.add_to_history(user_id, 'assistant', reply)
            return
        
        # Отзыв
        if category == 'review':
            user_states[user_id] = 'waiting_review'
            bot.reply_to(message, "Хотите оставить отзыв? Напишите его, пожалуйста.")
            return
        
        # Грубость
        if category == 'rude':
            reply = "Давайте общаться уважительно. Я здесь, чтобы помочь вам с юридическими вопросами."
            bot.reply_to(message, reply)
            lexaz_memory.add_to_history(user_id, 'user', user_query)
            lexaz_memory.add_to_history(user_id, 'assistant', reply)
            return
        
        user_data = lexaz_memory.get_user(user_id)
        
        # Вопросы о самом боте
        if category == 'about_bot':
            reply = lexaz_personality.generate_about_bot_answer(user_query, user_data)
            bot.reply_to(message, reply)
            lexaz_memory.add_to_history(user_id, 'user', user_query)
            lexaz_memory.add_to_history(user_id, 'assistant', reply)
            return
        
        # Неформальное общение
        if category == 'casual':
            quick = try_quick_casual(user_query)
            if quick:
                reply = quick
            else:
                reply = lexaz_personality.generate_casual_answer(user_query, user_data)
            bot.reply_to(message, reply)
            lexaz_memory.add_to_history(user_id, 'user', user_query)
            lexaz_memory.add_to_history(user_id, 'assistant', reply)
            return
        
        # Правовой вопрос
        if category == 'legal':
            search_query = analysis.get('search_query')
            if not search_query:
                search_query = user_query
            context = search_on_lexuz(search_query)
            reply = lexaz_personality.generate_legal_answer(user_query, context, user_data)
            send_long_message(message, reply)
            lexaz_memory.add_to_history(user_id, 'user', user_query)
            lexaz_memory.add_to_history(user_id, 'assistant', reply)
            return
        
        # Прочее
        reply = lexaz_personality.generate_casual_answer(user_query, user_data)
        bot.reply_to(message, reply)
        lexaz_memory.add_to_history(user_id, 'user', user_query)
        lexaz_memory.add_to_history(user_id, 'assistant', reply)
        
    except Exception as e:
        print(f"[Ошибка] {e}")
        bot.reply_to(message, "Извините, произошла техническая ошибка. Попробуйте позже.")

# ═══════════════════════════════════════════════════════════════
# ОТЗЫВЫ
# ═══════════════════════════════════════════════════════════════

def handle_review(message):
    user_id = message.from_user.id
    review_text = message.text
    
    lexaz_memory.add_review(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        review_text
    )
    
    if user_id in user_states:
        del user_states[user_id]
    
    bot.reply_to(message, "Спасибо за отзыв! Он очень важен для меня.")
    
    if ADMIN_USER_ID:
        admin_text = f""" *Новый отзыв*

*От:* {message.from_user.first_name or 'Неизвестно'}
*Username:* @{message.from_user.username or 'нет'}
*ID:* `{user_id}`

*Текст:*
{review_text}"""
        try:
            bot.send_message(ADMIN_USER_ID, admin_text, parse_mode='Markdown')
        except Exception as e:
            print(f"[Админ] Ошибка отправки: {e}")

# ═══════════════════════════════════════════════════════════════
# УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════

def try_quick_casual(query: str) -> str:
    q = query.lower().strip().rstrip('!?.,')
    if q in ['привет', 'здравствуй', 'здравствуйте', 'салам', 'салом', 'hi', 'hello', 'добрый день', 'доброе утро', 'добрый вечер']:
        return "Здравствуйте! Рад вас видеть. Чем могу помочь?"
    if q in ['спасибо', 'благодарю', 'thanks', 'рахмат']:
        return "Всегда пожалуйста."
    if q in ['пока', 'до свидания', 'бай', 'goodbye', 'хайр']:
        return "Всего доброго! Буду рад помочь, когда понадобится."
    return ""

def send_long_message(message, text: str):
    if len(text) <= 4000:
        bot.reply_to(message, text)
    else:
        for i in range(0, len(text), 4000):
            bot.reply_to(message, text[i:i+4000])

# ═══════════════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("="*60)
    print("LEXAZ TELEGRAM BOT")
    print("="*60)
    
    ai_manager.startup_check()
    
    print(f"Админ ID: {ADMIN_USER_ID}")
    print(f"Секретный код рассылки: {SECRET_CODE}")
    print("Бот запущен. Нажмите Ctrl+C для остановки.")
    print("="*60)
    print("Админ-команды (только для вас):")
    print("  /stats — статистика")
    print("  /feedbacks — отзывы")
    print(f"  /broadcast {SECRET_CODE} [текст] — рассылка")
    print("  /users — список пользователей")
    print("="*60)
    
    bot.infinity_polling()
