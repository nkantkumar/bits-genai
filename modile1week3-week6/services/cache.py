import sqlite3
import json
import hashlib
from datetime import datetime


class SQLiteCache:

    def __init__(self, db_path="cache.db"):

        self.db_path = db_path

        self._create_table()


    # ========================================================
    # Create cache table
    # ========================================================

    def _create_table(self):

        conn = sqlite3.connect(self.db_path)

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()


    # ========================================================
    # Generate cache key
    # ========================================================

    def generate_key(
        self,
        task: str,
        model: str,
        prompt: str
    ):

        raw_key = (
            f"{task}|"
            f"{model}|"
            f"{prompt}"
        )

        return hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()


    # ========================================================
    # GET
    # ========================================================

    def get(self, cache_key: str):

        conn = sqlite3.connect(self.db_path)

        cursor = conn.cursor()

        cursor.execute("""
            SELECT response
            FROM llm_cache
            WHERE cache_key = ?
        """, (cache_key,))

        row = cursor.fetchone()

        conn.close()

        if row:

            return json.loads(row[0])

        return None


    # ========================================================
    # SET
    # ========================================================

    def set(
        self,
        cache_key: str,
        task: str,
        model: str,
        prompt: str,
        response: dict
    ):

        conn = sqlite3.connect(self.db_path)

        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO llm_cache
            (
                cache_key,
                task,
                model,
                prompt,
                response,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            cache_key,
            task,
            model,
            prompt,
            json.dumps(response),
            datetime.utcnow().isoformat()
        ))

        conn.commit()
        conn.close()