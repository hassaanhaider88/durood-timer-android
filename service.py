"""
Durood Timer - Android background service.

Runs the interval countdown, shows a bottom-right 5..1 warning, then a
full-screen black overlay (Durood-e-Ibrahim + 60s countdown) drawn ON TOP
of whatever app the user is using (e.g. YouTube), via an Android
system-alert-window. This is the Android equivalent of the desktop
Win+D + fullscreen overlay step - there is no "minimize everything" call
on Android, so the overlay is drawn directly over the foreground app
instead.

Requires:
  - SYSTEM_ALERT_WINDOW permission granted by the user (button in main.py)
  - FOREGROUND_SERVICE / POST_NOTIFICATIONS / WAKE_LOCK in buildozer.spec

NOT implemented: auto-start after phone reboot. Android needs a compiled
BroadcastReceiver for RECEIVE_BOOT_COMPLETED, which python-for-android does
not expose cleanly without extra native (Java) glue. Practical workaround:
open the app once after reboot, and use "Ignore battery optimization" so
Android does not kill the service in the meantime.
"""

import json
import os
import time

from jnius import autoclass

PythonService = autoclass("org.kivy.android.PythonService")
Context = autoclass("android.content.Context")
LayoutParams = autoclass("android.view.WindowManager$LayoutParams")
Gravity = autoclass("android.view.Gravity")
TextView = autoclass("android.widget.TextView")
Color = autoclass("android.graphics.Color")
PixelFormat = autoclass("android.graphics.PixelFormat")
Build_VERSION = autoclass("android.os.Build$VERSION")
Handler = autoclass("android.os.Handler")
Looper = autoclass("android.os.Looper")
NotificationBuilder = autoclass("android.app.Notification$Builder")
NotificationChannel = autoclass("android.app.NotificationChannel")
NotificationManager = autoclass("android.app.NotificationManager")

try:
    from android.storage import app_storage_path
    DATA_DIR = app_storage_path()
except ImportError:
    DATA_DIR = os.path.expanduser("~/.durood_timer")

os.makedirs(DATA_DIR, exist_ok=True)
CONTROL_FILE = os.path.join(DATA_DIR, "control.json")

WARNING_SECONDS = 5
OVERLAY_SECONDS = 60
CHANNEL_ID = "durood_timer_channel"

DUROOD_ARABIC = (
    "اللَّهُمَّ صَلِّ عَلَى مُحَمَّدٍ وَعَلَى آلِ مُحَمَّدٍ\n"
    "كَمَا صَلَّيْتَ عَلَى إِبْرَاهِيمَ وَعَلَى آلِ إِبْرَاهِيمَ إِنَّكَ حَمِيدٌ مَجِيدٌ\n"
    "اللَّهُمَّ بَارِكْ عَلَى مُحَمَّدٍ وَعَلَى آلِ مُحَمَّدٍ\n"
    "كَمَا بَارَكْتَ عَلَى إِبْرَاهِيمَ وَعَلَى آلِ إِبْرَاهِيمَ إِنَّكَ حَمِيدٌ مَجِيدٌ"
)

service = PythonService.mService
main_handler = Handler(Looper.getMainLooper())


def load_control():
    default = {"running": True, "interval_minutes": 20}
    if os.path.exists(CONTROL_FILE):
        try:
            with open(CONTROL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            default.update(data)
        except (json.JSONDecodeError, OSError):
            pass
    return default


def save_remaining(seconds):
    control = load_control()
    control["remaining_seconds"] = seconds
    try:
        with open(CONTROL_FILE, "w", encoding="utf-8") as f:
            json.dump(control, f, indent=2)
    except OSError:
        pass


def start_foreground_notification():
    nm = service.getSystemService(Context.NOTIFICATION_SERVICE)
    if Build_VERSION.SDK_INT >= 26:
        channel = NotificationChannel(
            CHANNEL_ID, "Durood Timer", NotificationManager.IMPORTANCE_LOW,
        )
        nm.createNotificationChannel(channel)
        builder = NotificationBuilder(service, CHANNEL_ID)
    else:
        builder = NotificationBuilder(service)
    builder.setContentTitle("Durood Timer")
    builder.setContentText("Reminder active")
    builder.setSmallIcon(service.getApplicationInfo().icon)
    service.startForeground(1, builder.build())


class Overlay:
    """Wraps a system-alert-window view shown over every other app."""

    def __init__(self):
        self.view = None
        self.wm = service.getSystemService(Context.WINDOW_SERVICE)

    def _params(self, fullscreen):
        overlay_type = (
            LayoutParams.TYPE_APPLICATION_OVERLAY
            if Build_VERSION.SDK_INT >= 26
            else LayoutParams.TYPE_PHONE
        )
        flags = LayoutParams.FLAG_NOT_FOCUSABLE | LayoutParams.FLAG_LAYOUT_IN_SCREEN
        size = LayoutParams.MATCH_PARENT if fullscreen else LayoutParams.WRAP_CONTENT
        params = LayoutParams(size, size, overlay_type, flags, PixelFormat.TRANSLUCENT)
        if not fullscreen:
            params.gravity = Gravity.BOTTOM | Gravity.RIGHT
            params.x = 20
            params.y = 100
        return params

    def show_warning(self, text):
        def _run():
            try:
                if self.view is None:
                    self.view = TextView(service)
                    self.view.setTextColor(Color.parseColor("#FFCC00"))
                    self.view.setBackgroundColor(Color.parseColor("#CC1A1A1A"))
                    self.view.setTextSize(22)
                    self.view.setPadding(30, 20, 30, 20)
                    self.wm.addView(self.view, self._params(fullscreen=False))
                self.view.setText(text)
            except Exception as exc:  # permission not granted, etc.
                print("Overlay warning failed:", exc)
        main_handler.post(_run)

    def show_fullscreen(self, text):
        def _run():
            try:
                if self.view is not None:
                    self.wm.removeView(self.view)
                self.view = TextView(service)
                self.view.setTextColor(Color.WHITE)
                self.view.setBackgroundColor(Color.BLACK)
                self.view.setTextSize(20)
                self.view.setGravity(Gravity.CENTER)
                self.wm.addView(self.view, self._params(fullscreen=True))
                self.view.setText(text)
            except Exception as exc:
                print("Overlay fullscreen failed:", exc)
        main_handler.post(_run)

    def update_text(self, text):
        def _run():
            try:
                if self.view is not None:
                    self.view.setText(text)
            except Exception as exc:
                print("Overlay update failed:", exc)
        main_handler.post(_run)

    def hide(self):
        def _run():
            try:
                if self.view is not None:
                    self.wm.removeView(self.view)
                    self.view = None
            except Exception as exc:
                print("Overlay hide failed:", exc)
        main_handler.post(_run)


def run():
    start_foreground_notification()
    overlay = Overlay()

    while True:
        control = load_control()
        if not control.get("running", True):
            time.sleep(1)
            continue

        remaining = control["interval_minutes"] * 60
        warning_done = False
        broke_early = False

        while remaining > WARNING_SECONDS:
            control = load_control()
            if not control.get("running", True):
                broke_early = True
                break
            save_remaining(remaining)
            time.sleep(1)
            remaining -= 1

        if broke_early:
            overlay.hide()
            continue

        for count in range(WARNING_SECONDS, 0, -1):
            overlay.show_warning(f"Pause now: {count}")
            time.sleep(1)

        for count in range(OVERLAY_SECONDS, 0, -1):
            overlay.show_fullscreen(f"{DUROOD_ARABIC}\n\n{count}")
            time.sleep(1)

        overlay.hide()


run()
