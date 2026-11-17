# 追加機能: 管理画面(config.USE_ADMIN_SCREEN)
# ホームの「管理者」→ 管理者の社員証 → メニュー(利用者の登録 / 一覧 / 貸出の履歴)
# 管理者は admins テーブルに入れる。最初の1人は python register_user.py admin 社員番号
# 管理者がいなければ「管理者」ボタンは出ない

import logging

import customtkinter

import config
import excel_export
import overdue_record
from db import RentalError, normalize_card_id, parse_time
from gui_parts import (BLUE_TAG, GREEN_TAG, RED, SUB_TEXT_COLOR, TEXT_COLOR, WHITE, WHITE_BUTTON_BORDER_COLOR,
                       Screen, format_date_time, make_font, make_label, make_line, make_tag, make_white_button)

log = logging.getLogger(__name__)

ADMIN_STEPS = ["管理者の社員証", "管理メニュー"]
REGISTER_STEPS = ["新しい社員証", "社員番号・氏名", "完了"]


# ---- DB ----

def create_admin_table(database):
    database.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY REFERENCES users (id))")


def count_admins(database):
    return database.select_one("SELECT COUNT(*) FROM admins")[0]


def is_admin(database, user):
    return database.select_one("SELECT 1 FROM admins WHERE user_id = ?", (user["id"],)) is not None


def set_admin(database, user, admin):
    if admin:
        database.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user["id"],))
    else:
        database.execute("DELETE FROM admins WHERE user_id = ?", (user["id"],))


def find_user_by_employee_number(database, employee_number):
    return database.select_one("SELECT * FROM users WHERE employee_number = ?", (employee_number,))


def delete_user(database, user):
    # 貸出の記録がある人は、記録の名前が消えないよう行は残してカードだけ使えなくする
    if is_admin(database, user):
        raise RentalError("消せません",
                          f"管理者は消せません。先に python register_user.py unadmin {user['employee_number']} を実行してください。")

    conn = database.open()
    try:
        with conn:
            renting = conn.execute("SELECT 1 FROM rentals WHERE user_id = ? AND returned_at IS NULL",
                                   (user["id"],)).fetchone()
            if renting:
                raise RentalError("消せません", "この人はいまカメラを借りています。返却してから消してください。")

            count = conn.execute("SELECT COUNT(*) FROM rentals WHERE user_id = ?", (user["id"],)).fetchone()[0]
            if count == 0:
                conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
            else:
                conn.execute("UPDATE users SET card_id = ? WHERE id = ?", (f"DELETED-{user['id']}", user["id"]))
    finally:
        conn.close()


# ---- ホームから入る ----

def add_button_on_home(home):
    if count_admins(home.app.database) == 0:
        return
    home.show_footer()
    home.add_left_button("管理者", lambda: home.app.scan_card(ADMIN_STEPS, admin_card_read))


def admin_card_read(app, card_id):
    user = app.database.find_user_by_card(card_id)
    if user is None or not is_admin(app.database, user):
        log.info("管理者ではない社員証: %s", card_id)
        raise RentalError("管理者の社員証ではありません", "管理画面は管理者だけが使えます。")
    log.info("管理画面を開いた: %s", user["employee_number"])
    app.show(AdminMenuScreen)


def new_card_read(app, card_id):
    # 登録する社員証が読めたら呼ばれる
    if app.database.find_user_by_card(card_id) is not None:
        raise RentalError("登録済みの社員証です", "この社員証はもう登録されています。")
    app.show(RegisterScreen, card_id=normalize_card_id(card_id))


# ---- 画面 ----

class AdminMenuScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.show_steps(ADMIN_STEPS, 1)
        self.show_title("管理メニュー", "使い終わったら「終わる」を押してください。")
        self.add_left_button("終わる", app.go_home)

        buttons = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        buttons.pack(fill="both", expand=True)
        buttons.grid_columnconfigure((0, 1, 2), weight=1, uniform="a")
        buttons.grid_rowconfigure(0, weight=1)

        menu = [
            ("利用者の登録", lambda: app.scan_card(REGISTER_STEPS, new_card_read)),
            ("利用者の一覧", lambda: app.show(UserListScreen)),
            ("貸出の履歴", lambda: app.show(HistoryScreen)),
        ]
        for i, (text, command) in enumerate(menu):
            button = make_white_button(buttons, text, command, height=150)
            button.configure(font=make_font(26, True))
            button.grid(row=0, column=i, sticky="nsew", padx=8)


