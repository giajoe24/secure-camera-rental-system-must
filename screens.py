# 画面
# 貸出: ホーム → 社員証 → 貸出時間 → 確認 → 完了 → ホーム
# 返却: ホーム → 社員証 → 完了 → ホーム

import logging
import threading
import time
import tkinter
from datetime import datetime, timedelta

import customtkinter

import admin_screen
import config
import extend
import overdue_display
import overdue_record
from db import RentalError, parse_time
from gui_parts import (BLUE_TAG, ERROR_TEXT_COLOR, GREEN_TAG, PINK_TAG, SUB_TEXT_COLOR, TEXT_COLOR, WHITE,
                       Screen, disable_button, enable_red_button, format_date_time, format_minutes, make_font,
                       make_label, make_line, make_red_button, make_tag, make_white_button, show_as_selected)

log = logging.getLogger(__name__)

BORROW_STEPS = ["社員証", "貸出時間", "確認", "取り出し"]
RETURN_STEPS = ["社員証", "返却"]


class HomeScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.footer.pack_forget()  # ホームは下の帯なし(追加機能のボタンがあるときだけ出す)

        rental = app.database.current_rental()

        # カメラの状態
        make_label(self.top_area, config.CAMERA_NAME, 22, True).pack(anchor="w")
        status_row = tkinter.Frame(self.top_area, bg=WHITE)
        status_row.pack(anchor="w", pady=(14, 0))

        if rental is None:
            make_tag(status_row, "貸出可能", GREEN_TAG).pack(side="left")
            make_label(status_row, "  いつでも借りられます", 26, True).pack(side="left")
        else:
            make_tag(status_row, "貸出中", BLUE_TAG).pack(side="left")
            make_label(status_row, f"  {rental['name']} さんが借りています", 26, True).pack(side="left")

            due_at = parse_time(rental["due_at"])
            if datetime.now() > due_at:
                text = f"返却予定({format_date_time(due_at)})を過ぎています"
                make_label(self.top_area, text, color=ERROR_TEXT_COLOR).pack(anchor="w", pady=(10, 0))
            else:
                text = f"返却予定  {format_date_time(due_at)}"
                make_label(self.top_area, text, color=SUB_TEXT_COLOR).pack(anchor="w", pady=(10, 0))

        # 追加機能
        if config.USE_OVERDUE_DISPLAY:
            overdue_display.show_on_home(self, rental)
        if config.USE_EXTEND:
            extend.add_button_on_home(self, rental)
        if config.USE_ADMIN_SCREEN:
            admin_screen.add_button_on_home(self)

        make_line(self.content_area).pack(fill="x", pady=(0, 28))

        # 大きいボタン2つ
        buttons = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        buttons.pack(fill="both", expand=True)
        buttons.grid_columnconfigure((0, 1), weight=1, uniform="a")
        buttons.grid_rowconfigure(0, weight=1)

        borrow_button = make_red_button(buttons, "カメラを借りる", self.start_borrow, height=150)
        borrow_button.configure(font=make_font(30, True))
        borrow_button.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        return_button = make_red_button(buttons, "カメラを返す", self.start_return, height=150)
        return_button.configure(font=make_font(30, True))
        return_button.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        # 押しても意味がないボタンは押せなくする
        if not app.lock.ready:
            text = "電磁ロックが使えないため停止中です。管理者に連絡してください。"
            make_label(self.content_area, text, bold=True, color=ERROR_TEXT_COLOR).pack(anchor="w", pady=(20, 0))
            disable_button(borrow_button)
            disable_button(return_button)
        elif rental is None:
            disable_button(return_button)
        else:
            disable_button(borrow_button)

    def start_borrow(self):
        self.app.show(ScanScreen, purpose="borrow")

    def start_return(self):
        self.app.show(ScanScreen, purpose="return")


