"""
AI Manager — менеджер ИИ с автоматическим fallback.
Основной: Groq (стабильный, быстрый)
Резервный: OpenRouter (если Groq недоступен)
"""

import os
import json
import re
import time
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# МОДЕЛИ (правильные названия)
# ═══════════════════════════════════════════════════════════════

GROQ_MODELS = {
    'fast': 'llama-3.3-70b-versatile',
    'power': 'llama-3.3-70b-versatile'
}

OPENROUTER_FAST_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen-2.5-7b-instruct:free",
]

OPENROUTER_POWER_MODELS = [
    "qwen/qwen-2.5-7b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
]

# ═══════════════════════════════════════════════════════════════
# УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════

def _clean_json(text: str) -> str:
    """Очищает текст от markdown-обёртки и извлекает JSON"""
    if not text:
        return ""
    
    # Убираем markdown-обёртку ```json ... ```
    text = text.strip()
    if text.startswith("```"):
        # Убираем первую строку ```json или ```
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Убираем последнюю строку ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    
    # Ищем первый { и последний }
    start = text.find('{')
    end = text.rfind('}')
    
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    
    return text

def _parse_json(text: str) -> Optional[dict]:
    """Парсит JSON с очисткой"""
    cleaned = _clean_json(text)
    if not cleaned:
        return None
    try:
        return json.loads(cleaned)
    except Exception as e:
        print(f"[JSON parse error] {e}")
        print(f"[Raw text] {text[:200]}")
        return None

# ═══════════════════════════════════════════════════════════════
# GROQ (ОСНОВНОЙ)
# ═══════════════════════════════════════════════════════════════

def _groq_query(system_prompt: str, user_prompt: str, temperature: float = 0.3, 
                max_tokens: int = 500, model: str = 'fast') -> Optional[str]:
    try:
        from groq import Groq
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            return None
        
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODELS[model],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[Groq] Ошибка: {e}")
        return None

def _groq_json(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> Optional[dict]:
    """Groq с JSON-ответом (без response_format — Groq иногда его не поддерживает)"""
    # Добавляем инструкцию в промпт, чтобы модель вернула чистый JSON
    enhanced_system = system_prompt + "\n\nОТВЕЧАЙ ТОЛЬКО ВАЛИДНЫМ JSON. БЕЗ ПОЯСНЕНИЙ, БЕЗ MARKDOWN, БЕЗ ```."
    
    result = _groq_query(enhanced_system, user_prompt, temperature, 500, 'fast')
    if not result:
        return None
    
    parsed = _parse_json(result)
    if parsed is None:
        print(f"[Groq JSON] Не удалось распарсить: {result[:100]}")
    return parsed

# ═══════════════════════════════════════════════════════════════
# OPENROUTER (РЕЗЕРВНЫЙ)
# ═══════════════════════════════════════════════════════════════

def _openrouter_query(system_prompt: str, user_prompt: str, temperature: float = 0.3,
                      max_tokens: int = 500, models_list: list = None) -> Optional[str]:
    try:
        from openai import OpenAI
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            return None
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={"HTTP-Referer": "https://t.me/lexaz_bot"}
        )
        
        if models_list is None:
            models_list = OPENROUTER_FAST_MODELS
        
        for model in models_list:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    continue
                continue
        return None
    except Exception as e:
        print(f"[OpenRouter] Ошибка: {e}")
        return None

def _openrouter_json(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> Optional[dict]:
    enhanced_system = system_prompt + "\n\nОТВЕЧАЙ ТОЛЬКО ВАЛИДНЫМ JSON. БЕЗ ПОЯСНЕНИЙ, БЕЗ MARKDOWN, БЕЗ ```."
    
    result = _openrouter_query(enhanced_system, user_prompt, temperature, 500)
    if not result:
        return None
    
    parsed = _parse_json(result)
    if parsed is None:
        print(f"[OpenRouter JSON] Не удалось распарсить: {result[:100]}")
    return parsed

# ══════════════════════════════════════════════════════════════
# ПУБЛИЧНЫЕ ФУНКЦИИ С FALLBACK
# ═══════════════════════════════════════════════════════════════

def fast_query(system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 500) -> str:
    result = _groq_query(system_prompt, user_prompt, temperature, max_tokens, 'fast')
    if result:
        return result
    result = _openrouter_query(system_prompt, user_prompt, temperature, max_tokens)
    return result or ""

def fast_json(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> dict:
    result = _groq_json(system_prompt, user_prompt, temperature)
    if result:
        return result
    result = _openrouter_json(system_prompt, user_prompt, temperature)
    return result or {}

def power_query(system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 2000) -> str:
    result = _groq_query(system_prompt, user_prompt, temperature, max_tokens, 'power')
    if result:
        return result
    result = _openrouter_query(system_prompt, user_prompt, temperature, max_tokens, OPENROUTER_POWER_MODELS)
    return result or ""

def power_chat(messages: list, temperature: float = 0.3, max_tokens: int = 2000) -> str:
    try:
        from groq import Groq
        api_key = os.getenv('GROQ_API_KEY')
        if api_key:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=GROQ_MODELS['power'],
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
    except Exception as e:
        print(f"[Groq chat] Ошибка: {e}")
    
    try:
        from openai import OpenAI
        api_key = os.getenv('OPENROUTER_API_KEY')
        if api_key:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                default_headers={"HTTP-Referer": "https://t.me/lexaz_bot"}
            )
            for model in OPENROUTER_POWER_MODELS:
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    return response.choices[0].message.content
                except:
                    continue
    except Exception as e:
        print(f"[OpenRouter chat] Ошибка: {e}")
    
    return ""

# ═══════════════════════════════════════════════════════════════
# ДИАГНОСТИКА ПРИ СТАРТЕ
# ═══════════════════════════════════════════════════════════════

def check_connections() -> dict:
    status = {'groq': False, 'openrouter': False}
    
    try:
        from groq import Groq
        api_key = os.getenv('GROQ_API_KEY')
        if api_key:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            status['groq'] = True
            print("  [OK] Groq подключен")
    except Exception as e:
        print(f"  [!] Groq недоступен: {e}")
    
    try:
        from openai import OpenAI
        api_key = os.getenv('OPENROUTER_API_KEY')
        if api_key:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                default_headers={"HTTP-Referer": "https://t.me/lexaz_bot"}
            )
            response = client.chat.completions.create(
                model="meta-llama/llama-3.3-70b-instruct:free",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            status['openrouter'] = True
            print("  [OK] OpenRouter подключен")
    except Exception as e:
        print(f"  [!] OpenRouter недоступен: {e}")
    
    return status

def startup_check():
    print("\n" + "="*60)
    print("ПРОВЕРКА ПОДКЛЮЧЕНИЙ ИИ")
    print("="*60)
    status = check_connections()
    
    if not status['groq'] and not status['openrouter']:
        print("\n[КРИТИЧНО] Ни один ИИ-сервис не доступен!")
        return False
    
    if not status['groq']:
        print("\n[ВНИМАНИЕ] Groq недоступен. Используется только OpenRouter.")
    
    if not status['openrouter']:
        print("\n[ВНИМАНИЕ] OpenRouter недоступен. Используется только Groq.")
    
    print("="*60 + "\n")
    return True