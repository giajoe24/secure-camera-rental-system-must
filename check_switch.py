# LE-53 のマイクロスイッチの確認
#   python check_switch.py            GPIO23
#   python check_switch.py --pin 24   別の GPIO
# つなぎ方: COM → GND、NO → GPIO(5V はつながない)。施錠中だけ導通する。
# 状態が変わるたびに表示する。Ctrl+C で終了。

import argparse
import time

import config

parser = argparse.ArgumentParser()
parser.add_argument("--pin", type=int, default=config.LOCK_SWITCH_GPIO_PIN)
args = parser.parse_args()

try:
    from gpiozero import Button
    switch = Button(args.pin, pull_up=True, bounce_time=0.05)
except Exception as e:
    print("GPIO が使えません:", e)
    raise SystemExit(1)

print(f"GPIO{args.pin} を見ています(Ctrl+C で終了)")
last = None
try:
    while True:
        if switch.is_pressed:
            state = "施錠中"
        else:
            state = "解錠中"
        if state != last:
            print(time.strftime("%H:%M:%S"), state)
            last = state
        time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    switch.close()
