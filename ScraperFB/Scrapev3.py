from selenium import webdriver
from selenium.webdriver.common.by import By
import threading
import time
import firebase_admin
from firebase_admin import credentials, firestore
import requests

# Constants for sleep times
SCRAPING_DELAY = 2

# Initialize Firebase Admin
cred = credentials.Certificate("steamscraper-28b94-firebase-adminsdk-6h5dr-a270c8de6b.json")
firebase_admin.initialize_app(cred)

# Firestore database
db = firestore.client()

# Function to scrape data from a page
def scrape_page(url, data):
    # Set up options for Chrome WebDriver
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    # Initialize the Chrome webdriver
    driver = webdriver.Chrome(options=chrome_options)
    
    # Navigate to the provided URL
    driver.get(url)
    
    # Wait for the page to load
    time.sleep(SCRAPING_DELAY)
    
    try:
        for i in range(10):
            panel = driver.find_element(By.XPATH,"/html/body/div[1]/div[7]/div[2]/div[1]/div[4]/div[2]/div[2]/div/div[1]")
            individualItems = panel.find_elements(By.XPATH,"//div[@class='market_listing_row market_recent_listing_row market_listing_searchresult']")

            for individualItem in individualItems:
                title_element = individualItem.find_element(By.XPATH, ".//span[@class='market_listing_item_name']")
                price_element = individualItem.find_element(By.XPATH, ".//span[@class='normal_price']")

                title = title_element.text
                price = price_element.text[1:]  # Remove the dollar sign from the price
                
                data.append({"Name": title, "Price": price})
            
    except Exception as e:
        print("Error:", e)
    
    # Close the webdriver
    driver.quit()

# Function to save data to Firebase
def save_to_firebase(data):
    for item in data:
        db.collection('steam_market_data').add(item)

# URLs to scrape
urls = [
    "https://steamcommunity.com/market/search?appid=730",
    "https://steamcommunity.com/market/search?appid=730#p16_popular_desc",
    "https://steamcommunity.com/market/search?appid=730#p29_popular_desc"
]

# Data list to store scraped data
data = []

# Create threads for each URL
threads = []
for url in urls:
    thread = threading.Thread(target=scrape_page, args=(url, data))
    threads.append(thread)

# Start each thread
for thread in threads:
    thread.start()

# Wait for all threads to finish
for thread in threads:
    thread.join()

print(data)
# Save data to Firebase
save_to_firebase(data)