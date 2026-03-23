def init_db(db_func):
    conn = db_func()
    cur = conn.cursor()

    # USERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        password TEXT,
        name TEXT,
        role TEXT DEFAULT 'annotator'
    );
    """)

    # ANNOTATORS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS annotators (
        name TEXT PRIMARY KEY,
        submitted INTEGER DEFAULT 0,
        approved INTEGER DEFAULT 0,
        last_active TIMESTAMP
    );
    """)

    # REPOSITORY
    cur.execute("""
    CREATE TABLE IF NOT EXISTS repository (
        id SERIAL PRIMARY KEY,
        proverb_telugu TEXT,
        proverb_english TEXT,
        meaning_english TEXT,
        keywords TEXT,
        transliteration TEXT
    );
    """)

    # NEW ANNOTATIONS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS new_annotations (
        id SERIAL PRIMARY KEY,
        proverb_telugu TEXT,
        proverb_english TEXT,
        meaning_english TEXT,
        keywords TEXT,
        annotator TEXT,
        timestamp TIMESTAMP DEFAULT NOW()
    );
    """)

    # HISTORY
    cur.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id SERIAL PRIMARY KEY,
        annotator TEXT,
        proverb_telugu TEXT,
        proverb_english TEXT,
        meaning_english TEXT,
        keywords TEXT,
        action TEXT,
        admin TEXT,
        timestamp TIMESTAMP DEFAULT NOW()
    );
    """)

    conn.commit()
    conn.close()