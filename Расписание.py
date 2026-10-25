import io
import os
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image

# ================= НАСТРОЙКИ =================
URL_SCHEDULE_PAGE = "https://simfpolyteh.ru/schedule"

TELEGRAM_BOT_TOKEN = "8995067722:AAGxdaIoTvBd0Y7XV-bBHmnw9x0E1ys81ms"
TELEGRAM_CHAT_ID = "8797010997"

HASH_FILE = "last_schedule_hash.txt"


def get_image_data_and_hash():
    """Заходит на сайт, находит картинку и возвращает её байты и хеш."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(URL_SCHEDULE_PAGE, headers=headers, timeout=15)
        if response.status_code != 200:
            return None, None
    except Exception:
        return None, None

    soup = BeautifulSoup(response.text, "html.parser")

    # Ищем ссылку на картинку расписания
    img_url = None
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            img_url = urljoin(URL_SCHEDULE_PAGE, src)
            break

    if not img_url:
        return None, None

    try:
        img_bytes = requests.get(img_url, headers=headers, timeout=15).content
        # Считаем SHA-256 хеш от полученных байтов картинки
        current_hash = hashlib.sha256(img_bytes).hexdigest()
        return img_bytes, current_hash
    except Exception:
        return None, None


def send_to_telegram(image_bytes):
    """Конвертирует изображение в PNG и отправляет в личку Telegram."""
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": "🔔 <b>Внимание! Расписание на сайте обновилось!</b>",
        "parse_mode": "HTML"
    }
    files = {
        "document": ("schedule.png", output, "image/png")
    }
    requests.post(url, data=payload, files=files)


def check_for_updates():
    """Главная функция проверки изменений."""
    img_bytes, current_hash = get_image_data_and_hash()

    if not img_bytes or not current_hash:
        print("[!] Не удалось получить данные с сайта.")
        return

    # Читаем ранее сохранённый хеш (если он есть)
    old_hash = ""
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            old_hash = f.read().strip()

    # Сравниваем контрольные суммы
    if current_hash != old_hash:
        print("[*] Обнаружено новое расписание! Отправка в Telegram...")
        send_to_telegram(img_bytes)

        # Перезаписываем хеш новым значением
        with open(HASH_FILE, "w", encoding="utf-8") as f:
            f.write(current_hash)
        print("[+] Хеш обновлён, сообщение отправлено.")
    else:
        print("[-] Изменений нет. Картинка осталась прежней.")


if __name__ == "__main__":
    check_for_updates()
    import time

if __name__ == "__main__":
    while True:
        check_for_updates()
        time.sleep(3600)  # Пауза 20 минут (1200 секунд)