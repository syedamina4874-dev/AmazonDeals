from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import re
import random
import urllib.parse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_price(price_str):
    if not price_str: return 0
    clean = re.sub(r'[^\d.]', '', str(price_str))
    try: return float(clean)
    except: return 0

@app.get("/api/check")
def check_price(url: str, tag: str):
    try:
        # 1. Resolve Short Link (amzn.to)
        # Iske liye hum direct request bhej sakte hain kyunki ye block nahi hota
        session = requests.Session()
        try:
            resp = session.head(url, allow_redirects=True, timeout=5)
            final_url = resp.url
        except:
            final_url = url

        # Extract ASIN
        match = re.search(r'/(dp|gp/product)/([A-Z0-9]{10})', final_url)
        asin = match.group(2) if match else "UNKNOWN"
        
        affiliate_link = f"https://www.amazon.in/dp/{asin}?tag={tag}" if asin != "UNKNOWN" else final_url

        # 2. USE PROXY TO FETCH DATA (Bypass Blocking)
        # Hum 'api.allorigins.win' use karenge jo Amazon ka HTML laake dega
        proxy_url = f"https://api.allorigins.win/get?url={urllib.parse.quote(final_url)}"
        
        response = requests.get(proxy_url, timeout=10)
        json_data = response.json()
        html_content = json_data.get("contents", "")

        if not html_content:
            return {"error": "Proxy Failed"}

        soup = BeautifulSoup(html_content, "lxml")

        # --- DATA EXTRACTION ---
        
        # Title
        title = None
        if not title: title = soup.find("meta", attrs={"name": "title"})
        if title: title = title.get('content')
        if not title:
            t = soup.find("title")
            if t: title = t.get_text()
        
        if not title: title = "Amazon Product"
        title = title.replace("Amazon.in:", "").replace("Buy", "").strip()[:70] + "..."

        # Image
        image = None
        img_meta = soup.find("meta", property="og:image")
        if img_meta: image = img_meta.get('content')
        
        if not image: image = "https://placehold.co/200?text=Check+Link"

        # Price (MetaData se nikalna safe hai)
        selling_price_str = "Check Price"
        
        # Amazon kabhi kabhi price description meta me daalta hai
        desc = soup.find("meta", attrs={"name": "description"})
        if desc:
            desc_text = desc.get("content", "")
            price_match = re.search(r'₹\s?([\d,]+)', desc_text)
            if price_match:
                selling_price_str = "₹" + price_match.group(1)

        # Offers logic filhal simple rakhenge kyunki proxy HTML thoda alag ho sakta hai
        return {
            "title": title,
            "price": selling_price_str,
            "mrp": "",
            "discount": "",
            "coupon": "",
            "bank_offer": False,
            "image": image,
            "link": affiliate_link
        }

    except Exception as e:
        return {"error": str(e)}
