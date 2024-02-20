import random
import time
import pandas as pd
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By


def getData(url)->list:
    data = []
    #Start web browser driver to emulate a real browser visiting the site to avoid captcha or bot recognition
    browser_options = ChromeOptions()
    driver = Chrome(options=browser_options)

    driver.execute_cdp_cmd('Emulation.setUserAgentOverride', {

            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win32; x86) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.129 Safari/537.36",

            #"platform": "Win32",

            #"acceptLanguage":"ro-RO"

    })
    
    driver.get(url)

    time.sleep(5)
    
    title = driver.find_element(By.XPATH,"/html/body/div[1]/div[7]/div[2]/div[1]/div[4]/div[2]/div[2]/div/div[1]/a[1]/div/div[2]/span[1]")
    price = driver.find_element(By.XPATH,"/html/body/div[1]/div[7]/div[2]/div[1]/div[4]/div[2]/div[2]/div/div[1]/a[1]/div/div[1]/div[2]/span[1]/span[1]")
    quanitity = driver.find_element(By.XPATH,"/html/body/div[1]/div[7]/div[2]/div[1]/div[4]/div[2]/div[2]/div/div[1]/a[1]/div/div[1]/div[1]/span/span")
    data.append(title.text)
    data.append(price.text)
    data.append(quanitity.text)
    

    driver.quit()
    return data

def main():
    data = getData("https://steamcommunity.com/market/search?appid=730")
    print(data)

main()

