import io
import os
import re
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image

# ================= НАСТРОЙКИ =================
# Секреты берутся автоматически из настроек GitHub
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

# Страница с расписанием на сайте колледжа
URL_SCHEDULE_PAGE = os.getenv("SCHEDULE_URL", "https://simfpolyteh.ru/")

HASH_FILE = "last_schedule_hash.txt"


def get_image_data_and_hash():
    """Находит свежую картинку расписания из /api/uploads/ и считает её хеш."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(URL_SCHEDULE_PAGE, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"[!] Сайт вернул статус: {response.status_code}")
            return None, None
    except Exception as e:
        print(f"[!] Ошибка запроса к сайту: {e}")
        return None, None

    soup = BeautifulSoup(response.text, "html.parser")
    candidates = []

    # 1. Поиск по тегам <img>
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "/api/uploads/" in src:
            candidates.append(urljoin(URL_SCHEDULE_PAGE, src))

    # 2. Поиск по ссылкам <a>
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/api/uploads/" in href and any(href.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
            candidates.append(urljoin(URL_SCHEDULE_PAGE, href))

    # 3. Поиск регулярным выражением (если ссылки лежат внутри JS/JSON скриптов)
    found_urls = re.findall(r'(/api/uploads/\d+\.(?:png|jpg|jpeg))', response.text, re.IGNORECASE)
    for path in found_urls:
        candidates.append(urljoin(URL_SCHEDULE_PAGE, path))

    if not candidates:
        print("[!] Ссылки на картинки расписания не найдены на странице.")
        return None, None

    # Убираем дубликаты и сортируем по числу (таймстемпу) в имени файла
    candidates = sorted(list(set(candidates)))
    latest_img_url = candidates[-1]
    print(f"[*] Ссылка на свежее расписание: {latest_img_url}")

    try:
        img_bytes = requests.get(latest_img_url, headers=headers, timeout=25).content
        current_hash = hashlib.sha256(img_bytes).hexdigest()
        return img_bytes, current_hash
    except Exception as e:
        print(f"[!] Ошибка загрузки картинки: {e}")
        return None, None


def send_to_telegram(image_bytes):
    """Конвертирует в чистый PNG и отправляет в Telegram документом."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] Ошибка: Не заданы BOT_TOKEN или CHAT_ID в секретах!")
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
        "caption": "🔔 <b>Свежее расписание!</b>",
        "parse_mode": "HTML"
    }
    files = {
        "document": ("schedule.png", output, "image/png")
    }

    resp = requests.post(url, data=payload, files=files, timeout=30)
    if resp.status_code == 200:
        print("[+] Расписание успешно отправлено в Telegram!")
    else:
        print(f"[!] Ошибка отправки в TG: {resp.text}")


def check_for_updates():
    img_bytes, current_hash = get_image_data_and_hash()

    if not img_bytes or not current_hash:
        return

    old_hash = ""
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            old_hash = f.read().strip()

    if current_hash != old_hash:
        print("[*] Расписание изменилось (или первый запуск). Отправка...")
        send_to_telegram(img_bytes)

        with open(HASH_FILE, "w", encoding="utf-8") as f:
            f.write(current_hash)
    else:
        print("[-] Изменений нет. Хеш картинки совпадает с предыдущим.")


if __name__ == "__main__":
    check_for_updates()
