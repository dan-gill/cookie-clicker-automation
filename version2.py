from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from os.path import exists
import time

CHROMEDRIVER = "/opt/homebrew/bin/chromedriver"
SERVICE = Service(CHROMEDRIVER)
options = Options()
options.add_argument("--start-maximized")
PROGRESS_FILE = "./MoldySpaghettiBakery.txt"
UPGRADE_TYPES = ["upgrades", "techUpgrades", "toggleUpgrades"]
PRODUCT_TO_PURCHASE_XPATH = '//div[@class="product unlocked enabled"]/div/span[starts-with(@id,"productPrice") ' \
                            'and @style="color: rgb(0, 255, 0);"]/../..'
BULK_XPATH = '//div[@class="storePreButton storeBulkAmount" and @style="color: rgb(0, 255, 0);"]'

# Block ads
driver = webdriver.Chrome(service=SERVICE, options=options)
driver.get("https://chrome.google.com/webstore/detail/ublock-origin/cjpalhdlnbpafiamejdnhcphjbkeiagm")
time.sleep(5)
driver.find_element(by=By.XPATH, value='//div[@role="button" and @aria-label="Add to Chrome"]').click()
time.sleep(10)

# Load game webpage
driver.get("https://orteil.dashnet.org/cookieclicker/")

is_game_on = True
save_and_exit = "No"
trillion_cookies = input("Trillion cookie ascension achievement (On/Off)? ")


def harvest_fading_plants():
    xpath = '//div[@class="gardenTileIcon" and starts-with(@style,"display: block; opacity: 0.5;")]/..'
    try:
        next_tick = driver.find_element(by=By.XPATH, value='//div[@id="gardenNextTick"]').text
        if next_tick.find("minute") == -1:
            fading_plants = driver.find_elements(by=By.XPATH, value=xpath)
            for fading_plant in fading_plants:
                fading_plant.click()
    except:
        pass


def is_veil_active():
    try:
        driver.find_element(by=By.XPATH, value='//div[@id="toggleUpgrades"]/div[@data-id="564"]')
        return True
    except NoSuchElementException:
        return False


def trillion_cookie_check():
    cookie_count = int(driver.find_element(by=By.ID, value="cookies").text.split()[0].replace(",", ""))
    if cookie_count == 1000000000000:
        try:
            driver.find_element(by=By.ID, value="ascendMeter").click()
            time.sleep(.25)
            driver.find_element(by=By.ID, value="promptOption0").click()
            input("Finish ascending. ")
        except:
            pass
    else:
        pass


def click_cookie(trillion_cookie_achievement, veil_active):
    # shimmer_types = ["Golden cookie", "Reindeer", "Wrath cookie"]
    shimmer_types = ["Golden cookie", "Reindeer"]
    try:
        if not veil_active:
            cookie.click()
            if trillion_cookie_achievement == "On":
                trillion_cookie_check()
            # Click shimmer types
            for shimmer_type in shimmer_types:
                try:
                    driver.find_element(by=By.XPATH, value=f'//div[@id="shimmers"]/div[@alt="{shimmer_type}"]').click()
                except:
                    pass

    except:
        pass


def save_game():
    try:
        # driver.find_element(by=By.ID, value="prefsButton").click()
        # time.sleep(1)
        driver.execute_script("javascript:Game.ExportSave();")
        save_code = driver.find_element(by=By.ID, value="textareaPrompt").text
        if save_code == "":
            input("Save code corrupted. Copy save file before continuing.")
        with open(file=PROGRESS_FILE, mode="w") as progress:
            progress.write(save_code)

        # with open("./upgrades.json", "w") as f:
        #     json.dump(upgrades, f)

        driver.execute_script("javascript:Game.ClosePrompt();")
        # driver.execute_script("javascript:Game.ShowMenu();")
        # time.sleep(0.51)
    except:
        input("Save game failed. Waiting on user.")


def select_bulk_mode():
    try:
        driver.find_element(by=By.XPATH, value=BULK_XPATH).click()
    except:
        click_cookie(trillion_cookies, veil)


