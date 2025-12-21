from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import re
import random
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- USER AGENT LIST (To trick Amazon) ---
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
]

def clean_price(price_str):
    if not price_str: return 0
    clean = re.sub(r'[^\d.]', '', str(price_str))
    try: return float(clean)
    except: return 0

@app.get("/api/check")
def check_price(url: str, tag: str):
    session = requests.Session()
    final_data = {"error": "Failed"}

    # --- RETRY LOOP (Try 3 times) ---
    for i in range(3):
        try:
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://www.google.com/",
                "Upgrade-Insecure-Requests": "1",
            }
            
            response = session.get(url, headers=headers, timeout=8, allow_redirects=True)
            
            # Check if blocked (Captcha)
            if "api-services-support@amazon.com" in response.text or "Robot Check" in response.text:
                time.sleep(1) # Wait 1 sec and retry
                continue 

            if response.status_code != 200: continue

            final_url = response.url
            match = re.search(r'/(dp|gp/product)/([A-Z0-9]{10})', final_url)
            asin = match.group(2) if match else "UNKNOWN"
            affiliate_link = f"https://www.amazon.in/dp/{asin}?tag={tag}" if asin != "UNKNOWN" else final_url

            soup = BeautifulSoup(response.content, "lxml")

            # --- DATA EXTRACTION ---
            
            # 1. Title
            title = None
            if not title: title = soup.find("meta", attrs={"name": "title"})
            if title: title = title.get('content')
            
            if not title: title = soup.find("span", attrs={"id": "productTitle"})
            if title and not isinstance(title, str): title = title.get_text().strip()
            
            if not title: title = soup.find("meta", property="og:title")
            if title: title = title.get('content')

            if not title:
                # Agar title nahi mila, to retry karo
                continue
            
            title = title.replace("Amazon.in:", "").replace("Buy ", "").strip()[:70] + "..."

            # 2. Image
            image = None
            if not image: image = soup.find("meta", property="og:image")
            if image: image = image.get('content')
            
            if not image:
                img_div = soup.find("div", attrs={"id": "imgTagWrapperId"})
                if img_div and img_div.find("img"): image = img_div.find("img")["src"]

            # Fallback Image (Generic Amazon Logo instead of Gray Box)
            if not image: image = "https://upload.wikimedia.org/wikipedia/commons/4/4a/Amazon_icon.svg"

            # 3. Price
            price_tag = soup.find("span", attrs={"class": "a-price-whole"})
            selling_price_str = "Check Price"
            selling_price_val = 0
            
            if price_tag:
                raw_price = price_tag.get_text().strip().replace('.', '')
                selling_price_str = "₹" + raw_price
                selling_price_val = clean_price(selling_price_str)

            # 4. Offers
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

            coupon_text = ""
            page_text = soup.get_text()
            if "Apply" in page_text and "coupon" in page_text: coupon_text = "Coupon Available"

            bank_offer = False
            if "Bank Offer" in page_text or "Partner Offers" in page_text: bank_offer = True

            # SUCCESS! Return Data
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

        except Exception:
            continue
    
    # If all 3 tries fail, return a Fallback Card
    return {
        "title": "Exclusive Deal (Click to View)",
        "price": "Check Price",
        "image": "https://upload.wikimedia.org/wikipedia/commons/4/4a/Amazon_icon.svg", # Clean Logo
        "link": url, # Original Link
        "mrp": "", "discount": "", "coupon": "", "bank_offer": False
    }
