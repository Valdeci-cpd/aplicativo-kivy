[app]
title = Comodato Viewer
package.name = comodato_viewer
package.domain = org.valdeci
source.dir = .
source.include_exts = py,kv,db
source.exclude_patterns = __pycache__/*,*.pyc,*.pyo,*.pyd,*.swp,*.git/*,*.gitignore,old.db
version = 1.0
requirements = python3,kivy==2.3.1,certifi,filetype
orientation = portrait
fullscreen = 1

[buildozer]
log_level = 2
warn_on_root = 1

[android]
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.ndk = 25b
android.ndk_api = 21
android.accept_sdk_license = True
