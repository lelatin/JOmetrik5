"""
JOMetrik (version GitHub Pages) — scraper exécuté par GitHub Actions.
Produit des fichiers JSON statiques lus par le site :
  data/prices.json   (--prices)   data/news.json   (--news)
Les scrapers Selenium et le flux RSS sont repris tels quels de app.py.
"""
import re, time, json, argparse, hashlib, random
import requests as http_requests
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET
from email.utils import parsedate_to_datetime

try:  # inutile pour le mode --news
    from selenium import webdriver as selenium_webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import NoSuchElementException
    import undetected_chromedriver as uc
except ImportError:
    selenium_webdriver = None

from games_db import GAMES_DB

DATA = Path(__file__).resolve().parent.parent / "data"

# ─── Sources d'actualités ─────────────────────────────────────────────────────
NEWS_SOURCES = {
    "xboxygen": {
        "name":    "Xboxygen",
        "rss_url": "https://www.xboxygen.com/feed",
        "color":   "#52b043",
        "type":    "rss",
    },
    "actugaming": {
        "name":    "ActuGaming",
        "rss_url": "https://www.actugaming.net/feed",
        "color":   "#e63946",
        "type":    "rss",
    },
    "youtube": {
        "name":       "Origatube",
        # Flux RSS public YouTube — pas besoin de clé API
        "rss_url":    "https://www.youtube.com/feeds/videos.xml?channel_id=UCT-9GBbcYNAkpQBnxpRhzBw",
        "color":      "#ff0000",
        "type":       "youtube",
    },
}

# ─── Config Selenium ──────────────────────────────────────────────────────────
def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    driver = selenium_webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(20)
    return driver


def make_uc_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    driver = uc.Chrome(options=opts, headless=True)
    driver.set_page_load_timeout(25)
    return driver


def safe_text(el, selector):
    try:
        return el.find_element(By.CSS_SELECTOR, selector).text.strip()
    except NoSuchElementException:
        return ""


def parse_price(text):
    text = text.replace("\xa0", "").replace(" ", "")
    m = re.search(r"[\d]+[.,][\d]+", text)
    if m:
        return float(m.group().replace(",", "."))
    m = re.search(r"[\d]+", text)
    if m:
        return float(m.group())
    return None