class RegisterScreen(Screen):
    def __init__(self, app, card_id):
        super().__init__(app)
        self.card_id = card_id
        self.show_steps(REGISTER_STEPS, 1)
        self.show_title("社員番号と氏名を入れてください", f"カードID  {card_id}")
        self.add_left_button("やめる", lambda: app.show(AdminMenuScreen))
        self.add_right_button("登録する", self.register)

        form = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        form.pack(fill="x")
        form.grid_columnconfigure(0, minsize=180)
        form.grid_columnconfigure(1, weight=1)

        make_label(form, "社員番号", color=SUB_TEXT_COLOR).grid(row=0, column=0, sticky="w", pady=10)
        self.number_entry = self.make_entry(form, "例: 10001")
        self.number_entry.grid(row=0, column=1, sticky="ew", pady=10)

        make_label(form, "氏名", color=SUB_TEXT_COLOR).grid(row=1, column=0, sticky="w", pady=10)
        self.name_entry = self.make_entry(form, "例: 山田 太郎")
        self.name_entry.grid(row=1, column=1, sticky="ew", pady=10)

        self.admin_checkbox = customtkinter.CTkCheckBox(form, text="管理者にする", font=make_font(19),
                                                        text_color=TEXT_COLOR, fg_color=RED, hover_color=RED,
                                                        checkbox_width=30, checkbox_height=30)
        self.admin_checkbox.grid(row=2, column=1, sticky="w", pady=10)

        self.error_label = make_label(self.content_area, "", color=RED)
        self.error_label.pack(anchor="w", pady=(16, 0))
        self.number_entry.focus_set()

    def make_entry(self, parent, example):
        entry = customtkinter.CTkEntry(parent, height=56, font=make_font(22), placeholder_text=example,
                                       fg_color=WHITE, text_color=TEXT_COLOR, border_width=2,
                                       border_color=WHITE_BUTTON_BORDER_COLOR, corner_radius=8)
        entry.bind("<KeyPress>", self.app.record_touch, add="+")  # 入力中は「操作中」にする
        return entry

    def register(self):
        number = self.number_entry.get().strip()
        name = self.name_entry.get().strip()
        if number == "" or name == "":
            self.error_label.configure(text="社員番号と氏名の両方を入れてください。")
            return

        try:
            self.app.database.add_user(number, name, self.card_id)
        except RentalError as e:
            self.error_label.configure(text=e.message)
            return
        log.info("利用者を登録: %s", number)

        if self.admin_checkbox.get() == 1:
            set_admin(self.app.database, self.app.database.find_user_by_card(self.card_id), True)
            log.info("管理者にした: %s", number)

        self.app.show(RegisterDoneScreen, name=name)


class RegisterDoneScreen(Screen):
    def __init__(self, app, name):
        super().__init__(app)
        self.show_steps(REGISTER_STEPS, 2)
        make_tag(self.top_area, "登録しました", GREEN_TAG).pack(anchor="w", pady=(0, 16))
        make_label(self.top_area, f"{name} さんを登録しました。\nこの社員証で借りられます。", 34, True).pack(anchor="w")
        self.add_left_button("メニューに戻る", lambda: app.show(AdminMenuScreen))
        self.add_right_button("続けて登録する", lambda: app.scan_card(REGISTER_STEPS, new_card_read))


def make_table(parent, headers, widths):
    # 見出しつきの表(スクロールできる)。widths が 0 の列は残りの幅いっぱい
    table = customtkinter.CTkScrollableFrame(parent, fg_color="transparent")
    table.pack(fill="both", expand=True)
    for i, width in enumerate(widths):
        if width == 0:
            table.grid_columnconfigure(i, weight=1)
        else:
            table.grid_columnconfigure(i, minsize=width)

    for i, header in enumerate(headers):
        make_label(table, header, 17, color=SUB_TEXT_COLOR).grid(row=0, column=i, sticky="w", padx=8, pady=(0, 8))
    make_line(table).grid(row=1, column=0, columnspan=len(headers), sticky="ew")
    return table


