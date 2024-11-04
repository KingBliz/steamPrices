import time
import logging
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException
import requests
import json
import re
import firebase_admin
from firebase_admin import credentials, firestore
from urllib.parse import urlunparse, urlparse, parse_qs, quote

import tkinter as tk
from tkinter import *
import webbrowser
import customtkinter as customtkinter
import threading

# Constants for maximum retries
MAX_RETRIES = 3

# Initialize Firebase
cred = credentials.Certificate('/Users/eddieashkenazi/VSC/Tkinter_UI/steamscraper-28b94-firebase-adminsdk-6h5dr-287e5fb8bf.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Set up logging
logging.basicConfig(filename='scraping_errors.log', level=logging.ERROR, 
                    format='%(asctime)s:%(levelname)s:%(message)s')

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
            time.sleep(random.uniform(0, 10))
    return {"success": None}

# Function to handle stale element references
def retry_find_elements(driver, xpath, max_retries=MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            return elements
        except StaleElementReferenceException:
            print(f"StaleElementReferenceException encountered, retrying... (attempt {attempt + 1})")
            time.sleep(random.uniform(0, 10))
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
            time.sleep(random.uniform(0, 10))
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
        logging.error(f"Error extracting median sale price graph: {e}")
    return []

# Function to check if item exists in Firebase
def item_exists_in_db(item_id):
    doc_ref = db.collection('steam_market_data').document(item_id)
    doc = doc_ref.get()
    return doc.exists

# Function to update item data in Firebase
def update_item_in_db(item_id, item_data):
    db.collection('steam_market_data').document(item_id).update(item_data)

# Function to scrape data from Dota 2 market
def scrape_dota2(url, num_pages=2, items_per_page=10):
    builder = URLBuilder(url)

    # Initialize Chrome webdriver
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=chrome_options)

    # Tracking time
    start_time = time.time()
    total_delay_time = 0

    # Collect all item links across the specified pages
    all_item_links = []

    for page in range(num_pages):
        # Navigate to the built URL for the current page
        driver.get(builder.build() + f"&p={page + 1}")
        # Wait for the page to load
        delay = random.uniform(0, 10)
        time.sleep(delay)
        total_delay_time += delay

        try:
            # Wait for the panel to be present
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@id='searchResultsRows']"))
            )
            individual_items = retry_find_elements(driver, ".//a[@class='market_listing_row_link']")

            # Get the links of the items on the page
            item_links = [item.get_attribute("href") for item in individual_items[:items_per_page]]
            all_item_links.extend(item_links)

        except Exception as e:
            print(f"Error collecting links on page {page + 1}: {e}")
            logging.error(f"Error collecting links on page {page + 1}: {e}")

    print(f"Collected {len(all_item_links)} item links.")

    # Process each collected item link
    for item_link in all_item_links:
        try:
            print(f"Processing item link: {item_link}")

            # Navigate to the item's page to extract the item ID and other data
            driver.get(item_link)
            delay = random.uniform(0, 10)
            time.sleep(delay)
            total_delay_time += delay

            # Extract item ID from the item's page
            item_id = extract_item_id(driver)

            if item_id is None:
                print(f"Error: Item ID not found for item\n\n")
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
                    print(f"Item is already stored in the database. Updated the graphs.")
                else:
                    # Store the item data and JSON data
                    item_data.update({
                        "ItemID": item_id
                    })
                    # Save the item data to Firebase Firestore
                    db.collection('new_steam_market_data').document(item_id).set(item_data)
                    print(f"Item added to the database.")

        except Exception as e:
            print(f"Error processing item: {e}")
            logging.error(f"Error processing item: {e}")

    # Close the webdriver
    # driver.quit()

    # Print the total elapsed time and total delay time
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
    print(f"Total time of scraping delays: {total_delay_time:.2f} seconds")
    print(f"Total time of scraping: {elapsed_time-total_delay_time:.2f} seconds")

