# 顧客MTG用の画面デモ(DB や機器は使わない。社員証はボタンで代わりにする)
#   python key_demo.py

import time
from datetime import datetime, timedelta

import customtkinter

from gui_parts import (BLUE_TAG, ERROR_TEXT_COLOR, GREEN_TAG, PINK_TAG, RED, SUB_TEXT_COLOR, TEXT_COLOR, WHITE,
                       YELLOW_TAG, Screen, disable_button, enable_red_button, make_font, make_label, make_line,
                       make_red_button, make_tag, make_white_button, show_as_selected)

USER_NAME = "森 航太郎"
RENTAL_MINUTES = [15, 30, 60, 120, 240, 480]
BORROW_STEPS = ["社員証", "貸出時間", "確認", "取り出し"]
RETURN_STEPS = ["社員証", "確認", "返却"]
IDLE_SECONDS = 60


def format_minutes(minutes):
    # 例: 15 → 15分、120 → 2時間
    if minutes < 60:
        return f"{minutes}分"
    return f"{minutes // 60}時間"


def format_date_time(date_time):
    # 例: 11月17日 15:30
    return f"{date_time.month}月{date_time.day}日 {date_time:%H:%M}"


def show_table(parent, rows):
    # 「項目名  値」を縦に並べる
    table = customtkinter.CTkFrame(parent, fg_color="transparent")
    table.pack(fill="x", pady=(16, 0))
    table.grid_columnconfigure(0, minsize=180)
    table.grid_columnconfigure(1, weight=1)

    for row_number, (item_name, item_value) in enumerate(rows):
        grid_row = row_number * 2  # 行と行の間に線を入れるので、2つずつ進める

        name_label = make_label(table, item_name, color=SUB_TEXT_COLOR)
        name_label.grid(row=grid_row, column=0, sticky="w", pady=12)

        value_label = make_label(table, item_value, 22, True)
        value_label.grid(row=grid_row, column=1, sticky="w")

        separator = make_line(table)
        separator.grid(row=grid_row + 1, column=0, columnspan=2, sticky="ew")


class DemoApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        customtkinter.set_appearance_mode("light")
        self.title("セキュアカメラ貸出(画面デモ)")
        self.geometry("1000x680")
        self.configure(fg_color=WHITE)

        # 貸出中なら {"rented_at": 貸出日時, "due_at": 返却予定}、貸出中でなければ None
        self.rental = None

        self.last_touch_time = time.monotonic()
        self.bind_all("<ButtonPress>", self.record_touch, add="+")

        header = customtkinter.CTkFrame(self, height=52, fg_color=RED, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        system_name = make_label(header, "セキュアカメラ貸出", 18, True, WHITE)
        system_name.pack(side="left", padx=40)
        demo_name = make_label(header, "画面デモ", 16, True, WHITE)
        demo_name.pack(side="right", padx=40)

        self.body = customtkinter.CTkFrame(self, fg_color=WHITE, corner_radius=0)
        self.body.pack(fill="both", expand=True)

        self.screen = None
        self.go_home()
        self.check_idle()

    def record_touch(self, event):
        self.last_touch_time = time.monotonic()

    def check_idle(self):
        # 1分操作がなければホームに戻る
        idle_seconds = time.monotonic() - self.last_touch_time
        if idle_seconds > IDLE_SECONDS:
            self.last_touch_time = time.monotonic()
            self.go_home()
        self.after(1000, self.check_idle)

    def show(self, screen_class, **screen_arguments):
        if self.screen is not None:
            self.screen.leave()
            self.screen.destroy()
        self.screen = screen_class(self, **screen_arguments)
        self.screen.pack(fill="both", expand=True)

    def go_home(self):
        self.show(HomeScreen)


class HomeScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.footer.pack_forget()

        camera_label = make_label(self.top_area, "セキュアカメラ", 22, True)
        camera_label.pack(anchor="w")

        status_row = customtkinter.CTkFrame(self.top_area, fg_color="transparent")
        status_row.pack(anchor="w", pady=(14, 0))

        if app.rental is None:
            status_tag = make_tag(status_row, "貸出可能", GREEN_TAG)
            status_text = make_label(status_row, "  いつでも借りられます", 26, True)
        else:
            status_tag = make_tag(status_row, "貸出中", BLUE_TAG)
            status_text = make_label(status_row, f"  {USER_NAME} さんが借りています", 26, True)
        status_tag.pack(side="left")
        status_text.pack(side="left")

        if app.rental is not None:
            due_label = make_label(self.top_area, f"返却予定  {format_date_time(app.rental['due_at'])}",
                                   color=SUB_TEXT_COLOR)
            due_label.pack(anchor="w", pady=(10, 0))

        separator = make_line(self.content_area)
        separator.pack(fill="x", pady=(0, 28))

        button_area = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        button_area.pack(fill="both", expand=True)
        button_area.grid_columnconfigure((0, 1), weight=1, uniform="main_buttons")
        button_area.grid_rowconfigure(0, weight=1)

        borrow_button = make_red_button(button_area, "カメラを借りる", self.start_borrow, height=150)
        borrow_button.configure(font=make_font(30, bold=True))
        borrow_button.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        return_button = make_red_button(button_area, "カメラを返す", self.start_return, height=150)
        return_button.configure(font=make_font(30, bold=True))
        return_button.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        # その時に押せないボタンはグレーにする
        if app.rental is None:
            disable_button(return_button)
        else:
            disable_button(borrow_button)

    def start_borrow(self):
        self.app.show(ScanScreen, purpose="borrow")

    def start_return(self):
        self.app.show(ScanScreen, purpose="return")


class ScanScreen(Screen):
    def __init__(self, app, purpose):
        super().__init__(app)
        self.purpose = purpose

        if purpose == "borrow":
            self.show_steps(BORROW_STEPS, 0)
        else:
            self.show_steps(RETURN_STEPS, 0)
        self.show_title("社員証をカードリーダーにかざしてください", "読み取るまで動かさずにお待ちください")

        demo_box = customtkinter.CTkFrame(self.content_area, fg_color=YELLOW_TAG[1], corner_radius=6)
        demo_box.pack(side="bottom", fill="x")

        demo_title = make_label(demo_box, "デモ用:かざす社員証を選ぶ", 16, True, YELLOW_TAG[0])
        demo_title.pack(anchor="w", padx=16, pady=(10, 6))

        button_row = customtkinter.CTkFrame(demo_box, fg_color="transparent")
        button_row.pack(fill="x", padx=16, pady=(0, 14))

        registered_button = make_white_button(button_row, f"{USER_NAME}(登録済み)", self.registered_card_touched,
                                              width=220, height=48)
        registered_button.configure(font=make_font(16))
        registered_button.pack(side="left", padx=(0, 8))

        unknown_button = make_white_button(button_row, "未登録のカード", self.unknown_card_touched,
                                           width=160, height=48)
        unknown_button.configure(font=make_font(16))
        unknown_button.pack(side="left")

        self.add_left_button("やめる", app.go_home)

    def registered_card_touched(self):
        if self.purpose == "borrow":
            self.app.show(TimeScreen)
        else:
            self.app.show(ReturnConfirmScreen)

    def unknown_card_touched(self):
        self.app.show(UnknownCardScreen)


class UnknownCardScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        error_tag = make_tag(self.top_area, "エラー", PINK_TAG)
        error_tag.pack(anchor="w", pady=(0, 16))
        self.show_title("登録されていない社員証です", "利用登録は管理者に依頼してください。", ERROR_TEXT_COLOR)
        self.add_left_button("ホームに戻る", app.go_home)


class TimeScreen(Screen):
    # 時間のボタンを押すと下に返却予定が出て、よければ「OK」で確認画面へ

    COLUMNS = 3

    def __init__(self, app, selected_minutes=None):
        super().__init__(app)
        self.selected_minutes = None
        self.show_steps(BORROW_STEPS, 1)
        self.show_title("貸出時間を選んでください", f"{USER_NAME} さん")

        self.add_left_button("やめる", app.go_home)
        self.ok_button = self.add_right_button("OK", self.go_next)
        disable_button(self.ok_button)  # 時間を選ぶまでは押せない

        self.time_buttons = {}  # {分: ボタン}
        button_grid = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        button_grid.pack(fill="x")
        button_grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="time_buttons")

        for position, minutes in enumerate(RENTAL_MINUTES):
            button = make_white_button(button_grid, format_minutes(minutes), lambda m=minutes: self.select(m),
                                       height=76)
            button.configure(font=make_font(24, bold=True))

            row = position // self.COLUMNS
            column = position % self.COLUMNS
            button.grid(row=row, column=column, sticky="ew", padx=6, pady=6)
            self.time_buttons[minutes] = button

        self.due_label = make_label(self.content_area, "時間を選ぶと、返却予定が出ます。", color=SUB_TEXT_COLOR)
        self.due_label.pack(anchor="w", padx=6, pady=(20, 0))

        if selected_minutes is not None:
            self.select(selected_minutes)

    def select(self, minutes):
        self.selected_minutes = minutes

        for button_minutes, button in self.time_buttons.items():
            show_as_selected(button, button_minutes == minutes)

        due_at = datetime.now() + timedelta(minutes=minutes)
        self.due_label.configure(
            text=f"返却予定  {format_date_time(due_at)}",
            font=make_font(28, bold=True),
            text_color=TEXT_COLOR,
        )
        enable_red_button(self.ok_button)

    def go_next(self):
        self.app.show(BorrowConfirmScreen, minutes=self.selected_minutes)


