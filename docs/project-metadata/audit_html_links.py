from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# ============================================================
# CONFIG
# ============================================================

HTML_FILE = Path(r"\\bluemorpho\StatsWebsiteWritable\index.html")
WEB_ROOT = Path(r"\\bluemorpho\StatsWebsiteWritable")
BASE_URL = "https://stats.spotswoodtrailers.com.au/"

OUTPUT_CSV = WEB_ROOT / "html_link_audit_report.csv"

TIMEOUT = 12

# ============================================================
# LOAD HTML
# ============================================================

html = HTML_FILE.read_text(encoding="utf-8", errors="ignore")
soup = BeautifulSoup(html, "html.parser")

# ============================================================
# COLLECT LINKS
# ============================================================

items = []

def add_ref(tag, attr):
    value = tag.get(attr)
    if not value:
        return

    value = value.strip()

    if not value or value.startswith(("javascript:", "mailto:", "tel:", "data:")):
        return

    items.append({
        "tag": tag.name,
        "attr": attr,
        "ref": value,
        "text": tag.get_text(" ", strip=True)[:120],
    })

for tag in soup.find_all(True):
    for attr in ["href", "src", "poster"]:
        add_ref(tag, attr)

# Also catch common JS fetch/image path strings
for match in re.findall(r'["\']([^"\']+\.(?:json|csv|png|jpg|jpeg|gif|webp|mp4|html|py))["\']', html, flags=re.I):
    items.append({
        "tag": "script/text",
        "attr": "string",
        "ref": match,
        "text": "",
    })

# Deduplicate
seen = set()
unique = []
for item in items:
    key = (item["ref"], item["tag"], item["attr"])
    if key not in seen:
        seen.add(key)
        unique.append(item)

# ============================================================
# ANCHORS
# ============================================================

ids = set()
for tag in soup.find_all(True):
    if tag.get("id"):
        ids.add(tag["id"])

# ============================================================
# CHECK FUNCTIONS
# ============================================================

def is_external(url):
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and parsed.netloc not in ("", urlparse(BASE_URL).netloc)

def local_path_from_ref(ref):
    clean, frag = urldefrag(ref)

    parsed = urlparse(clean)

    if parsed.scheme in ("http", "https"):
        if parsed.netloc == urlparse(BASE_URL).netloc:
            rel = parsed.path.lstrip("/")
            return WEB_ROOT / rel
        return None

    if clean.startswith("#"):
        return None

    return WEB_ROOT / clean.lstrip("/")

def check_http(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=TIMEOUT)

        # Some servers block HEAD, so fallback to GET
        if r.status_code in (403, 405) or r.status_code >= 500:
            r = requests.get(url, stream=True, allow_redirects=True, timeout=TIMEOUT)

        return r.status_code, r.url, ""
    except Exception as e:
        return None, "", str(e)

# ============================================================
# AUDIT
# ============================================================

rows = []

for item in unique:
    ref = item["ref"]
    clean, frag = urldefrag(ref)

    status = "UNKNOWN"
    detail = ""
    local_exists = ""
    http_status = ""
    final_url = ""

    # Anchor-only link
    if ref.startswith("#"):
        anchor = ref[1:]
        if anchor in ids:
            status = "OK"
            detail = "Anchor exists"
        else:
            status = "BROKEN"
            detail = "Missing anchor id"
        rows.append({**item, "status": status, "detail": detail, "local_exists": local_exists, "http_status": http_status, "final_url": final_url})
        continue

    # Check fragment anchor on same/local page too
    if frag:
        if frag not in ids and (not clean or clean.endswith(HTML_FILE.name) or clean == BASE_URL):
            status = "BROKEN"
            detail = f"Missing fragment anchor #{frag}"

    local_path = local_path_from_ref(ref)

    if local_path is not None:
        local_exists = local_path.exists()

        if local_exists:
            if status != "BROKEN":
                status = "OK"
                detail = "Local file exists"
        else:
            status = "BROKEN"
            detail = "Local file missing"

        # Also check live URL
        live_url = urljoin(BASE_URL, clean.lstrip("/"))
        http_status, final_url, err = check_http(live_url)

        if err:
            detail += f" | HTTP error: {err}"
        elif http_status and http_status >= 400:
            status = "BROKEN"
            detail += f" | HTTP {http_status}"

    else:
        # External URL
        if is_external(ref):
            http_status, final_url, err = check_http(ref)
            if err:
                status = "ERROR"
                detail = err
            elif http_status and http_status < 400:
                status = "OK"
                detail = f"External HTTP {http_status}"
            else:
                status = "BROKEN"
                detail = f"External HTTP {http_status}"

    rows.append({
        **item,
        "status": status,
        "detail": detail,
        "local_exists": local_exists,
        "http_status": http_status,
        "final_url": final_url,
    })

# ============================================================
# OUTPUT
# ============================================================

df = pd.DataFrame(rows)
df = df.sort_values(["status", "ref"])

df.to_csv(OUTPUT_CSV, index=False)

print()
print("======================================")
print("HTML LINK AUDIT COMPLETE")
print("======================================")
print(f"Total checked : {len(df)}")
print(f"OK            : {(df['status'] == 'OK').sum()}")
print(f"BROKEN        : {(df['status'] == 'BROKEN').sum()}")
print(f"ERROR         : {(df['status'] == 'ERROR').sum()}")
print(f"UNKNOWN       : {(df['status'] == 'UNKNOWN').sum()}")
print()
print(f"Report written to:")
print(OUTPUT_CSV)
print()

if (df["status"] != "OK").any():
    print("Non-OK links:")
    print(df[df["status"] != "OK"][["status", "ref", "detail"]].to_string(index=False))