def buy_products():
    wait = False
    exit_time = time.time() + 3

    while not wait and time.time() <= exit_time:
        select_bulk_mode()
        wait = wait_for_upgrade()

        if not wait:
            try:
                driver.find_element(by=By.XPATH, value=PRODUCT_TO_PURCHASE_XPATH).click()
            except:
                click_cookie(trillion_cookies, veil)
                break


def buy_upgrades():
    global veil
    div_crate_class = 'div[@class="crate upgrade enabled"]'

    for upgrade_type in UPGRADE_TYPES:
        if upgrade_type == "upgrades":
            div_color_class = 'div[@class="CMBackBlue" or @class="CMBackGray"]'
        else:
            div_color_class = 'div[@class="CMBackBlue"]'
        upgrade_enabled_xpath = f'//div[@id="{upgrade_type}"]/{div_crate_class}/{div_color_class}/..'
        season_active = is_season_timer_active()
        try:
            desired_upgrades = driver.find_elements(by=By.XPATH, value=upgrade_enabled_xpath)
            for desired_upgrade in desired_upgrades:
                data_id = int(desired_upgrade.get_attribute("data-id"))
                if data_id != 452 and not (data_id in {331, 182, 183, 184, 185, 209, 563} and
                                           season_active):
                    desired_upgrade.click()
                    if data_id == 563:
                        veil = True
                    elif data_id in {182, 183, 184, 185, 209}:
                        season_active = True
                else:
                    click_cookie(trillion_cookies, veil)
        except:
            click_cookie(trillion_cookies, veil)


def wait_for_upgrade():
    wait = False
    div_crate_class = 'div[@class="crate upgrade" or @class="crate upgrade enabled"]'
    for upgrade_type in UPGRADE_TYPES:
        if upgrade_type == "toggleUpgrades":
            elder_pledge_xpath = f'//div[@id="toggleUpgrades"]/div[@data-id="74"]/div[@class="pieTimer"]'
            # div_color_class = 'div[@class="CMBackBlue" or @class="CMBackGray"]'
            div_color_class = 'div[@class="CMBackBlue"]'
            try:
                driver.find_element(by=By.XPATH, value=elder_pledge_xpath)
                elder_pledge_active = True
            except:
                elder_pledge_active = False
        else:
            div_color_class = 'div[@class="CMBackBlue"]'

        upgrades_xpath = f'//div[@id="{upgrade_type}"]/{div_crate_class}/{div_color_class}/..'
        try:
            upgrade = driver.find_element(by=By.XPATH, value=upgrades_xpath)
            if (int(upgrade.get_attribute("data-id")) not in {452, 563} and
                    not (int(upgrade.get_attribute("data-id")) == 74 and elder_pledge_active)):
                wait = True
                return wait
        except:
            click_cookie(trillion_cookies, veil)

    return wait


def is_season_timer_active():
    season_ids = [182, 183, 184, 185, 209]
    season_active = False

    for season_id in season_ids:
        season_xpath = f'//div[@id="toggleUpgrades"]/div[@data-id="{season_id}"]/div[@class="pieTimer"]'
        try:
            driver.find_element(by=By.XPATH, value=season_xpath)
            season_active = True
        except:
            pass

    return season_active


def harvest_lumps():
    try:
        lump = driver.find_element(by=By.ID, value="lumpsIcon2")
        opacity = float(lump.get_attribute("style").split("opacity: ")[1].split(";")[0])
        if opacity == 1:
            driver.execute_script("javascript:Game.clickLump();")
    except:
        pass


