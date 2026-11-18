# 管理画面
# ホームの「管理者」→ 管理者の社員証 → メニュー(利用者の登録 / 記録を Excel に保存)
# 記録を見られるのは管理者だけ。管理者は admins テーブルに入れる。
# 管理者がまだ1人もいないときは、「管理者」から最初の管理者を登録する(初期設定)

import logging

import customtkinter

import config
import export
from db import RentalError, normalize_card_id
from gui_parts import (ERROR_TEXT_COLOR, GREEN_TAG, SUB_TEXT_COLOR, TEXT_COLOR, WHITE, BORDER_COLOR, Screen,
                       make_font, make_label, make_sub_button, make_tag)

log = logging.getLogger(__name__)

ADMIN_STEPS = ["管理者の社員証", "管理メニュー"]
REGISTER_STEPS = ["新しい社員証", "社員番号・氏名", "完了"]
FIRST_ADMIN_STEPS = ["管理者の社員証", "社員番号・氏名", "完了"]


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


# ---- ホームから入る ----

def add_button_on_home(home):
    home.add_left_button("管理者", lambda: start_admin(home.app))


def start_admin(app):
    if count_admins(app.database) == 0:
        app.scan_card(FIRST_ADMIN_STEPS, first_admin_card_read)   # 初期設定
    else:
        app.scan_card(ADMIN_STEPS, admin_card_read)


def admin_card_read(app, card_id):
    user = app.database.find_user_by_card(card_id)
    if user is None or not is_admin(app.database, user):
        log.info("管理者ではない社員証: %s", card_id)
        raise RentalError("管理者の社員証ではありません", "管理画面は管理者だけが使えます。")
    log.info("管理画面を開いた: %s", user["employee_number"])
    app.show(AdminMenuScreen)


def first_admin_card_read(app, card_id):
    # 最初の管理者の社員証が読めたら呼ばれる
    if count_admins(app.database) > 0:
        raise RentalError("管理者はもう登録されています", "管理者の社員証で入ってください。")

    user = app.database.find_user_by_card(card_id)
    if user is not None:
        # もう利用者として登録されている人なら、そのまま管理者にする
        set_admin(app.database, user, True)
        log.info("最初の管理者を登録: %s", user["employee_number"])
        app.show(AdminMenuScreen)
    else:
        app.show(RegisterScreen, card_id=normalize_card_id(card_id), first_admin=True)


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
        buttons.grid_columnconfigure((0, 1), weight=1, uniform="a")
        buttons.grid_rowconfigure(0, weight=1)

        register_button = make_sub_button(buttons, "利用者の登録",
                                          lambda: app.scan_card(REGISTER_STEPS, new_card_read))
        register_button.configure(font=make_font(22, True))
        register_button.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        save_button = make_sub_button(buttons, "記録を Excel に保存", self.save_excel)
        save_button.configure(font=make_font(22, True))
        save_button.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self.result_label = make_label(self.content_area, "", color=SUB_TEXT_COLOR)
        self.result_label.pack(anchor="w", pady=(10, 0))

    def save_excel(self):
        try:
            path = export.export_to_excel(self.app.database, config.EXPORT_DIR)
        except Exception as e:
            self.app.show_error(e)
            return
        log.info("記録を Excel に保存: %s", path)
        self.result_label.configure(text=f"保存しました: exports/{path.name}")


class RegisterScreen(Screen):
    # first_admin=True: 初期設定(最初の管理者を登録する)
    # 社員番号と氏名は USB キーボードで入れる
    def __init__(self, app, card_id, first_admin=False):
        super().__init__(app)
        self.card_id = card_id
        self.first_admin = first_admin

        if first_admin:
            self.show_steps(FIRST_ADMIN_STEPS, 1)
            self.show_title("最初の管理者を登録します", f"社員番号と氏名を入れてください。(カードID {card_id})")
            self.add_left_button("戻る", app.go_home)
        else:
            self.show_steps(REGISTER_STEPS, 1)
            self.show_title("社員番号と氏名を入れてください", f"カードID {card_id}")
            self.add_left_button("戻る", lambda: app.show(AdminMenuScreen))
        self.add_right_button("登録する", self.register)

        form = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        form.pack(fill="x")
        form.grid_columnconfigure(0, minsize=120)
        form.grid_columnconfigure(1, weight=1)

        make_label(form, "社員番号", color=SUB_TEXT_COLOR).grid(row=0, column=0, sticky="w", pady=6)
        self.number_entry = self.make_entry(form, "例: 10001")
        self.number_entry.grid(row=0, column=1, sticky="ew", pady=6)

        make_label(form, "氏名", color=SUB_TEXT_COLOR).grid(row=1, column=0, sticky="w", pady=6)
        self.name_entry = self.make_entry(form, "例: 山田 太郎")
        self.name_entry.grid(row=1, column=1, sticky="ew", pady=6)

        self.error_label = make_label(self.content_area, "", bold=True, color=ERROR_TEXT_COLOR)
        self.error_label.pack(anchor="w", pady=(8, 0))
        self.number_entry.focus_set()

    def make_entry(self, parent, example):
        entry = customtkinter.CTkEntry(parent, height=52, font=make_font(20), placeholder_text=example,
                                       fg_color=WHITE, text_color=TEXT_COLOR, border_width=2,
                                       border_color=BORDER_COLOR, corner_radius=8)
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

        if self.first_admin:
            set_admin(self.app.database, self.app.database.find_user_by_card(self.card_id), True)
            log.info("最初の管理者を登録: %s", number)
            self.app.show(AdminMenuScreen)
        else:
            self.app.show(RegisterDoneScreen, name=name)


class RegisterDoneScreen(Screen):
    def __init__(self, app, name):
        super().__init__(app)
        self.show_steps(REGISTER_STEPS, 2)
        make_tag(self.top_area, "  登録しました  ", GREEN_TAG).pack(anchor="w", pady=(0, 10))
        make_label(self.top_area, f"{name} さんを登録しました。", 26, True).pack(anchor="w")
        make_label(self.top_area, "この社員証でカメラを借りられます。", 20).pack(anchor="w", pady=(6, 0))
        self.add_left_button("メニュー", lambda: app.show(AdminMenuScreen))
        self.add_right_button("続けて登録", lambda: app.scan_card(REGISTER_STEPS, new_card_read))