class ScanScreen(Screen):
    # 社員証をかざしてもらう。
    # 読み取りは app.card_reader_worker(別スレッド)に頼み、
    # 100ms ごとに「終わったか」を見に行く(customtkinter は別スレッドから触れないため)

    idle_timeout = False  # 読み取りの待ち時間で戻るので、こちらでは戻さない

    def __init__(self, app, purpose="borrow", steps=None, on_card=None):
        # on_card: 追加機能用。指定されていたら、貸出・返却の代わりにこれを呼ぶ
        super().__init__(app)
        self.purpose = purpose
        self.steps = steps
        self.on_card = on_card

        if steps is None:
            if purpose == "borrow":
                steps = BORROW_STEPS
            else:
                steps = RETURN_STEPS
        self.show_steps(steps, 0)
        self.show_title("社員証をカードリーダーにかざしてください")

        self.remaining_label = make_label(self.top_area, "", color=SUB_TEXT_COLOR)
        self.remaining_label.pack(anchor="w", pady=(6, 0))

        self.add_left_button("やめる", app.go_home)

        self.cancel_event = threading.Event()  # 「やめる」を読み取り側に伝える
        self.start_time = time.monotonic()

        # 読み取りを頼む。結果はあとで future から受け取る
        self.future = app.card_reader_worker.submit(
            app.card_reader.read_card, config.CARD_WAIT_SECONDS, self.cancel_event)
        self.check_result()

    def check_result(self):
        if not self.future.done():
            remaining = max(0, int(config.CARD_WAIT_SECONDS - (time.monotonic() - self.start_time)))
            self.remaining_label.configure(text=f"読み取るまで動かさずにお待ちください(残り {remaining} 秒)")
            self.run_later(100, self.check_result)
            return

        try:
            card_id = self.future.result()
        except Exception as e:
            self.app.show_error(e, retry=self.scan_again, retry_text="もう一度かざす")
            return

        if card_id is None:
            self.app.go_home()  # 時間切れ
        else:
            self.use_card(card_id)

    def scan_again(self):
        self.app.show(ScanScreen, purpose=self.purpose, steps=self.steps, on_card=self.on_card)

    def use_card(self, card_id):
        try:
            if self.on_card is not None:
                self.on_card(self.app, card_id)
                return

            user = self.app.database.find_user_by_card(card_id)
            if user is None:
                log.info("未登録の社員証: %s", card_id)
                raise RentalError("登録されていない社員証です", "利用登録は管理者に依頼してください。")

            if self.purpose == "borrow":
                if self.app.database.current_rental() is not None:
                    raise RentalError("いまは借りられません", "ほかの人が借りています。")
                self.app.show(TimeScreen, user=user)
            else:
                rental = self.app.database.return_camera(user, self.app.open_door)
                log.info("返却: %s", user["employee_number"])
                self.app.show(DoneScreen, purpose="return", returned_rental=rental)

        except RentalError as e:
            self.app.show_error(e, retry=self.scan_again, retry_text="もう一度かざす")
        except Exception as e:
            self.app.show_error(e)

    def leave(self):
        self.future.cancel()      # まだ始まっていなければ取り消し
        self.cancel_event.set()   # 始まっていれば止める
        super().leave()


