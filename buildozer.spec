[app]
title = Comodato Viewer
package.name = comodato_viewer
package.domain = org.valdeci
source.dir = .
source.include_exts = py,kv,db,png
source.exclude_patterns = __pycache__/*,*.pyc,*.pyo,*.pyd,*.swp,*.git/*,*.gitignore,old.db
version = 1.0
requirements = python3,kivy==2.3.1,certifi,filetype
orientation = portrait
fullscreen = 1
presplash = assets/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1

[android]
android.permissions = INTERNET
android.presplash_color = #111621
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.ndk = 25b
android.ndk_api = 21
android.accept_sdk_license = True