def stock_market():
    try:
        broker = driver.find_element(by=By.ID, value="bankBrokersBuy")
        if broker.get_attribute("class") != "bankButton bankButtonBuy bankButtonOff":
            broker.click()
    except:
        click_cookie(trillion_cookies, veil)

    # if int(time.time()) % 49 < 3:
    try:
        bank_level = int(driver.find_element(by=By.ID, value="productLevel5").text.split()[1])
        number_of_goods = len(driver.find_elements(by=By.XPATH, value='//div[@class="bankGood"]'))
        for i in range(number_of_goods - 1):
            try:
                stock_price = float(driver.find_element(by=By.ID, value=f"bankGood-{i}-val").text.replace("$", ""))
                stock_shares = int(driver.find_element(by=By.ID, value=f"bankGood-{i}-stock").text)
                stock_max = int(driver.find_element(by=By.ID, value=f"bankGood-{i}-stockMax").text.replace("/", ""))
                if stock_price <= (10 * i + bank_level - 1) / 4 and stock_shares != stock_max:
                    driver.find_element(by=By.ID, value=f"bankGood-{i}_Max").click()
                elif stock_shares > 0 and stock_price >= (10 * i + bank_level - 1):
                    driver.find_element(by=By.ID, value=f"bankGood-{i}_-All").click()
                else:
                    click_cookie(trillion_cookies, veil)
            except:
                click_cookie(trillion_cookies, veil)
    except:
        click_cookie(trillion_cookies, veil)


def upgrade_santa():
    try:
        driver.execute_script("javascript:Game.UpgradeSanta();")
    except:
        pass


def train_dragon():
    try:
        driver.execute_script("javascript:Game.UpgradeDragon();")
    except:
        pass


def pet_the_dragon():
    global dragon_upgrades_complete
    dragon_xpath = '//div[@id="statsUpgrades"]//div[@class="crate upgrade enabled noFrame" and (@data-id="648" or ' \
                   '@data-id="649" or @data-id="650" or @data-id="651")]'
    available_xpath = '//div[@id="upgrades"]//div[@class="crate upgrade" and (@data-id="648" or ' \
                      '@data-id="649" or @data-id="650" or @data-id="651")]'
    try:
        driver.find_element(by=By.ID, value="statsButton").click()
        dragon_upgrades = driver.find_elements(by=By.XPATH, value=dragon_xpath)
        driver.execute_script("javascript:Game.ShowMenu();")
    except:
        dragon_upgrades = []

    try:
        available_dragon = driver.find_elements(by=By.XPATH, value=available_xpath)
    except:
        available_dragon = []

    upgrades_obtained = len(dragon_upgrades) + len(available_dragon)

    try:
        if upgrades_obtained < 4:
            driver.execute_script("javascript:Game.ClickSpecialPic();")
        else:
            dragon_upgrades_complete = True
    except:
        pass


def pantheon():
    global veil
    utc_hour = time.gmtime().tm_hour
    utc_min = time.gmtime().tm_min

    if (utc_hour in {0, 12, 18, 21} and utc_min == 0) or (utc_hour == 9 and utc_min == 19):
        temple_slot = "templeSlot0"  # Diamond
    elif utc_hour in {1, 13} and utc_min == 12:
        temple_slot = "templeSlot1"  # Ruby
    elif (utc_hour == 4 and utc_min == 0) or (utc_hour == 10 and utc_min == 20):
        temple_slot = "templeSlot2"  # Jade
    elif utc_hour in {19, 22} and utc_min == 30:
        temple_slot = "None"
    else:
        temple_slot = "No change"

    if temple_slot != "No change":
        current_slot = driver.find_element(by=By.XPATH, value='//div[@id="templeGodDrag3"]/../..')
        current_slot_id = current_slot.get_attribute("id")
        cyclius = driver.find_element(by=By.ID, value="templeGodDrag3")
        if temple_slot != current_slot_id:
            if temple_slot != "None":
                new_slot = driver.find_element(by=By.ID, value=temple_slot)
                ActionChains(driver).drag_and_drop(source=cyclius, target=new_slot).perform()
            else:
                if veil:
                    new_slot = driver.find_element(by=By.ID, value="templeGodDrag0")
                else:
                    new_slot = driver.find_element(by=By.ID, value="templeGodDrag9")
                ActionChains(driver).drag_and_drop(source=new_slot, target=current_slot).perform()