def scrape_CSGO(url, num_pages=2, items_per_page=10):
    # Set up options for Chrome WebDriver
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    # Initialize the Chrome webdriver
    driver = webdriver.Chrome(options=chrome_options)

    # Tracking time
    start_time = time.time()
    total_delay_time = 0

    # Collect all item links across the specified pages
    all_item_links = []

    for page in range(num_pages):
        # Navigate to the provided URL for the current page
        driver.get(url + f"&p={page + 1}")
        # Wait for the page to load
        delay = random.uniform(0, 10)
        time.sleep(delay)
        total_delay_time += delay

        try:
            # Wait for the panel to be present
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@id='searchResultsRows']"))
            )
            individual_items = retry_find_elements(driver, ".//a[@class='market_listing_row_link']")

            # Get the links of the items on the page
            item_links = [item.get_attribute("href") for item in individual_items[:items_per_page]]
            all_item_links.extend(item_links)

        except Exception as e:
            print(f"Error collecting links on page {page + 1}: {e}")
            logging.error(f"Error collecting links on page {page + 1}: {e}")

    print(f"Collected {len(all_item_links)} item links.")

    # Process each collected item link
    for item_link in all_item_links:
        try:
            print(f"Processing item link: {item_link}")

            # Navigate to the item's page to extract the item ID and other data
            driver.get(item_link)
            delay = random.uniform(0, 10)
            time.sleep(delay)
            total_delay_time += delay

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
                    print(f"Item is already stored in the database. Updated the graphs.")
                else:
                    # Store the item data and JSON data
                    item_data.update({
                        "ItemID": item_id
                    })
                    # Save the item data to Firebase Firestore
                    db.collection('new_steam_market_data').document(item_id).set(item_data)
                    print(f"Item added to the database.")

        except Exception as e:
            print(f"Error processing item: {e}")
            logging.error(f"Error processing item: {e}")

    # Close the webdriver
    # driver.quit()

    # Print the total elapsed time and total delay time
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
    print(f"Total time of scraping delays: {total_delay_time:.2f} seconds")
    print(f"Total time of scraping: {elapsed_time-total_delay_time:.2f} seconds")

