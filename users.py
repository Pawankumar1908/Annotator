import sqlite3

DB = "proverbs.db"

def add_user(username, password, name, role):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Check if already exists
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    exists = cur.fetchone()

    if exists:
        print(f"⚠️ User '{username}' already exists")
        return

    cur.execute("""
    INSERT INTO users (username, password, name, role)
    VALUES (?, ?, ?, ?)
    """, (username, password, name, role))

    conn.commit()
    conn.close()

    print(f"✅ User '{username}' added successfully")


def verify_users():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("SELECT username, name, role FROM users")
    rows = cur.fetchall()

    print("\n📋 CURRENT USERS:")
    print("----------------------")

    for r in rows:
        print(f"Username: {r[0]} | Name: {r[1]} | Role: {r[2]}")

    conn.close()


if __name__ == "__main__":
    print("🚀 Creating default users...\n")

    add_user("admin", "admin", "Admin", "admin")
    add_user("pawan", "123", "Pawan", "annotator")

    verify_users()