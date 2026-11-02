#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Keep shell state in one process: emulator-runner splits inline script by line.
set -euo pipefail
compat_api="${1:?Android API required}"
case "$compat_api" in 26|28|30|33|35|36|37) ;; *) exit 2 ;; esac
test "$(adb -s emulator-5554 shell getprop ro.kernel.qemu | tr -d '\r')" = 1
compat_full_flag=()
if [ "$compat_api" -ge 33 ]; then compat_full_flag=(--require-full-ui); fi
adb -s emulator-5554 shell wm size 1080x1920
adb -s emulator-5554 shell wm density 420
python3 -B scripts/test_android_compat.py --run --serial emulator-5554 --display-size 1080x1920 --label "api${compat_api}-16x9" "${compat_full_flag[@]}"
adb -s emulator-5554 shell wm size 1080x2400
python3 -B scripts/test_android_compat.py --run --serial emulator-5554 --display-size 1080x2400 --label "api${compat_api}-20x9" "${compat_full_flag[@]}"
if [ "$compat_api" -ge 28 ]; then
  if adb -s emulator-5554 shell cmd overlay list | grep -q 'com.android.internal.display.cutout.emulation.corner'; then
    adb -s emulator-5554 shell cmd overlay enable --user 0 com.android.internal.display.cutout.emulation.corner
    # Restore the emulator overlay even if the assertions fail.
    trap 'adb -s emulator-5554 shell cmd overlay disable --user 0 com.android.internal.display.cutout.emulation.corner' EXIT
    python3 -B scripts/test_android_compat.py --run --serial emulator-5554 --display-size 1080x2400 --label "api${compat_api}-corner-cutout" "${compat_full_flag[@]}"
    adb -s emulator-5554 shell cmd overlay disable --user 0 com.android.internal.display.cutout.emulation.corner
    trap - EXIT
  else
    echo 'Cutout overlay unavailable in this system image; no cutout run claimed.'
  fi
fi
