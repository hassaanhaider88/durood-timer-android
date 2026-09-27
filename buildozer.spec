[app]
title = Durood Timer
package.name = duroodtimer
package.domain = org.duroodtimer
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

android.permissions = SYSTEM_ALERT_WINDOW,FOREGROUND_SERVICE,WAKE_LOCK,POST_NOTIFICATIONS,RECEIVE_BOOT_COMPLETED
android.api = 33
android.minapi = 24
android.archs = arm64-v8a,armeabi-v7a

services = Timer:service.py:foreground

[buildozer]
log_level = 2
warn_on_root = 1
