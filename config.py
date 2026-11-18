# 設定

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "camera_rental.sqlite3"
LOG_PATH = BASE_DIR / "logs" / "camera_rental.log"
EXPORT_DIR = BASE_DIR / "exports"   # CSV / Excel の保存先

CAMERA_NAME = "セキュアカメラ"

# 貸出時間の選択肢(分)
RENTAL_MINUTES = [15, 30, 60, 120, 240, 480]

# 電磁ロック
LOCK_GPIO_PIN = 18        # BCM 番号
LOCK_ACTIVE_HIGH = True   # Low で動くリレーなら False

# 解錠パルス(実機では 2ms で外れたので 5ms にしている)
UNLOCK_PULSE_COUNT = 1
UNLOCK_PULSE_ON_SECONDS = 0.005
UNLOCK_PULSE_OFF_SECONDS = 0.2    # 2回以上出すときの間隔

# LE-53 のマイクロスイッチ(COM → GND、NO → この GPIO)
LOCK_SWITCH_GPIO_PIN = 23

# カードリーダー
CARD_READER_PATH = "usb"
CARD_TARGETS = ["212F", "106A", "106B"]  # FeliCa / Type A / Type B
CARD_WAIT_SECONDS = 30

# 画面
FULLSCREEN = False        # タッチモニターでは True(Esc で解除)
IDLE_SECONDS = 60         # 操作がないとホームに戻るまでの秒数
DONE_SCREEN_SECONDS = 15  # スイッチが使えないとき、完了画面を出す秒数

# ---- 追加機能 ----
# 使うものだけ True にする

USE_OVERDUE_DISPLAY = True   # 期限切れをホームに出す(overdue_display.py)
USE_OVERDUE_RECORD = True    # 何分遅れて返したかを記録する(overdue_record.py)

USE_EXTEND = True            # 返却予定の延長(extend.py)
EXTEND_MINUTES = [15, 30, 60, 120]

USE_BACKUP = True            # DB を1日1回バックアップ(backup.py)
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_KEEP_DAYS = 14

USE_ADMIN_SCREEN = True      # 管理画面(admin_screen.py)
# 管理者がまだいないときは、ホームの「管理者」から最初の管理者を登録する

# 履歴の保存(export.py)は管理画面から。Excel も作るには openpyxl が必要
