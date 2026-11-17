# 追加機能: 期限切れの表示(config.USE_OVERDUE_DISPLAY)
# 返却予定を過ぎていたら、ホームの一番上に「返却期限を過ぎています」の帯を出す

import tkinter
from datetime import datetime

from db import minutes_past, parse_time
from gui_parts import ERROR_TEXT_COLOR, PINK_TAG, format_minutes, make_label


def show_on_home(home, rental):
    if rental is None:
        return

    # 1分ごとにホームを作り直す(期限を過ぎたらすぐ帯が出るように)
    home.run_later(60 * 1000, home.app.go_home)

    late = minutes_past(parse_time(rental["due_at"]), datetime.now())
    if late == 0:
        return

    banner = tkinter.Frame(home.step_area, bg=PINK_TAG[1], height=60)
    banner.pack(fill="x")
    banner.pack_propagate(False)

    text = f"返却期限を過ぎています   {rental['name']} さん({format_minutes(late)} 延滞)"
    make_label(banner, text, 22, True, ERROR_TEXT_COLOR).pack(side="left", padx=40)
