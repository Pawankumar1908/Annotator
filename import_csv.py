import pandas as pd
import sqlite3
from indic_transliteration.sanscript import transliterate, TELUGU, ITRANS

df = pd.read_csv("repository.csv")

conn = sqlite3.connect("proverbs.db")
cur = conn.cursor()

for _, row in df.iterrows():

    tel = str(row["proverb_telugu"]).strip()
    eng = str(row["proverb_english"]).strip()
    mean = str(row["meaning"]).strip()
    key = str(row["keywords"]).strip()

    roman = transliterate(tel, TELUGU, ITRANS).lower()

    cur.execute("""
    INSERT OR IGNORE INTO repository
    (proverb_telugu, proverb_english, meaning_english, keywords, transliteration)
    VALUES (?, ?, ?, ?, ?)
    """, (tel, eng, mean, key, roman))

conn.commit()
conn.close()

print("✅ Repository Imported Successfully")