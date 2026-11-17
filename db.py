# DB(SQLite)の読み書き
# users: 利用者  rentals: 貸出の記録(returned_at が空なら貸出中)

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class RentalError(Exception):
    # 画面にそのまま出すエラー
    def __init__(self, title, message=""):
        super().__init__(title)
        self.title = title
        self.message = message


def normalize_card_id(card_id):
    # "01:2e:4c" も "012E4C" も同じカードにする
    return card_id.replace(":", "").replace(" ", "").upper()


def parse_time(text):
    return datetime.strptime(text, TIME_FORMAT)


def minutes_past(due_at, at_time):
    # 返却予定を何分過ぎたか(過ぎていなければ 0)
    seconds = (at_time - due_at).total_seconds()
    if seconds <= 0:
        return 0
    return int(seconds // 60)


class Database:
    def __init__(self, path):
        self.path = Path(path)

    def open(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row  # row["name"] のように列名で取れるようにする
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # よく使う形をまとめたもの。どれも最後に必ず close する
    # (close しないと Windows で DB ファイルが消せなくなる)

    def select_one(self, sql, params=()):
        conn = self.open()
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()

    def select_all(self, sql, params=()):
        conn = self.open()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def execute(self, sql, params=()):
        # 書き込み1回分。変わった行の数を返す
        conn = self.open()
        try:
            with conn:  # 成功したら commit、エラーなら rollback
                cursor = conn.execute(sql, params)
            return cursor.rowcount
        finally:
            conn.close()

    def create_tables(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY,
                employee_number TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL,
                card_id         TEXT NOT NULL UNIQUE
            )
        """)
        self.execute("""
            CREATE TABLE IF NOT EXISTS rentals (
                id          INTEGER PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users (id),
                rented_at   TEXT NOT NULL,
                due_at      TEXT NOT NULL,
                returned_at TEXT
            )
        """)

    # ---- 利用者 ----

    def add_user(self, employee_number, name, card_id):
        try:
            self.execute(
                "INSERT INTO users (employee_number, name, card_id) VALUES (?, ?, ?)",
                (employee_number, name, normalize_card_id(card_id)),
            )
        except sqlite3.IntegrityError:
            raise RentalError("登録できません", "社員番号かカードIDがすでに登録されています。")

    def list_users(self):
        return self.select_all("SELECT * FROM users ORDER BY employee_number")

    def find_user_by_card(self, card_id):
        return self.select_one("SELECT * FROM users WHERE card_id = ?", (normalize_card_id(card_id),))

    # ---- 貸出・返却 ----

    def current_rental(self):
        # 貸出中の記録(借りている人の名前つき)。なければ None
        return self.select_one("""
            SELECT rentals.*, users.name
            FROM rentals JOIN users ON users.id = rentals.user_id
            WHERE rentals.returned_at IS NULL
        """)

    def borrow(self, user, minutes, open_door, now=None):
        # 記録 → 扉を開ける → commit の順。
        # 記録に失敗したら扉は開かない。扉が開かなかったら記録は取り消し(rollback)。
        if now is None:
            now = datetime.now()
        due = now + timedelta(minutes=minutes)

        conn = self.open()
        try:
            with conn:
                rented = conn.execute("SELECT 1 FROM rentals WHERE returned_at IS NULL").fetchone()
                if rented:
                    raise RentalError("いまは借りられません", "ほかの人が借りています。")

                conn.execute(
                    "INSERT INTO rentals (user_id, rented_at, due_at) VALUES (?, ?, ?)",
                    (user["id"], now.strftime(TIME_FORMAT), due.strftime(TIME_FORMAT)),
                )
                open_door()
        finally:
            conn.close()

        return due

    def return_camera(self, user, open_door, now=None):
        # 借りた本人だけ返せる。返した記録(返却日時入り)を返す
        if now is None:
            now = datetime.now()
        returned_at = now.strftime(TIME_FORMAT)

        conn = self.open()
        try:
            with conn:
                rental = conn.execute(
                    "SELECT * FROM rentals WHERE user_id = ? AND returned_at IS NULL",
                    (user["id"],),
                ).fetchone()
                if rental is None:
                    raise RentalError("返却するカメラがありません", "借りた人の社員証をかざしてください。")

                conn.execute("UPDATE rentals SET returned_at = ? WHERE id = ?", (returned_at, rental["id"]))
                open_door()
        finally:
            conn.close()

        rental = dict(rental)
        rental["returned_at"] = returned_at
        return rental

    def list_rentals(self):
        # 新しい順
        return self.select_all("""
            SELECT rentals.*, users.employee_number, users.name
            FROM rentals JOIN users ON users.id = rentals.user_id
            ORDER BY rentals.id DESC
        """)
