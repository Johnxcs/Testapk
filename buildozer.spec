[app]
title = Code Reels
package.name = codereels
package.domain = ph.codebyte
source.dir = .
source.include_exts = py,json,ttf,otf,png
source.include_patterns = src/*,topics/*,fonts/*,config.json
source.exclude_dirs = __pycache__,output,bin,.buildozer,.github
source.exclude_patterns = cli_main.py,DESKTOP_README.md
version = 1.0
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #0F1115

# pure-python deps are listed explicitly so python-for-android bundles them
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,pillow,pygments

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,MANAGE_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.extra_manifest_xml = ./extra_manifest.xml
android.api = 33
android.minapi = 29
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
