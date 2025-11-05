import time
import pandas
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Function to click the button on the page and wait a few seconds
def click_button():
    # Try a resilient locator for the Show more button, fallback to the legacy class
    try:
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(., 'Show more') or contains(., 'Show More')]]"))
        )
    except Exception:
        button = driver.find_element(By.CLASS_NAME, "content_3dXxd")
    button.click()
    # Brief wait to allow new items to load
    time.sleep(2)

# Function to write csv files with a pandas dataframe
def write_csv(dataframe, file_name):
	dataframe.to_csv(f"{file_name}.csv")

url = "https://www.bestbuy.ca/en-ca/search?search=security+camera"

options = webdriver.ChromeOptions()
options.add_argument("--incognito") # Fresh start every time so no interference
#options.add_argument("--headless") # The chrome window won't pop up on screen and show animations

driver = webdriver.Chrome(options=options) # Initialize driver with chrome options defined above
driver.get(url) # Bring the browser to the url specified above
driver.set_window_size(1200, 900) # Set window resolution so that all elements can still load on page

# Debug: print initial page info
print("TITLE (initial):", driver.title)
print("URL (initial):", driver.current_url)

# Handle possible consent/region modal if present (best-effort, ignore failures)
try:
    consent = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept') or contains(., 'Got it') or contains(., 'I agree')]"))
    )
    consent.click()
except Exception:
    pass

# Wait for the main content to be present (works for both collection and search pages)
WebDriverWait(driver, 30).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "main"))
)

# The loop below will repeatedly click the "Show more" button until it disappears

while True: # If the button exists, click it
	try:
		click_button()
		print("\"Show more\" buttton has been clicked")
	except:
		break

def scroll_to_bottom():
    previous_height = driver.execute_script("return document.body.scrollHeight")
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1.5)
    current_height = driver.execute_script("return document.body.scrollHeight")
    return current_height != previous_height

# Keep clicking Show more while available and also perform a final scroll to ensure all items render
while True: # If the button exists, click it
	try:
		click_button()
		print("\"Show more\" buttton has been clicked")
		# wait a bit for content to append
		WebDriverWait(driver, 10).until(lambda d: scroll_to_bottom() or True)
	except Exception:
		# try one last scroll after no button is clickable
		scrolled = scroll_to_bottom()
		if not scrolled:
			break

## Approach A: Gather from live DOM (may be empty if CSR hasn't rendered yet)
product_elements = driver.find_elements(By.XPATH, "//div[contains(@class,'productItemTextContainer')]")
print("Found product containers (selenium):", len(product_elements))

## Approach B: Pull directly from BestBuy's in-page state (React) if available
def get_products_via_app_state():
    script = (
        "return (window.AppEventData && AppEventData.computedState && AppEventData.computedState.state && "
        "AppEventData.computedState.state.search && AppEventData.computedState.state.search.searchResult && "
        "AppEventData.computedState.state.search.searchResult.products) || [];"
    )
    try:
        return driver.execute_script(script) or []
    except Exception:
        return []

# Wait briefly for products to populate in app state
try:
    WebDriverWait(driver, 10).until(lambda d: len(get_products_via_app_state()) > 0)
except Exception:
    pass

app_products = get_products_via_app_state()
print("Products from app state:", len(app_products))

# Create lists to be added to
names = []
prices = []
discounts = []
ratings = []
num_reviews = []
urls = []

