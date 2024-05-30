from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException
import time
import requests
import json
import re
import firebase_admin
from firebase_admin import credentials, firestore

import tkinter as tk;
from tkinter import *;

# Initialize Firebase
cred = credentials.Certificate('/Users/eddieashkenazi/VSC/Tkinter_UI/steamscraper-28b94-firebase-adminsdk-6h5dr-287e5fb8bf.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Constants for sleep times
SCRAPING_DELAY = 2
MAX_RETRIES = 3

# Function to fetch and parse JSON data from URL
def fetch_and_parse_json(item_id):
    url = f"https://steamcommunity.com/market/itemordershistogram?country=US&language=english&currency=1&item_nameid={item_id}&two_factor=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }
    for attempt in range(MAX_RETRIES):
        try:
            print(f"Requesting URL: {url}")
            response = requests.get(url, headers=headers)
            print(f"Response status code: {response.status_code}")
            print(f"Response text: {response.text}")

            json_data = response.json()
            if json_data.get('success') == 1:
                return json_data
            else:
                print(f"Unexpected success value: {json_data.get('success')}")
                return {"success": json_data.get("success")}
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"Error fetching JSON data (attempt {attempt+1}): {e}")
            time.sleep(2)
    return {"success": None}

# Function to handle stale element references
def retry_find_elements(driver, xpath, max_retries=MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            return elements
        except StaleElementReferenceException:
            print(f"StaleElementReferenceException encountered, retrying... (attempt {attempt + 1})")
            time.sleep(1)
    raise StaleElementReferenceException(f"Could not find elements by XPATH: {xpath} after {max_retries} attempts")

# Function to extract item ID from the item's page
def extract_item_id(driver):
    for attempt in range(MAX_RETRIES):
        try:
            script = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//script[contains(text(), 'Market_LoadOrderSpread')]"))
            ).get_attribute("innerHTML")
            start_index = script.find("Market_LoadOrderSpread(") + len("Market_LoadOrderSpread(")
            end_index = script.find(",", start_index)
            item_id = script[start_index:end_index].strip()
            item_id = re.sub(r'\D', '', item_id)  # Remove non-numeric characters
            return item_id
        except (NoSuchElementException, TimeoutException) as e:
            print(f"Error extracting item ID (attempt {attempt+1}): {e}")
            time.sleep(2)
    return None

# Function to extract median sale price graph from the item's page
def extract_median_sale_price_graph(driver):
    try:
        script = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//script[contains(text(), 'var line1=')]"))
        ).get_attribute("innerHTML")
        start_index = script.find("var line1=") + len("var line1=")
        end_index = script.find("];", start_index) + 1
        median_sale_price_graph = json.loads(script[start_index:end_index])

        # Get the last 7 days of median sale prices
        last_7_days = median_sale_price_graph[-50:]
        print(last_7_days)
        return last_7_days
    except (NoSuchElementException, TimeoutException, json.JSONDecodeError) as e:
        print(f"Error extracting median sale price graph: {e}")
    return []

# Function to check if item exists in Firebase
def item_exists_in_db(item_id):
    doc_ref = db.collection('steam_market_data').document(item_id)
    doc = doc_ref.get()
    return doc.exists

# Function to update item data in Firebase
def update_item_in_db(item_id, item_data):
    db.collection('steam_market_data').document(item_id).update(item_data)

