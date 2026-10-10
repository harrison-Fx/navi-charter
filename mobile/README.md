# Kuching Trip Advisor — mobile prototype (Expo / React Native)

Practice version of the advisor as a real phone app. Traffic is **made up** (same model as `poc/advisor.html` and `kuching_advisor.py`, approximate map), so it tests the process, not prediction accuracy.

## What it does
- **Plan:** start from *My location* (phone GPS → nearest area; Google Maps uses your exact position) or pick an area or saved place. Destination from saved places, Kuching areas, or areas around Kuching (Samarahan, Siburan, Matang outer, Samariang, Sejingkat). Arrive-by time with −15/−5/+5/+15 buttons, today/tomorrow, school day (auto: weekends = no school), how sure you want to be (80/90/95%).
- **Advice:** leave-by time, chance of being late, route, arrival range, notes (school drop-off/pick-up, busy roads, people driving in from outside Kuching, other planned trips), simple route map.
- **Hand-off:** *Open in Google Maps* (adds a stop only when we send you away from the road Maps would normally pick), *Open without the extra stop*, *Remind me* (notification 5 minutes before leave-by), *Send as message* (WhatsApp/SMS share for people who don't use maps).
- **Road reports:** mark a road closed or jammed for 2 hours (on this phone only for now).
- **Test trips:** start a trip as "Following advice" or "My usual way", tap *I'm leaving* (opens Google Maps when following advice) and *I've arrived*: times are recorded automatically. Answer whether Maps kept the route. Summary: on time (advice vs usual), typical time error, how often Maps kept the route. *Send results (CSV)* shares the log.
- **Settings:** nickname, large text, saved places ("Save where I am now"), made-up traffic switches. No account; everything stays on the phone.

## Run it on your Android phone (Expo Go)
**Easiest on Windows:** double-click `OPEN-LAUNCHER.bat`. It opens a small window (Python + CustomTkinter) that:
1. checks Node.js, the app packages and the tunnel helper, with an *Install* button for each;
2. lets you pick **Same Wi-Fi** (choose this PC's Wi-Fi address from a list) or **Tunnel (any network)**;
3. starts the app server and shows the QR code to scan with Expo Go (before that, a QR code to get Expo Go from the Play Store);
4. has a one-click *Use tunnel* switch when the phone says "Failed to download remote update", and a Windows Firewall fix.
The launcher installs Python 3.12 (via winget) and its helpers (customtkinter, qrcode, pillow) the first time. It runs Expo without live reload, which is fine for testing; use `npx expo start` when editing code.

Fallback without the launcher: `START-HERE.bat` (Wi-Fi) or `START-TUNNEL.bat` (tunnel).

Manual steps:
1. Install **Expo Go** from the Play Store.
2. On your PC (Node 20+): `cd mobile` → `npm install` → `npx expo start`.
3. Scan the QR code with Expo Go. Phone and PC on the same Wi-Fi; if that doesn't work (campus Wi-Fi), use `npx expo start --tunnel`.

**Version note:** this project uses **Expo SDK 57** (latest stable on 10 Oct 2026). Expo Go only opens projects made for the SDK it supports. If Expo Go says the project is incompatible, run `npx expo install expo@latest` then `npx expo install --fix`, and start again.

## On Replit
Import the `mobile` folder into a Node/Expo Repl, run `npm install`, then `npx expo start --tunnel` and scan the QR code with Expo Go.

## Make an installable APK
Double-click `BUILD-APK.bat` (or press *Build an installable APK* in the launcher).
1. Make a free Expo account at expo.dev/signup; the window asks you to sign in.
2. First build only: answer **Y** to "create an EAS project" and **Y** to "generate a new Android keystore".
3. The build runs in Expo's cloud (about 10–20 minutes on the free plan). At the end you get a link and QR code: open it on the phone, download the APK, allow "install unknown apps" for your browser, install.
4. Share the same link with testers. No PC needed after that.

Settings live in `eas.json` (profile `preview` builds an APK). To ship a new version, raise `version` and `android.versionCode` in `app.json` and build again.

## Files
- `App.js` — screens (Plan, Test trips, Settings).
- `src/engine.js` — the advice engine (JavaScript port of the approximate model).
- `src/RouteMap.js` — simplified map (react-native-svg).
- `launcher.py` / `OPEN-LAUNCHER.bat` — Windows launcher window (checks, connection choice, QR code, APK build button).
- `BUILD-APK.bat`, `eas.json` — cloud APK build.
- `assets/` — app icon (clock = when to leave, road = which way), splash.

## Known limits
- Made-up traffic, approximate areas: advice is worked out between area centres.
- The extra Maps stop is an area's centre point and can land on a side street; the real-map version should put it on the main road.
- Road reports and test trips are per phone; sharing needs a small backend (e.g. on Replit).
- Exact-time reminders on Android 12+ may arrive a little late without the exact-alarm permission (fine for a prototype).
