# 記録を Excel(.xlsx)にして exports/rental_log.xlsx に保存する
# 貸出・返却が終わるたびに作り直すので、いつでも最新の記録が見られる。
# このファイルはラズパイの中にあるので、見られるのはラズパイを触れる管理者だけ。
#   シート「貸出一覧」 : 借りた人、貸出日時、返却予定、返した人、返却日時
#   シート「操作の記録」: logs テーブルの中身をそのまま(解錠・完了・取り消し)

import logging
import os
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

import config
from db import parse_time

log = logging.getLogger(__name__)

HEADER_FILL = PatternFill("solid", fgColor="1E4FA3")
HEADER_FONT = Font(bold=True, color="FFFFFF")
DATE_FORMAT = "yyyy/mm/dd hh:mm"


def to_time(text):
    # 文字の日時を Excel の日時にする(空なら空のまま)
    if text is None:
        return None
    return parse_time(text)


def add_sheet(book, title, headers, widths, rows):
    sheet = book.create_sheet(title)
    sheet.append(headers)
    for i in range(len(headers)):
        cell = sheet.cell(row=1, column=i + 1)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        sheet.column_dimensions[get_column_letter(i + 1)].width = widths[i]

    for row in rows:
        sheet.append(row)
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, datetime):
                cell.number_format = DATE_FORMAT

    sheet.freeze_panes = "A2"   # 見出しを固定
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"   # 絞り込みできるように
    return sheet


def rental_rows(database):
    rows = []
    for rental in database.list_rentals():
        if rental["returned_at"] is None:
            state = "貸出中"
        else:
            state = "返却済み"
        rows.append([
            rental["borrower_number"], rental["borrower_name"], to_time(rental["rented_at"]),
            to_time(rental["due_at"]), rental["returner_number"], rental["returner_name"],
            to_time(rental["returned_at"]), state,
        ])
    return rows


def log_rows(database):
    rows = []
    for log in database.list_logs():
        rows.append([log["id"], to_time(log["time"]), log["action"], log["step"], log["employee_number"],
                     log["name"], to_time(log["due_at"]), log["note"]])
    return rows


def export_to_excel(database, path):
    book = Workbook()
    book.remove(book.active)   # 最初からある空のシートは使わない

    add_sheet(book, "貸出一覧",
              ["借りた人(社員番号)", "借りた人", "貸出日時", "返却予定", "返した人(社員番号)", "返した人", "返却日時", "状態"],
              [18, 16, 18, 18, 18, 16, 18, 10],
              rental_rows(database))
    add_sheet(book, "操作の記録",
              ["番号", "日時", "操作", "段階", "社員番号", "氏名", "返却予定", "メモ"],
              [8, 18, 8, 10, 12, 16, 18, 30],
              log_rows(database))

    # いったん別の名前で保存してから置き換える(途中で止まっても、壊れたファイルが残らないように)
    path.parent.mkdir(exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    book.save(temp_path)
    os.replace(temp_path, path)


def update_excel(database):
    # 失敗しても貸出・返却は止めない(ログに残すだけ)
    try:
        export_to_excel(database, config.EXCEL_PATH)
    except Exception:
        log.exception("Excel の記録を更新できませんでした")
