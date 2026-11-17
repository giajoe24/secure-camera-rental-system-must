# 画面で使う部品(色、フォント、ボタンなど)と、全画面の土台 Screen

import tkinter
import tkinter.font

import customtkinter

# ---- 色 ----
RED = "#DC0032"
RED_WHEN_TOUCHED = "#B8002A"
LIGHT_RED = "#FDECEF"
TEXT_COLOR = "#202124"
SUB_TEXT_COLOR = "#6B7280"
LINE_COLOR = "#E5E7EB"
FOOTER_COLOR = "#F3F4F6"
WHITE = "#FFFFFF"
GRAY_BUTTON_COLOR = "#E5E7EB"
GRAY_TEXT_COLOR = "#9CA3AF"
WHITE_BUTTON_BORDER_COLOR = "#C9CDD3"
ERROR_TEXT_COLOR = "#B3002A"

# 札の色 (文字, 背景)
GREEN_TAG = ("#137A4B", "#EAF8F0")
BLUE_TAG = ("#1D4ED8", "#EAF1FF")
YELLOW_TAG = ("#8A5A00", "#FFF6DB")
PINK_TAG = ("#B3002A", "#FDECEF")

CIRCLED_NUMBERS = ["①", "②", "③", "④", "⑤"]


# ---- 日時の表示 ----

def format_date_time(date_time):
    # 例: 11月17日 15:30
    return f"{date_time.month}月{date_time.day}日 {date_time:%H:%M}"


def format_minutes(minutes):
    # 例: 15 → 15分、120 → 2時間、90 → 1時間30分
    hours = minutes // 60
    rest = minutes % 60
    if hours == 0:
        return f"{rest}分"
    if rest == 0:
        return f"{hours}時間"
    return f"{hours}時間{rest}分"


# ---- フォント ----

# 上から順に探して、あったものを使う
JAPANESE_FONT_NAMES = ["Yu Gothic UI", "Meiryo UI", "Noto Sans CJK JP", "Noto Sans JP"]
japanese_font = ""   # まだ探していないときは ""


def find_japanese_font():
    global japanese_font
    if japanese_font == "":
        japanese_font = None  # 見つからなければ標準のフォント
        installed = tkinter.font.families()
        for name in JAPANESE_FONT_NAMES:
            if name in installed:
                japanese_font = name
                break
    return japanese_font


def make_font(size, bold=False):
    if bold:
        weight = "bold"
    else:
        weight = "normal"
    return customtkinter.CTkFont(family=find_japanese_font(), size=size, weight=weight)


# ---- 部品 ----

def make_label(parent, text, size=19, bold=False, color=TEXT_COLOR):
    return customtkinter.CTkLabel(parent, text=text, font=make_font(size, bold), text_color=color,
                                  anchor="w", justify="left")


def make_tag(parent, text, colors):
    # 「貸出可能」などの札
    text_color, background = colors
    return customtkinter.CTkLabel(parent, text=text, width=110, height=34, corner_radius=4,
                                  fg_color=background, text_color=text_color, font=make_font(16, True))


def make_red_button(parent, text, command, width=260, height=68):
    return customtkinter.CTkButton(
        parent, text=text, command=command, width=width, height=height, corner_radius=6,
        fg_color=RED, hover_color=RED_WHEN_TOUCHED, text_color=WHITE,
        text_color_disabled=GRAY_TEXT_COLOR, font=make_font(21, True),
    )


def make_white_button(parent, text, command, width=260, height=68):
    return customtkinter.CTkButton(
        parent, text=text, command=command, width=width, height=height, corner_radius=6,
        fg_color=WHITE, hover_color=GRAY_BUTTON_COLOR, border_width=2,
        border_color=WHITE_BUTTON_BORDER_COLOR, text_color=TEXT_COLOR, font=make_font(21),
    )


def disable_button(button):
    button.configure(state="disabled", fg_color=GRAY_BUTTON_COLOR)


def enable_red_button(button):
    button.configure(state="normal", fg_color=RED)


