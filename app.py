from flask import Flask, request, jsonify, render_template, redirect, session
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from indic_transliteration.sanscript import transliterate, TELUGU, ITRANS
from database import init_db
import csv

app = Flask(__name__)

# ================= SECURITY =================
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret")

# ================= DB =================
def db():
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not set")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


# ================= AUTO IMPORT =================
def auto_import_csv():
    conn = db()
    cur = conn.cursor()

    try:
        # Check if data exists
        cur.execute("SELECT COUNT(*) FROM repository")
        count = list(cur.fetchone().values())[0]

        if count > 0:
            print("✅ Repository already has data, skipping import")
            return

        print("⚡ Importing CSV data...")

        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(BASE_DIR, "repository.csv")

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                cur.execute("""
                    INSERT INTO repository
                    (proverb_telugu, proverb_english, meaning_english, keywords, transliteration)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    row["proverb_telugu"],
                    row["proverb_english"],
                    row["meaning"],
                    row["keywords"],
                    transliterate(row["proverb_telugu"], TELUGU, ITRANS).lower()
                ))

        conn.commit()
        print("🔥 CSV Imported Successfully")

    except Exception as e:
        print("❌ CSV import error:", e)

    finally:
        conn.close()


# ================= INIT =================
init_db(db)
auto_import_csv()


# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        name = request.form.get("name", "").strip()

        conn = db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if user:
            if user["password"] == password:
                session["user"] = email
                session["name"] = user["name"]
                session["role"] = user["role"]
                conn.close()
                return redirect("/admin" if user["role"] == "admin" else "/annotate")
            else:
                conn.close()
                return render_template("login.html", error="Wrong password")

        else:
            if not name:
                conn.close()
                return render_template("login.html", error="Enter name for new user")

            cur.execute(
                "INSERT INTO users(email,password,name) VALUES (%s,%s,%s)",
                (email, password, name),
            )
            conn.commit()
            conn.close()

            session["user"] = email
            session["name"] = name
            session["role"] = "annotator"

            return redirect("/annotate")

    return render_template("login.html", error=None)


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ================= VERIFY =================
@app.route("/verify", methods=["POST"])
def verify():
    value = request.json["value"].strip()

    is_telugu = any('\u0C00' <= c <= '\u0C7F' for c in value)

    if is_telugu:
        telugu = value
        roman = transliterate(value, TELUGU, ITRANS).lower()
    else:
        roman = value.lower()
        telugu = transliterate(value, ITRANS, TELUGU)

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM repository WHERE transliteration=%s", (roman,))
    row = cur.fetchone()
    conn.close()

    if row:
        return jsonify({
            "status": "exists",
            "telugu": row["proverb_telugu"],
            "roman": row["proverb_english"],
            "meaning": row["meaning_english"],
            "keywords": row["keywords"]
        })

    return jsonify({
        "status": "new",
        "telugu": telugu,
        "roman": roman
    })


# ================= ANNOTATE =================
@app.route("/annotate", methods=["GET", "POST"])
def annotate():

    if "user" not in session:
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT submitted, approved FROM annotators WHERE name=%s",
        (session["user"],),
    )
    row = cur.fetchone()

    submitted = row["submitted"] if row else 0
    approved = row["approved"] if row else 0

    if request.method == "POST":

        tel = request.form["proverb_telugu"]
        eng = request.form["proverb_english"]
        mean = request.form["meaning_english"]
        key = request.form["keywords"]

        cur.execute("""
            INSERT INTO new_annotations
            (proverb_telugu, proverb_english, meaning_english, keywords, annotator)
            VALUES (%s, %s, %s, %s, %s)
        """, (tel, eng, mean, key, session["user"]))

        cur.execute("""
            INSERT INTO annotators(name, submitted, approved, last_active)
            VALUES (%s,1,0,NOW())
            ON CONFLICT (name)
            DO UPDATE SET
                submitted = annotators.submitted + 1,
                last_active = NOW()
        """, (session["user"],))

        conn.commit()
        conn.close()

        return redirect("/annotate")

    conn.close()

    return render_template(
        "annotate.html",
        name=session["name"],
        submitted=submitted,
        approved=approved,
    )


# ================= ADMIN =================
@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect("/")
    return render_template("admin_dashboard.html")


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
