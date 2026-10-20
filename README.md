# FileDrop for Windows

**English** | [Slovenčina](README_SK.md)

Send files between a Windows PC and an iPhone over your home Wi-Fi. Nothing needs to be installed on the iPhone; Safari is enough.

## Getting started

1. Double-click `start.bat` (or run `python filedrop.py`). You need Python 3.8 or newer; nothing else has to be installed.
2. When Windows asks about the firewall on the first run, allow access for **private networks**.
3. A browser window with a QR code opens on the PC. Scan it with the iPhone camera.
4. Recommended: in Safari on the iPhone, tap **Share → Add to Home Screen**. You can then open FileDrop like an app, without scanning.

### Optional: portable version (no Python needed)

If you don't have Python installed, download **[FileDrop-Windows.zip](https://github.com/chose-sm/FileDrop_windows/releases/latest/download/FileDrop-Windows.zip)**. The link always points to the latest version (see [Releases](https://github.com/chose-sm/FileDrop_windows/releases) for the changelog). It includes the official portable Python from python.org (digitally signed by the Python Software Foundation), so nothing needs to be installed. Extract the ZIP anywhere and double-click `start.bat`. The rest of the steps above stay the same. The firewall prompt will mention `python.exe`; allow it for private networks.

## Usage

| Direction | How |
|---|---|
| PC → iPhone | Drag files into the window on the PC (or press Ctrl+V). On the iPhone, tap the files you want (or **Select all**) and tap **Save**, then choose **Save Images** (to Photos) or **Save to Files**. **Open** shows a file inside the app; **‹ Back** (or a swipe) returns to the list. |
| iPhone → PC | Tap **Send to PC** and pick photos or files. |

Files are stored in the FileDrop folder, by default `Downloads\FileDrop` (the exact path is shown at the top of the window on the PC):
- `Prijate` contains files received from the iPhone,
- `Odoslane` contains files ready for the iPhone.

### Choosing your own folder

You can keep the files anywhere you like. Create a text file named `filedrop_folder.txt` next to `filedrop.py` and write the folder path on the first line, for example:

```
D:\FileDrop
```

Restart FileDrop. The folder is created automatically if it doesn't exist.

### Secure connection (HTTPS) – save many photos at once

The iPhone only allows a web page to save several files at once (the **Share** menu with **Save Images** / **Save to Files**) over HTTPS. FileDrop therefore creates its own small certificate authority on the PC, and the iPhone needs to trust it once. The app shows a step-by-step guide on the phone (**Set up** button):

1. In **Safari** (not from the Home Screen icon), tap **Download certificate** → **Allow**.
2. **Settings** → **Profile Downloaded** → **Install**.
3. **Settings → General → About → Certificate Trust Settings** → turn on **FileDrop Local CA**.
4. Back in FileDrop, tap **Check**. The app switches to HTTPS automatically from now on.

The certificate can only be used for private IP addresses in home networks (it has *name constraints*), so it cannot be misused to impersonate other websites, even if someone stole it from the PC. To remove it: Settings → General → VPN & Device Management → FileDrop Local CA → Remove Profile. The certificate files are stored in the `.certs` folder inside the FileDrop folder.

Without the certificate everything else keeps working; **Save** then downloads the files to the Files app one by one.

## Settings (environment variables)

- `FILEDROP_PORT` sets the port, `8765` by default.
- `FILEDROP_DIR` sets the folder for files and takes precedence over `filedrop_folder.txt`.
- Running with `--no-browser` does not open the browser.

## Security

Access is protected by a random key contained in the QR code and stored in the `.token` file inside the FileDrop folder. If you delete it, a new key is generated and the old link stops working. Once the phone trusts the FileDrop certificate (see *Secure connection* above), transfers are encrypted (HTTPS). Without it they go over unencrypted HTTP within your local network, so use it only at home or on a trusted Wi-Fi.

Other protections:
- Websites open in your PC browser cannot control FileDrop (protection against CSRF and DNS rebinding).
- Files received from the phone are marked as downloaded from the internet, so Windows warns before opening them. Executable files (`.exe`, `.bat`, `.ps1`, …) are never launched by the **Open** button; they are only highlighted in File Explorer.
- Transferred files are served in a sandbox, so an HTML or SVG file cannot run scripts inside the app.
- All parts of the app, including the QR code library, are bundled locally; nothing is loaded from the internet.

## Troubleshooting

- **The iPhone can't connect:** both devices must be on the same Wi-Fi, and the network in Windows must be set to *Private*. You can also add the firewall rule manually (PowerShell as administrator):
  ```
  New-NetFirewallRule -DisplayName "FileDrop for Windows" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow -Profile Private
  ```
- **Multiple network addresses (VPN, Hyper-V):** pick the correct address below the QR code.
- **Photos arrive as .HEIC:** on the iPhone, set *Settings → Camera → Formats → Most Compatible*.

## Language

The interface is available in Slovak and English. Switch it with the selector next to the FileDrop title. Each device (PC and iPhone) remembers its own choice; on first launch the language follows the device setting.

## Building the release (for developers)

Regular users don't need this. Just download the ZIP using the link above.

To build the portable package from source, run in the project folder:

```
powershell -ExecutionPolicy Bypass -File build_release.ps1 -Version 1.1.0
```

- The result is `dist\FileDrop-Windows.zip`. Upload it to a new GitHub release under exactly this name, so the download link in this README keeps pointing to the latest version.
- `-Version` only sets the version in the folder name inside the ZIP (e.g. `FileDrop-Windows-v1.1.0`).
- The script downloads the official portable Python from python.org (`-PythonVersion`, default `3.14.8`) and checks the digital signatures of all its files.

## Upgrading from AirDrop for Windows (v1.x)

The project was renamed to FileDrop in version 1.2.0. Your files and settings are kept: the default folder `Downloads\AirDrop` is moved to `Downloads\FileDrop` automatically, and `airdrop_folder.txt` and the `AIRDROP_*` variables still work. Scan the QR code again on your phone and add the new page to the Home Screen.

## License

FileDrop is free and open source under the [MIT License](LICENSE). Anyone may use, copy, modify and share it, including commercially, as long as the copyright notice and license text are kept. The software is provided "as is", without warranty of any kind; the author is not liable for any damage arising from its use.

Third-party components and their licenses are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Trademarks

FileDrop is an independent project and is not affiliated with, endorsed by, or sponsored by Apple Inc. iPhone, Safari and AirDrop are trademarks of Apple Inc., registered in the U.S. and other countries. Windows is a trademark of Microsoft Corporation. These names are used only to describe compatibility.
