import io
import os
import re
import hashlib
import requests
from urllib.parse import urljoin
from PIL import Image

# ================= НАСТРОЙКИ =================
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

SCHEDULE_PAGE_URL = "https://simfpolyteh.ru/schedule"
SCHEDULE_API_URL = "https://simfpolyteh.ru/api/schedule"

HASH_FILE = "last_schedule_hash.txt"


def get_image_data_and_hash():
    """Ищет расписание через API или разметку страницы /schedule."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://simfpolyteh.ru/schedule"
    }

    found_files = []
    pattern = r'/api/uploads/(\d{10,15}\.(?:png|jpg|jpeg|webp))'

    # Шаг 1: Пробуем запросить напрямую внутренний API
    try:
        api_res = requests.get(SCHEDULE_API_URL, headers=headers, timeout=15)
        if api_res.status_code == 200:
            matches = re.findall(pattern, api_res.text, re.IGNORECASE)
            found_files.extend(matches)
    except Exception as e:
        print(f"[!] API недоступен, пробуем страницу: {e}")

    # Шаг 2: Если API не ответил, забираем исходный код страницы /schedule
    if not found_files:
        try:
            page_res = requests.get(SCHEDULE_PAGE_URL, headers=headers, timeout=15)
            if page_res.status_code == 200:
                matches = re.findall(pattern, page_res.text, re.IGNORECASE)
                found_files.extend(matches)
        except Exception as e:
            print(f"[!] Ошибка загрузки страницы: {e}")

    if not found_files:
        print("[!] Не удалось найти файл расписания в /api/uploads/")
        return None, None

    # Сортируем таймстемпы и выбираем самый свежий
    unique_files = sorted(list(set(found_files)))
    latest_filename = unique_files[-1]
    latest_url = f"https://simfpolyteh.ru/api/uploads/{latest_filename}"
    print(f"[*] Найдено свежее расписание: {latest_url}")

    try:
        img_bytes = requests.get(latest_url, headers=headers, timeout=25).content
        current_hash = hashlib.sha256(img_bytes).hexdigest()
        return img_bytes, current_hash
    except Exception as e:
        print(f"[!] Ошибка загрузки картинки: {e}")
        return None, None


def send_to_telegram(image_bytes):
    """Конвертирует изображение в PNG и отправляет в личку Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] Ошибка: Не заданы BOT_TOKEN или CHAT_ID!")
        return

    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": "🔔 <b>Расписание политеха обновилось!</b>",
        "parse_mode": "HTML"
    }
    files = {
        "document": ("schedule.png", output, "image/png")
    }

    try:
        resp = requests.post(url, data=payload, files=files, timeout=30)
        if resp.status_code == 200:
            print("[+] Расписание успешно отправлено в Telegram!")
        else:
            print(f"[!] Ошибка отправки: {resp.text}")
    except Exception as e:
        print(f"[!] Ошибка сети при отправке в TG: {e}")


def check_for_updates():
    img_bytes, current_hash = get_image_data_and_hash()
    if not img_bytes or not current_hash:
        return

    old_hash = ""
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            old_hash = f.read().strip()

    if current_hash != old_hash:
        print("[*] Обнаружено новое расписание. Отправка...")
        send_to_telegram(img_bytes)

        with open(HASH_FILE, "w", encoding="utf-8") as f:
            f.write(current_hash)
        print("[+] Хеш обновлён.")
    else:
        print("[-] Изменений нет. Хеш картинки совпадает с предыдущим.")


if __name__ == "__main__":
    check_for_updates()
