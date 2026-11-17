# 電磁ロックをパルスで外せるか試す
#   python check_lock_pulse.py                5ms のパルスを 200ms 間隔で 2 回
#   python check_lock_pulse.py --on-ms 20     パルスを 20ms にする
#   python check_lock_pulse.py --count 1      1 回だけにする

import argparse
import time

import config

parser = argparse.ArgumentParser()
parser.add_argument("--count", type=int, default=2, help="回数")
parser.add_argument("--on-ms", type=float, default=5, help="ON の長さ(ms)")
parser.add_argument("--off-ms", type=float, default=200, help="間隔(ms)")
args = parser.parse_args()

print(f"GPIO{config.LOCK_GPIO_PIN} に ON {args.on_ms}ms × {args.count} 回(間隔 {args.off_ms}ms)を出します。")
if input("よければ y を入力: ").strip() != "y":
    raise SystemExit

try:
    from gpiozero import DigitalOutputDevice
    output = DigitalOutputDevice(config.LOCK_GPIO_PIN, active_high=config.LOCK_ACTIVE_HIGH, initial_value=False)
except Exception as e:
    print("GPIO が使えません:", e)
    raise SystemExit(1)

try:
    for i in range(args.count):
        if i > 0:
            time.sleep(args.off_ms / 1000)
        output.on()
        time.sleep(args.on_ms / 1000)
        output.off()
        print(f"{i + 1} 回目")
finally:
    output.off()
    output.close()

print("終わり。ラッチが外れたか確認してください。")
