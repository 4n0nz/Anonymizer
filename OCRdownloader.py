#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCRdownloader.py — OpenClassrooms Offline Downloader
Télécharge vidéos + sous-titres d'un cours OC pour usage offline.

Dépendances :
    pip install yt-dlp requests beautifulsoup4

Usage :
    python OCRdownloader.py <url_du_cours>
    python OCRdownloader.py <url_du_cours> --list
    python OCRdownloader.py <url_du_cours> --quality 720
"""

import subprocess
import sys
import json
import shutil
import argparse
import time
import re
import tempfile
import os
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ======================
# IDENTIFIANTS
# ======================
# Les identifiants sont chargés depuis ocr_credentials.py (jamais pushé sur git)
# ou depuis les variables d'environnement OCR_USERNAME / OCR_PASSWORD.
# Créer ocr_credentials.py avec :
#   OCR_USERNAME = "votre_email"
#   OCR_PASSWORD = "votre_mot_de_passe"

import os as _os

try:
    from ocr_credentials import OCR_USERNAME, OCR_PASSWORD  # type: ignore
except ImportError:
    OCR_USERNAME = _os.environ.get("OCR_USERNAME", "")
    OCR_PASSWORD = _os.environ.get("OCR_PASSWORD", "")

# ======================
# CONFIGURATION
# ======================

DOWNLOAD_DIR   = Path("OCR_courses")
COOKIES_FILE   = "ocr_cookies.txt"
VIDEO_FORMAT   = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
SLEEP_INTERVAL = 2
MAX_RETRIES    = 5
SUBTITLE_LANGS = "fr,en"

OCR_BASE = "https://openclassrooms.com"
OCR_API  = "https://api.openclassrooms.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Origin":          OCR_BASE,
    "Referer":         OCR_BASE + "/",
}

# ======================
# VÉRIFICATIONS
# ======================

def check_dependencies():
    if not shutil.which("yt-dlp"):
        print("[ERREUR] yt-dlp introuvable — pip install yt-dlp")
        sys.exit(1)
    if not REQUESTS_OK:
        print("[ERREUR] requests/beautifulsoup4 introuvable — pip install requests beautifulsoup4")
        sys.exit(1)

# ======================
# NORMALISATION URL
# ======================

def normalize_course_url(url):
    """Extrait l'URL du cours (sans l'activité spécifique)."""
    m = re.match(r"(https://openclassrooms\.com/[^/]+/courses/\d+[^/?#]*)", url)
    if m:
        return m.group(1)
    return url

def extract_course_id(url):
    m = re.search(r"/courses/(\d+)", url)
    return m.group(1) if m else None

def extract_lang(url):
    m = re.search(r"openclassrooms\.com/([^/]+)/", url)
    return m.group(1) if m else "fr"

# ======================
# LOGIN OPENCLASSROOMS
# ======================

def login_openclassrooms(username, password):
    """
    Login à OpenClassrooms via leur API REST.
    Retourne une session requests authentifiée, ou None si échec.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"[AUTH] Connexion à OpenClassrooms ({username})...")

    # ── Étape 1 : récupérer le token CSRF ──
    try:
        resp = session.get(f"{OCR_BASE}/fr/login", timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        csrf = None
        for tag in soup.find_all(["input", "meta"]):
            name = tag.get("name", "")
            if "csrf" in name.lower() or "token" in name.lower():
                csrf = tag.get("value") or tag.get("content")
                break
    except Exception as e:
        print(f"[AUTH] Impossible d'accéder à la page login : {e}")
        return None

    # ── Étape 2 : tentative login via plusieurs endpoints ──
    login_endpoints = [
        {
            "url":    f"{OCR_BASE}/login_check",
            "method": "post",
            "data":   {"_username": username, "_password": password,
                       **({"_csrf_token": csrf} if csrf else {})},
        },
        {
            "url":    f"{OCR_BASE}/api/v2/login",
            "method": "post",
            "json":   {"email": username, "password": password},
        },
        {
            "url":    f"{OCR_BASE}/api/v2/auth",
            "method": "post",
            "json":   {"username": username, "password": password},
        },
        {
            "url":    f"{OCR_API}/users/me",
            "method": "post",
            "json":   {"username": username, "password": password},
        },
    ]

    for ep in login_endpoints:
        try:
            if "json" in ep:
                r = session.post(ep["url"], json=ep["json"], timeout=15, allow_redirects=True)
            else:
                r = session.post(ep["url"], data=ep["data"], timeout=15, allow_redirects=True)

            if r.status_code in (200, 302):
                if any(k in session.cookies for k in
                       ["PHPSESSID", "REMEMBERME", "token", "session", "auth"]):
                    print(f"[AUTH] ✓ Connecté via {ep['url']}")
                    return session
                try:
                    data = r.json()
                    if "token" in data or "access_token" in data:
                        token = data.get("token") or data.get("access_token")
                        session.headers["Authorization"] = f"Bearer {token}"
                        print(f"[AUTH] ✓ Token JWT obtenu via {ep['url']}")
                        return session
                except Exception:
                    pass
        except Exception:
            continue

    # ── Étape 3 : vérification via le dashboard ──
    try:
        r = session.get(f"{OCR_BASE}/fr/dashboard", timeout=15, allow_redirects=True)
        if "login" not in r.url and r.status_code == 200:
            print("[AUTH] ✓ Session active détectée")
            return session
    except Exception:
        pass

    print("[AUTH] ✗ Échec de la connexion automatique.")
    print("         → Essayez avec --cookies ocr_cookies.txt")
    print("           (installer l'extension 'Get cookies.txt LOCALLY' dans Chrome)")
    return None


def session_to_cookies_file(session, path):
    """Sauvegarde les cookies d'une session requests en format Netscape."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in session.cookies:
            secure  = "TRUE" if c.secure else "FALSE"
            expires = str(int(c.expires)) if c.expires else "0"
            domain  = c.domain or "openclassrooms.com"
            dot     = "TRUE" if domain.startswith(".") else "FALSE"
            f.write(f"{domain}\t{dot}\t{c.path or '/'}\t"
                    f"{secure}\t{expires}\t{c.name}\t{c.value}\n")
        if "Authorization" in session.headers:
            token = session.headers["Authorization"].replace("Bearer ", "")
            f.write(f".openclassrooms.com\tTRUE\t/\tFALSE\t0\ttoken\t{token}\n")


# ======================
# FETCH ACTIVITIES
# ======================

def fetch_activities(course_url, session):
    """
    Retourne (list[dict], course_title).
    Chaque dict : {"index": int, "title": str, "url": str}

    Stratégie 1 : API REST openclassrooms.com
    Stratégie 2 : __NEXT_DATA__ JSON dans la page HTML
    Stratégie 3 : Scraping des liens <a>
    """
    course_id = extract_course_id(course_url)
    lang      = extract_lang(course_url)

    if not course_id:
        return [], "Cours inconnu"

    # ── Stratégie 1 : API REST ──
    try:
        r = session.get(f"{OCR_API}/courses/{course_id}", timeout=15)
        if r.status_code == 200:
            data         = r.json()
            course_title = data.get("title") or data.get("name") or f"Course {course_id}"
            course_slug  = data.get("slug") or str(course_id)

            activities = []
            idx = 1
            parts = data.get("parts") or data.get("chapters") or []
            for part in parts:
                for act in (part.get("activities") or part.get("lessons") or []):
                    act_id   = act.get("id") or act.get("activityId")
                    act_slug = act.get("slug") or str(act_id)
                    title    = act.get("title") or act.get("name") or f"Activité {idx}"
                    if act_id:
                        url = (f"{OCR_BASE}/{lang}/courses/"
                               f"{course_id}-{course_slug}/"
                               f"{act_id}-{act_slug}")
                        activities.append({"index": idx, "title": title, "url": url})
                        idx += 1

            if activities:
                print(f"[INFO] {len(activities)} activité(s) trouvée(s) via API REST")
                return activities, course_title
    except Exception:
        pass

    # ── Stratégie 2 : __NEXT_DATA__ ──
    try:
        r    = session.get(course_url, timeout=20)
        m_nd = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            r.text, re.DOTALL
        )
        if m_nd:
            nd = json.loads(m_nd.group(1))

            # Cherche récursivement des tableaux "activities"
            collected = []

            def _walk(obj, depth=0):
                if depth > 15 or not isinstance(obj, (dict, list)):
                    return
                if isinstance(obj, list):
                    for item in obj:
                        _walk(item, depth + 1)
                    return
                if "activities" in obj and isinstance(obj["activities"], list):
                    for act in obj["activities"]:
                        if isinstance(act, dict) and (act.get("id") or act.get("activityId")):
                            collected.append(act)
                for v in obj.values():
                    _walk(v, depth + 1)

            _walk(nd)

            if collected:
                seen_ids   = set()
                activities = []
                idx        = 1
                # Get course slug from the original URL
                cs_m = re.search(r"/courses/\d+(-[^/]+)?", course_url)
                cs   = cs_m.group(1) or "" if cs_m else ""

                for act in collected:
                    act_id = act.get("id") or act.get("activityId")
                    if act_id in seen_ids:
                        continue
                    seen_ids.add(act_id)

                    title    = act.get("title") or act.get("name") or f"Activité {idx}"
                    act_slug = act.get("slug") or str(act_id)
                    url      = act.get("url") or act.get("path") or act.get("href")

                    if url:
                        if not url.startswith("http"):
                            url = OCR_BASE + url
                    else:
                        url = (f"{OCR_BASE}/{lang}/courses/"
                               f"{course_id}{cs}/{act_id}-{act_slug}")

                    activities.append({"index": idx, "title": title, "url": url})
                    idx += 1

                if activities:
                    props        = nd.get("props", {}).get("pageProps", {})
                    course_data  = props.get("course") or props.get("courseData") or {}
                    course_title = course_data.get("title") or f"Course {course_id}"
                    print(f"[INFO] {len(activities)} activité(s) trouvée(s) via __NEXT_DATA__")
                    return activities, course_title
    except Exception:
        pass

    # ── Stratégie 3 : Scraping <a> ──
    try:
        r    = session.get(course_url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        pattern = re.compile(rf"/[^/]+/courses/{course_id}[^/]*/(\d+)")
        seen       = set()
        activities = []
        idx        = 1

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].split("?")[0].split("#")[0]
            if pattern.search(href):
                full_url = (OCR_BASE + href) if href.startswith("/") else href
                if full_url not in seen:
                    seen.add(full_url)
                    text = a_tag.get_text(strip=True) or f"Activité {idx}"
                    activities.append({"index": idx, "title": text[:120], "url": full_url})
                    idx += 1

        if activities:
            print(f"[INFO] {len(activities)} activité(s) trouvée(s) via scraping HTML")
            return activities, f"Course {course_id}"
    except Exception:
        pass

    print("[WARN] Impossible de récupérer la liste des activités")
    return [], f"Course {course_id}"


# ======================
# ARGS YT-DLP COMMUNS
# ======================

def _yt_dlp_common(cookies_path, quality):
    """Arguments yt-dlp communs à tous les appels."""
    fmt = VIDEO_FORMAT if quality == "best" else f"best[height<={quality}]"
    return [
        "--format",              fmt,
        "--merge-output-format", "mp4",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",           SUBTITLE_LANGS,
        "--embed-subs",
        "--write-thumbnail",
        "--embed-thumbnail",
        "--retries",             str(MAX_RETRIES),
        "--fragment-retries",    str(MAX_RETRIES),
        "--sleep-interval",      str(SLEEP_INTERVAL),
        "--continue",
        "--no-overwrites",
        "--progress",
        "--cookies",             cookies_path,
        "--add-header",          f"Referer: {OCR_BASE}/",
        # Évite l'erreur "macOS API 404" sur les vidéos Vimeo embarquées
        "--extractor-args",      "vimeo:api_token_source=none",
    ]


# ======================
# TÉLÉCHARGEMENT
# ======================

def download_videos(course_url, session, cookies_path, output_dir, quality="best"):
    """
    Télécharge toutes les vidéos d'un cours.
    Si les activités sont trouvées via l'API → téléchargement par activité.
    Sinon → fallback mode playlist yt-dlp.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    activities   = []
    course_title = ""

    if session:
        activities, course_title = fetch_activities(course_url, session)

    # Sous-dossier nommé d'après le titre du cours
    safe_title = re.sub(r'[<>:"/\\|?*]', "", course_title).strip() or "cours"
    course_dir = output_dir / safe_title
    course_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[*] Cours : {course_title or course_url}")
    print(f"    Destination : {course_dir.resolve()}\n")

    if not activities:
        # Fallback : yt-dlp en mode playlist
        print("[*] Aucune activité trouvée → mode playlist yt-dlp...\n")
        out_tmpl = str(course_dir / "%(playlist_index|00)02d - %(title)s.%(ext)s")
        cmd = (
            ["yt-dlp", "--yes-playlist", "--output", out_tmpl]
            + _yt_dlp_common(cookies_path, quality)
            + [course_url]
        )
        result = subprocess.run(cmd)
        return result.returncode == 0

    # Téléchargement activité par activité
    print(f"[*] {len(activities)} activité(s) à télécharger\n")
    ok_count = 0

    for act in activities:
        idx   = act["index"]
        title = act["title"]
        url   = act["url"]

        safe     = re.sub(r'[<>:"/\\|?*]', "", title)[:80].strip() or f"activite_{idx}"
        out_tmpl = str(course_dir / f"{idx:02d} - {safe}.%(ext)s")

        print(f"  [{idx:02d}/{len(activities):02d}] {title}")

        cmd = (
            ["yt-dlp", "--output", out_tmpl]
            + _yt_dlp_common(cookies_path, quality)
            + [url]
        )

        result = subprocess.run(cmd)
        if result.returncode == 0:
            ok_count += 1
        else:
            print(f"           → [WARN] Échec pour cette activité")

        if idx < len(activities):
            time.sleep(SLEEP_INTERVAL)

    print(f"\n  ✓ {ok_count}/{len(activities)} activité(s) téléchargée(s)")
    return ok_count > 0


# ======================
# LISTE DES LEÇONS
# ======================

def list_lessons(course_url, session, cookies_path):
    """Retourne la liste des activités d'un cours."""
    # Priorité à l'API
    if session:
        activities, _ = fetch_activities(course_url, session)
        if activities:
            return activities

    # Fallback yt-dlp --flat-playlist
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(playlist_index)s|%(title)s|%(webpage_url)s",
        "--no-warnings",
        "--cookies", cookies_path,
        "--add-header", f"Referer: {OCR_BASE}/",
        "--extractor-args", "vimeo:api_token_source=none",
        course_url,
    ]
    result  = subprocess.run(cmd, capture_output=True, text=True)
    lessons = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            idx, title, url = parts
            lessons.append({
                "index": idx.strip(),
                "title": title.strip(),
                "url":   url.strip(),
            })
    return lessons


