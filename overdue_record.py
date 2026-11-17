# 追加機能: 延滞の記録(config.USE_OVERDUE_RECORD)
# 返却日時 - 返却予定 で何分遅れたかを出す(DB に列は増やさない)
# 返却の完了画面と、履歴(history / CSV / Excel / 管理画面)で使う

from db import minutes_past, parse_time
from gui_parts import ERROR_TEXT_COLOR, make_label


def late_minutes_of(rental):
    # 何分遅れて返したか。まだ返していなければ None
    if rental["returned_at"] is None:
        return None
    return minutes_past(parse_time(rental["due_at"]), parse_time(rental["returned_at"]))


def late_text(rental):
    # CSV 用の文字(例: "25"、"0"、"貸出中")
    late = late_minutes_of(rental)
    if late is None:
        return "貸出中"
    return str(late)


def show_on_done(done, rental):
    late = late_minutes_of(rental)
    if late:
        text = f"返却予定より {late}分 遅れての返却でした。"
        make_label(done.content_area, text, bold=True, color=ERROR_TEXT_COLOR).pack(anchor="w", pady=(0, 6))
