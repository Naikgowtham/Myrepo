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
    
    encoded_query = urllib.parse.quote(f"{name} exam updates news")
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
        
    prompt = f"""
    You are an AI assistant tracking updates for the exam: '{name}'.
    Analyze these two data snapshots:
    
    SOURCE 1: Official Portal text ({official_url})
    ---
    {official_text}
    ---
    
    SOURCE 2: Recent news headlines RSS
    ---
    {external_news_text}
    ---
    
    Task:
    Provide a unified summary for '{name}'.
    - Extract any new active timelines (Application dates, Exam dates, Results, Admit cards).
    - Mention any crucial news or changes from trusted news outlets.
    - CRITICAL FORMATTING RULE: Write your output in absolute PLAIN TEXT. Do NOT use asterisks (*), underscores (_), brackets, or any markdown symbols whatsoever. Use simple hyphens (-) for bullet points.
    - Keep it under 400 characters.
    - If absolutely no new application dates, changes, or major news are visible, reply with exactly: 'No new updates.'
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
        sanitized_response = ai_response.replace("*", "").replace("_", "").replace("`", "")
        compiled_report += f"🔹 *{name}*\n{sanitized_response}\n\n"
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
        print("🚀 Report successfully dispatched to Telegram!")
else:
    print("All quiet today! No new exam updates discovered across portals or news feeds.")