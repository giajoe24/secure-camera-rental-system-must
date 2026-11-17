# 追加機能のテスト(画面は使わず、計算と DB の書き換えだけ確かめる)
# python -m unittest で test_db.py と一緒に実行される

import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import admin_screen
import extend
import overdue_record
from db import Database, RentalError, minutes_past

NOW = datetime(2026, 11, 20, 10, 0, 0)


def do_nothing():
    pass


class AddonTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.database = Database(Path(self.folder) / "test.sqlite3")
        self.database.create_tables()
        self.database.add_user("10001", "管理 太郎", "AAAA")
        self.database.add_user("10002", "森 航太郎", "BBBB")
        self.mori = self.database.find_user_by_card("BBBB")

        admin_screen.create_admin_table(self.database)
        self.admin = self.database.find_user_by_card("AAAA")
        admin_screen.set_admin(self.database, self.admin, True)

    def tearDown(self):
        shutil.rmtree(self.folder)

    # ---- 延滞の記録 ----

    def test_minutes_past(self):
        due = NOW
        self.assertEqual(minutes_past(due, NOW - timedelta(minutes=5)), 0)
        self.assertEqual(minutes_past(due, NOW + timedelta(seconds=59)), 0)
        self.assertEqual(minutes_past(due, NOW + timedelta(minutes=25, seconds=30)), 25)

    def test_late_minutes_of_returned_rental(self):
        self.database.borrow(self.mori, 30, do_nothing, now=NOW)
        rental = self.database.return_camera(self.mori, do_nothing, now=NOW + timedelta(minutes=55))
        self.assertEqual(overdue_record.late_minutes_of(rental), 25)

    def test_late_minutes_of_rental_not_returned(self):
        self.database.borrow(self.mori, 30, do_nothing, now=NOW)
        self.assertIsNone(overdue_record.late_minutes_of(self.database.current_rental()))

    # ---- 貸出の延長 ----

    def test_extend_from_due_time(self):
        self.database.borrow(self.mori, 60, do_nothing, now=NOW)
        rental = self.database.current_rental()
        new_due = extend.new_due_at(rental, 30, NOW + timedelta(minutes=10))
        self.assertEqual(new_due, NOW + timedelta(minutes=90))

    def test_extend_after_due_starts_from_now(self):
        self.database.borrow(self.mori, 60, do_nothing, now=NOW)
        rental = self.database.current_rental()
        later = NOW + timedelta(minutes=80)
        self.assertEqual(extend.new_due_at(rental, 30, later), later + timedelta(minutes=30))

    def test_extend_rental_updates_due(self):
        self.database.borrow(self.mori, 60, do_nothing, now=NOW)
        rental = self.database.current_rental()
        extend.extend_rental(self.database, rental, NOW + timedelta(hours=3))
        self.assertEqual(self.database.current_rental()["due_at"], "2026-11-20 13:00:00")

    def test_cannot_extend_returned_rental(self):
        self.database.borrow(self.mori, 60, do_nothing, now=NOW)
        rental = self.database.current_rental()
        self.database.return_camera(self.mori, do_nothing, now=NOW)
        with self.assertRaises(RentalError):
            extend.extend_rental(self.database, rental, NOW + timedelta(hours=3))

    # ---- 管理画面(登録の削除) ----

    def test_delete_user_without_rentals(self):
        admin_screen.delete_user(self.database, self.mori)
        self.assertIsNone(self.database.find_user_by_card("BBBB"))
        self.assertEqual(len(self.database.list_users()), 1)

    def test_delete_user_with_history_keeps_name(self):
        self.database.borrow(self.mori, 30, do_nothing, now=NOW)
        self.database.return_camera(self.mori, do_nothing, now=NOW)
        admin_screen.delete_user(self.database, self.mori)

        self.assertIsNone(self.database.find_user_by_card("BBBB"))
        self.assertEqual(self.database.list_rentals()[0]["name"], "森 航太郎")
        # 同じ社員証を別の人として登録し直せる
        self.database.add_user("10003", "新しい 人", "BBBB")

    def test_cannot_delete_user_who_is_renting(self):
        self.database.borrow(self.mori, 30, do_nothing, now=NOW)
        with self.assertRaises(RentalError):
            admin_screen.delete_user(self.database, self.mori)

    def test_cannot_delete_admin(self):
        with self.assertRaises(RentalError):
            admin_screen.delete_user(self.database, self.admin)

    def test_admin_flag(self):
        self.assertTrue(admin_screen.is_admin(self.database, self.admin))
        self.assertFalse(admin_screen.is_admin(self.database, self.mori))
        self.assertEqual(admin_screen.count_admins(self.database), 1)

        admin_screen.set_admin(self.database, self.admin, False)
        self.assertEqual(admin_screen.count_admins(self.database), 0)


if __name__ == "__main__":
    unittest.main()
