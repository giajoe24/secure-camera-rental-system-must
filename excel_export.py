# 追加機能: 履歴を Excel(.xlsx)で exports/ に保存する
#   python excel_export.py
# openpyxl が必要(pip install openpyxl)

from datetime import datetime

import config
import overdue_record
from db import Database, minutes_past, parse_time

HEADERS = ["貸出ID", "社員番号", "氏名", "貸出日時", "返却予定", "返却日時", "状態"]
WIDTHS = [8, 12, 18, 18, 18, 18, 10]


def is_late(rental, now):
    # 遅れて返した、または今まさに期限切れ
    if rental["returned_at"] is None:
        end = now
    else:
        end = parse_time(rental["returned_at"])
    return minutes_past(parse_time(rental["due_at"]), end) > 0


def export_to_excel(database, output_dir):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    headers = list(HEADERS)
    widths = list(WIDTHS)
    if config.USE_OVERDUE_RECORD:
        headers.append("延滞(分)")
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
        if rental["returned_at"] is None:
            state = "貸出中"
            returned_at = None
        else:
            state = "返却済み"
            returned_at = parse_time(rental["returned_at"])

        row = [rental["id"], rental["employee_number"], rental["name"],
               parse_time(rental["rented_at"]), parse_time(rental["due_at"]), returned_at, state]
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


if __name__ == "__main__":
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("openpyxl が入っていません: pip install openpyxl")
        raise SystemExit(1)

    database = Database(config.DB_PATH)
    database.create_tables()
    path, count = export_to_excel(database, config.EXPORT_DIR)
    print(f"{count} 件を保存しました: {path}")
