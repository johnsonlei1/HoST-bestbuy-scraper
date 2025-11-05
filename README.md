Simple python program to scrape BestBuy.ca

Thanks to jamikhai for template

Libraries needed:
- pandas
- selenium (Webdriver)
- bs4 (BeautifulSoup)

Usage:

Optional: create a virtual environment
    1. run python -m venv .venv  
    2. run Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    3. run venv\Scripts\activate

1. in terminal run pip install pandas selenium beautifulsoup4
2. edit line 32 of bestbuy_webscrape.py to any bestbuy.ca search url.
3. run python3 bestbuy_webscrape.py to scrape all products from that search result
4. the product urls are saved to product_urls.txt
5. run python3 product.py to scrape the information from each individual product page
6. product data is saved in product_details.csv

