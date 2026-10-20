"""FileDrop pre Windows - prenos suborov medzi PC a iPhonom cez lokalnu siet.

Spusti:  python filedrop.py   (alebo dvojklik na start.bat)
Na PC sa otvori prehliadac s QR kodom, iPhone ho naskenuje fotoaparatom.
"""
import getpass
import hashlib
import http.cookies
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import socket
import ssl
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Nazvy AIRDROP_* / airdrop_folder.txt / Downloads\AirDrop su z verzii 1.x a stale funguju.
PORT = int(os.environ.get("FILEDROP_PORT") or os.environ.get("AIRDROP_PORT") or "8765")
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))  # prenosny Python (._pth) nepridava priecinok skriptu automaticky
import tlscert  # noqa: E402

DEFAULT_DIR = Path.home() / "Downloads" / "FileDrop"
LEGACY_DIR = Path.home() / "Downloads" / "AirDrop"


def data_dir():
    """Priecinok so subormi: FILEDROP_DIR, potom filedrop_folder.txt, inak Stiahnute\\FileDrop."""
    env = os.environ.get("FILEDROP_DIR") or os.environ.get("AIRDROP_DIR")
    if env:
        return Path(env)
    for cfg in (BASE / "filedrop_folder.txt", BASE / "airdrop_folder.txt"):
        if cfg.exists():
            line = cfg.read_text(encoding="utf-8-sig").strip().strip('"')
            if line:
                return Path(os.path.expandvars(line))
    return DEFAULT_DIR


DATA = data_dir()
BOXES = {
    "inbox": DATA / "Prijate",     # z iPhonu do PC
    "outbox": DATA / "Odoslane",   # z PC do mobilu
}
CHUNK = 1024 * 1024
LOCK = threading.Lock()
TOKEN = ""

# Prijate subory s tymito priponami sa otvoria priamo, ostatne (napr. .exe, .bat) sa len ukazu v priecinku.
SAFE_OPEN = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff",
    ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg",
    ".pdf", ".txt", ".csv", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp",
}
PAGE_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' https://{host}; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
CA_DER = b""  # certifikat lokalnej CA na instalaciu do iPhonu (prazdny = HTTPS nedostupne)


def fingerprint(der):
    """SHA-256 odtlacok v tvare, aky ukazuje iPhone (AB CD EF ...)."""
    return " ".join(f"{b:02X}" for b in hashlib.sha256(der).digest())


def protect(path):
    """Subor s tajomstvom (kluc CA, pristupovy kluc) smie citat len aktualny pouzivatel Windows."""
    if os.name != "nt" or not path.exists():
        return
    try:
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except OSError:
        pass  # napr. disk bez NTFS opravneni

for ext, ctype in ((".heic", "image/heic"), (".heif", "image/heif"), (".mov", "video/quicktime"),
                   (".mp4", "video/mp4"), (".js", "text/javascript"), (".webp", "image/webp")):
    mimetypes.add_type(ctype, ext)


def load_token():
    """Pristupovy kluc je ulozeny, aby zalozka na iPhone fungovala aj po restarte."""
    f = DATA / ".token"
    if f.exists():
        t = f.read_text().strip()
        if t:
            return t
    t = secrets.token_urlsafe(9)
    f.write_text(t)
    return t


def lan_ips():
    ips = []
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ips.append(s.getsockname()[0])
    except OSError:
        pass
    finally:
        s.close()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith(("127.", "169.254.")):
                ips.append(ip)
    except OSError:
        pass
    return ips or ["127.0.0.1"]


def safe_name(name):
    name = os.path.basename(name.replace("\\", "/")).strip().strip(".")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name[:200] or "subor"


def unique_path(folder, name):
    p = folder / name
    i = 1
    while p.exists():
        p = folder / f"{Path(name).stem} ({i}){Path(name).suffix}"
        i += 1
    return p


def listing(box):
    items = []
    for p in BOXES[box].iterdir():
        if p.is_file() and not p.name.startswith("."):
            st = p.stat()
            items.append({"name": p.name, "size": st.st_size, "time": st.st_ctime,
                          "type": mimetypes.guess_type(p.name)[0] or ""})
    items.sort(key=lambda x: x["time"], reverse=True)
    return items


def mark_from_internet(path):
    """Mark of the Web - Windows pred otvorenim varuje ako pri subore stiahnutom z internetu."""
    try:
        with open(f"{path}:Zone.Identifier", "wb") as f:
            f.write(b"[ZoneTransfer]\r\nZoneId=3\r\n")
    except OSError:
        pass  # napr. disk FAT/exFAT nepodporuje alternativne datove prudy


def resolve(box, name):
    if box not in BOXES:
        return None
    folder = BOXES[box].resolve()
    p = (folder / name).resolve()
    if p.parent != folder or not p.is_file() or p.name.startswith("."):
        return None
    return p