# ─── Scrapers (inchangés) ─────────────────────────────────────────────────────
def scrape_instant_gaming(driver, game):
    results = []
    try:
        url = f"https://www.instant-gaming.com/fr/rechercher/?query={quote_plus(game)}"
        driver.get(url)
        time.sleep(2)
        items = driver.find_elements(By.CSS_SELECTOR, ".item.maingame")[:6]
        for item in items:
            try:
                title = safe_text(item, ".title")
                if not title or game.lower()[:6] not in title.lower():
                    continue
                price_el = safe_text(item, ".price")
                price    = parse_price(price_el)
                if price is None:
                    continue
                platform = "PC"
                try:
                    plat_img = item.find_element(By.CSS_SELECTOR, ".platform img")
                    alt = plat_img.get_attribute("alt") or ""
                    if "playstation" in alt.lower() or "ps" in alt.lower():
                        platform = "PlayStation"
                    elif "xbox" in alt.lower():
                        platform = "Xbox"
                    elif "nintendo" in alt.lower() or "switch" in alt.lower():
                        platform = "Nintendo"
                except NoSuchElementException:
                    pass
                discount = 0
                try:
                    pct = safe_text(item, ".discount")
                    m   = re.search(r"\d+", pct)
                    if m:
                        discount = int(m.group())
                except Exception:
                    pass
                link = item.find_element(By.CSS_SELECTOR, "a").get_attribute("href") or url
                results.append({
                    "store": "Instant Gaming", "platform": platform,
                    "type": f"{platform} Key", "price": price,
                    "discount": discount, "url": link, "available": True,
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[Instant Gaming] Error: {e}")
    return results


def scrape_kinguin(driver, game):
    results = []
    try:
        url = f"https://www.kinguin.net/catalogsearch/result/?q={quote_plus(game)}"
        driver.get(url)
        time.sleep(2)
        items = driver.find_elements(By.CSS_SELECTOR, ".product-inner")[:6]
        for item in items:
            try:
                title = safe_text(item, ".product-title")
                if not title or game.lower()[:5] not in title.lower():
                    continue
                if any(w in title.lower() for w in ["account", "compte", "smurf", "boosted"]):
                    continue
                price_text = safe_text(item, ".product-price")
                price      = parse_price(price_text)
                if price is None:
                    continue
                platform = "PC"
                title_l  = title.lower()
                if "ps4" in title_l or "ps5" in title_l or "playstation" in title_l:
                    platform = "PlayStation"
                elif "xbox" in title_l:
                    platform = "Xbox"
                elif "nintendo" in title_l or "switch" in title_l:
                    platform = "Nintendo"
                key_type = "Steam Key"
                if "gog" in title_l:       key_type = "GOG Key"
                elif "xbox" in title_l:    key_type = "Xbox Key"
                elif "ps4" in title_l or "ps5" in title_l: key_type = "PlayStation Code"
                elif "nintendo" in title_l or "switch" in title_l: key_type = "Nintendo eShop Code"
                elif "epic" in title_l:    key_type = "Epic Games Key"
                link = item.find_element(By.CSS_SELECTOR, "a").get_attribute("href") or url
                results.append({
                    "store": "Kinguin", "platform": platform,
                    "type": key_type, "price": price,
                    "discount": 0, "url": link, "available": True,
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[Kinguin] Error: {e}")
    return results


def scrape_eneba(driver, game):
    results = []
    try:
        url = f"https://www.eneba.com/fr/store/games?text={quote_plus(game)}"
        driver.get(url)
        time.sleep(2)
        items = driver.find_elements(By.CSS_SELECTOR, "[data-testid='product-card']")[:6]
        if not items:
            items = driver.find_elements(By.CSS_SELECTOR, ".T3g9E")[:6]
        for item in items:
            try:
                title = safe_text(item, "h3") or safe_text(item, "span")
                if not title or game.lower()[:5] not in title.lower():
                    continue
                if any(w in title.lower() for w in ["account", "compte", "smurf"]):
                    continue
                price_text = safe_text(item, "[class*='price']") or safe_text(item, "[class*='Price']")
                price = parse_price(price_text)
                if price is None:
                    continue
                platform = "PC"
                title_l  = title.lower()
                if "ps4" in title_l or "ps5" in title_l or "playstation" in title_l:
                    platform = "PlayStation"
                elif "xbox" in title_l:
                    platform = "Xbox"
                elif "nintendo" in title_l or "switch" in title_l:
                    platform = "Nintendo"
                link = url
                try:
                    link = item.find_element(By.CSS_SELECTOR, "a").get_attribute("href") or url
                except Exception:
                    pass
                results.append({
                    "store": "Eneba", "platform": platform,
                    "type": "Steam Key" if platform == "PC" else f"{platform} Code",
                    "price": price, "discount": 0, "url": link, "available": True,
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[Eneba] Error: {e}")
    return results


def scrape_gog(driver, game):
    results = []
    try:
        url = f"https://www.gog.com/en/games?query={quote_plus(game)}"
        driver.get(url)
        time.sleep(2)
        items = driver.find_elements(By.CSS_SELECTOR, "product-tile, .product-tile")[:4]
        for item in items:
            try:
                title = safe_text(item, ".product-title__text") or safe_text(item, "a")
                if not title or game.lower()[:5] not in title.lower():
                    continue
                price_text = safe_text(item, ".final-value") or safe_text(item, "[class*='price']")
                price = parse_price(price_text)
                if price is None:
                    continue
                link = url
                try:
                    link = item.find_element(By.CSS_SELECTOR, "a").get_attribute("href") or url
                except Exception:
                    pass
                results.append({
                    "store": "GOG", "platform": "PC", "type": "GOG Key",
                    "price": price, "discount": 0, "url": link, "available": True,
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[GOG] Error: {e}")
    return results


def scrape_steam(driver, game):
    results = []
    try:
        url = f"https://store.steampowered.com/search/?term={quote_plus(game)}&category1=998"
        driver.get(url)
        time.sleep(2)
        items = driver.find_elements(By.CSS_SELECTOR, "#search_resultsRows a.search_result_row")[:4]
        for item in items:
            try:
                title = safe_text(item, ".title")
                if not title or game.lower()[:5] not in title.lower():
                    continue
                price_text = (
                    safe_text(item, ".discount_final_price") or
                    safe_text(item, ".search_price")
                )
                price = parse_price(price_text)
                if price is None:
                    continue
                discount = 0
                try:
                    pct = safe_text(item, ".discount_pct")
                    m   = re.search(r"\d+", pct)
                    if m:
                        discount = int(m.group())
                except Exception:
                    pass
                link = item.get_attribute("href") or url
                results.append({
                    "store": "Steam", "platform": "PC", "type": "Steam Key",
                    "price": price, "discount": discount, "url": link, "available": True,
                })
                break
            except Exception:
                continue
    except Exception as e:
        print(f"[Steam] Error: {e}")
    return results


def scrape_xbox(driver, game):
    results = []
    try:
        url = f"https://www.xbox.com/fr-FR/search?q={quote_plus(game)}"
        driver.get(url)
        time.sleep(3)
        items = driver.find_elements(
            By.CSS_SELECTOR,
            "[class*='SearchResultCard'], [class*='ProductCard'], [class*='gameCard']"
        )[:4]
        for item in items:
            try:
                title = safe_text(item, "[class*='title'], [class*='Title'], h3, h4")
                if not title or game.lower()[:4] not in title.lower():
                    continue
                price_text = safe_text(item, "[class*='price'], [class*='Price']")
                price = parse_price(price_text)
                if price is None:
                    continue
                link = url
                try:
                    link = item.find_element(By.CSS_SELECTOR, "a").get_attribute("href") or url
                except Exception:
                    pass
                results.append({
                    "store": "Xbox", "platform": "Xbox", "type": "Xbox Key",
                    "price": price, "discount": 0, "url": link, "available": True,
                })
                break
            except Exception:
                continue
    except Exception as e:
        print(f"[Xbox] Error: {e}")
    return results


def scrape_epic(driver, game):
    results = []
    try:
        url = f"https://store.epicgames.com/fr/browse?q={quote_plus(game)}&sortBy=relevancy&sortDir=DESC&count=10"
        driver.get(url)
        time.sleep(3)
        items = driver.find_elements(
            By.CSS_SELECTOR,
            "[data-component='CardGrid'] a, [class*='ProductCard'] a"
        )[:6]
        for item in items:
            try:
                title = safe_text(item, "[class*='title'], [class*='Title'], span")
                if not title or game.lower()[:4] not in title.lower():
                    continue
                if any(w in title.lower() for w in ["account", "compte", "smurf", "boosted"]):
                    continue
                price_text = safe_text(item, "[class*='price'], [class*='Price']")
                price = parse_price(price_text)
                if price is None:
                    continue
                link = item.get_attribute("href") or url
                if link and not link.startswith("http"):
                    link = "https://store.epicgames.com" + link
                results.append({
                    "store": "Epic Games", "platform": "PC", "type": "Epic Games Key",
                    "price": price, "discount": 0, "url": link, "available": True,
                })
                break
            except Exception:
                continue
    except Exception as e:
        print(f"[Epic Games] Error: {e}")
    return results


# ─── Fallback (données déterministes si scrape échoue) ───────────────────────
FALLBACK_STORES = [
    ("Steam",          "PC",          "Steam Key",           [19.99, 29.99, 39.99, 49.99, 59.99]),
    ("GOG",            "PC",          "GOG Key",             [17.99, 27.99, 37.99, 47.99]),
    ("Epic Games",     "PC",          "Epic Games Key",      [19.99, 29.99, 39.99, 49.99]),
    ("Instant Gaming", "PC",          "Steam Key",           [12.99, 17.99, 24.99, 34.99]),
    ("Instant Gaming", "PlayStation", "PlayStation Code",    [22.99, 32.99, 42.99, 54.99]),
    ("Instant Gaming", "Xbox",        "Xbox Key",            [19.99, 29.99, 39.99, 49.99]),
    ("Kinguin",        "PC",          "Steam Key",           [10.99, 16.99, 22.99, 31.99]),
    ("Kinguin",        "PlayStation", "PlayStation Code",    [19.99, 29.99, 39.99, 49.99]),
    ("Kinguin",        "Xbox",        "Xbox Key",            [17.99, 27.99, 37.99, 47.99]),
    ("Kinguin",        "Nintendo",    "Nintendo eShop Code", [32.99, 42.99, 52.99]),
    ("Eneba",          "PC",          "Steam Key",           [11.49, 18.49, 25.49, 33.49]),
    ("Eneba",          "PlayStation", "PlayStation Code",    [20.49, 31.49, 41.49, 51.49]),
    ("Eneba",          "Xbox",        "Xbox Key",            [18.49, 28.49, 38.49]),
    ("Eneba",          "Nintendo",    "Nintendo eShop Code", [33.49, 43.49, 53.49]),
    ("Xbox",           "Xbox",        "Xbox Key",            [24.99, 34.99, 44.99, 59.99]),
    ("Xbox",           "PC",          "Xbox PC Key",         [19.99, 29.99, 39.99, 49.99]),
]


def fallback_prices(game: str) -> list:
    seed = int(hashlib.md5(game.lower().encode()).hexdigest(), 16) % 10000
    rng  = random.Random(seed)
    results = []
    for store, platform, key_type, price_pool in FALLBACK_STORES:
        if rng.random() < 0.15:
            continue
        base  = rng.choice(price_pool)
        disc  = rng.choice([0, 0, 0, 10, 15, 20, 25, 30, 40, 50])
        price = round(base * (1 - disc / 100), 2) if disc else base
        url_q = quote_plus(game)
        urls  = {
            "Steam":          f"https://store.steampowered.com/search/?term={url_q}",
            "GOG":            f"https://www.gog.com/en/games?query={url_q}",
            "Epic Games":     f"https://store.epicgames.com/fr/browse?q={url_q}&sortBy=relevancy&sortDir=DESC&count=10",
            "Instant Gaming": f"https://www.instant-gaming.com/fr/rechercher/?query={url_q}",
            "Kinguin":        f"https://www.kinguin.net/catalogsearch/result/?q={quote_plus(game + ' ' + platform)}",
            "Eneba":          f"https://www.eneba.com/fr/store/games?text={quote_plus(game + ' ' + platform)}",
            "Xbox":           f"https://www.xbox.com/fr-FR/search?q={url_q}",
        }
        results.append({
            "store": store, "platform": platform, "type": key_type,
            "price": price, "originalPrice": base if disc else None,
            "discount": disc, "url": urls.get(store, "#"), "available": True,
            "simulated": True,
        })
    return results



# ─── News ─────────────────────────────────────────────────────────────────────
def _relative_time(dt: datetime) -> str:
    """Retourne une chaîne relative lisible ('il y a 2h', 'hier', etc.)"""
    diff = datetime.now() - dt
    secs = int(diff.total_seconds())
    if secs < 60:
        return "à l'instant"
    if secs < 3600:
        m = secs // 60
        return f"il y a {m} min"
    if secs < 86400:
        h = secs // 3600
        return f"il y a {h}h"
    if secs < 172800:
        return "hier"
    d = secs // 86400
    return f"il y a {d}j"


def _parse_rss_date(date_str: str) -> datetime | None:
    """Parse une date RSS (RFC 2822 ou ISO 8601) en datetime naïf local."""
    if not date_str:
        return None
    try:
        # RFC 2822 — format standard RSS (ex: "Mon, 12 May 2025 10:00:00 +0000")
        dt = parsedate_to_datetime(date_str)
        # Convertir en naïf UTC puis supprimer tzinfo pour homogénéité
        return dt.replace(tzinfo=None)
    except Exception:
        pass
    try:
        # ISO 8601 — format Atom / YouTube (ex: "2025-05-12T10:00:00+00:00")
        ds = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ds)
        return dt.replace(tzinfo=None)
    except Exception:
        return None


def fetch_rss(source_id: str, source_cfg: dict, max_items: int = 8) -> list:
    """
    Télécharge et parse un flux RSS ou Atom (YouTube inclus).
    Retourne une liste de dicts article normalisés.
    """
    rss_url = source_cfg["rss_url"]
    is_yt   = source_cfg.get("type") == "youtube"
    articles = []

    try:
        resp = http_requests.get(rss_url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (compatible; JOMetrik/1.0)",
            "Accept":     "application/rss+xml, application/xml, text/xml, */*",
        })
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        ns   = {
            "atom":    "http://www.w3.org/2005/Atom",
            "media":   "http://search.yahoo.com/mrss/",
            "content": "http://purl.org/rss/1.0/modules/content/",
        }

        # ── YouTube / Atom ────────────────────────────────────────────────────
        if is_yt or root.tag in ("{http://www.w3.org/2005/Atom}feed", "feed"):
            entries = root.findall("atom:entry", ns) or root.findall("entry")
            for entry in entries[:max_items]:
                def _t(tag):
                    el = entry.find(f"atom:{tag}", ns) or entry.find(tag)
                    return el.text.strip() if el is not None and el.text else ""

                title    = _t("title")
                url      = ""
                link_el  = entry.find("atom:link", ns) or entry.find("link")
                if link_el is not None:
                    url = link_el.get("href", "") or (link_el.text or "")

                pub_str  = _t("published") or _t("updated")
                pub_dt   = _parse_rss_date(pub_str)

                # Thumbnail YouTube via media:group/media:thumbnail
                image = ""
                mg = entry.find("media:group", ns)
                if mg is not None:
                    th = mg.find("media:thumbnail", ns)
                    if th is not None:
                        image = th.get("url", "")
                if not image:
                    th = entry.find("media:thumbnail", ns)
                    if th is not None:
                        image = th.get("url", "")

                if title and url:
                    articles.append({
                        "title":         title,
                        "url":           url,
                        "image":         image,
                        "pub_ts":        int(pub_dt.timestamp()) if pub_dt else 0,
                        "relative_time": _relative_time(pub_dt) if pub_dt else "",
                        "source":        source_cfg["name"],
                    })

        # ── RSS 2.0 standard ─────────────────────────────────────────────────
        else:
            channel = root.find("channel")
            items   = (channel or root).findall("item")
            for item in items[:max_items]:
                def _f(tag):
                    el = item.find(tag)
                    return el.text.strip() if el is not None and el.text else ""

                title   = _f("title")
                url     = _f("link")
                pub_str = _f("pubDate")
                pub_dt  = _parse_rss_date(pub_str)

                # Image : media:content, enclosure, ou og dans content:encoded
                image = ""
                mc = item.find("media:content", ns)
                if mc is not None:
                    image = mc.get("url", "")
                if not image:
                    enc = item.find("enclosure")
                    if enc is not None and (enc.get("type", "").startswith("image")):
                        image = enc.get("url", "")
                if not image:
                    # Chercher dans content:encoded
                    ce = item.find("content:encoded", ns)
                    if ce is not None and ce.text:
                        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', ce.text)
                        if m:
                            image = m.group(1)

                if title and url:
                    articles.append({
                        "title":         title,
                        "url":           url,
                        "image":         image,
                        "pub_ts":        int(pub_dt.timestamp()) if pub_dt else 0,
                        "relative_time": _relative_time(pub_dt) if pub_dt else "",
                        "source":        source_cfg["name"],
                    })

    except Exception as e:
        print(f"[News] Erreur fetch '{source_id}': {e}")

    return articles


# ─── Scrape d'un jeu (même logique que app.py, sans SQLite) ──────────────────
def scrape_game(game):
    results = []
    try:
        driver = make_driver()
        for s in [scrape_steam, scrape_gog, scrape_epic, scrape_xbox]:
            try: results.extend(s(driver, game))
            except Exception as e: print(f"  {s.__name__}: {e}")
        driver.quit()
    except Exception as e:
        print(f"  [Driver standard] {e}")
    try:
        uc_driver = make_uc_driver()
        for s in [scrape_instant_gaming, scrape_kinguin, scrape_eneba]:
            try: results.extend(s(uc_driver, game))
            except Exception as e: print(f"  {s.__name__}: {e}")
        uc_driver.quit()
    except Exception as e:
        print(f"  [Driver UC] {e}")
    found = {r["store"] for r in results}
    missing = {"Steam","GOG","Epic Games","Instant Gaming","Kinguin","Eneba","Xbox"} - found
    for fb in fallback_prices(game):
        if fb["store"] in missing:
            results.append(fb)
    seen, out = set(), []
    for r in results:
        k = (r["store"], r["platform"])
        if k not in seen:
            seen.add(k); out.append(r)
    return out


def fetch_game_image(game):
    try:
        r = http_requests.get(f"https://store.steampowered.com/api/storesearch/?term={quote_plus(game)}&l=french&cc=FR",
                              timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        items = r.json().get("items", [])
        if items:
            return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{items[0]['id']}/header.jpg"
    except Exception as e:
        print(f"  [Image] {e}")
    return ""


def load(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default


def run_prices(only, shard, limit):
    path = DATA / "prices.json"
    db = load(path, {"games": {}})
    games = [g for g in GAMES_DB if not only or only.lower() in g.lower()]
    if shard:
        i, n = map(int, shard.split("/")); games = games[i::n]
    if limit: games = games[:limit]
    for k, game in enumerate(games, 1):
        print(f"[{k}/{len(games)}] {game}")
        try:
            entries = scrape_game(game)
            prev = db["games"].get(game.lower(), {})
            db["games"][game.lower()] = {
                "name": game, "entries": entries,
                "image": prev.get("image") or fetch_game_image(game),
                "scraped_at": datetime.utcnow().isoformat() + "Z",
            }
            db["updated"] = datetime.utcnow().isoformat() + "Z"
            path.write_text(json.dumps(db, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        except Exception as e:
            print(f"  Erreur: {e}")
        time.sleep(2)


def run_news():
    sources = {sid: {"articles": fetch_rss(sid, cfg)} for sid, cfg in NEWS_SOURCES.items()}
    old = load(DATA / "news.json", {}).get("sources", {})
    for sid, s in sources.items():          # garde l'ancien flux si une source est KO
        if not s["articles"] and old.get(sid): sources[sid] = old[sid]
    (DATA / "news.json").write_text(json.dumps(
        {"ok": True, "sources": sources, "fetched_at": datetime.now().isoformat()},
        ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", action="store_true"); ap.add_argument("--news", action="store_true")
    ap.add_argument("--only"); ap.add_argument("--shard"); ap.add_argument("--limit", type=int)
    a = ap.parse_args(); DATA.mkdir(exist_ok=True)
    if a.news: run_news()
    if a.prices: run_prices(a.only, a.shard, a.limit)
