import os
import sqlite3
from flask import Flask, render_template_string, request, session, redirect, url_for
import google.generativeai as genai
import uuid

app = Flask(__name__)
app.secret_key = "zaydi_secure_secret_key_change_this"

# مفتاح الـ API المعتمد
GEMINI_API_KEY = "AQ.Ab8RN6LJf4vFI3bexQwBH1NPUqGcEpmN18tEW6s98d6Wm5uZGQ"
genai.configure(api_key=GEMINI_API_KEY)

# إعداد قاعدة البيانات المحلية SQLite لتخزين المحادثات
def init_db():
    conn = sqlite3.connect("chat_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_session TEXT,
            sender TEXT,
            text TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# نظام قراءة وفهرسة الكتب مرة واحدة في ذاكرة الخادم لسرعة فائقة
GLOBAL_BOOKS_CACHE = []

def load_and_index_books():
    global GLOBAL_BOOKS_CACHE
    if GLOBAL_BOOKS_CACHE:
        return # تم جدولتها وفهرستها مسبقاً
        
    books_folder = "books"
    if not os.path.exists(books_folder):
        os.makedirs(books_folder)
        return
    
    files = os.listdir(books_folder)
    for filename in files:
        if filename.endswith(".txt"):
            file_path = os.path.join(books_folder, filename)
            txt_content = ""
            for enc in ['utf-8', 'utf-8-sig', 'cp1256', 'latin-1']:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        txt_content = f.read()
                    break
                except Exception:
                    continue
            
            if txt_content:
                # تقسيم الكتاب إلى فقرات وتخزينها في الذاكرة
                paragraphs = txt_content.split('\n\n')
                for para in paragraphs:
                    if para.strip():
                        GLOBAL_BOOKS_CACHE.append({
                            "filename": filename,
                            "content": para.strip()
                        })

# تشغيل الفهرسة فور بدء السيرفر لتكون جاهزة وفورية
load_and_index_books()

def lightning_fast_search(query):
    # التأكد من تحميل الكتب في الذاكرة
    if not GLOBAL_BOOKS_CACHE:
        load_and_index_books()
        if not GLOBAL_BOOKS_CACHE:
            return "المكتبة فارغة."
            
    keywords = [kw.strip() for kw in query.split() if len(kw.strip()) > 2]
    matched_snippets = []
    
    for item in GLOBAL_BOOKS_CACHE:
        para = item["content"]
        filename = item["filename"]
        
        if keywords:
            score = sum(1 for kw in keywords if kw in para)
            if score > 0:
                matched_snippets.append((score, filename, para))
        else:
            matched_snippets.append((1, filename, para))
            
    # ترتيب النتائج بحسب الأكثر صلة
    matched_snippets.sort(key=lambda x: x[0], reverse=True)
    
    final_context = ""
    for score, filename, para in matched_snippets[:4]: # نأخذ أضل 4 فقرات مطابقة
        final_context += f"\n\n--- من كتاب: {filename} ---\n{para}"
        
    if not final_context.strip():
        final_context = "هذه المسألة غير مذكورة في النصوص المرفقة."
        
    return final_context

html_template = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>مساعد الفقه الزيدي</title>
    <style>
        :root {
            --bg-color: #343541;
            --chat-bg: #444654;
            --text-color: #ececf1;
            --border-color: #565869;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        .header {
            background-color: #202123;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            font-size: 16px;
            font-weight: 600;
        }
        .reset-btn {
            background: transparent;
            color: #ececf1;
            border: 1px solid var(--border-color);
            padding: 6px 12px;
            font-size: 13px;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .reset-btn:hover { background: #2a2b32; }
        .chat-container {
            flex: 1;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding-bottom: 120px;
        }
        .message-row {
            width: 100%;
            display: flex;
            justify-content: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding: 24px 0;
        }
        .message-row.bot { background-color: rgba(68, 70, 84, 0.5); }
        .message-content {
            width: 100%;
            max-width: 768px;
            display: flex;
            gap: 20px;
            padding: 0 20px;
            box-sizing: border-box;
            line-height: 1.7;
            font-size: 15px;
            white-space: pre-wrap;
        }
        .avatar {
            width: 32px;
            height: 32px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 13px;
            flex-shrink: 0;
        }
        .user-avatar { background-color: #5436da; color: white; }
        .bot-avatar { background-color: #10a37f; color: white; }
        .text { flex: 1; overflow-x: auto; }
        .input-area {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background: linear-gradient(180deg, rgba(53,53,65,0) 0%, var(--bg-color) 50%);
            padding: 20px 0;
            display: flex;
            justify-content: center;
            box-sizing: border-box;
        }
        .input-form {
            width: 100%;
            max-width: 768px;
            display: flex;
            background: var(--chat-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 10px 15px;
            box-shadow: 0 0 15px rgba(0,0,0,0.1);
            align-items: flex-end;
            box-sizing: border-box;
            margin: 0 20px;
        }
        textarea {
            flex: 1;
            background: transparent;
            border: none;
            color: #ececf1;
            font-size: 15px;
            resize: none;
            outline: none;
            max-height: 200px;
            font-family: inherit;
            line-height: 1.5;
            padding-top: 4px;
        }
        textarea::placeholder { color: #8e8ea0; }
        .send-btn {
            background: #10a37f;
            color: white;
            border: none;
            width: 32px;
            height: 32px;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
            flex-shrink: 0;
            margin-right: 10px;
        }
        .send-btn:hover { background: #0d8a6c; }
        .welcome-screen { text-align: center; margin-top: 10vh; color: #8e8ea0; }
    </style>
</head>
<body>

    <div class="header">
        <span>مساعد الفقه الزيدي (الفهرسة السريعة)</span>
        <form method="POST" action="/reset" style="margin:0;">
            <button type="submit" class="reset-btn">محادثة جديدة +</button>
        </form>
    </div>

    <div class="chat-container">
        {% if chat_history %}
            {% for sender, text in chat_history %}
                {% if sender == 'user' %}
                    <div class="message-row">
                        <div class="message-content">
                            <div class="avatar user-avatar">أنت</div>
                            <div class="text">{{ text }}</div>
                        </div>
                    </div>
                {% else %}
                    <div class="message-row bot">
                        <div class="message-content">
                            <div class="avatar bot-avatar">م</div>
                            <div class="text">{{ text }}</div>
                        </div>
                    </div>
                {% endif %}
            {% endfor %}
        {% else %}
            <div class="welcome-screen">
                <h2>مرحباً بك في مساعد الفقه الزيدي</h2>
                <p>النظام جاهز ومفهرس بالكامل للرد الفوري على أسئلتك الفقهية.</p>
            </div>
        {% endif %}
    </div>

    <div class="input-area">
        <form method="POST" class="input-form">
            <textarea name="query" placeholder="أرسل سؤالاً فقهياً..." rows="1" required oninput="this.style.height = ''; this.style.height = this.scrollHeight + 'px'"></textarea>
            <button type="submit" class="send-btn" title="إرسال">
                <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" height="16" width="16" xmlns="http://www.w3.org/2000/svg"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
        </form>
    </div>

</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if "user_uuid" not in session:
        session["user_uuid"] = str(uuid.uuid4())
    
    user_session = session["user_uuid"]

    conn = sqlite3.connect("chat_database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        query = request.form.get("query", "")
        if query:
            # البحث الفائق السرعة من الذاكرة مباشرة بدون فتح الملفات
            library_content = lightning_fast_search(query)
            
            system_instruction = f"""
أنت عالم وباحث فقهي خبير، استقِ إجابتك بدقة من النصوص المستخرجة من الكتب التالية حصراً:
{library_content}

قواعد الإجابة الصارمة:
1. اعتمد على النصوص الواردة أعلاه فقط.
2. يجب عليك التوثيق وذكر اسم الكتاب صراحة في إجابتك.
3. إن لم تكن المسألة مذكورة في النصوص، قل: "هذه المسألة غير مذكورة في النصوص المرفقة."
"""

            model = genai.GenerativeModel(
                model_name="gemini-3.6-flash",
                system_instruction=system_instruction
            )
            
            cursor.execute("SELECT sender, text FROM messages WHERE user_session = ?", (user_session,))
            db_history = cursor.fetchall()

            formatted_history = []
            for sender, text in db_history:
                role = "user" if sender == "user" else "model"
                formatted_history.append({"role": role, "parts": [text]})

            try:
                chat = model.start_chat(history=formatted_history)
                response = chat.send_message(query)
                answer = response.text
            except Exception as e:
                answer = "عذراً، حدث ضغط مؤقت في الخدمة، يرجى إعادة المحاولة."

            cursor.execute("INSERT INTO messages (user_session, sender, text) VALUES (?, ?, ?)", (user_session, "user", query))
            cursor.execute("INSERT INTO messages (user_session, sender, text) VALUES (?, ?, ?)", (user_session, "model", answer))
            conn.commit()

    cursor.execute("SELECT sender, text FROM messages WHERE user_session = ?", (user_session,))
    chat_history = cursor.fetchall()
    conn.close()

    return render_template_string(html_template, chat_history=chat_history)

@app.route("/reset", methods=["POST"])
def reset():
    if "user_uuid" in session:
        user_session = session["user_uuid"]
        conn = sqlite3.connect("chat_database.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE user_session = ?", (user_session,))
        conn.commit()
        conn.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)