def show_as_selected(button, selected):
    # 選んだボタンは薄い赤 + 赤い枠にする
    if selected:
        button.configure(fg_color=LIGHT_RED, border_color=RED, border_width=3, text_color=RED)
    else:
        button.configure(fg_color=WHITE, border_color=WHITE_BUTTON_BORDER_COLOR, border_width=2,
                         text_color=TEXT_COLOR)


def make_line(parent, thickness=1, color=LINE_COLOR):
    # 区切り線(CTkFrame だと 1px の線が出ないので tkinter.Frame)
    return tkinter.Frame(parent, height=thickness, bg=color, bd=0, highlightthickness=0)


# ---- 画面の土台 ----
# 上から step_area(手順)、top_area(見出し)、content_area(中身)、footer(下のボタン)

class Screen(customtkinter.CTkFrame):
    idle_timeout = True   # 放っておいたらホームに戻すか

    def __init__(self, app):
        super().__init__(app.body, fg_color=WHITE, corner_radius=0)
        self.app = app
        self.jobs = []   # after() で予約した処理

        self.step_area = tkinter.Frame(self, bg=WHITE)
        self.step_area.pack(fill="x")

        self.footer = customtkinter.CTkFrame(self, height=92, fg_color=FOOTER_COLOR, corner_radius=0)
        self.footer.pack(side="bottom", fill="x")
        self.footer.pack_propagate(False)  # ボタンで高さが変わらないように

        self.footer_line = make_line(self)
        self.footer_line.pack(side="bottom", fill="x")

        self.top_area = tkinter.Frame(self, bg=WHITE)
        self.top_area.pack(fill="x", padx=40, pady=(22, 0))

        self.content_area = customtkinter.CTkFrame(self, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True, padx=40, pady=22)

    def show_steps(self, names, current):
        # ① 社員証 → ② 貸出時間 → … を出して、今の手順を赤くする
        bar = tkinter.Frame(self.step_area, bg=WHITE, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        row = tkinter.Frame(bar, bg=WHITE)
        row.pack(side="left", fill="y", padx=40)

        for i, name in enumerate(names):
            if i > 0:
                make_label(row, "→", 17, color=SUB_TEXT_COLOR).pack(side="left", padx=10)

            if i == current:
                color = RED
            elif i < current:
                color = TEXT_COLOR
            else:
                color = SUB_TEXT_COLOR

            cell = tkinter.Frame(row, bg=WHITE)
            cell.pack(side="left", fill="y")
            make_label(cell, f"{CIRCLED_NUMBERS[i]} {name}", 17, i == current, color).pack(expand=True)

            # 今の手順だけ下に赤い線
            if i == current:
                make_line(cell, 4, RED).pack(side="bottom", fill="x")
            else:
                make_line(cell, 4, WHITE).pack(side="bottom", fill="x")

        make_line(self.step_area).pack(fill="x")

    def show_title(self, title, note=None, color=TEXT_COLOR):
        make_label(self.top_area, title, 26, True, color).pack(anchor="w")
        if note:
            make_label(self.top_area, note, color=SUB_TEXT_COLOR).pack(anchor="w", pady=(6, 0))

    def show_footer(self):
        # 帯を隠している画面(ホーム)で、あとから出すとき用
        if self.footer.winfo_manager() == "":
            self.footer.pack(side="bottom", fill="x", before=self.footer_line)

    def add_left_button(self, text, command):
        button = make_white_button(self.footer, text, command)
        button.pack(side="left", padx=40)
        return button

    def add_right_button(self, text, command):
        button = make_red_button(self.footer, text, command)
        button.pack(side="right", padx=40)
        return button

    def run_later(self, ms, function):
        # after() と同じ。画面を離れるときにまとめて取り消せるよう覚えておく
        self.jobs.append(self.after(ms, function))

    def leave(self):
        # 画面を離れる直前に呼ばれる
        for job in self.jobs:
            self.after_cancel(job)
