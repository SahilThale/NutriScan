import hashlib
import os
import base64
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from config import get_db_connection

# -----------------------------
# Flask app setup
# -----------------------------
app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change this in production



app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)  # ensure folder exists
# Upload folder setup
# UPLOAD_FOLDER = os.path.join("static", "uploads")
# if not os.path.exists(UPLOAD_FOLDER):
#     os.makedirs(UPLOAD_FOLDER)

# app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# -----------------------------
# Helpers
# -----------------------------
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def call_gemini(prompt, image_path=None):
    """Send query (and optional image) to Gemini API"""
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "Your Gemini Api Key")
    MODEL_NAME = "models/gemini-1.5-flash"
    GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"

    headers = {"Content-Type": "application/json"}
    parts = [{"text": prompt}]

    if image_path:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",  # change if png
                "data": image_b64
            }
        })

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ]
    }

    response = requests.post(GEMINI_URL, headers=headers, json=payload)

    if response.status_code == 200:
        result = response.json()
        try:
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            return "⚠️ Gemini returned an unexpected response."
    else:
        return f"❌ Gemini API Error: {response.text}"

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and user["password"] == hashlib.sha256(password.encode()).hexdigest():
            session["user_id"] = user["id"]
            session["username"] = user["name"]
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid email or password", "danger")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = hashlib.sha256(request.form["password"].encode()).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", 
                           (name, email, password))
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        except:
            flash("Email already exists!", "danger")
        finally:
            conn.close()

    return render_template("register.html")

@app.route("/profile")
def profile():
    if not session.get("user_id"):
        flash("Please login to view your profile.", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()
    conn.close()

    return render_template("profile.html", user=user)

@app.route("/analyze", methods=["GET", "POST"])
def analyze():
    if not session.get("user_id"):
        flash("Please login to use Analyze.", "warning")
        return redirect(url_for("login"))

    analysis_result = None
    filename = None  

    if request.method == "POST":
        category = request.form.get("category")
        file = request.files.get("image")
        upload_path = None

        if file and allowed_file(file.filename):
            safe_filename = secure_filename(file.filename)
            filename = datetime.now().strftime("%Y%m%d%H%M%S_") + safe_filename
            upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(upload_path)

        # 🔹 Step 1: Identify product
        identify_prompt = f"Identify the product brand/name from this image. Category: {category}. Respond only with product name (e.g., 'Coca Cola')."
        product_name = call_gemini(identify_prompt, image_path=upload_path)

        # 🔹 Step 2: Health analysis
        health_prompt = f"The product is {product_name}. Is it healthy or not? Explain briefly in 3–4 sentences."
        result = call_gemini(health_prompt)

        # Save to DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO history (user_id, category, filename, result, timestamp) VALUES (%s, %s, %s, %s, %s)",
            (session["user_id"], category, filename, result, datetime.now())
        )
        conn.commit()
        conn.close()

        analysis_result = f"Product: {product_name}\n\n Health Analysis: {result}"

    return render_template(
        "analyze.html",
        username=session.get("username"),
        result=analysis_result,
        filename=filename
    )


@app.route("/history")
def history():
    if not session.get("user_id"):
        flash("Please login to view history.", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch from normal history table
    cursor.execute(
        "SELECT id, category, filename, result, timestamp FROM history WHERE user_id = %s ORDER BY timestamp DESC",
        (session["user_id"],)
    )
    user_history = cursor.fetchall()

    # Fetch from custom_requests table
    cursor.execute(
        "SELECT id, prompt, filename, result, timestamp FROM custom_requests WHERE user_id = %s ORDER BY timestamp DESC",
        (session["user_id"],)
    )
    custom_history = cursor.fetchall()

    conn.close()

    return render_template(
        "history.html",
        username=session.get("username"),
        history=user_history,
        custom_history=custom_history
    )


@app.route("/delete_history/<int:history_id>", methods=["POST"])
def delete_history(history_id):
    if not session.get("user_id"):
        flash("Please login to delete history.", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE id = %s AND user_id = %s", (history_id, session["user_id"]))
    conn.commit()
    conn.close()

    flash("History entry deleted successfully.", "success")
    return redirect(url_for("history"))


@app.route("/delete_custom_history/<int:custom_id>", methods=["POST"])
def delete_custom_history(custom_id):
    if not session.get("user_id"):
        flash("Please login to delete history.", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM custom_requests WHERE id = %s AND user_id = %s", (custom_id, session["user_id"]))
    conn.commit()
    conn.close()

    flash("Custom history entry deleted successfully.", "success")
    return redirect(url_for("history"))



@app.route("/custom_request", methods=["GET", "POST"])
def custom_request():
    if not session.get("user_id"):
        flash("Please login to use Custom Request.", "warning")
        return redirect(url_for("login"))

    result = None
    filename = None
    user_prompt = None

    if request.method == "POST":
        user_prompt = request.form.get("prompt")
        file = request.files.get("image")
        upload_path = None

        # Handle optional image
        if file and allowed_file(file.filename):
            safe_filename = secure_filename(file.filename)
            filename = datetime.now().strftime("%Y%m%d%H%M%S_") + safe_filename
            upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(upload_path)

        # Call Gemini with text + optional image
        result = call_gemini(user_prompt, image_path=upload_path)

        # Save to DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO custom_requests (user_id, prompt, filename, result, timestamp) VALUES (%s, %s, %s, %s, %s)",
            (session["user_id"], user_prompt, filename, result, datetime.now())
        )
        conn.commit()
        conn.close()

    return render_template(
        "custom_request.html",
        username=session.get("username"),
        result=result,
        filename=filename,
        prompt=user_prompt
    )





@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
