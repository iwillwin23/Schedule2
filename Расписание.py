import io
import os
import re
import hashlib
import requests
from urllib.parse import urljoin
from PIL import Image

# ================= НАСТРОЙКИ =================
# Секреты подтягиваются из репозитория GitHub Actions
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

# Ссылка на страницу с расписанием (если есть прямой подраздел, можно переопределить через секрет SCHEDULE_URL)
URL_SCHEDULE_PAGE = os.getenv("SCHEDULE_URL", "https://simfpolyteh.ru/")

HASH_FILE = "last_schedule_hash.txt"


def get_image_data_and_hash():
    """Ищет файлы вида /api/uploads/<10-15 цифр>.(png|jpg) и забирает самый свежий."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(URL_SCHEDULE_PAGE, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"[!] Ошибка: Сайт вернул HTTP-код {response.status_code}")
            return None, None
    except Exception as e:
        print(f"[!] Ошибка подключения к сайту: {e}")
        return None, None

    # Ищем строго: /api/uploads/ + от 10 до 15 цифр + .png/.jpg/.jpeg/.webp
    # Любой poster.jpg, banner.jpg или logo.png этот фильтр просто проигнорирует
    pattern = r'/api/uploads/(\d{10,15}\.(?:png|jpg|jpeg|webp))'
    found_filenames = re.findall(pattern, response.text, re.IGNORECASE)

    if not found_filenames:
        print("[!] Картинка расписания с цифровым ID не найдена на странице.")
        return None, None

    # Убираем дубликаты и сортируем по числу
    unique_files = sorted(list(set(found_filenames)))
    print(f"[*] Найдены файлы расписания: {unique_files}")

    # Забираем самый последний добавленный файл (максимальное число)
    latest_file = unique_files[-1]
    latest_img_url = urljoin(URL_SCHEDULE_PAGE, f"/api/uploads/{latest_file}")
    print(f"[*] Актуальное расписание: {latest_img_url}")

    try:
        img_bytes = requests.get(latest_img_url, headers=headers, timeout=25).content
        current_hash = hashlib.sha256(img_bytes).hexdigest()
        return img_bytes, current_hash
    except Exception as e:
        print(f"[!] Ошибка при скачивании файла расписания: {e}")
        return None, None


def send_to_telegram(image_bytes):
    """Конвертирует изображение в чистый PNG и отправляет документом без сжатия."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] Ошибка: BOT_TOKEN или CHAT_ID не найдены в переменных окружения!")
        return

    # Конвертация в PNG для максимальной четкости текста
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": "🔔 <b>Расписание занятий обновилось!</b>",
        "parse_mode": "HTML"
    }
    files = {
        "document": ("schedule.png", output, "image/png")
    }

    try:
        resp = requests.post(url, data=payload, files=files, timeout=30)
        if resp.status_code == 200:
            print("[+] Расписание успешно улетело в Telegram!")
        else:
            print(f"[!] Ошибка отправки в Telegram API: {resp.text}")
    except Exception as e:
        print(f"[!] Ошибка HTTP-запроса к Telegram: {e}")


def check_for_updates():
    """Сверяет хеш скачанной картинки с предыдущим значением."""
    img_bytes, current_hash = get_image_data_and_hash()

    if not img_bytes or not current_hash:
        return

    old_hash = ""
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            old_hash = f.read().strip()

    if current_hash != old_hash:
        print("[*] Обнаружено новое расписание (или первый запуск). Отправка...")
        send_to_telegram(img_bytes)

        with open(HASH_FILE, "w", encoding="utf-8") as f:
            f.write(current_hash)
        print("[+] Контрольный хеш сохранён.")
    else:
        print("[-] Изменений нет. Хеш совпадает с сохранённым ранее.")


if __name__ == "__main__":
    check_for_updates()
