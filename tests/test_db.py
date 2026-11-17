# python -m unittest で実行
# ハードウェアがなくても動く。扉を開ける処理は記録だけするダミーを使う。

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from db import Database, RentalError

NOW = datetime(2026, 11, 20, 10, 0, 0)


class DoorForTest:
    def __init__(self, fail=False):
        self.fail = fail
        self.opened = 0

    def open(self):
        if self.fail:
            raise OSError("扉が開かない")
        self.opened += 1


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = Path(self.folder) / "test.sqlite3"
        self.db = Database(self.path)
        self.db.create_tables()
        self.db.add_user("10001", "デモ 太郎", "AAAA")
        self.db.add_user("10002", "森 航太郎", "BBBB")
        self.taro = self.db.find_user_by_card("AAAA")
        self.mori = self.db.find_user_by_card("BBBB")
        self.door = DoorForTest()

    def tearDown(self):
        # 接続を閉じ忘れていると、Windows ではここで消せずにエラーになる
        os.remove(self.path)
        os.rmdir(self.folder)

    def test_registered_card_is_found(self):
        self.assertEqual(self.db.find_user_by_card("bbbb")["name"], "森 航太郎")

    def test_unknown_card_is_not_found(self):
        self.assertIsNone(self.db.find_user_by_card("CCCC"))

    def test_same_card_cannot_be_registered_twice(self):
        with self.assertRaises(RentalError):
            self.db.add_user("10003", "別の人", "AAAA")

    def test_borrow_records_and_opens_door(self):
        due = self.db.borrow(self.mori, 120, self.door.open, now=NOW)

        rental = self.db.current_rental()
        self.assertEqual(rental["name"], "森 航太郎")
        self.assertEqual(rental["rented_at"], "2026-11-20 10:00:00")
        self.assertEqual(rental["due_at"], "2026-11-20 12:00:00")
        self.assertEqual(due, datetime(2026, 11, 20, 12, 0, 0))
        self.assertEqual(self.door.opened, 1)

    def test_cannot_borrow_while_rented(self):
        self.db.borrow(self.mori, 60, self.door.open, now=NOW)
        with self.assertRaises(RentalError):
            self.db.borrow(self.taro, 60, self.door.open, now=NOW)
        self.assertEqual(self.door.opened, 1)

    def test_door_does_not_open_if_record_fails(self):
        self.db.execute("DROP TABLE rentals")
        with self.assertRaises(sqlite3.Error):
            self.db.borrow(self.mori, 60, self.door.open, now=NOW)
        self.assertEqual(self.door.opened, 0)

    def test_record_is_cancelled_if_door_fails(self):
        with self.assertRaises(OSError):
            self.db.borrow(self.mori, 60, DoorForTest(fail=True).open, now=NOW)
        self.assertIsNone(self.db.current_rental())
        self.assertEqual(len(self.db.list_rentals()), 0)

    def test_return(self):
        self.db.borrow(self.mori, 60, self.door.open, now=NOW)
        self.db.return_camera(self.mori, self.door.open, now=NOW)
        self.assertIsNone(self.db.current_rental())
        self.assertEqual(self.db.list_rentals()[0]["returned_at"], "2026-11-20 10:00:00")
        self.assertEqual(self.door.opened, 2)

    def test_only_borrower_can_return(self):
        self.db.borrow(self.mori, 60, self.door.open, now=NOW)
        with self.assertRaises(RentalError):
            self.db.return_camera(self.taro, self.door.open, now=NOW)
        self.assertIsNotNone(self.db.current_rental())

    def test_nothing_to_return(self):
        with self.assertRaises(RentalError):
            self.db.return_camera(self.mori, self.door.open, now=NOW)

    def test_history_remains_after_restart(self):
        self.db.borrow(self.mori, 60, self.door.open, now=NOW)
        self.db.return_camera(self.mori, self.door.open, now=NOW)
        restarted = Database(self.path)
        restarted.create_tables()
        self.assertEqual(len(restarted.list_rentals()), 1)


if __name__ == "__main__":
    unittest.main()
