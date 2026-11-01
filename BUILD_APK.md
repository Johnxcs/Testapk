# Build the APK

## Easiest: GitHub Actions (works from Windows, nothing to install)
1. Create a new GitHub repo and upload everything in this folder (keep `.github/workflows/build-apk.yml`).
2. Open the repo -> **Actions** -> "Build APK" (it runs on every push; first build ~25-40 min).
3. When it turns green, open the run and download the **CodeReels-apk** artifact (zip containing the .apk).
4. Copy the .apk to your phone, allow "install unknown apps", install.

## Or locally (Ubuntu / WSL2)
    sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
        zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
    pip install --user buildozer cython
    buildozer -v android debug        # APK appears in ./bin/

## Using the app
Pick a topic, edit the JSON in the box (Save JSON), choose fps, press RENDER.
Keep the app open while rendering. The video is copied to Movies/CodeReels (Gallery).
Edit `config.json` (resolution, theme, handle, voice) before building to change defaults.

## If the build fails
- aiohttp/edge-tts won't compile: remove `edge-tts,aiohttp,multidict,yarl,frozenlist,aiosignal,async-timeout`
  from `requirements` in buildozer.spec and set `"engine": "gtts"` in config.json (needs only `requests`).
- `av` won't compile: see the log; this is the most fragile package. Paste the error and I'll adjust.