def open_mini_games():
    minigame_rows = [2, 5, 6, 7]

    for minigame_row in minigame_rows:
        try:
            driver.find_element(by=By.XPATH, value=f'//div[@id="row{minigame_row}" and @class="row enabled"]')
            driver.execute_script(f"javascript:Game.ObjectsById[{minigame_row}].switchMinigame(-1);")
        except:
            pass


# time.sleep(2)
# Click to accept cookie notification
try:
    driver.find_element(by=By.XPATH, value='//a[@class="cc_btn cc_btn_accept_all"]').click()
except NoSuchElementException:
    pass

# time.sleep(2)
# If language isn't selected, select it.
try:
    driver.find_element(by=By.ID, value="langSelect-EN").click()
except NoSuchElementException:
    pass

time.sleep(0.5)
# Close save progress notification
try:
    driver.execute_script("javascript:Game.CloseNote(1);")
except:
    pass

# Configure options
time.sleep(1)
# driver.find_element(by=By.ID, value="prefsButton").click()
if exists(PROGRESS_FILE):
    try:
        driver.execute_script("javascript:Game.ImportSave();")
        with open(file=PROGRESS_FILE, mode="r") as save_file:
            load_save = save_file.read()
            driver.find_element(by=By.ID, value="textareaPrompt").send_keys(load_save)

        driver.find_element(by=By.ID, value="promptOption0").click()
        try:
            upload_error_element = driver.find_element(by=By.ID, value="importError")
            upload_error = False if upload_error_element.text == "" else True
        except NoSuchElementException:
            upload_error = False

        if upload_error:
            input("Try uploading manually. Press Return when done.")
        else:
            time.sleep(1)

    except NoSuchElementException:
        driver.execute_script("javascript:Game.ClosePrompt();")

# Turn off short numbers
# driver.execute_script(
#     "javascript:Game.Toggle('format','formatButton','Short numbers OFF','Short numbers ON','1');BeautifyAll();"
#     "Game.RefreshStore();Game.upgradesToRebuild=1;PlaySound('snd/tick.mp3');")

driver.execute_script(
    "javascript:(function() {Game.LoadMod('https://cookiemonsterteam.github.io/CookieMonster/dist/CookieMonster.js');}"
    "());")

input("Sort buildings and upgrades before continuing.")

# driver.execute_script("javascript:Game.ClosePrompt();")

cookie = driver.find_element(by=By.ID, value="bigCookie")
end_time = time.time() + (3600 * 12)
prompt_for_save = input("Do you want a manual run this round (Yes/No)? ")
dragon_upgrades_complete = False

while is_game_on and not (save_and_exit == "Yes"):
    open_mini_games()
    harvest_lumps()
    train_dragon()
    veil = is_veil_active()
    harvest_fading_plants()
    # pantheon()
    if not dragon_upgrades_complete:
        pet_the_dragon()
    upgrade_santa()

    if not prompt_for_save == "Yes":
        click_cookie(trillion_cookies, veil)

        # Check for buffs
        try:
            driver.find_element(by=By.XPATH, value='//div[@id="buffs"]/div[@class="crate enabled buff"]')
            skip_pause = True
        except:
            skip_pause = False

        # Buy upgrades and products
        if trillion_cookies != "On":
            buy_upgrades()
            buy_products()

        # Click fortune
        try:
            driver.find_element(by=By.XPATH, value='//div[@id="commentsText1"]/span[@class="fortune"]/..').click()
        except:
            click_cookie(trillion_cookies, veil)

        stock_market()

        if not skip_pause:
            if time.time() >= end_time:
                is_game_on = False

            if time.gmtime().tm_sec < 5:
                save_game()
                time.sleep(5)
                # Close notes
                try:
                    driver.execute_script("javascript:Game.CloseNotes();")
                except:
                    click_cookie(trillion_cookies, veil)

    elif prompt_for_save == "Yes":
        save_and_exit = input("Save game and exit (Yes/No)? ")

save_game()
driver.quit()
