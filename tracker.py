import os
import time
import json
import requests
import urllib.parse
import pandas as pd
from google import genai
from google.genai import types  # Import types for JSON configuration

# 1. Fetch data from your Google Sheet
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1_x_nW-3ppImt2CzdtPNh3KAnOjSCMuzXhbSUxZUYbqc/export?format=csv"

try:
    df = pd.read_csv(SHEET_CSV_URL)
except Exception as e:
    print(f"Error reading Google Sheet: {e}")
    exit(1)

# 2. Configure GenAI Client
client = genai.Client()

# Active, stable model fallback array
MODELS_TO_TRY = ['gemini-3.5-flash', 'gemini-3.1-flash-lite', 'gemini-2.5-flash']

compiled_report = "📅 *Daily Exam Updates & News Report* 📅\n\n"
updates_found = False

# Standard browser persona headers to sneak past portal firewalls
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/"
}

for index, row in df.iterrows():
    name = str(row['Exam Name']).strip()
    official_url = str(row['Website URL']).strip()
    
    encoded_query = urllib.parse.quote(f"{name} exam updates timelines 2026")
    google_news_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    official_text = ""
    external_news_text = ""
    
    # Fetch Data using Browser Persona Headers
    try:
        official_text = requests.get(official_url, headers=BROWSER_HEADERS, timeout=12).text[:15000]
    except Exception:
        official_text = "⚠️ Portal connection timed out."

    try:
        external_news_text = requests.get(google_news_url, headers=BROWSER_HEADERS, timeout=12).text[:15000]
    except Exception:
        external_news_text = "⚠️ News stream connection timed out."
        
    # We now instruct the AI to build a structural JSON dictionary
    prompt = f"""
    You are an API extraction layer tracking the exam: '{name}'.
    Analyze the raw data sources:
    
    SOURCE 1: Official Portal text
    ---
    {official_text}
    ---
    
    SOURCE 2: Recent news headlines RSS
    ---
    {external_news_text}
    ---
    
    Task:
    Extract 2026 cycle timelines. Return your response ONLY as a valid JSON object matching this schema structure:
    {{
        "status": "updates_found" or "no_updates",
        "notification": "Exact date, tentative month, or expected quarter. Write TBA if unknown.",
        "exam_dates": "Exact schedules or tentative exam slots. Write TBA if unknown.",
        "latest_news": "A clean 1-2 sentence raw update summary of notifications, forms, or results."
    }}
    Do not use any markdown formatting or asterisks inside your text strings.
    """
    
    ai_response_text = None
    
    # Fallback Execution Loop
    for model_name in MODELS_TO_TRY:
        try:
            # Forcing JSON Mode output schema configuration
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            ai_response_text = response.text.strip()
            if ai_response_text:
                break  
        except Exception as e:
            print(f"⚠️ {model_name} processing failed for {name}. Error details: {e}")
            time.sleep(2)  
            
    if not ai_response_text:
        print(f"❌ All active models failed for {name}.")
        continue

    try:
        # Safely extract the structural properties from the JSON package
        data = json.loads(ai_response_text)
        
        if data.get("status") != "no_updates":
            notif = str(data.get("notification", "TBA")).replace("*", "")
            dates = str(data.get("exam_dates", "TBA")).replace("*", "")
            news = str(data.get("latest_news", "No news alerts.")).replace("*", "")
            
            # Formulate the layout safely inside python 
            compiled_report += f"🔹 *{name}*\n"
            compiled_report += f"📅 Notification: {notif}\n"
            compiled_report += f"✍️ Exam Dates: {dates}\n"
            compiled_report += f"📰 Latest News: {news}\n"
            compiled_report += f"🔗 *Source:* {official_url}\n\n"
            updates_found = True
            print(f"✅ Structurally extracted {name}")
            
    except Exception as parse_err:
        print(f"⚠️ JSON mapping failed for {name}: {parse_err}")

# 4. Ship structural payload to Telegram
if updates_found:
    telegram_url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/sendMessage"
    payload = {
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": compiled_report,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    r = requests.post(telegram_url, data=payload)
    if r.status_code != 200:
        print(f"Telegram failed to send. Error: {r.text}")
    else:
        print("🚀 Formatted cards successfully dropped to Telegram!")
else:
    print("All quiet today! No structural shifts discovered.")