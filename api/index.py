from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import re
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROTATING HEADERS TO AVOID BLOCKING ---
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

def get_headers():
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache"
    }

def clean_price(price_str):
    if not price_str: return 0
    clean = re.sub(r'[^\d.]', '', str(price_str))
    try: return float(clean)
    except: return 0

@app.get("/api/check")
def check_price(url: str, tag: str):
    try:
        session = requests.Session()
        # 1. First Request to Resolve Short Link (amzn.to)
        response = session.get(url, headers=get_headers(), timeout=10, allow_redirects=True)
        
        if response.status_code != 200:
            return {"error": "Amazon Blocked Request"}

        final_url = response.url
        
        # 2. Extract ASIN
        match = re.search(r'/(dp|gp/product)/([A-Z0-9]{10})', final_url)
        asin = match.group(2) if match else "UNKNOWN"
        affiliate_link = f"https://www.amazon.in/dp/{asin}?tag={tag}" if asin != "UNKNOWN" else final_url

        soup = BeautifulSoup(response.content, "lxml")

        # --- 3. ROBUST TITLE EXTRACTION (Priority: Meta > ID) ---
        title = None
        # Meta Title (Most Reliable)
        meta_title = soup.find("meta", attrs={"name": "title"})
        if meta_title: title = meta_title.get('content')
        
        # Open Graph Title
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title: title = og_title.get('content')

        # ID Fallback
        if not title:
            id_title = soup.find("span", attrs={"id": "productTitle"})
            if id_title: title = id_title.get_text().strip()

        if not title: title = "Amazon Best Deal" # Last Resort
        
        # Clean Title (Remove 'Amazon.in: ...')
        title = title.replace("Amazon.in:", "").replace("Buy ", "").strip()
        title = title[:70] + "..." if len(title) > 70 else title

        # --- 4. ROBUST IMAGE EXTRACTION ---
        image = None
        # Open Graph Image (Best Quality & Always present even if blocked)
        og_image = soup.find("meta", property="og:image")
        if og_image: image = og_image.get('content')

        # Landing Image Fallback
        if not image:
            landing = soup.find("img", attrs={"id": "landingImage"})
            if landing: image = landing.get("src")
            
        # JS Dynamic Image Fallback
        if not image:
            img_div = soup.find("div", attrs={"id": "imgTagWrapperId"})
            if img_div and img_div.find("img"): image = img_div.find("img")["src"]

        if not image: image = "https://placehold.co/200?text=Check+Link"

        # --- 5. PRICE EXTRACTION ---
        price_tag = soup.find("span", attrs={"class": "a-price-whole"})
        if not price_tag: price_tag = soup.find("span", attrs={"class": "a-offscreen"})
        
        selling_price_str = "Check Price"
        selling_price_val = 0
        
        if price_tag:
            raw_price = price_tag.get_text().strip().replace('.', '')
            selling_price_str = "₹" + raw_price if "₹" not in raw_price else raw_price
            selling_price_val = clean_price(selling_price_str)

        # --- 6. OFFERS & COUPONS ---
        mrp_str = ""
        discount_str = ""
        
        mrp_tag = soup.find("span", attrs={"class": "a-text-price"})
        if mrp_tag:
            mrp_inner = mrp_tag.find("span", attrs={"class": "a-offscreen"})
            if mrp_inner:
                mrp_str = mrp_inner.get_text().strip()
                mrp_val = clean_price(mrp_str)
                if mrp_val > selling_price_val and mrp_val > 0:
                    off = int(((mrp_val - selling_price_val) / mrp_val) * 100)
                    if off > 0: discount_str = f"-{off}%"

        # Coupon Check
        coupon_text = ""
        page_text = soup.get_text()
        if "Apply" in page_text and "coupon" in page_text:
             # Basic check to avoid regex errors if text is messy
             coupon_text = "Coupon Available"

        # Bank Offer Check
        bank_offer = False
        if "Bank Offer" in page_text or "Partner Offers" in page_text:
            bank_offer = True

        return {
            "title": title,
            "price": selling_price_str,
            "mrp": mrp_str,
            "discount": discount_str,
            "coupon": coupon_text,
            "bank_offer": bank_offer,
            "image": image,
            "link": affiliate_link
        }

    except Exception as e:
        return {"error": str(e)}
