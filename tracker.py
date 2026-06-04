import os
import time
import requests
import urllib.parse
import pandas as pd
from google import genai

# 1. Fetch data from your Google Sheet
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1_x_nW-3ppImt2CzdtPNh3KAnOjSCMuzXhbSUxZUYbqc/export?format=csv"

try:
    df = pd.read_csv(SHEET_CSV_URL)
except Exception as e:
    print(f"Error reading Google Sheet: {e}")
    exit(1)

# 2. Configure GenAI Client
client = genai.Client()

# Active, live 2026 Model Fallback Sequence
MODELS_TO_TRY = ['gemini-3.5-flash', 'gemini-3.1-flash-lite', 'gemini-2.5-flash']

compiled_report = "📅 *Daily Exam Updates & News Report* 📅\n\n"
updates_found = False

for index, row in df.iterrows():
    name = str(row['Exam Name']).strip()
    official_url = str(row['Website URL']).strip()
    
    encoded_query = urllib.parse.quote(f"{name} exam updates news 2026")
    google_news_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    official_text = ""
    external_news_text = ""
    
    try:
        official_text = requests.get(official_url, timeout=10).text[:12000]
    except Exception:
        official_text = "⚠️ Could not reach official portal right now."

    try:
        external_news_text = requests.get(google_news_url, timeout=10).text[:12000]
    except Exception:
        external_news_text = "⚠️ Could not pull Google News stream."
        
    # Strictly commanding a clean layout with zero markdown symbols to prevent Telegram breakdown
    prompt = f"""
    You are an AI assistant tracking specific timelines for the exam: '{name}'.
    Analyze these two data snapshots for any active or tentative details concerning the 2026/2027 cycle:
    
    SOURCE 1: Official Portal text ({official_url})
    ---
    {official_text}
    ---
    
    SOURCE 2: Recent news headlines RSS
    ---
    {external_news_text}
    ---
    
    Task:
    Extract the timeline specifics and output EXACTLY the following template. Do NOT use any asterisks (*), underscores (_), or markdown text style formatting in your response. Fill out the text using raw characters only.
    
    📅 Notification: [List specific date, tentative month, or "Expected June 2026" etc. If completely unknown, write TBA]
    ✍️ Exam Dates: [List exact dates, prelims/mains months, or tentative schedule details. If completely unknown, write TBA]
    📰 Latest News: [Provide a brief 1-2 sentence raw text update of recent alerts, results, patterns, or notification releases]
    
    CRITICAL: If absolutely no reference to timelines or current status exists in the data, reply with exactly: 'No new updates.'
    """
    
    ai_response = None
    
    # Fallback Execution Loop
    for model_name in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            ai_response = response.text.strip()
            if ai_response:
                print(f"✅ Successfully extracted data for {name} using {model_name}")
                break  
        except Exception as e:
            print(f"⚠️ {model_name} failed or overloaded for {name}. Shifting to next fallback...")
            time.sleep(2)  
            
    if not ai_response:
        print(f"❌ All active AI models failed or were overloaded for {name}.")
        continue

    if "no new updates" not in ai_response.lower():
        # Strip out any lingering markdown symbols the AI might have accidentally added
        sanitized_response = ai_response.replace("*", "").replace("_", "").replace("`", "")
        
        # Assemble the formatted block cleanly inside the Python ecosystem
        compiled_report += f"🔹 *{name}*\n{sanitized_response}\n🔗 *Source:* {official_url}\n\n"
        updates_found = True

# 4. Ship clean report to Telegram
if updates_found:
    telegram_url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/sendMessage"
    payload = {
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": compiled_report,
        "parse_mode": "Markdown"  
    }
    r = requests.post(telegram_url, data=payload)
    if r.status_code != 200:
        print(f"Telegram failed to send. Error: {r.text}")
    else:
        print("🚀 Structured report successfully dispatched to Telegram!")
else:
    print("All quiet today! No new exam updates discovered across portals or news feeds.")