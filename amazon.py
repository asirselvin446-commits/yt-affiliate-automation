"""Amazon Product Fetcher and Affiliate Link Generator.
Extracts title, price, rating, bullet points, and high-resolution images from Amazon.in.
"""
import json, os, re, sys, urllib.request
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

MARKETPLACE = os.getenv("AMAZON_MARKETPLACE", "amazon.in")
TAG = os.getenv("AMAZON_AFFILIATE_TAG", "asirselvin336-21")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}


def build_affiliate_url(asin: str) -> str:
    return f"https://www.{MARKETPLACE}/dp/{asin}?tag={TAG}"


def extract_asin(url_or_asin: str) -> str:
    url_or_asin = url_or_asin.strip()
    if re.fullmatch(r"[A-Z0-9]{10}", url_or_asin):
        return url_or_asin
    m = re.search(r"/(?:dp|gp/product|d)/([A-Z0-9]{10})", url_or_asin)
    if m:
        return m.group(1)
    raise ValueError(f"Could not extract ASIN from '{url_or_asin}'")


def fetch_product(url_or_asin: str) -> dict:
    asin = extract_asin(url_or_asin)
    url = f"https://www.{MARKETPLACE}/dp/{asin}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Amazon HTTP {resp.status_code} for {url}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Title
    title_el = soup.select_one("#productTitle") or soup.select_one("h1.a-size-large") or soup.find("title")
    title = title_el.get_text(strip=True) if title_el else ""
    title = re.sub(r"\s*:\s*Amazon\.in.*$", "", title).strip()
    if not title or len(title) < 5 or "Page Not Found" in title or "Looking for something?" in title:
        raise ValueError(f"Product page for ASIN {asin} returned no valid title (likely 404 or inactive)")

    # Price
    price_whole = soup.select_one(".a-price-whole")
    price = f"₹{price_whole.get_text(strip=True)}" if price_whole else ""

    # Rating
    rating_el = soup.select_one("span.a-icon-alt")
    rating_str = rating_el.get_text(strip=True) if rating_el else "4.3 out of 5 stars"
    rating_m = re.search(r"([0-9.]+)", rating_str)
    rating = float(rating_m.group(1)) if rating_m else 4.3

    # Review Count
    reviews_el = soup.select_one("#acrCustomerReviewText")
    reviews = reviews_el.get_text(strip=True) if reviews_el else "1,000+ ratings"

    # Bullet Points / Features
    bullets = []
    for li in soup.select("#feature-bullets li span.a-list-item"):
        text = li.get_text(strip=True)
        if text and not text.startswith("Make sure this fits"):
            bullets.append(text)

    # Images
    images = []
    # Dynamic image data attribute in Amazon DOM
    img_script = soup.find("script", string=re.compile(r"colorImages"))
    if img_script:
        matches = re.findall(r'"hiRes":"(https://[^"]+)"', img_script.string)
        if matches:
            images = list(dict.fromkeys(matches))
        else:
            matches_large = re.findall(r'"large":"(https://[^"]+)"', img_script.string)
            images = list(dict.fromkeys(matches_large))

    # Fallback to main image
    if not images:
        main_img = soup.select_one("#landingImage, #imgBlkFront")
        if main_img and main_img.get("src"):
            images.append(main_img["src"])

    affiliate_url = build_affiliate_url(asin)

    return {
        "asin": asin,
        "title": title[:140],
        "full_title": title,
        "price": price,
        "rating": rating,
        "reviews": reviews,
        "bullets": bullets[:5],
        "images": images[:6],
        "affiliate_url": affiliate_url,
    }


def download_images(image_urls: list, dest_dir: Path) -> list:
    dest_dir.mkdir(parents=True, exist_ok=True)
    local_paths = []
    for idx, u in enumerate(image_urls):
        ext = ".jpg" if ".jpg" in u.lower() else ".png"
        target = dest_dir / f"product_{idx+1:02d}{ext}"
        try:
            req = urllib.request.Request(u, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r, open(target, "wb") as f:
                f.write(r.read())
            local_paths.append(str(target))
        except Exception as e:
            print(f"Warning: Failed to download {u}: {e}")
    return local_paths


if __name__ == "__main__":
    test_target = sys.argv[1] if len(sys.argv) > 1 else "B08N5WRWNW"
    data = fetch_product(test_target)
    print(json.dumps(data, indent=2, ensure_ascii=False))