# ======================
# MISE À JOUR yt-dlp
# ======================

def update_yt_dlp():
    print("[*] Mise à jour de yt-dlp...")
    subprocess.run(["yt-dlp", "--update"], check=False)
    print()


# ======================
# MAIN
# ======================

def main():
    parser = argparse.ArgumentParser(
        description="OpenClassrooms Offline Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url",              help="URL du cours OpenClassrooms")
    parser.add_argument("--username", "-u", default=OCR_USERNAME)
    parser.add_argument("--password", "-p", default=OCR_PASSWORD)
    parser.add_argument("--cookies",        default=None,
                        help="Fichier cookies Netscape (bypass le login auto)")
    parser.add_argument("--output",  "-o",  default=str(DOWNLOAD_DIR))
    parser.add_argument("--quality",        default="best",
                        help="best | 1080 | 720 | 480")
    parser.add_argument("--list",           action="store_true",
                        help="Liste les leçons sans télécharger")
    parser.add_argument("--update",         action="store_true",
                        help="Mettre à jour yt-dlp avant de télécharger")

    args = parser.parse_args()

    print()
    print("  ╔═══════════════════════════════════════════╗")
    print("  ║   OpenClassrooms Offline Downloader       ║")
    print("  ╚═══════════════════════════════════════════╝")
    print()

    check_dependencies()

    if args.update:
        update_yt_dlp()

    course_url = normalize_course_url(args.url)
    if course_url != args.url:
        print(f"[URL] Normalisée → {course_url}")

    output_dir = Path(args.output)

    # ── Obtenir les cookies ──
    tmp_cookies = None
    session     = None

    if args.cookies and Path(args.cookies).exists():
        cookies_path = args.cookies
        print(f"[AUTH] Cookies depuis fichier : {cookies_path}")
    elif Path(COOKIES_FILE).exists():
        cookies_path = COOKIES_FILE
        print(f"[AUTH] Cookies depuis fichier par défaut : {cookies_path}")
    else:
        session = login_openclassrooms(args.username, args.password)
        if session is None:
            print("\n[ERREUR] Impossible de se connecter.")
            sys.exit(1)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                          delete=False, prefix="ocr_")
        tmp_cookies = tmp.name
        tmp.close()
        session_to_cookies_file(session, tmp_cookies)
        cookies_path = tmp_cookies
        print("[AUTH] Cookies sauvegardés temporairement")

    try:
        if args.list:
            print(f"\n[*] Récupération de la liste des leçons...")
            lessons = list_lessons(course_url, session, cookies_path)
            if not lessons:
                print("[ERREUR] Aucune leçon trouvée.")
                sys.exit(1)
            print(f"\n    {len(lessons)} leçon(s) :\n")
            for l in lessons:
                print(f"    {str(l['index']):>3}. {l['title']}")
            print()
            return

        success = download_videos(course_url, session, cookies_path, output_dir, args.quality)

        if not success:
            print("\n[ERREUR] Téléchargement échoué.")
            print("  → Si l'erreur persiste, exportez les cookies manuellement :")
            print("    1. Installer 'Get cookies.txt LOCALLY' dans Chrome")
            print("    2. Exporter depuis openclassrooms.com → ocr_cookies.txt")
            print("    3. Relancer avec --cookies ocr_cookies.txt")
            sys.exit(1)

        print(f"\n  ✓ Terminé ! Fichiers dans : {output_dir.resolve()}\n")

    finally:
        if tmp_cookies and os.path.exists(tmp_cookies):
            os.remove(tmp_cookies)


if __name__ == "__main__":
    main()
