# 追加機能: 貸出の記録をファイルに保存する(管理画面の「ファイルに保存」から使う)
# CSV はいつでも、Excel は openpyxl が入っているときだけ作る

import csv
from datetime import datetime

import config
import overdue_record
from db import minutes_past, parse_time

HEADERS = ["貸出ID", "社員番号", "氏名", "貸出日時", "返却予定", "返却日時", "状態"]
WIDTHS = [8, 12, 18, 18, 18, 18, 10]   # Excel の列の幅


def can_make_excel():
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        return False


def make_headers():
    headers = list(HEADERS)
    if config.USE_OVERDUE_RECORD:
        headers.append("延滞(分)")
    return headers


def state_of(rental):
    if rental["returned_at"] is None:
        return "貸出中"
    return "返却済み"


def is_late(rental, now):
    # 遅れて返した、または今まさに期限切れ
    if rental["returned_at"] is None:
        end = now
    else:
        end = parse_time(rental["returned_at"])
    return minutes_past(parse_time(rental["due_at"]), end) > 0


def export_to_csv(database, output_dir):
    output_dir.mkdir(exist_ok=True)
    path = output_dir / datetime.now().strftime("rental_log_%Y%m%d_%H%M%S.csv")
    rentals = database.list_rentals()

    # utf-8-sig にすると Excel で開いても文字化けしない
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(make_headers())
        for rental in rentals:
            row = [rental["id"], rental["employee_number"], rental["name"], rental["rented_at"],
                   rental["due_at"], rental["returned_at"] or "", state_of(rental)]
            if config.USE_OVERDUE_RECORD:
                row.append(overdue_record.late_text(rental))
            writer.writerow(row)

    return path, len(rentals)


def export_to_excel(database, output_dir):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    headers = make_headers()
    widths = list(WIDTHS)
    if config.USE_OVERDUE_RECORD:
        widths.append(10)

    book = Workbook()
    sheet = book.active
    sheet.title = "貸出履歴"

    # 見出し(赤地に白文字)
    sheet.append(headers)
    for i in range(len(headers)):
        cell = sheet.cell(row=1, column=i + 1)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="DC0032")
        sheet.column_dimensions[get_column_letter(i + 1)].width = widths[i]

    now = datetime.now()
    pink = PatternFill("solid", fgColor="FDECEF")
    rentals = database.list_rentals()

    for rental in rentals:
        returned_at = None
        if rental["returned_at"] is not None:
            returned_at = parse_time(rental["returned_at"])

        row = [rental["id"], rental["employee_number"], rental["name"],
               parse_time(rental["rented_at"]), parse_time(rental["due_at"]), returned_at, state_of(rental)]
        if config.USE_OVERDUE_RECORD:
            row.append(overdue_record.late_minutes_of(rental))
        sheet.append(row)

        # 日時の表示形式と、延滞した行の色
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, datetime):
                cell.number_format = "yyyy/mm/dd hh:mm"
            if is_late(rental, now):
                cell.fill = pink

    sheet.freeze_panes = "A2"   # 見出しを固定
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rentals) + 1}"

    output_dir.mkdir(exist_ok=True)
    path = output_dir / now.strftime("rental_log_%Y%m%d_%H%M%S.xlsx")
    book.save(path)
    return path, len(rentals)