def add_table_row(table, row_number, values):
    # row_number は 0 から。値が文字ならラベルにして、部品ならそのまま置く
    grid_row = row_number * 2 + 2   # 見出しと線の下から、行と線を交互に置く
    for i, value in enumerate(values):
        if isinstance(value, str):
            value = make_label(table, value)
        value.grid(row=grid_row, column=i, sticky="w", padx=8, pady=8)
    make_line(table).grid(row=grid_row + 1, column=0, columnspan=len(values), sticky="ew")


class UserListScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.show_steps(ADMIN_STEPS, 1)

        users = []
        for user in app.database.list_users():
            if not user["card_id"].startswith("DELETED-"):
                users.append(user)

        self.show_title("利用者の一覧", f"{len(users)} 人")
        self.add_left_button("メニューに戻る", lambda: app.show(AdminMenuScreen))

        table = make_table(self.content_area, ["社員番号", "氏名", "カードID", ""], [160, 0, 220, 140])
        for i, user in enumerate(users):
            if is_admin(app.database, user):
                last = make_tag(table, "管理者", BLUE_TAG)   # 管理者は消せない
            else:
                last = make_white_button(table, "消す", None, width=120, height=44)
                last.configure(font=make_font(17), command=lambda b=last, u=user: self.press_delete(b, u))
            add_table_row(table, i, [user["employee_number"], user["name"], user["card_id"], last])

        if not users:
            make_label(table, "まだ誰も登録されていません。", color=SUB_TEXT_COLOR).grid(row=2, column=0, columnspan=4,
                                                                                    sticky="w", padx=8, pady=20)

    def press_delete(self, button, user):
        # 1回目は「本当に消す」に変えるだけ。2回目で消す
        if button.cget("text") == "消す":
            button.configure(text="本当に消す", text_color=RED, border_color=RED)
            return

        try:
            delete_user(self.app.database, user)
        except Exception as e:
            self.app.show_error(e, retry=lambda: self.app.show(UserListScreen), retry_text="一覧に戻る")
            return
        log.info("利用者を消した: %s", user["employee_number"])
        self.app.show(UserListScreen)


class HistoryScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.show_steps(ADMIN_STEPS, 1)
        self.show_title("貸出の履歴", "新しいものから 30 件まで")
        self.add_left_button("メニューに戻る", lambda: app.show(AdminMenuScreen))

        # openpyxl があるときだけ Excel 保存のボタンを出す
        try:
            import openpyxl  # noqa: F401
            self.save_button = self.add_right_button("Excel に保存", self.save_excel)
        except ImportError:
            pass

        headers = ["貸出日時", "氏名", "返却予定", "状態"]
        widths = [220, 0, 220, 160]
        if config.USE_OVERDUE_RECORD:
            headers.append("延滞")
            widths.append(100)
        table = make_table(self.content_area, headers, widths)

        rentals = app.database.list_rentals()[:30]
        for i, rental in enumerate(rentals):
            if rental["returned_at"] is None:
                state = make_tag(table, "貸出中", BLUE_TAG)
            else:
                state = make_tag(table, "返却済み", GREEN_TAG)

            row = [format_date_time(parse_time(rental["rented_at"])), rental["name"],
                   format_date_time(parse_time(rental["due_at"])), state]
            if config.USE_OVERDUE_RECORD:
                late = overdue_record.late_minutes_of(rental)
                if late:
                    row.append(f"{late}分")
                else:
                    row.append("")
            add_table_row(table, i, row)

        if not rentals:
            make_label(table, "まだ記録はありません。", color=SUB_TEXT_COLOR).grid(row=2, column=0, columnspan=len(headers),
                                                                              sticky="w", padx=8, pady=20)

    def save_excel(self):
        try:
            path, count = excel_export.export_to_excel(self.app.database, config.EXPORT_DIR)
        except Exception as e:
            self.app.show_error(e)
            return
        log.info("Excel に保存: %s", path)
        self.save_button.configure(text="保存しました")
        make_label(self.top_area, f"{count} 件を保存しました: {path.name}").pack(anchor="w", pady=(6, 0))
