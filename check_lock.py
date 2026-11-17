# 電磁ロック(GPIO)だけの確認。UNLOCK_SECONDS 秒 ON にする
#   python check_lock.py
# 最初はロックをつながず、LED かテスターで確かめる

import config
from lock import GpioLock

print(f"GPIO{config.LOCK_GPIO_PIN} を {config.UNLOCK_SECONDS} 秒間 ON にします。")
if input("よければ y を入力: ").strip() != "y":
    raise SystemExit

lock = GpioLock(config.LOCK_GPIO_PIN, config.LOCK_ACTIVE_HIGH, config.LOCK_SWITCH_GPIO_PIN)
if not lock.ready:
    print("GPIO を使えません:", lock.error)
    raise SystemExit(1)

try:
    print("ON(解錠)")
    lock.open_for(config.UNLOCK_SECONDS)
    print("OFF(施錠)")
finally:
    lock.close()
