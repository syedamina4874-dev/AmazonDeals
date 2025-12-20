from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/check")
def check_price(url: str, tag: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        # 1. REQUEST BHEJO (Allow Redirects = True)
        # Ye short link (amzn.to) ko open karke full link bana dega
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        
        if response.status_code != 200: 
            return {"error": "Link Blocked"}

        # Ye hai asli lamba URL
        final_url = response.url

        # 2. AB ASIN NIKALO (Final URL se)
        # Hum multiple patterns check karenge taaki galti na ho
        match = re.search(r'/dp/([A-Z0-9]{10})', final_url)
        if not match:
            match = re.search(r'/gp/product/([A-Z0-9]{10})', final_url)
        if not match:
            match = re.search(r'/([A-Z0-9]{10})', final_url) # Fallback

        if not match:
            return {"error": "Product ID Not Found"}
            
        asin = match.group(1)
        
        # Affiliate Link Banao
        affiliate_link = f"https://www.amazon.in/dp/{asin}?tag={tag}"

        # 3. DATA NIKALO HTML SE
        soup = BeautifulSoup(response.content, "lxml")

        # Title
        title = soup.find("span", attrs={"id": "productTitle"})
        title = title.get_text().strip()[:60] + "..." if title else "Amazon Deal"

        # Price
        price = "See Price"
        price_tag = soup.find("span", attrs={"class": "a-price-whole"})
        if not price_tag:
            price_tag = soup.find("span", attrs={"class": "a-offscreen"})
            
        if price_tag:
            price_text = price_tag.get_text().strip().replace('.', '')
            # Agar symbol nahi hai to lagao
            if "₹" not in price_text:
                price = "₹" + price_text
            else:
                price = price_text

        # Image
        image = "https://placehold.co/200?text=No+Image"
        img_div = soup.find("div", attrs={"id": "imgTagWrapperId"})
        if img_div and img_div.find("img"):
            image = img_div.find("img")["src"]
        else:
            landing_img = soup.find("img", attrs={"id": "landingImage"})
            if landing_img:
                image = landing_img["src"]

        return {
            "title": title,
            "price": price,
            "image": image,
            "link": affiliate_link
        }

    except Exception as e:
        return {"error": str(e)}
