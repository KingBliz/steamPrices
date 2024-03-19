from selenium import webdriver
from selenium.webdriver.common.by import By
import threading
import time
import mysql.connector

#33 listing per second

# Constants for sleep times
SCRAPING_DELAY = 2

# Function to scrape data from a page
def scrape_page(url, proxy, data):
    # Set up options for Chrome WebDriver
    chrome_options = webdriver.ChromeOptions()
    #chrome_options.add_argument('--proxy-server=%s' % proxy)
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    # Initialize the Chrome webdriver with proxy
    driver = webdriver.Chrome(options=chrome_options)
    
    # Navigate to the provided URL
    driver.get(url)
    
    # Wait for the page to load
    time.sleep(SCRAPING_DELAY)
    
    try:
        for i in range(10):
            pannel = driver.find_element(By.XPATH,"/html/body/div[1]/div[7]/div[2]/div[1]/div[4]/div[2]/div[2]/div/div[1]")
            individualItems = pannel.find_elements(By.XPATH,"//div[@class='market_listing_row market_recent_listing_row market_listing_searchresult']")

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

# Function to save data to MySQL database
def save_to_mysql(data):
    # Connect to MySQL database
    db_connection = mysql.connector.connect(
        host="localhost",
        user="myuser",
        password="mypassword",
        database="market"
    )
    cursor = db_connection.cursor()

    # Create table if not exists
    create_table_query = """
    CREATE TABLE IF NOT EXISTS steam_market_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255),
        price VARCHAR(255)
    )
    """
    cursor.execute(create_table_query)

    # Insert data into the table
    insert_query = """
    INSERT INTO steam_market_data (name, price)
    VALUES (%s, %s)
    """
    for item in data:
        cursor.execute(insert_query, (item["Name"], item["Price"]))

    # Commit changes and close connection
    db_connection.commit()
    cursor.close()
    db_connection.close()

# URLs to scrape
urls = [
    "https://steamcommunity.com/market/search?appid=730",
    "https://steamcommunity.com/market/search?appid=730#p16_popular_desc",
    "https://steamcommunity.com/market/search?appid=730#p29_popular_desc"
]

proxies = [
    "66.42.60.190:21358",
    "178.72.192.37:5678",
    "178.72.192.37:5678"
]

# Data list to store scraped data
data = []

# Create threads for each URL with respective proxies
threads = []
for url, proxy in zip(urls, proxies):
    thread = threading.Thread(target=scrape_page, args=(url, proxy, data))
    threads.append(thread)

# Start each thread
for thread in threads:
    thread.start()

# Wait for all threads to finish
for thread in threads:
    thread.join()

print(data)
# Save data to MySQL database
save_to_mysql(data)
