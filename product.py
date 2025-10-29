# Scrape individual BestBuy product pages listed in product_urls.txt
# Outputs products_details.csv with Title, Price, Rating, Number of Reviews, Description, URL

import time
import csv
import re
from typing import Dict, Any, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def read_urls_list(path: str) -> List[str]:
    urls: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                u = line.strip()
                if u:
                    urls.append(u)
    except FileNotFoundError:
        print(f"File not found: {path}")
    return urls


def setup_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_argument("--incognito")
    # Uncomment for headless mode
    # options.add_argument("--headless=new")
    options.add_argument("--window-size=1200,900")
    driver = webdriver.Chrome(options=options)
    return driver


def get_text_or_empty(el) -> str:
    try:
        return el.text.strip()
    except Exception:
        return ""


def normalize_space(value: Any) -> str:
    try:
        text = str(value) if value is not None else ""
    except Exception:
        text = ""
    # Collapse newlines and excessive whitespace to a single space to keep CSV rows on one line
    return re.sub(r"\s+", " ", text).strip()


def extract_from_app_state(driver: webdriver.Chrome) -> Dict[str, Any]:
    # Try to read product data from the in-page app state used across BestBuy
    script = (
        "const s=(window.AppEventData && AppEventData.computedState && AppEventData.computedState.state)||{};" \
        "const pdp=s.pdp||{};" \
        "const product=pdp.product||s.product||{};" \
        "const pricing=product.pricing||product.price||{};" \
        "const reviews=pdp.customerReviews||s.customerReviews||{};" \
        "return {" \
        "  name: product.name || product.title || s.productName, " \
        "  price: pricing.current || pricing.sale || product.priceWithoutEhf || product.salePrice || product.price, " \
        "  ratingAverage: (reviews.ratingAverage || reviews.average || product.ratingAverage || product.rating), " \
        "  ratingCount: (reviews.ratingCount || reviews.count || product.ratingCount || product.reviews), " \
        "  description: (product.longDescription || product.description || pdp.longDescription || s.description) " \
        "};"
    )
    try:
        result = driver.execute_script(script) or {}
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def extract_from_dom(driver: webdriver.Chrome) -> Dict[str, Any]:
    data: Dict[str, Any] = {"name": "", "price": "", "ratingAverage": None, "ratingCount": 0, "description": ""}
    # Title
    name = ""
    for xp in [
        "//h1[contains(@class,'productName')]",
        "//h1[@data-automation='x-product-title']",
        "//h1",
    ]:
        try:
            name = get_text_or_empty(WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xp))))
            if name:
                break
        except Exception:
            pass
    if not name:
        # meta og:title as a fallback
        try:
            meta_title = driver.find_element(By.XPATH, "//meta[@property='og:title']")
            name = meta_title.get_attribute("content") or ""
        except Exception:
            name = ""
    data["name"] = normalize_space(name)

    # Price
    price = ""
    for xp in [
        "//div[starts-with(@class,'price_')]",
        "//*[@data-automation='product-price']",
        "//*[contains(@class,'price') and (self::div or self::span)]",
    ]:
        try:
            el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xp)))
            price = el.text.strip()
            if price:
                break
        except Exception:
            pass
    data["price"] = normalize_space(price)

    # Rating average
    rating_avg = None
    try:
        meta_rating = driver.find_element(By.XPATH, "//meta[@itemprop='ratingValue']")
        val = meta_rating.get_attribute("content")
        if val:
            rating_avg = float(val)
    except Exception:
        try:
            txt = driver.find_element(By.XPATH, "//*[contains(@class,'rating') and contains(@class,'average')]").text
            m = re.search(r"\d+(?:\.\d+)?", txt or "")
            rating_avg = float(m.group(0)) if m else None
        except Exception:
            rating_avg = None
    data["ratingAverage"] = rating_avg

    # Rating count
    rating_count = 0
    try:
        el = driver.find_element(By.XPATH, "//span[@itemprop='ratingCount']")
        t = el.text.strip()
        if t.startswith("(") and t.endswith(")"):
            t = t[1:-1]
        m = re.search(r"\d+", t or "")
        rating_count = int(m.group(0)) if m else 0
    except Exception:
        try:
            txt = driver.find_element(By.XPATH, "//*[contains(.,'Review') and (self::span or self::div)]").text
            m = re.search(r"\d+", txt or "")
            rating_count = int(m.group(0)) if m else 0
        except Exception:
            rating_count = 0
    data["ratingCount"] = rating_count

    # Description
    description = ""
    for xp in [
        "//*[@data-automation='long-description']",
        "//div[contains(@class,'productDescription')]",
        "//div[contains(@class,'description') and (self::div)]",
    ]:
        try:
            el = driver.find_element(By.XPATH, xp)
            description = el.text.strip()
            if description:
                break
        except Exception:
            pass
    if not description:
        try:
            meta_desc = driver.find_element(By.XPATH, "//meta[@name='description']")
            description = meta_desc.get_attribute("content") or ""
        except Exception:
            description = ""
    data["description"] = normalize_space(description)

    return data


def scrape_product(driver: webdriver.Chrome, url: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {"Title": "", "Price": "", "Rating": None, "Number of Reviews": 0, "Description": "", "URL": url}
    try:
        driver.get(url)
        # Wait for page main to exist
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "main")))

        # Best-effort consent handling
        try:
            consent = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept') or contains(., 'Got it') or contains(., 'I agree')]"))
            )
            consent.click()
        except Exception:
            pass

        # Try app-state first
        app = extract_from_app_state(driver)
        if app and (app.get("name") or app.get("price") is not None):
            data["Title"] = normalize_space(app.get("name"))
            # Normalize price to string
            pv = app.get("price")
            data["Price"] = normalize_space(pv)
            data["Rating"] = app.get("ratingAverage")
            try:
                data["Number of Reviews"] = int(app.get("ratingCount") or 0)
            except Exception:
                data["Number of Reviews"] = 0
            data["Description"] = normalize_space(app.get("description"))
        else:
            # Fallback to DOM extraction
            dom = extract_from_dom(driver)
            data["Title"] = normalize_space(dom.get("name"))
            data["Price"] = normalize_space(dom.get("price"))
            data["Rating"] = dom.get("ratingAverage")
            try:
                data["Number of Reviews"] = int(dom.get("ratingCount") or 0)
            except Exception:
                data["Number of Reviews"] = 0
            data["Description"] = normalize_space(dom.get("description"))

    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
    return data


def write_csv(rows: List[Dict[str, Any]], path: str) -> None:
    fieldnames = ["Title", "Price", "Rating", "Number of Reviews", "Description", "URL"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main() -> None:
    urls = read_urls_list("product_urls.txt")
    if not urls:
        print("No URLs found in product_urls.txt")
        return

    driver = setup_driver()
    results: List[Dict[str, Any]] = []
    try:
        for idx, url in enumerate(urls, start=1):
            print(f"[{idx}/{len(urls)}] Scraping: {url}")
            data = scrape_product(driver, url)
            results.append(data)
            # Brief delay to be polite and ensure rendering
            time.sleep(0.5)
    finally:
        driver.quit()
        print("Driver closed.")

    write_csv(results, "products_details.csv")
    print(f"Wrote {len(results)} rows to products_details.csv")


if __name__ == "__main__":
    main()


