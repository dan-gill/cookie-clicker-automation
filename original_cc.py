from selenium import webdriver
from selenium.common import StaleElementReferenceException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time

CHROMEDRIVER = "/opt/homebrew/bin/chromedriver"
SERVICE = Service(CHROMEDRIVER)
UPGRADE_IDS = ["buyTime machine", "buyPortal", "buyAlchemy lab", "buyShipment", "buyMine", "buyFactory", "buyGrandma",
               "buyCursor"]

driver = webdriver.Chrome(service=SERVICE)
upgrades = {
    "buyCursor": {
        "price": 0,
        "quantity": 0,
        "cookie_rate": 1,
        "CPC": 0
    },
    "buyGrandma": {
        "price": 0,
        "quantity": 0,
        "cookie_rate": 4,
        "CPC": 0
    },
    "buyFactory": {
        "price": 0,
        "quantity": 0,
        "cookie_rate": 20,
        "CPC": 0
    },
    "buyMine": {
        "price": 0,
        "quantity": 0,
        "cookie_rate": 50,
        "CPC": 0
    },
    "buyShipment": {
        "price": 0,
        "quantity": 0,
        "cookie_rate": 100,
        "CPC": 0
    },
    "buyAlchemy lab": {
        "price": 0,
        "quantity": 0,
        "cookie_rate": 500,
        "CPC": 0
    },
    "buyPortal": {
        "price": 0,
        "quantity": 0,
        "cookie_rate": 6666,
        "CPC": 0
    },
    "buyTime machine": {
        "price": 0,
        "quantity": 0,
        "cookie_rate": 123456,
        "CPC": 0
    }
}

driver.get("http://orteil.dashnet.org/experiments/cookie/")

is_game_on = True
cookie = driver.find_element(by=By.ID, value="cookie")
start_time = time.time()
end_time = time.time() + 3600

while is_game_on:
    money = int(driver.find_element(by=By.ID, value="money").text.replace(",", ""))
    cookie.click()

    factory_upgrade = 1 if upgrades["buyFactory"]["quantity"] > 0 else 0
    mine_upgrade = 2 if upgrades["buyMine"]["quantity"] > 0 else 0
    shipment_upgrade = 3 if upgrades["buyShipment"]["quantity"] > 0 else 0
    lab_upgrade = 4 if upgrades["buyAlchemy lab"]["quantity"] > 0 else 0
    portal_upgrade = 5 if upgrades["buyPortal"]["quantity"] > 0 else 0
    time_machine_upgrade = 6 if upgrades["buyTime machine"]["quantity"] > 0 else 0
    upgrades["buyGrandma"]["cookie_rate"] = 4 + factory_upgrade + mine_upgrade + shipment_upgrade + lab_upgrade + \
                                            portal_upgrade + time_machine_upgrade

    for upgrade_id in UPGRADE_IDS:
        cookie.click()
        try:
            upgrade = driver.find_element(by=By.ID, value=upgrade_id)
            price = int(upgrade.find_element(by=By.CSS_SELECTOR, value="b").text.split(" - ")[1].replace(",", ""))
            upgrades[upgrade_id]["price"] = price
        except StaleElementReferenceException:
            continue

    best_cookie_rate = 0
    for (k, v) in upgrades.items():
        cookie.click()
        upgrades[k]["CPC"] = upgrades[k]["cookie_rate"] / upgrades[k]["price"]
        if upgrades[k]["CPC"] > best_cookie_rate:
            best_cookie_rate = upgrades[k]["CPC"]

    found_keys = [k for k, v in upgrades.items() if best_cookie_rate == v["CPC"]]

    for key in found_keys:
        cookie.click()
        if money >= upgrades[key]["price"]:
            try:
                driver.find_element(by=By.ID, value=key).click()
                upgrades[key]["quantity"] += 1
            except StaleElementReferenceException:
                continue

    cookie.click()

    if time.time() >= end_time:
        is_game_on = False
        cps = driver.find_element(by=By.ID, value="cps")
        print(cps.text)

    cookie.click()
