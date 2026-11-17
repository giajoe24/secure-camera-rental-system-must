# 追加機能: 返却予定の延長(config.USE_EXTEND)
# 貸出中はホームに「返却予定を延ばす」を出す。借りた本人の社員証で延ばせる。
# 期限を過ぎてから延ばすときは「今」から延ばす

from datetime import datetime, timedelta

import customtkinter

import config
from db import TIME_FORMAT, RentalError, parse_time
from gui_parts import (GREEN_TAG, SUB_TEXT_COLOR, TEXT_COLOR, Screen, disable_button, enable_red_button,
                       format_date_time, format_minutes, make_font, make_label, make_tag, make_white_button,
                       show_as_selected)

STEPS = ["社員証", "延長時間", "完了"]


def add_button_on_home(home, rental):
    if rental is None:
        return
    home.show_footer()
    home.add_right_button("返却予定を延ばす", lambda: home.app.scan_card(STEPS, card_read))


def card_read(app, card_id):
    # 社員証が読めたら呼ばれる
    user = app.database.find_user_by_card(card_id)
    if user is None:
        raise RentalError("登録されていない社員証です", "利用登録は管理者に依頼してください。")

    rental = app.database.current_rental()
    if rental is None:
        raise RentalError("延長できません", "いまは貸出中ではありません。")
    if rental["user_id"] != user["id"]:
        raise RentalError("延長できません", "借りた人の社員証をかざしてください。")

    app.show(ExtendScreen, user=user, rental=rental)


def new_due_at(rental, minutes, now):
    due_at = parse_time(rental["due_at"])
    if due_at > now:
        return due_at + timedelta(minutes=minutes)
    return now + timedelta(minutes=minutes)  # もう過ぎていたら今から


def extend_rental(database, rental, new_due):
    changed = database.execute(
        "UPDATE rentals SET due_at = ? WHERE id = ? AND returned_at IS NULL",
        (new_due.strftime(TIME_FORMAT), rental["id"]),
    )
    if changed == 0:
        raise RentalError("延長できません", "すでに返却されています。")


class ExtendScreen(Screen):
    def __init__(self, app, user, rental):
        super().__init__(app)
        self.rental = rental
        self.new_due = None

        self.show_steps(STEPS, 1)
        due_text = format_date_time(parse_time(rental["due_at"]))
        self.show_title("どれだけ延ばしますか?", f"{user['name']} さん   今の返却予定  {due_text}")

        self.add_left_button("やめる", app.go_home)
        self.ok_button = self.add_right_button("OK", self.extend)
        disable_button(self.ok_button)

        grid = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="a")

        self.time_buttons = {}
        for i, minutes in enumerate(config.EXTEND_MINUTES):
            button = make_white_button(grid, f"+ {format_minutes(minutes)}", lambda m=minutes: self.select(m), height=76)
            button.configure(font=make_font(24, True))
            button.grid(row=i // 4, column=i % 4, sticky="ew", padx=6, pady=6)
            self.time_buttons[minutes] = button

        self.due_label = make_label(self.content_area, "時間を選ぶと、新しい返却予定が出ます。", color=SUB_TEXT_COLOR)
        self.due_label.pack(anchor="w", padx=6, pady=(20, 0))

    def select(self, minutes):
        for m, button in self.time_buttons.items():
            show_as_selected(button, m == minutes)

        self.new_due = new_due_at(self.rental, minutes, datetime.now())
        self.due_label.configure(text=f"新しい返却予定  {format_date_time(self.new_due)}",
                                 font=make_font(28, True), text_color=TEXT_COLOR)
        enable_red_button(self.ok_button)

    def extend(self):
        disable_button(self.ok_button)
        try:
            extend_rental(self.app.database, self.rental, self.new_due)
        except Exception as e:
            self.app.show_error(e)
            return
        self.app.show(ExtendDoneScreen, new_due=self.new_due)


class ExtendDoneScreen(Screen):
    def __init__(self, app, new_due):
        super().__init__(app)
        self.show_steps(STEPS, 2)
        make_tag(self.top_area, "延長しました", GREEN_TAG).pack(anchor="w", pady=(0, 16))
        text = f"返却予定を延ばしました。\n新しい返却予定は {format_date_time(new_due)} です。"
        make_label(self.top_area, text, 34, True).pack(anchor="w")

        self.add_right_button("ホームに戻る", app.go_home)
        self.run_later(8000, app.go_home)