# Function to scrape data from a page
def scrape_page(url, num_pages=2, items_per_page=10):
    # Set up options for Chrome WebDriver
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    # Initialize the Chrome webdriver
    driver = webdriver.Chrome(options=chrome_options)

    # Navigate to the provided URL
    driver.get(url)

    for page in range(num_pages):
        # Wait for the page to load
        time.sleep(SCRAPING_DELAY)

        try:
            # Wait for the panel to be present
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@id='searchResultsRows']"))
            )
            individual_items = retry_find_elements(driver, ".//a[@class='market_listing_row_link']")

            num_items = min(len(individual_items), items_per_page)
            for i in range(num_items):
                try:
                    # Re-locate the element to handle potential stale element reference
                    individual_items = retry_find_elements(driver, ".//a[@class='market_listing_row_link']")
                    if i >= len(individual_items):
                        print(f"No more items found on page {page + 1}. Processed {i} items.")
                        break
                    individual_item = individual_items[i]
                    title_element = individual_item.find_element(By.XPATH, ".//span[@class='market_listing_item_name']")
                    price_element = individual_item.find_element(By.XPATH, ".//span[@class='normal_price']")

                    item_link = individual_item.get_attribute("href")
                    title = title_element.text
                    price = price_element.text[1:]  # Remove the dollar sign from the price

                    print(f"Processing item: {title} with price {price} and link {item_link}")

                    # Navigate to the item's page to extract the item ID and other data
                    driver.get(item_link)
                    time.sleep(SCRAPING_DELAY)

                    # Extract item ID from the item's page
                    item_id = extract_item_id(driver)

                    if item_id is None:
                        print(f"Error: Item ID not found for item")
                    else:
                        print(f"Extracted Item ID: {item_id}")

                        # Fetch and parse JSON data for the item
                        json_data = fetch_and_parse_json(item_id)

                        # Extract relevant fields from JSON data
                        if json_data['success'] == 1:
                            buy_order_graph = json_data.get('buy_order_graph', [])
                            sell_order_graph = json_data.get('sell_order_graph', [])
                            highest_buy_order = json_data.get('highest_buy_order', 0)
                            lowest_sell_order = json_data.get('lowest_sell_order', 0)
                        else:
                            buy_order_graph = []
                            sell_order_graph = []
                            highest_buy_order = 0
                            lowest_sell_order = 0

                        # Convert the buy and sell order graphs to a format Firestore accepts
                        buy_order_graph = [{"price": b[0], "quantity": b[1], "description": b[2]} for b in buy_order_graph]
                        sell_order_graph = [{"price": s[0], "quantity": s[1], "description": s[2]} for s in sell_order_graph]

                        # Extract the median sale price graph
                        median_sale_price_graph = extract_median_sale_price_graph(driver)

                        # Convert median sale price graph to Firestore compatible format
                        median_sale_price_graph = [
                            {"time": entry[0], "price": entry[1], "volume": entry[2]}
                            for entry in median_sale_price_graph
                        ]

                        item_data = {
                            "HighestBuyOrder": highest_buy_order,
                            "LowestSellOrder": lowest_sell_order,
                            "BuyOrderGraph": buy_order_graph,
                            "SellOrderGraph": sell_order_graph,
                            "MedianSalePriceGraph": median_sale_price_graph
                        }

                        if item_exists_in_db(item_id):
                            update_item_in_db(item_id, item_data)
                            print(f"{title} is already stored in the database. Updated the graphs.")
                        else:
                            # Store the item data and JSON data
                            item_data.update({
                                "Name": title,
                                "Price": price,
                                "ItemID": item_id
                            })
                            # Save the item data to Firebase Firestore
                            db.collection('new_steam_market_data').document(item_id).set(item_data)
                            print(f"{title} added to the database.")

                    # Navigate back to the search results page
                    driver.back()
                    time.sleep(SCRAPING_DELAY)

                except StaleElementReferenceException as e:
                    print(f"StaleElementReferenceException encountered while processing item {i + 1} on page {page + 1}: {e}")
                    break
                except IndexError as e:
                    print(f"IndexError encountered while processing item {i + 1} on page {page + 1}: {e}")
                    break
                except Exception as e:
                    print(f"Error processing item: {e}")

            # Click the "Next" button to navigate to the next page
            try:
                next_button = driver.find_element(By.XPATH, "//a[@class='pagebtn' and @title='Next']")
                driver.execute_script("arguments[0].click();", next_button)
            except (NoSuchElementException, TimeoutException) as e:
                print(f"Next button not found or could not be clicked: {e}")
                break

        except Exception as e:
            print(f"Error: {e}")

    # Close the webdriver
    driver.quit()


# def get_game_app_id():
#     while True:
#         game_choice = input("Enter the game to scrape (csgo or dota2): ").strip().lower()
#         if game_choice == "csgo":
#             return 730
#         elif game_choice == "dota2":
#             return 570
#         else:
#             print("Invalid input. Please enter 'csgo' or 'dota2'.")

# # Main function
# if __name__ == "__main__":
#     app_id = get_game_app_id()
#     url = f"https://steamcommunity.com/market/search?appid={app_id}"

#     # Scrape the first 2 pages with 10 items per page
#     scrape_page(url, num_pages=2, items_per_page=10)

#     # Print confirmation
#     print("Scraping complete.")




root = tk.Tk()

root.title("SteamScraper")
root.geometry("400x300")

gameIdLabel = tk.Label(root, text="GameID", font=('Arial', 10))
gameIdLabel.pack()

gameIdEntry = tk.Entry(root)
gameIdEntry.pack()

pagesLabel = tk.Label(root, text="Pages (1-5)", font=('Arial', 10))
pagesLabel.pack()

pagesEntry = tk.Entry(root)
pagesEntry.pack()

outputText = tk.Text(root, height=10, width=50, font=('Arial', 10))
outputText.pack(pady=10)

def submitButton():
    game_id = gameIdEntry.get()
    pages = int(pagesEntry.get())

    # Clear the previous text in the Text widget
    outputText.delete('1.0', tk.END)

    url = f"https://steamcommunity.com/market/search?appid={game_id}"
    output = scrape_page(url, num_pages=pages, items_per_page=10)

    # Insert the new text into the Text widget
    outputText.insert(tk.END, f"{output}")

button = tk.Button(root, text="Submit", font=('Arial', 14), command=submitButton)
button.pack(pady=10)


root.mainloop()