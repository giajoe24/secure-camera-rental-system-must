# 利用者の登録と、記録の確認
#   python register_user.py add 10002 "森 航太郎" 012E4CAA12345678
#   python register_user.py list            登録した人
#   python register_user.py history         貸出の記録
#   python register_user.py export          貸出の記録を CSV に保存
#   python register_user.py admin 10001     管理者にする(管理画面)
#   python register_user.py unadmin 10001   管理者をやめる
# カードIDは check_card_reader.py で調べる

import csv
import sys
from datetime import datetime

import admin_screen
import config
import overdue_record
from db import Database, RentalError


def add_user(database, employee_number, name, card_id):
    try:
        database.add_user(employee_number, name, card_id)
        print(f"登録しました: {employee_number} {name}")
    except RentalError as e:
        print(f"{e.title}: {e.message}")


def show_users(database):
    for user in database.list_users():
        line = f"{user['employee_number']}  {user['name']}  {user['card_id']}"
        if config.USE_ADMIN_SCREEN and admin_screen.is_admin(database, user):
            line += "  [管理者]"
        print(line)


def show_history(database):
    for rental in database.list_rentals():
        returned_at = rental["returned_at"] or "貸出中"
        line = f"{rental['rented_at']}  {rental['name']}  返却予定 {rental['due_at']}  返却 {returned_at}"
        if config.USE_OVERDUE_RECORD:
            line += f"  延滞(分) {overdue_record.late_text(rental)}"
        print(line)


def export_history(database):
    config.EXPORT_DIR.mkdir(exist_ok=True)
    path = config.EXPORT_DIR / datetime.now().strftime("rental_log_%Y%m%d_%H%M%S.csv")
    rentals = database.list_rentals()

    # utf-8-sig にすると Excel で開いても文字化けしない
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        header = ["貸出ID", "社員番号", "氏名", "貸出日時", "返却予定", "返却日時", "状態"]
        if config.USE_OVERDUE_RECORD:
            header.append("延滞(分)")
        writer.writerow(header)

        for rental in rentals:
            if rental["returned_at"] is None:
                state = "貸出中"
            else:
                state = "返却済み"
            row = [rental["id"], rental["employee_number"], rental["name"], rental["rented_at"],
                   rental["due_at"], rental["returned_at"] or "", state]
            if config.USE_OVERDUE_RECORD:
                row.append(overdue_record.late_text(rental))
            writer.writerow(row)

    print(f"{len(rentals)} 件を保存しました: {path}")


def change_admin(database, employee_number, admin):
    user = admin_screen.find_user_by_employee_number(database, employee_number)
    if user is None:
        print(f"社員番号 {employee_number} の人は登録されていません")
        return
    admin_screen.set_admin(database, user, admin)
    if admin:
        print(f"管理者にしました: {employee_number} {user['name']}")
    else:
        print(f"管理者をやめました: {employee_number} {user['name']}")


def show_usage():
    print("使い方:")
    print('  python register_user.py add 社員番号 "氏名" カードID')
    print("  python register_user.py list")
    print("  python register_user.py history")
    print("  python register_user.py export")
    if config.USE_ADMIN_SCREEN:
        print("  python register_user.py admin 社員番号")
        print("  python register_user.py unadmin 社員番号")


def main():
    args = sys.argv[1:]

    database = Database(config.DB_PATH)
    database.create_tables()
    if config.USE_ADMIN_SCREEN:
        admin_screen.create_admin_table(database)

    if len(args) == 4 and args[0] == "add":
        add_user(database, args[1], args[2], args[3])
    elif args == ["list"]:
        show_users(database)
    elif args == ["history"]:
        show_history(database)
    elif args == ["export"]:
        export_history(database)
    elif len(args) == 2 and args[0] == "admin" and config.USE_ADMIN_SCREEN:
        change_admin(database, args[1], True)
    elif len(args) == 2 and args[0] == "unadmin" and config.USE_ADMIN_SCREEN:
        change_admin(database, args[1], False)
    else:
        show_usage()


if __name__ == "__main__":
    main()
