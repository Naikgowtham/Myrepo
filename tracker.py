import os
import requests
import urllib.parse
import pandas as pd
from google import genai  # Upgraded SDK import

# 1. Fetch your target list directly from your Google Sheet
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1_x_nW-3ppImt2CzdtPNh3KAnOjSCMuzXhbSUxZUYbqc/export?format=csv"

try:
    df = pd.read_csv(SHEET_CSV_URL)
except Exception as e:
    print(f"Error reading Google Sheet: {e}")
    exit(1)

# 2. Configure the modern GenAI Client
# It automatically picks up your GEMINI_API_KEY environment variable
client = genai.Client()

compiled_report = "📅 **Daily Exam Updates & News Report** 📅\n\n"
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
        
    # 3. Prompting Gemini
    prompt = f"""
    You are an AI assistant tracking updates for the exam: '{name}'.
    Analyze these two raw data snapshots:
    
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
    - CRITICAL: Keep your response incredibly concise (maximum 3-4 bullet points, under 400 characters total). Telegram messages have strict character limits.
    - If absolutely no new application dates, changes, or major news are visible in either source, reply with exactly: 'No new updates.'
    """
    
    try:
        # Using the upgraded SDK call format and a modern model
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        ai_response = response.text.strip()
        
        if "no new updates" not in ai_response.lower():
            compiled_report += f"🔹 **{name}**\n{ai_response}\n\n"
            updates_found = True
    except Exception as e:
        print(f"Error processing {name}: {e}")

# 4. Ship it to Telegram
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
    print("All quiet today! No new exam updates discovered across portals or news feeds.")