# AirDrop for Windows

**English** | [Slovenčina](README_SK.md)

Send files between a Windows PC and an iPhone over your home Wi-Fi. Nothing needs to be installed on the iPhone; Safari is enough.

## Getting started

1. Double-click `start.bat` (or run `python airdrop.py`). You need Python 3.8 or newer; nothing else has to be installed.
2. When Windows asks about the firewall on the first run, allow access for **private networks**.
3. A browser window with a QR code opens on the PC. Scan it with the iPhone camera.
4. Recommended: in Safari on the iPhone, tap **Share → Add to Home Screen**. You can then open AirDrop like an app, without scanning.

### Optional: portable version (no Python needed)

If you don't have Python installed, download **[AirDrop-Windows.zip](https://github.com/chose-sm/AirDrop_windows/releases/latest/download/AirDrop-Windows.zip)**. The link always points to the latest version (see [Releases](https://github.com/chose-sm/AirDrop_windows/releases) for the changelog). It includes the official portable Python from python.org (digitally signed by the Python Software Foundation), so nothing needs to be installed. Extract the ZIP anywhere and double-click `start.bat`. The rest of the steps above stay the same. The firewall prompt will mention `python.exe`; allow it for private networks.

## Usage

| Direction | How |
|---|---|
| PC → iPhone | Drag files into the window on the PC (or press Ctrl+V). On the iPhone, tap **Download** to save a file to the Files app. For photos and videos, tap **Open**, press and hold, then choose **Add to Photos**. |
| iPhone → PC | Tap **Send to PC** and pick photos or files. |

Files are stored in the AirDrop folder, by default `Downloads\AirDrop` (the exact path is shown at the top of the window on the PC):
- `Prijate` contains files received from the iPhone,
- `Odoslane` contains files ready for the iPhone.

### Choosing your own folder

You can keep the files anywhere you like. Create a text file named `airdrop_folder.txt` next to `airdrop.py` and write the folder path on the first line, for example:

```
D:\AirDrop
```

Restart AirDrop. The folder is created automatically if it doesn't exist.

## Settings (environment variables)

- `AIRDROP_PORT` sets the port, `8765` by default.
- `AIRDROP_DIR` sets the folder for files and takes precedence over `airdrop_folder.txt`.
- Running with `--no-browser` does not open the browser.

## Security

Access is protected by a random key contained in the QR code and stored in the `.token` file inside the AirDrop folder. If you delete it, a new key is generated and the old link stops working. Transfers are unencrypted HTTP within your local network, so use it only at home or on a trusted Wi-Fi.

Other protections:
- Websites open in your PC browser cannot control AirDrop (protection against CSRF and DNS rebinding).
- Files received from the phone are marked as downloaded from the internet, so Windows warns before opening them. Executable files (`.exe`, `.bat`, `.ps1`, …) are never launched by the **Open** button; they are only highlighted in File Explorer.
- Transferred files are served in a sandbox, so an HTML or SVG file cannot run scripts inside the app.
- All parts of the app, including the QR code library, are bundled locally; nothing is loaded from the internet.

## Troubleshooting

- **The iPhone can't connect:** both devices must be on the same Wi-Fi, and the network in Windows must be set to *Private*. You can also add the firewall rule manually (PowerShell as administrator):
  ```
  New-NetFirewallRule -DisplayName "AirDrop for Windows" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow -Profile Private
  ```
- **Multiple network addresses (VPN, Hyper-V):** pick the correct address below the QR code.
- **Photos arrive as .HEIC:** on the iPhone, set *Settings → Camera → Formats → Most Compatible*.

## Language

The interface is available in Slovak and English. Switch it with the selector next to the AirDrop title. Each device (PC and iPhone) remembers its own choice; on first launch the language follows the device setting.

## Building the release (for developers)

Regular users don't need this. Just download the ZIP using the link above.

To build the portable package from source, run in the project folder:

```
powershell -ExecutionPolicy Bypass -File build_release.ps1 -Version 1.1.0
```

- The result is `dist\AirDrop-Windows.zip`. Upload it to a new GitHub release under exactly this name, so the download link in this README keeps pointing to the latest version.
- `-Version` only sets the version in the folder name inside the ZIP (e.g. `AirDrop-Windows-v1.1.0`).
- The script downloads the official portable Python from python.org (`-PythonVersion`, default `3.14.8`) and checks the digital signatures of all its files.