class URLBuilder:
    def __init__(self, base_url):
        self.base_url = base_url
        self.parsed_url = urlparse(base_url)
        self.scheme = self.parsed_url.scheme
        self.netloc = self.parsed_url.netloc
        self.path = self.parsed_url.path
        self.params = self.parsed_url.params
        self.query = parse_qs(self.parsed_url.query, keep_blank_values=True)
        self.fragment = self.parsed_url.fragment
        self.custom_queries = []

    def add_path(self, path_segment):
        if not self.path.endswith('/'):
            self.path += '/'
        self.path += path_segment

    def add_query_param(self, key, value):
        self.custom_queries.append((key, value))

    def remove_query_param(self, key):
        self.query.pop(key, None)
        self.custom_queries = [q for q in self.custom_queries if q[0] != key]

    def set_fragment(self, fragment):
        self.fragment = fragment

    def build(self):
        # Update the query with custom queries
        query_params = []

        for key, values in self.query.items():
            for value in values:
                query_params.append((key, value))

        for key, value in self.custom_queries:
            query_params.append((key, value))

        # Append appid=570 to the final query string
        query_params.append(('appid', '570'))

        # Construct the final query string manually with proper encoding
        final_query_parts = []

        for key, value in query_params:
            if isinstance(value, list):
                for v in value:
                    final_query_parts.append(f"{quote(key)}%5B%5D={quote(v)}")
            else:
                final_query_parts.append(f"{quote(key)}={quote(value)}")

        final_query = '&'.join(final_query_parts)

        # Build the final URL with appid=570 at the end
        final_url = urlunparse((self.scheme, self.netloc, self.path, self.params, final_query, self.fragment))

        return final_url

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        def center_window(root, width=400, height=400):
            # Get the screen width and height
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            
            # Calculate the position of the window
            x = (screen_width // 2) - (width // 2)
            y = (screen_height // 2) - (height // 2)
            
            # Set the position of the window
            root.geometry(f'{width}x{height}+{x}+{y}')

        self.title("Steam Scraper")
        center_window(self)
        self.geometry("400x300")
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.chosenGame = MyRadiobuttonFrame(self, "Choose a game", values=["CSGO", "DOTA2"])
        self.chosenGame.grid(row=0, column=0, padx=(0, 10), pady=(10, 0), sticky="nsew")
        self.chosenPages = MyRadiobuttonFrame(self, "Pages", values=["1", "2", "3", "4", "5"])
        self.chosenPages.grid(row=0, column=1, padx=10, pady=(10, 0), sticky="nsew")

        self.button = customtkinter.CTkButton(self, text="Submit", command=self.submit_button)
        self.button.grid(row=3, column=0, padx=10, pady=10, sticky="ew", columnspan=2)

         # Loading label (hidden initially)
        self.loading_label = customtkinter.CTkLabel(self, text="Loading...", fg_color="gray30")
        self.loading_label.grid(row=3, column=0, padx=10, pady=10, sticky="ew", columnspan=2)
        self.loading_label.grid_remove()

        # Link button (hidden initially)
        self.link_button = customtkinter.CTkButton(self, text="Go to Firebase", command=self.open_link)
        self.link_button.grid(row=3, column=0, padx=10, pady=10, sticky="ew", columnspan=2)
        self.link_button.grid_remove()

    def submit_button(self):
        

        self.button.grid_remove()
        self.loading_label.grid()

        threading.Thread(target=self.run_scrape).start()

    def run_scrape(self):
        pages = int(self.chosenPages.get(), base = 0 )

        if(self.chosenGame.get() == "DOTA2"):
            url = f"https://steamcommunity.com/market/search?appid=570"
            base_url = 'https://steamcommunity.com/market/search?q=&category_570_Hero%5B%5D=any&category_570_Slot%5B%5D=any&category_570_Type%5B%5D=any'
            builder = URLBuilder(base_url)

            filters = {
                "quality": {
                    "1": ("Standard", "category_570_Quality[]", "tag_unique"),
                    "2": ("Inscribed", "category_570_Quality[]", "tag_strange"),
                    "3": ("Auspicious", "category_570_Quality[]", "tag_lucky"),
                    "4": ("Genuine", "category_570_Quality[]", "tag_genuine"),
                    "5": ("Autographed", "category_570_Quality[]", "tag_autographed"),
                    "6": ("Heroic", "category_570_Quality[]", "tag_tournament"),
                    "7": ("Frozen", "category_570_Quality[]", "tag_frozen"),
                    "8": ("Cursed", "category_570_Quality[]", "tag_haunted"),
                    "9": ("Base", "category_570_Quality[]", "tag_base"),
                    "10": ("Infused", "category_570_Quality[]", "tag_infused"),
                    "11": ("Corrupted", "category_570_Quality[]", "tag_corrupted"),
                    "12": ("Unusual", "category_570_Quality[]", "tag_unusual"),
                    "13": ("Exalted", "category_570_Quality[]", "tag_exalted"),
                    "14": ("Elder", "category_570_Quality[]", "tag_vintage"),
                    "15": ("Glitter", "category_570_Quality[]", "tag_glitter"),
                    "16": ("Gold", "category_570_Quality[]", "tag_gold"),
                    "17": ("Holo", "category_570_Quality[]", "tag_holo"),
                    "18": ("Legacy", "category_570_Quality[]", "tag_legacy"),
                    "19": ("Favored", "category_570_Quality[]", "tag_favored"),
                    "20": ("Ascendant", "category_570_Quality[]", "tag_ascendant")
                },
                "rarity": {
                    "1": ("Common", "category_570_Rarity[]", "tag_Rarity_Common"),
                    "2": ("Uncommon", "category_570_Rarity[]", "tag_Rarity_Uncommon"),
                    "3": ("Rare", "category_570_Rarity[]", "tag_Rarity_Rare"),
                    "4": ("Mythical", "category_570_Rarity[]", "tag_Rarity_Mythical"),
                    "5": ("Immortal", "category_570_Rarity[]", "tag_Rarity_Immortal"),
                    "6": ("Legendary", "category_570_Rarity[]", "tag_Rarity_Legendary"),
                    "7": ("Seasonal", "category_570_Rarity[]", "tag_Rarity_Seasonal"),
                    "8": ("Arcana", "category_570_Rarity[]", "tag_Rarity_Arcana"),
                    "9": ("Ancient", "category_570_Rarity[]", "tag_Rarity_Ancient")
                }
            }

            while True:
                print("Choose a filter category to add:")
                print("1. Quality")
                print("2. Rarity")
                print("3. Remove a query parameter")
                print("4. Set URL fragment")
                print("5. Build URL")
                print("6. Exit")
                category_choice = input("Enter your choice: ")

                if category_choice == '1':
                    category = "quality"
                elif category_choice == '2':
                    category = "rarity"
                elif category_choice == '3':
                    key = input("Enter the query parameter key to remove: ")
                    builder.remove_query_param(key)
                    continue
                elif category_choice == '4':
                    fragment = input("Enter the URL fragment: ")
                    builder.set_fragment(fragment)
                    continue
                elif category_choice == '5':
                    final_url = builder.build()
                    print(f"Final URL: {final_url}")
                    continue
                elif category_choice == '6':
                    break
                else:
                    print("Invalid choice. Please try again.")
                    continue

                print(f"Choose a {category} filter to add:")
                for key, (description, query_key, value) in filters[category].items():
                    print(f"{key}. {description}")
                filter_choice = input("Enter your choice: ")

                if filter_choice in filters[category]:
                    description, query_key, value = filters[category][filter_choice]
                    builder.add_query_param(query_key, value)
                    print(f"Added {category} filter: {description}")
                else:
                    print("Invalid choice. Please try again.")

            self.after(scrape_dota2, self.process_complete)
            # Run Dota 2 scraping with built URL
            scrape_dota2(final_url, num_pages=pages, items_per_page=10)

        else:
            url = f"https://steamcommunity.com/market/search?appid=730"
            scrape_CSGO(url, num_pages=pages, items_per_page=10)
        
        self.after(0, self.process_complete)
    
    def process_complete(self):
        # Hide loading label and show link button
        self.loading_label.grid_remove()
        self.link_button.grid()

    def open_link(self):
        import webbrowser
        webbrowser.open("https://console.firebase.google.com/u/0/project/steamscraper-28b94/firestore/databases/-default-/data/~2Fnew_steam_market_data")

class MyRadiobuttonFrame(customtkinter.CTkFrame):
    def __init__(self, master, title, values):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.values = values
        self.title = title
        self.radiobuttons = []
        self.variable = customtkinter.StringVar(value="")

        self.title = customtkinter.CTkLabel(self, text=self.title, fg_color="gray30", corner_radius=6)
        self.title.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")

        for i, value in enumerate(self.values):
            radiobutton = customtkinter.CTkRadioButton(self, text=value, value=value, variable=self.variable)
            radiobutton.grid(row=i + 1, column=0, padx=10, pady=(10, 0), sticky="w")
            self.radiobuttons.append(radiobutton)

    def get(self):
        return self.variable.get()

    def set(self, value):
        self.variable.set(value)

class MyCheckboxFrame(customtkinter.CTkFrame):
    def __init__(self, master, title, values):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.values = values
        self.title = title
        self.checkboxes = []

        self.title = customtkinter.CTkLabel(self, text=self.title, fg_color="gray30", corner_radius=6)
        self.title.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")

        for i, value in enumerate(self.values):
            checkbox = customtkinter.CTkCheckBox(self, text=value)
            checkbox.grid(row=i+1, column=0, padx=10, pady=(10, 0), sticky="w")
            self.checkboxes.append(checkbox)

    def get(self):
        checked_checkboxes = []
        for checkbox in self.checkboxes:
            if checkbox.get() == 1:
                checked_checkboxes.append(checkbox.cget("text"))
        return checked_checkboxes
    

app = App()
app.mainloop()