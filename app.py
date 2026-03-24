from flask import Flask, request, jsonify, render_template, redirect, session
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from indic_transliteration.sanscript import transliterate, TELUGU, ITRANS
from database import init_db
import csv

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret")

# ================= DB =================
def db():
    DATABASE_URL = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


# ================= AUTO IMPORT =================
def auto_import_csv():
    conn = db()
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM repository")
        count = list(cur.fetchone().values())[0]

        if count > 0:
            return

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

    except Exception as e:
        print("CSV import error:", e)

    finally:
        conn.close()

def create_admin():
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE email=%s", ("admin@gmail.com",))
    user = cur.fetchone()

    if not user:
        cur.execute("""
            INSERT INTO users(email, password, name, role)
            VALUES (%s, %s, %s, %s)
        """, ("admin@gmail.com", "admin123", "Admin", "admin"))

        conn.commit()
        print("🔥 Admin created")

    conn.close()

# ================= INIT =================
init_db(db)
auto_import_csv()
create_admin()


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

    return jsonify({"status": "new", "telugu": telugu, "roman": roman})


# ================= ANNOTATE =================
@app.route("/annotate", methods=["GET", "POST"])
def annotate():

    if "user" not in session:
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT submitted, approved FROM annotators WHERE name=%s",
                (session["user"],))
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

    return render_template("annotate.html",
                           name=session["name"],
                           submitted=submitted,
                           approved=approved)


# ================= ADMIN DASHBOARD =================
@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect("/")
    return render_template("admin_dashboard.html")


# ================= ADMIN NEW =================
@app.route("/admin/new")
def admin_new():
    if session.get("role") != "admin":
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM new_annotations ORDER BY timestamp DESC
    """)
    data = cur.fetchall()

    conn.close()
    return render_template("admin_new.html", data=data)


# ================= APPROVE =================
@app.route("/approve/<int:id>")
def approve(id):

    if session.get("role") != "admin":
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM new_annotations WHERE id=%s", (id,))
    row = cur.fetchone()

    if not row:
        return redirect("/admin/new")

    telugu = row["proverb_telugu"]
    english = row["proverb_english"]
    meaning = row["meaning_english"]
    keywords = row["keywords"]
    annotator = row["annotator"]

    roman = transliterate(telugu, TELUGU, ITRANS).lower()

    cur.execute("""
        INSERT INTO repository
        (proverb_telugu, proverb_english, meaning_english, keywords, transliteration)
        VALUES (%s,%s,%s,%s,%s)
    """, (telugu, english, meaning, keywords, roman))

    cur.execute("""
        UPDATE annotators SET approved = approved + 1 WHERE name=%s
    """, (annotator,))

    cur.execute("DELETE FROM new_annotations WHERE id=%s", (id,))

    conn.commit()
    conn.close()

    return redirect("/admin/new")


# ================= REJECT =================
@app.route("/reject/<int:id>")
def reject(id):
    conn = db()
    cur = conn.cursor()

    cur.execute("DELETE FROM new_annotations WHERE id=%s", (id,))
    conn.commit()
    conn.close()

    return redirect("/admin/new")


# ================= ADMIN REPOSITORY =================
@app.route("/admin/repository")
def admin_repo():
    if session.get("role") != "admin":
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM repository")
    data = cur.fetchall()

    conn.close()
    return render_template("admin_repository.html", data=data)


# ================= ADMIN ANNOTATORS =================
@app.route("/admin/annotators")
def admin_annotators():
    if session.get("role") != "admin":
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM annotators ORDER BY approved DESC")
    data = cur.fetchall()

    conn.close()
    return render_template("admin_annotators.html", data=data)


# ================= ADMIN HISTORY =================
@app.route("/admin/history")
def admin_history():
    if session.get("role") != "admin":
        return redirect("/")

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM history ORDER BY timestamp DESC")
    data = cur.fetchall()

    conn.close()
    return render_template("admin_history.html", data=data)


# ================= SWITCH ROLE =================
@app.route("/switch-to-annotator", methods=["POST"])
def switch_to_annotator():
    session["role"] = "annotator"
    return redirect("/annotate")


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
