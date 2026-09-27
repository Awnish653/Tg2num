import asyncio
import re
import time
from flask import Flask, request, jsonify
from pyrogram import Client
from pyrogram.errors import FloodWait

# --- Telegram config ---
API_ID = 29969433
API_HASH = "884f9ffa4e8ece099cccccade82effac"
PHONE_NUMBER = "+919214045762"
TARGET_BOT = "@telebrecheddb_bot"

# --- Client setup (no session string) ---
tg_client = Client(
    "vercel_session",
    api_id=API_ID,
    api_hash=API_HASH,
    phone_number=PHONE_NUMBER,
    no_updates=True
)

def parse_bot_response(text: str) -> dict:
    text = text.replace("Телефон", "Phone") \
               .replace("История изменения имени", "Name change history") \
               .replace("Интересовались этим", "Viewed by")

    data = {"success": True, "username": None, "id": None,
            "phone": None, "viewed_by": None, "name_history": []}

    if m := re.search(r"t\.me/([A-Za-z0-9_]+)", text):
        data["username"] = m.group(1)
    if m := re.search(r"ID[:： ]+(\d+)", text):
        data["id"] = m.group(1)
    if m := re.search(r"Phone[:： ]+(\d+)", text):
        data["phone"] = m.group(1)
    if m := re.search(r"Viewed by[:： ]*(\d+)", text):
        data["viewed_by"] = int(m.group(1))

    for d, u, i in re.findall(r"(\d{2}\.\d{2}\.\d{4}) → @([\w\d_]+),\s*([\w\d, ]+)", text):
        ids = re.findall(r"\d+", i)
        data["name_history"].append({"date": d, "username": u, "id": ids[0] if ids else None})

    return data

async def send_and_wait(username: str) -> dict:
    username = username.strip().lstrip("@")
    try:
        sent = await tg_client.send_message(TARGET_BOT, f"t.me/{username}")
    except FloodWait as e:
        await asyncio.sleep(e.value)
        sent = await tg_client.send_message(TARGET_BOT, f"t.me/{username}")
    except Exception as e:
        return {"success": False, "error": f"Error contacting bot: {e}"}

    reply_text = None
    start_time = time.time()
    while time.time() - start_time < 60:
        async for msg in tg_client.get_chat_history(TARGET_BOT, limit=10):
            if msg.id > sent.id and not msg.outgoing and msg.text:
                reply_text = msg.text
                break
        if reply_text:
            break
        await asyncio.sleep(2)

    if not reply_text:
        return {"success": False, "error": "No reply received from bot after 60s."}
    return parse_bot_response(reply_text)

app = Flask(__name__)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

@app.route("/check")
def check():
    username = request.args.get("username")
    if not username:
        return jsonify({"success": False, "error": "Missing 'username' parameter"}), 400

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(send_and_wait(username))
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
