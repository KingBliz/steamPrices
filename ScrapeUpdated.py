import time
import mysql.connector
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By


class SteamMarketScraper:
    def __init__(self):
        self.data = []
        self.driver = None

    def start_driver(self):
        # Start web browser driver to emulate a real browser visiting the site to avoid captcha or bot recognition
        browser_options = ChromeOptions()
        self.driver = Chrome(options=browser_options)

        self.driver.execute_cdp_cmd('Emulation.setUserAgentOverride', {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win32; x86) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.129 Safari/537.36",
            #"platform": "Win32",
            #"acceptLanguage":"ro-RO"
        })

    def scrape_data(self, url):
        self.driver.get(url)
        time.sleep(5)

        for i in range(2): #Number of pages to scrape
            panel = self.driver.find_element(By.XPATH, "/html/body/div[1]/div[7]/div[2]/div[1]/div[4]/div[2]/div[2]/div/div[1]")
            individualItems = panel.find_elements(By.XPATH, "//div[@class='market_listing_row market_recent_listing_row market_listing_searchresult']")

            for individualItem in individualItems:
                title = individualItem.find_element(By.XPATH, ".//span[@class='market_listing_item_name']")
                price = individualItem.find_element(By.XPATH, ".//span[@class='normal_price']")

                item_data = {
                    "Name": title.text,
                    "Price": price.text[1:],
                    "Type": "Case" if "Case" in title.text else None
                }

                self.data.append(item_data)

            time.sleep(5)

            forwardButton = self.driver.find_element(By.XPATH, "/html/body/div[1]/div[7]/div[2]/div/div[4]/div[2]/div[2]/div/div[2]/div[1]/span[3]")
            forwardButton.click()

            time.sleep(5)

    def close_driver(self):
        if self.driver:
            self.driver.quit()

    def get_data(self, url):
        self.start_driver()
        self.scrape_data(url)
        self.close_driver()
        return self.data


def save_to_mysql(data):
    # Connect to MySQL database
    db_connection = mysql.connector.connect(
        host="localhost",
        user="user",
        password="password",
        database="steam_market"
    )
    cursor = db_connection.cursor()

    # Create table if not exists
    create_table_query = """
    CREATE TABLE IF NOT EXISTS steam_market_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255),
        price VARCHAR(255),
        type VARCHAR(255)
    )
    """
    cursor.execute(create_table_query)

    # Insert data into the table
    insert_query = """
    INSERT INTO steam_market_data (name, price, type)
    VALUES (%s, %s, %s)
    """
    for item in data:
        cursor.execute(insert_query, (item["Name"], item["Price"], item["Type"]))

    # Commit changes and close connection
    db_connection.commit()
    cursor.close()
    db_connection.close()


def main():
    scraper = SteamMarketScraper()
    data = scraper.get_data("https://steamcommunity.com/market/search?appid=730")
    print(data)

    # Save data to MySQL database
    save_to_mysql(data)


if __name__ == "__main__":
    main()