class TimeScreen(Screen):
    # 時間を選ぶと返却予定が出る → OK で確認へ

    def __init__(self, app, user, selected_minutes=None):
        super().__init__(app)
        self.user = user
        self.selected_minutes = None
        self.show_steps(BORROW_STEPS, 1)
        self.show_title("貸出時間を選んでください", f"{user['name']} さん")

        self.add_left_button("やめる", app.go_home)
        self.ok_button = self.add_right_button("OK", self.go_next)
        disable_button(self.ok_button)  # 選ぶまで押せない

        grid = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="a")

        self.time_buttons = {}  # {分: ボタン}
        for i, minutes in enumerate(config.RENTAL_MINUTES):
            button = make_white_button(grid, format_minutes(minutes), lambda m=minutes: self.select(m), height=76)
            button.configure(font=make_font(24, True))
            button.grid(row=i // 3, column=i % 3, sticky="ew", padx=6, pady=6)
            self.time_buttons[minutes] = button

        self.due_label = make_label(self.content_area, "時間を選ぶと、返却予定が出ます。", color=SUB_TEXT_COLOR)
        self.due_label.pack(anchor="w", padx=6, pady=(20, 0))

        # 確認画面から戻ってきたときは、前に選んだ時間を選んでおく
        if selected_minutes is not None:
            self.select(selected_minutes)

    def select(self, minutes):
        self.selected_minutes = minutes
        for m, button in self.time_buttons.items():
            show_as_selected(button, m == minutes)

        due_at = datetime.now() + timedelta(minutes=minutes)
        self.due_label.configure(text=f"返却予定  {format_date_time(due_at)}", font=make_font(28, True),
                                 text_color=TEXT_COLOR)
        enable_red_button(self.ok_button)

    def go_next(self):
        self.app.show(ConfirmScreen, user=self.user, minutes=self.selected_minutes)


class ConfirmScreen(Screen):
    def __init__(self, app, user, minutes):
        super().__init__(app)
        self.user = user
        self.minutes = minutes
        self.show_steps(BORROW_STEPS, 2)
        self.show_title("この内容で借ります", "「借りる」を押すと記録され、扉のロックが開きます。")

        due_at = datetime.now() + timedelta(minutes=minutes)
        rows = [
            ("利用者", f"{user['name']} さん"),
            ("貸出時間", format_minutes(minutes)),
            ("返却予定", format_date_time(due_at)),
        ]

        table = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        table.pack(fill="x")
        table.grid_columnconfigure(0, minsize=180)
        table.grid_columnconfigure(1, weight=1)
        for i, (name, value) in enumerate(rows):
            make_label(table, name, color=SUB_TEXT_COLOR).grid(row=i * 2, column=0, sticky="w", pady=12)
            make_label(table, value, 22, True).grid(row=i * 2, column=1, sticky="w")
            make_line(table).grid(row=i * 2 + 1, column=0, columnspan=2, sticky="ew")

        self.back_button = self.add_left_button("戻る", self.go_back)
        self.borrow_button = self.add_right_button("借りる", self.borrow)

    def go_back(self):
        self.app.show(TimeScreen, user=self.user, selected_minutes=self.minutes)

    def borrow(self):
        # 二度押し防止
        disable_button(self.borrow_button)
        self.back_button.configure(state="disabled")
        self.update_idletasks()

        try:
            due_at = self.app.database.borrow(self.user, self.minutes, self.app.open_door)
        except Exception as e:
            self.app.show_error(e)
            return

        log.info("貸出: %s %s分", self.user["employee_number"], self.minutes)
        self.app.show(DoneScreen, purpose="borrow", due_at=due_at)


class DoneScreen(Screen):
    # 扉が開いたあとの画面。マイクロスイッチで扉が閉まったのがわかったらホームへ。
    # スイッチが使えないときは DONE_SCREEN_SECONDS 秒でホームへ。

    idle_timeout = False

    def __init__(self, app, purpose, due_at=None, returned_rental=None):
        super().__init__(app)

        if purpose == "borrow":
            self.show_steps(BORROW_STEPS, 3)
            make_tag(self.top_area, "貸出完了", GREEN_TAG).pack(anchor="w", pady=(0, 16))
            text = "扉が開きました。\nカメラを取り出して、扉を閉めてください。"
        else:
            self.show_steps(RETURN_STEPS, 1)
            make_tag(self.top_area, "返却完了", GREEN_TAG).pack(anchor="w", pady=(0, 16))
            text = "扉が開きました。\nカメラを戻して、扉を閉めてください。"
        make_label(self.top_area, text, 34, True).pack(anchor="w")

        if due_at is not None:
            make_label(self.content_area, f"返却予定  {format_date_time(due_at)}", color=SUB_TEXT_COLOR).pack(anchor="w")

        # 追加機能: 遅れて返したら何分遅れたかを出す
        if config.USE_OVERDUE_RECORD and returned_rental is not None:
            overdue_record.show_on_done(self, returned_rental)

        self.guide_label = make_label(self.content_area, "", color=SUB_TEXT_COLOR)
        self.guide_label.pack(anchor="w", pady=(6, 0))

        self.add_right_button("ホームに戻る", app.go_home)

        self.door_opened = False
        self.seconds_left = config.DONE_SCREEN_SECONDS

        if app.lock.is_locked() is None:
            self.count_down()
        else:
            self.guide_label.configure(text="扉を閉めると、ホームに戻ります。")
            self.watch_door()

    def watch_door(self):
        # 一度「開いた」を見てから「閉まった」を待つ(パルス直後はまだ外れきっていないことがある)
        if not self.app.lock.is_locked():
            self.door_opened = True
        elif self.door_opened:
            log.info("扉が閉まりました")
            self.app.go_home()
            return
        self.run_later(200, self.watch_door)

    def count_down(self):
        if self.seconds_left <= 0:
            self.app.go_home()
            return
        self.guide_label.configure(text=f"{self.seconds_left} 秒後にホームに戻ります。")
        self.seconds_left -= 1
        self.run_later(1000, self.count_down)


class MessageScreen(Screen):
    # エラー画面
    def __init__(self, app, title, message, retry=None, retry_text="もう一度試す"):
        super().__init__(app)
        make_tag(self.top_area, "エラー", PINK_TAG).pack(anchor="w", pady=(0, 16))
        self.show_title(title, message, ERROR_TEXT_COLOR)
        self.add_left_button("ホームに戻る", app.go_home)
        if retry is not None:
            self.add_right_button(retry_text, retry)