class BorrowConfirmScreen(Screen):
    def __init__(self, app, minutes):
        super().__init__(app)
        self.show_steps(BORROW_STEPS, 2)
        self.show_title("この内容で借ります", "「借りる」を押すと記録され、鍵のロックが外れます。")

        self.minutes = minutes
        self.due_at = datetime.now() + timedelta(minutes=minutes)
        rows = [
            ("利用者", f"{USER_NAME} さん"),
            ("貸出時間", format_minutes(minutes)),
            ("返却予定", format_date_time(self.due_at)),
        ]
        show_table(self.content_area, rows)

        self.add_left_button("戻る", self.go_back)
        self.add_right_button("借りる", self.borrow)

    def go_back(self):
        self.app.show(TimeScreen, selected_minutes=self.minutes)

    def borrow(self):
        self.app.rental = {"rented_at": datetime.now(), "due_at": self.due_at}
        self.app.show(UnlockedScreen, purpose="borrow")


class ReturnConfirmScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        if app.rental is None:
            # ホームで「返す」は押せないようにしているので、通常は来ない
            app.after(0, app.go_home)
            return

        self.show_steps(RETURN_STEPS, 1)
        self.show_title("このカメラを返却します", "「返却する」を押すと記録され、鍵のロックが外れます。")

        rows = [
            ("利用者", f"{USER_NAME} さん"),
            ("貸出日時", format_date_time(app.rental["rented_at"])),
            ("返却予定", format_date_time(app.rental["due_at"])),
        ]
        show_table(self.content_area, rows)

        self.add_left_button("やめる", app.go_home)
        self.add_right_button("返却する", self.give_back)

    def give_back(self):
        self.app.rental = None
        self.app.show(UnlockedScreen, purpose="return")


class UnlockedScreen(Screen):
    # 鍵のロックが外れたあとの案内

    def __init__(self, app, purpose):
        super().__init__(app)

        if purpose == "borrow":
            self.show_steps(BORROW_STEPS, 3)
            what_to_do = ["鍵を取り出す", "棚を開けて、カメラを取り出す", "棚を閉めて、鍵を戻す"]
        else:
            self.show_steps(RETURN_STEPS, 2)
            what_to_do = ["鍵を取り出す", "棚を開けて、カメラを戻す", "棚を閉めて、鍵を戻す"]

        recorded_tag = make_tag(self.top_area, "記録しました", GREEN_TAG)
        recorded_tag.pack(anchor="w", pady=(0, 16))

        title_label = make_label(self.top_area, "鍵のロックが外れました", 34, True)
        title_label.pack(anchor="w", pady=(0, 20))

        for step_number, step_text in enumerate(what_to_do, start=1):
            step_label = make_label(self.content_area, f"{step_number}.  {step_text}", 26, True)
            step_label.pack(anchor="w", pady=4)

        self.add_right_button("鍵を戻した", app.go_home)


if __name__ == "__main__":
    DemoApp().mainloop()