class Server(ThreadingHTTPServer):
    """HTTP aj HTTPS na jednom porte - sifrovane spojenie sa spozna podla prveho bajtu (TLS handshake)."""
    daemon_threads = True
    tls = None

    def finish_request(self, request, client_address):
        if self.tls:
            try:
                request.settimeout(15)
                if request.recv(1, socket.MSG_PEEK) == b"\x16":
                    request = self.tls.wrap_socket(request, server_side=True)
                request.settimeout(None)
            except OSError:  # aj ssl.SSLError, napr. iPhone este nedoveruje certifikatu
                return
        try:
            self.RequestHandlerClass(request, client_address, self)
        finally:
            if isinstance(request, ssl.SSLSocket):
                request.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "FileDrop/1.3.2"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    # --- pomocne ---------------------------------------------------------
    @property
    def secure(self):
        return isinstance(self.connection, ssl.SSLSocket)

    @property
    def local(self):
        return self.client_address[0] in ("127.0.0.1", "::1")

    def parse(self):
        u = urllib.parse.urlsplit(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        return urllib.parse.unquote(u.path), q

    def host_ok(self):
        """Ochrana pred DNS rebinding: povolena je len adresa IP alebo localhost, nie cudzia domena."""
        name = urllib.parse.urlsplit("//" + self.headers.get("Host", "")).hostname or ""
        if name == "localhost":
            return True
        try:
            ipaddress.ip_address(name)
            return True
        except ValueError:
            return False

    def post_allowed(self):
        """Ochrana pred CSRF: cudzia stranka nemoze poslat vlastnu hlavicku bez CORS, ktory server nepovoluje."""
        if self.headers.get("X-FileDrop") != "1":
            return False
        origin = self.headers.get("Origin")
        return origin is None or urllib.parse.urlsplit(origin).netloc == self.headers.get("Host", "")

    def authed(self, q):
        if self.local or secrets.compare_digest(q.get("k", ""), TOKEN):
            return True
        c = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return "ad" in c and secrets.compare_digest(c["ad"].value, TOKEN)

    def send(self, code, body=b"", ctype="text/plain; charset=utf-8", headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, obj):
        self.send(200, json.dumps(obj), "application/json; charset=utf-8")

    def send_file(self, path, attach):
        size = path.stat().st_size
        start, end, code = 0, size - 1, 200
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", "").strip())
        if m and size and m.group(0) != "bytes=-":
            s, e = m.groups()
            if s == "":
                start = max(0, size - int(e))
            else:
                start = int(s)
                end = min(int(e), size - 1) if e else size - 1
            if start > end or start >= size:
                return self.send(416, headers={"Content-Range": f"bytes */{size}"})
            code = 206
        self.send_response(code)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        # prenasany subor (napr. HTML/SVG) nesmie spustit skript s pravami aplikacie
        self.send_header("Content-Security-Policy", "sandbox")
        self.send_header("X-Content-Type-Options", "nosniff")
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        disp = "attachment" if attach else "inline"
        self.send_header("Content-Disposition",
                         f"{disp}; filename*=UTF-8''{urllib.parse.quote(path.name)}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(CHUNK, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    # --- GET -------------------------------------------------------------
    def do_GET(self):
        path, q = self.parse()
        if not self.host_ok():
            return self.send(403)
        if path == "/favicon.ico":
            return self.send(204)
        if path == "/qrcode.min.js":
            return self.send(200, (BASE / "qrcode.min.js").read_bytes(), "text/javascript; charset=utf-8",
                             {"X-Content-Type-Options": "nosniff"})
        if path == "/filedrop-ca.crt" and CA_DER:
            # bez Content-Disposition -> Safari na iPhone ponukne instalaciu profilu
            return self.send(200, CA_DER, "application/x-x509-ca-cert")
        if path == "/ping":  # stranka cez HTTP tymto zisti, ci iPhone uz doveruje HTTPS
            return self.send(204)
        if not self.authed(q):
            return self.send(403, "<meta name=viewport content='width=device-width'>"
                                  "<h2 style='font-family:sans-serif'>Naskenuj znovu QR kód z PC.<br>"
                                  "Scan the QR code on the PC again.</h2>",
                             "text/html; charset=utf-8")
        if path == "/":
            headers = {"Content-Security-Policy": PAGE_CSP.format(host=self.headers.get("Host", "")),
                       "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                       "X-Content-Type-Options": "nosniff"}
            if not self.local:
                headers["Set-Cookie"] = (f"ad={TOKEN}; Path=/; Max-Age=31536000; SameSite=Strict; HttpOnly"
                                         + ("; Secure" if self.secure else ""))
            html = (BASE / "index.html").read_bytes()
            return self.send(200, html, "text/html; charset=utf-8", headers)
        if path == "/api/state":
            data = {"local": self.local, "outbox": listing("outbox"),
                    "https": bool(CA_DER), "secure": self.secure}
            if self.local:
                data["inbox"] = listing("inbox")
                data["urls"] = [f"http://{ip}:{PORT}/?k={TOKEN}" for ip in lan_ips()]
                data["folder"] = str(DATA)
                data["caFingerprint"] = fingerprint(CA_DER) if CA_DER else ""
            return self.send_json(data)
        m = re.match(r"^/f/(inbox|outbox)/(.+)$", path)
        if m:
            box, name = m.groups()
            if box == "inbox" and not self.local:
                return self.send(403)
            p = resolve(box, name)
            if not p:
                return self.send(404, "Súbor neexistuje.")
            try:
                return self.send_file(p, q.get("dl") == "1")
            except (ConnectionError, OSError):
                return
        self.send(404)

    # --- POST ------------------------------------------------------------
    def do_POST(self):
        path, q = self.parse()
        if not (self.host_ok() and self.post_allowed() and self.authed(q)):
            return self.send(403)
        if path == "/api/upload":
            return self.upload(q)
        if not self.local:
            return self.send(403)
        if path == "/api/delete":
            p = resolve(q.get("box", ""), q.get("name", ""))
            if p:
                p.unlink()
            return self.send_json({"ok": True})
        if path == "/api/clear":
            for item in listing("outbox"):
                (BOXES["outbox"] / item["name"]).unlink(missing_ok=True)
            return self.send_json({"ok": True})
        if path == "/api/open":
            # len priecinok Prijate; spustitelne subory sa nespustaju, iba ukazu v Prieskumnikovi
            if not q.get("name"):
                os.startfile(str(BOXES["inbox"]))
                return self.send_json({"ok": True})
            p = resolve("inbox", q["name"])
            if not p:
                return self.send(404)
            if p.suffix.lower() in SAFE_OPEN:
                os.startfile(str(p))
                return self.send_json({"ok": True, "revealed": False})
            subprocess.Popen(["explorer", "/select,", str(p)])
            return self.send_json({"ok": True, "revealed": True})
        self.send(404)

    def upload(self, q):
        # z PC ide subor do "Odoslane", z iPhonu do "Prijate"
        folder = BOXES["outbox" if self.local else "inbox"]
        name = safe_name(q.get("name", "subor"))
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.send(411, "Chýba Content-Length.")
        tmp = folder / f".{secrets.token_hex(6)}.part"
        try:
            with open(tmp, "wb") as f:
                left = length
                while left > 0:
                    chunk = self.rfile.read(min(CHUNK, left))
                    if not chunk:
                        raise ConnectionError("prerusene nahravanie")
                    f.write(chunk)
                    left -= len(chunk)
            with LOCK:
                final = unique_path(folder, name)
                os.replace(tmp, final)
            if not self.local:
                mark_from_internet(final)
            mtime = q.get("mtime", "")
            if mtime.isdigit():
                os.utime(final, (int(mtime) / 1000, int(mtime) / 1000))
        except (ConnectionError, OSError) as e:
            tmp.unlink(missing_ok=True)
            self.close_connection = True
            print(f"  ! Chyba pri prijímaní {name}: {e}")
            return
        who = "PC -> iPhone" if self.local else "iPhone -> PC"
        print(f"  {who}: {final.name} ({length / 1048576:.1f} MB)")
        self.send_json({"ok": True, "name": final.name})


def main():
    global TOKEN, CA_DER
    if DATA == DEFAULT_DIR and not DATA.exists() and LEGACY_DIR.is_dir():
        LEGACY_DIR.rename(DATA)  # presun z verzie 1.x
    old_outbox = DATA / "Na iPhone"  # nazov z predchadzajucej verzie
    if old_outbox.is_dir() and not BOXES["outbox"].exists():
        old_outbox.rename(BOXES["outbox"])
    try:
        for folder in BOXES.values():
            folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Priečinok {DATA} sa nedá vytvoriť / Cannot create folder: {e}")
        print("Skontroluj filedrop_folder.txt / Check filedrop_folder.txt")
        return
    for stale in DATA.glob("*/.*.part"):
        stale.unlink(missing_ok=True)
    TOKEN = load_token()
    try:
        srv = Server(("0.0.0.0", PORT), Handler)
    except OSError:
        print(f"Port {PORT} je obsadený - FileDrop už pravdepodobne beží.")
        webbrowser.open(f"http://localhost:{PORT}/")
        return
    try:
        cert, key, CA_DER = tlscert.ensure(DATA / ".certs", lan_ips(), socket.gethostname())
        srv.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        srv.tls.minimum_version = ssl.TLSVersion.TLSv1_2
        srv.tls.load_cert_chain(cert, key)
    except (OSError, ValueError, ssl.SSLError) as e:
        srv.tls, CA_DER = None, b""
        print(f"  HTTPS nie je dostupné / HTTPS unavailable: {e}")
    for secret in (DATA / ".token", DATA / ".certs" / "ca.key", DATA / ".certs" / "server.key"):
        protect(secret)
    print("FileDrop pre Windows beží.")
    print(f"  Priečinok: {DATA}")
    if CA_DER:
        print(f"  Odtlačok certifikátu (SHA-256): {fingerprint(CA_DER)}")
    for ip in lan_ips():
        print(f"  Adresa pre iPhone: http://{ip}:{PORT}/?k={TOKEN}")
    print("  Ukonči Ctrl+C.\n")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.5, webbrowser.open, [f"http://localhost:{PORT}/"]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("Ukončené.")


if __name__ == "__main__":
    main()
