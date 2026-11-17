# ウィンドウ本体
# 上の赤い帯と時計、画面の切り替え、放置したらホームに戻す、エラー画面

import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import customtkinter

import config
from card_reader import CardReaderError
from db import RentalError
from gui_parts import RED, WHITE, format_date_time, make_label
from lock import LockError
from screens import HomeScreen, MessageScreen, ScanScreen

log = logging.getLogger(__name__)


class App(customtkinter.CTk):
    def __init__(self, database, card_reader, lock):
        super().__init__()
        self.database = database
        self.card_reader = card_reader
        self.lock = lock
        self.screen = None
        self.last_touch_time = time.monotonic()

        # 社員証の読み取りは別スレッドでやる。
        # max_workers=1 なので、読み取りは1回ずつ順番になる(リーダーの取り合いにならない)
        self.card_reader_worker = ThreadPoolExecutor(max_workers=1)

        customtkinter.set_appearance_mode("light")
        self.title("セキュアカメラ貸出")
        self.geometry("1000x680")
        self.minsize(900, 620)
        self.configure(fg_color=WHITE)
        if config.FULLSCREEN:
            self.attributes("-fullscreen", True)

        self.bind("<Escape>", self.exit_fullscreen)       # 保守用
        self.protocol("WM_DELETE_WINDOW", self.close)      # × で閉じたとき
        self.bind_all("<ButtonPress>", self.record_touch, add="+")

        # 上の赤い帯
        header = customtkinter.CTkFrame(self, height=52, fg_color=RED, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        make_label(header, "セキュアカメラ貸出", 18, True, WHITE).pack(side="left", padx=40)
        self.clock_label = make_label(header, "", 18, color=WHITE)
        self.clock_label.pack(side="right", padx=40)

        # 画面を入れる場所
        self.body = customtkinter.CTkFrame(self, fg_color=WHITE, corner_radius=0)
        self.body.pack(fill="both", expand=True)

        self.go_home()
        self.every_second()

    def exit_fullscreen(self, event):
        self.attributes("-fullscreen", False)

    def record_touch(self, event):
        self.last_touch_time = time.monotonic()

    def every_second(self):
        self.clock_label.configure(text=format_date_time(datetime.now()))

        # しばらく触られていなければホームに戻す
        if self.screen.idle_timeout and time.monotonic() - self.last_touch_time > config.IDLE_SECONDS:
            log.info("操作がないのでホームに戻ります")
            self.go_home()

        self.after(1000, self.every_second)

    def show(self, screen_class, **kwargs):
        # 前の画面を消して、新しい画面を作る(前の人の情報が残らないように毎回作り直す)
        if self.screen is not None:
            self.screen.leave()
            self.screen.destroy()
        self.screen = screen_class(self, **kwargs)
        self.screen.pack(fill="both", expand=True)
        self.last_touch_time = time.monotonic()

    def go_home(self):
        self.show(HomeScreen)

    def scan_card(self, steps, on_card):
        # 追加機能用。社員証を読んで、読めたら on_card(app, カードID) を呼ぶ
        self.show(ScanScreen, steps=steps, on_card=on_card)

    def open_door(self):
        self.lock.open()

    def close(self):
        # 読み取り中でもすぐ終われるように、先に読み取りを止めてから閉じる
        if self.screen is not None:
            self.screen.leave()
        self.card_reader_worker.shutdown(wait=False, cancel_futures=True)
        self.destroy()

    def show_error(self, error, retry=None, retry_text="もう一度試す"):
        # エラーの種類ごとに、利用者向けの文に直して出す
        if isinstance(error, RentalError):
            title = error.title
            message = error.message
        elif isinstance(error, LockError):
            log.error("解錠に失敗: %s", error)
            title = "扉が開きませんでした"
            message = "記録は取り消しました。管理者に連絡してください。"
        elif isinstance(error, CardReaderError):
            log.error("カードリーダーのエラー: %s", error)
            title = "社員証を読み取れませんでした"
            message = "もう一度かざしてください。続く場合は管理者に連絡してください。"
        elif isinstance(error, sqlite3.Error):
            log.exception("DB のエラー", exc_info=error)
            title = "記録できませんでした"
            message = "扉は開けていません。もう一度お試しください。"
        else:
            log.exception("想定外のエラー", exc_info=error)
            title = "処理を中止しました"
            message = "扉は開けていません。続く場合は管理者に連絡してください。"

        self.show(MessageScreen, title=title, message=message, retry=retry, retry_text=retry_text)

    def report_callback_exception(self, exc_type, exc, tb):
        # ボタンの処理などで起きたエラーもエラー画面にする(tkinter が呼ぶ)
        self.show_error(exc)