for product in product_elements: # Go through each product on page (DOM extraction)
    # Extract via relative XPaths with class-substring predicates for resilience
    try:
        name_el = product.find_element(By.XPATH, ".//div[contains(@class,'productItemName')]")
    except Exception:
        name_el = None
    try:
        price_el = product.find_element(By.XPATH, ".//div[starts-with(@class,'price_')]")
    except Exception:
        price_el = None
    # Try to capture URL from anchor around the name
    product_url = ""
    try:
        link_el = product.find_element(By.XPATH, ".//a[contains(@href,'/en-ca/')]")
        href = link_el.get_attribute("href") or ""
        product_url = href
    except Exception:
        product_url = ""

    if not name_el or not price_el:
        continue
    names.append(name_el.text.strip())
    prices.append(price_el.text.strip())
    urls.append(product_url)

    # Discount
    try:
        discount_el = product.find_element(By.XPATH, ".//span[contains(@class,'productSaving')]")
        tokens = discount_el.text.strip().split()
        discounts.append(tokens[-1] if tokens else "")
    except Exception:
        discounts.append("")

    # Ratings
    try:
        rating_meta = product.find_element(By.XPATH, ".//meta[@itemprop='ratingValue']")
        ratings.append(float(rating_meta.get_attribute("content")))
    except Exception:
        ratings.append(None)

    # Reviews count
    try:
        review_el = product.find_element(By.XPATH, ".//span[@itemprop='ratingCount']")
        review_text = review_el.text.strip()
        if review_text.startswith("(") and review_text.endswith(")"):
            review_text = review_text[1:-1]
        review_tokens = review_text.split()
        num_reviews.append(int(review_tokens[0]))
    except Exception:
        num_reviews.append(0)

# If DOM method found nothing, fallback to app state extraction
if not names and app_products:
    def slugify(text):
        text = (text or "").lower()
        text = re.sub(r"[^a-z0-9]+", "-", text)
        text = re.sub(r"-+", "-", text).strip("-")
        return text

    for p in app_products:
        # Name
        name_val = (p.get('name') or '').strip()
        names.append(name_val)
        # Price: choose priceWithoutEhf or salePrice fields if available
        price_value = p.get('priceWithoutEhf') or p.get('salePrice') or p.get('price')
        prices.append(str(price_value) if price_value is not None else '')
        # Discount/saving
        saving_value = p.get('saving')
        discounts.append(str(saving_value) if saving_value is not None else '')
        # Ratings
        rating_avg = p.get('ratingAverage') or p.get('rating')
        try:
            ratings.append(float(rating_avg) if rating_avg is not None else None)
        except Exception:
            ratings.append(None)
        # Reviews count
        rc = p.get('ratingCount') or p.get('reviews')
        try:
            num_reviews.append(int(rc) if rc is not None else 0)
        except Exception:
            num_reviews.append(0)
        # URL: try direct field, else build from name and sku
        sku = p.get('sku') or p.get('skuId')
        url_field = p.get('productUrl') or p.get('url')
        if url_field:
            full_url = url_field if url_field.startswith('http') else f"https://www.bestbuy.ca{url_field}"
            urls.append(full_url)
        elif sku and name_val:
            slug = slugify(name_val)
            urls.append(f"https://www.bestbuy.ca/en-ca/product/{slug}/{sku}")
        elif sku:
            urls.append(f"https://www.bestbuy.ca/en-ca/sku/{sku}")
        else:
            urls.append("")

# Dictionary with headers and values of product data
product_dict = {
	"Name": names,
	"Sale Price": prices,
	"Discount": discounts,
	"Rating": ratings,
	"Number of Reviews": num_reviews,
	"URL": urls
}

#Create structured dataframe of dictionary data for easy access and use
results_dataframe = pandas.DataFrame(product_dict)
print("Rows captured:", len(results_dataframe))

# Finally write file to csv for external use and print end statement
write_csv(results_dataframe, "searchresults")
if len(results_dataframe) == 0:
    print("No products parsed. Writing debug_page.html for inspection.")
    try:
        # Ensure we snapshot the final DOM state
        html_snapshot = driver.page_source
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html_snapshot)
    except Exception:
        pass

# Also write product URLs to a text file (one per line), if available
try:
    unique_urls = []
    seen = set()
    for u in urls:
        if not u:
            continue
        if u in seen:
            continue
        seen.add(u)
        unique_urls.append(u)
    with open("product_urls.txt", "w", encoding="utf-8") as f:
        for u in unique_urls:
            f.write(u + "\n")
    print(f"Wrote {len(unique_urls)} URLs to product_urls.txt")
except Exception as e:
    print("Could not write product_urls.txt:", e)

driver.quit() # Close our automated browser
print("Driver has been quit")
print("Web Scraping and CSV file writing complete!")
