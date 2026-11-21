# CR Stockfish on your phone

Two ways to get the engine onto a phone. The second exists today and is the
one to use first; the first is a scaffold that still has to be built once.

## A. Standalone Android app (`android/`)

An APK you can sideload and send to friends. Everything runs on the phone:

| Piece | What it does |
|---|---|
| Python engine (Chaquopy) | The same `crsf` package as the PC app is bundled into the APK with numpy and OpenCV. Gradle copies `crsf/` and `knowledge/` in at build time (`syncCrsf` task). |
| Capture service | Asks for screen-capture consent (MediaProjection), grabs ~3 frames per second downscaled to 540 px wide, and feeds them to the engine. |
| Overlay | A draggable floating panel with the eval, the top plays and a command box (`o hog`, `d ...`, `r`). |
| Tap service | An Accessibility service that performs the two taps of a play (card slot, then tile). Only used when autoplay is armed and dry run is off. |

### Getting the APK without Android Studio

1. Push the branch to GitHub. The workflow `.github/workflows/android.yml` builds the
   debug APK on every change under `cr-stockfish/android/`, `crsf/` or `knowledge/`
   (or run it by hand: Actions → "Android APK" → Run workflow).
2. Open the finished run → Artifacts → `cr-stockfish-debug-apk` → download the zip,
   which contains `app-debug.apk`.
3. Copy the APK to the phone (or send it to someone). Android will ask to allow
   installs from that source; it is a debug-signed app, so Play Protect may warn.

Building locally instead: open `cr-stockfish/android` in Android Studio (Hedgehog
or newer), let it sync, and Build → Build APK(s).

### First run on the phone

1. Open **CR Stockfish** → **1. Allow overlay** → toggle on for this app.
2. **2. Enable tap service** → Accessibility → Installed apps → *CR Stockfish taps* → on.
   (Skip this if you only want advice.)
3. **3. Start capture** → accept the screen-capture prompt (Android asks every time).
4. Open Clash Royale. The floating panel shows the engine's plays. Type `o hog` in its
   box when the opponent plays, exactly like the PC app.
5. Teaching cards: the hand slots are read by template matching, so the first time
   the app sees your deck the hand will show `?`. The bridge exposes
   `label_slot(slot, card_key)`; a label button in the overlay is the next UI task
   (today you can label through the PC app and copy `templates/cards/*.png` into the
   app's files directory with `adb push`).
6. **Autoplay**: keep *Dry run* on and watch the "last decision" text for a whole
   training match. Then switch dry run off with the tap service enabled.

### Limits, honestly

- **Not compiled yet.** The project was written without an Android build
  environment. Expect a build-fix pass the first time CI runs (Chaquopy/AGP
  version pairing is the usual culprit: Chaquopy 16 wants AGP 8.1-8.5).
- **Performance.** About 3 decisions per second on a mid-range phone; the PC app
  runs 4-6. Python startup adds a few seconds when the app opens.
- **Google Play Store will not accept it.** Screen-capture + accessibility-driven
  game automation is against Play policy. Sideload only.
- **Supercell's terms** forbid bots. Secondary account, training camp, friendlies.
- **Tower HP / clock OCR is off** on the phone (no Tesseract); the match clock is
  estimated from the first frame, like the PC app without OCR.
- **One phone, one game.** The app captures the phone's own screen; it cannot
  watch a game on another device.

## B. PC-driven (works today)

The phone runs the game; the PC runs the engine and taps the phone over ADB.

```bash
# on the phone: Developer options -> USB debugging; plug in USB once
adb tcpip 5555                      # optional: switch to Wi-Fi ADB
python -m crsf play --emulator phone --dry-run             # USB
python -m crsf play --connect 192.168.1.23:5555 --dry-run  # Wi-Fi (phone's IP)
python -m crsf gui                                         # or the dashboard, source "Emulator via ADB" -> phone
```

Frames come from `adb exec-out screencap`, taps from `adb shell input tap`.
This path is independent of your mouse and keyboard and has no app to install.

## C. Windows one-file build (to send the PC app)

```
cd cr-stockfish
build_windows.bat        -> dist\CRStockfish.exe
```

The exe bundles the engine, knowledge files and dashboard; double-click opens
the GUI in a browser app window. Build it on Windows (PyInstaller does not
cross-compile). Recipients still need Google Play Games or an emulator with
Clash Royale, and `adb` on PATH if they use the ADB input.
