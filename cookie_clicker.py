import math

from selenium import webdriver
from selenium.common import NoSuchElementException, WebDriverException, ElementClickInterceptedException, \
    JavascriptException, ElementNotInteractableException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time
from os.path import exists
from os import environ

CHROME_BINARY_FULL_PATH = environ["CHROME_BINARY_FULL_PATH"]
SECONDS_UNTIL_NEXT_TICK = 20


def timestamp():
    ts = time.localtime()
    return f'{ts.tm_hour:02}:{ts.tm_min:02}:{ts.tm_sec:02}'


class CookieClicker:
    def __init__(self, trillion_cookies, endless_cycle, save_file, farming_goal, building_level_goal):
        self.upgrades_to_buy = []
        self.dragon_auras = None
        self.dragon_auras_lookup = None
        self.chromedriver = "/opt/homebrew/bin/chromedriver"
        # Install Chrome for testing: npx @puppeteer/browsers install chrome@stable
        self.service = Service(self.chromedriver)
        self.options = webdriver.ChromeOptions()
        self.options.binary_location = CHROME_BINARY_FULL_PATH
        self.driver = webdriver.Chrome(service=self.service, options=self.options)

        self.attempt_1T_achievement = trillion_cookies
        self.building_level_goal = building_level_goal
        self.attempt_endless_cycle = endless_cycle
        self.save_file = save_file

        self.is_veil_active = False
        self.season_active = False
        self.dragon_upgrades_complete = False
        self.time_last_wrinkler_popped = time.time()
        self.time_next_save = time.time() + 60
        self.next_garden_tick = time.time()
        self.last_harvest_check = time.time() - (60 * 15)
        self.last_garden_clean = time.time() - (60 * 15)
        self.last_plant_time = time.time() - (60 * 15)
        self.ascensions = 0
        self.dragon_level = 0
        self.max_dragon_level = 0
        self.endless_cycle_achievement_won = False
        self.dragon_complete = False
        self.title = None
        self.farm_level = 0
        self.all_garden_drops_unlocked = False
        self.farm_minigame = "Game.Objects['Farm'].minigame"
        self.farm_size = None
        self.plants = None
        self.plants_by_id = None
        self.max_plants = 34
        self.num_plants_unlocked = 0
        self.same_plant_setup = None
        self.two_plant_setup = None
        self.invalid_plant_id = 9999
        self.empty_tile_plant_id = -1
        self.cpsMult = 0
        self.spell_count_four_leaf_cookie = float(
            'inf')  # https://mylaaan.github.io/FtHoF-Planner-v4/ Two FTHOF from 5897
        # Gambler's Dream
        self.click_golden_cookies = True
        if farming_goal == "lumps":
            # self.final_wanted_aura = 20  # Supreme Intellect
            self.final_wanted_aura = 17  # dragon's curve
        else:
            self.final_wanted_aura = 17  # dragon's curve
        self.overrides = {
            'Plastic mouse': 0,
            'Iron mouse': 0,
            'Titanium mouse': 0,
            'Adamantium mouse': 0,
            'Unobtainium mouse': 0,
            'Eludium mouse': 0,
            'Wishalloy mouse': 0,
            'Fantasteel mouse': 0,
            'Nevercrack mouse': 0,
            'Armythril mouse': 0,
            'Technobsidian mouse': 0,
            'Plasmarble mouse': 0,
            'Lucky day': 0.5,
            'Serendipity': 0.5,
            'Get lucky': 0.5,
            'A crumbly egg': 0.5,
            'A festive hat': 0.1,
            'Reindeer baking grounds': 0.1,
            'Weighted sleighs': 0.1,
            'Ho ho ho-flavored frosting': 0.1,
            'Season savings': 0.01,
            'Toy workshop': 0.05,
            "Santa's bottomless bag": 0.1,
            "Santa's helpers": 0,
            'Golden goose egg': 0.05,
            'Faberge egg': 0.01,
            'Wrinklerspawn': 0.05,
            'Cookie egg': 0,
            'Omelette': 0.1,
            'Elder Pledge': 0.1
        }
        self.cursor_upgrades = [0, 1, 2, 3, 4, 5, 6, 43, 82, 109, 188, 189, 660, 764, 873]
        self.clicking_upgrades = [75, 76, 77, 78, 119, 190, 191, 366, 367, 427, 460, 461, 661, 765, 874]

    def install_ublock(self):
        self.options.add_extension("./uBlock-Origin.crx")

    def check_achievements(self, achievement):
        try:
            if self.driver.execute_script(f"javascript:return Game.Achievements['{achievement}'].won;"):
                return True
            else:
                return False
        except JavascriptException:
            return False

    def freeze_check(self):
        new_title = self.driver.title
        if new_title != self.title:
            self.title = new_title
        else:
            self.reload_cookieclicker()

    def reload_cookieclicker(self, skip_save=False):
        if not skip_save:
            self.save_game(path=self.save_file)
        self.driver.quit()
        time.sleep(7)
        self.load_cookieclicker()

    def load_cookieclicker(self):
        self.service = Service(self.chromedriver)
        self.options = webdriver.ChromeOptions()
        self.options.binary_location = CHROME_BINARY_FULL_PATH

        self.options.add_argument("--start-maximized")
        self.options.add_argument("--mute-audio")
        self.install_ublock()
        self.driver = webdriver.Chrome(service=self.service, options=self.options)

        # Load game webpage
        self.driver.get("https://orteil.dashnet.org/cookieclicker/")
        # input("Pausing for Cloudfare")
        time.sleep(1)
        # input("Waiting for page to load")

        # Click to accept cookie notification
        self.accept_cookie_notification()

        # If language isn't selected, select it.
        self.select_language()
        time.sleep(0.5)

        # Close save progress notification
        self.close_notes()

        # Load save game
        time.sleep(1)
        self.load_save()

        self.time_last_wrinkler_popped = time.time()

        self.load_mods()

    def load_mods(self):
        self.driver.execute_script("javascript:(function() {"
                                   "Game.LoadMod('https://klattmose.github.io/CookieClicker/FortuneCookie.js'); }());")
        time.sleep(1)
        self.driver.execute_script(
            "javascript:(function() {"
            "Game.LoadMod('https://cookiemonsterteam.github.io/CookieMonster/dist/CookieMonster.js');}());")

    def accept_cookie_notification(self):
        try:
            self.driver.find_element(by=By.XPATH, value='//a[@class="cc_btn cc_btn_accept_all"]').click()
        except NoSuchElementException:
            return

    def select_language(self):
        try:
            self.driver.find_element(by=By.ID, value="langSelect-EN").click()
        except NoSuchElementException:
            return

    def click_fortune(self):
        try:
            self.driver.execute_script("javascript:if (Game.TickerEffect) {Game.tickerL.click()}")
        except JavascriptException:
            print(f"{timestamp()}: Failed to click fortune.")
            self.click_cookie()

    def close_notes(self):
        try:
            self.driver.execute_script("javascript:Game.CloseNotes();")
        except JavascriptException:
            self.click_cookie()

    def get_next_garden_tick_in_seconds(self):
        next_tick_time_js = f"javascript:return {self.farm_minigame}.nextStep / 1000"
        try:
            self.next_garden_tick = float(self.driver.execute_script(next_tick_time_js))
        except JavascriptException:
            self.next_garden_tick = float('inf')
            self.click_cookie()

    def plant_age_at_next_tick(self, x, y):
        plant_id = self.get_plant_id_of_tile(x, y)
        if plant_id != self.empty_tile_plant_id:
            age_tick = self.plants_by_id[plant_id]["ageTick"]
            age_tick_r = self.plants_by_id[plant_id]["ageTickR"]
            tile_maturity = self.get_plant_maturity_of_tile(x, y)
            age_per_tick = age_tick + age_tick_r * 0.5
            plant_mature_age = self.plants_by_id[plant_id]['mature']
            if tile_maturity / plant_mature_age < 1 / 3:
                plant_maturity = "bud"
            elif tile_maturity / plant_mature_age < 2 / 3:
                plant_maturity = "sprout"
            elif tile_maturity / plant_mature_age < 1:
                plant_maturity = "bloom"
            else:
                plant_maturity = "mature"
            ticks_until_mature = (plant_mature_age - tile_maturity) / age_per_tick
            ticks_until_mature = 0 if ticks_until_mature < 0 else ticks_until_mature
            age_at_next_tick = age_per_tick + tile_maturity
            age_at_next_tick = age_at_next_tick + (age_tick_r / 2) if age_at_next_tick + (age_tick_r / 2) >= 100 \
                else age_at_next_tick
            if age_at_next_tick + (age_tick_r / 2) >= 100 or 0 < ticks_until_mature <= 1:
                print(f"{timestamp()}: {x, y} {self.plants_by_id[plant_id]['name']} stage: {plant_maturity}; "
                      f"Age at next tick: {tile_maturity + age_per_tick}; Mature at {plant_mature_age}; "
                      f"{ticks_until_mature} ticks until mature.")
            return age_at_next_tick
        else:
            return 0

    def harvest_plants(self):
        try:
            if not self.driver.execute_script('javascript:return Game.isMinigameReady(Game.Objects["Farm"])'):
                return
        except JavascriptException:
            self.click_cookie()
            return

        if self.cpsMult <= 1 and self.next_garden_tick - time.time() > SECONDS_UNTIL_NEXT_TICK:
            return

        try:
            step_t = self.driver.execute_script(f"javascript:return {self.farm_minigame}.stepT")
        except JavascriptException:
            self.click_cookie()
            return

        if self.last_harvest_check + step_t <= self.next_garden_tick:
            for tile in self.farm_size:
                self.click_cookie()
                self.last_harvest_check = time.time()
                plant_id = self.get_plant_id_of_tile(x=tile['x'], y=tile['y'])
                if plant_id not in {self.invalid_plant_id, self.empty_tile_plant_id}:
                    self.get_plant_details()
                    plant_name = self.plants_by_id[plant_id]["key"]
                    plant_age = self.get_plant_maturity_of_tile(x=tile['x'], y=tile['y'])
                    plant_mature_age = self.plants_by_id[plant_id]["mature"]
                    plant_unlocked = self.plants_by_id[plant_id]["unlocked"]
                    plant_age_at_next_tick = self.plant_age_at_next_tick(x=tile['x'], y=tile['y'])

                    # Harvest decaying plants
                    if plant_age_at_next_tick >= 100:
                        print(f'{timestamp()}: Harvesting {plant_name} from {(tile["x"], tile["y"])} before '
                              'decay.')
                        try:
                            self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile['x']},"
                                                       f"{tile['y']})")
                        except JavascriptException:
                            self.click_cookie()
                    # Harvest mature plants to unlock seeds
                    elif not plant_unlocked and plant_name != "meddleweed" and plant_age >= plant_mature_age:
                        print(f'{timestamp()}: Harvesting all mature {plant_name} '
                              f'from ({tile["x"]}, {tile["y"]}) to unlock new seed.')
                        try:
                            self.driver.execute_script(f"javascript:{self.farm_minigame}.harvestAll("
                                                       f"{self.farm_minigame}.plants['{plant_name}'], 0, 0);")
                        except JavascriptException:
                            self.click_cookie()
                    # Harvest meddleweed if Brown Mold and Crumbspore unlocked
                    elif plant_name == "meddleweed" and self.is_seed_unlocked_or_growing("brownMold") and \
                            self.is_seed_unlocked_or_growing("crumbspore"):
                        print(f'{timestamp()}: Harvesting all meddleweed.')
                        try:
                            self.driver.execute_script(f"javascript:{self.farm_minigame}.harvestAll("
                                                       f"{self.farm_minigame}.plants['meddleweed'], 0, 1);")
                        except JavascriptException:
                            self.click_cookie()

    def harvest_fading_plants(self):
        if self.cpsMult > 1 or self.next_garden_tick - time.time() <= SECONDS_UNTIL_NEXT_TICK:
            for tile in self.farm_size:
                self.click_cookie()
                if self.plant_age_at_next_tick(x=tile["x"], y=tile["y"]) >= 100:
                    print(f'{timestamp()}: Harvesting tile {tile} before decay.')
                    try:
                        self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile['x']},{tile['y']})")
                    except JavascriptException:
                        self.click_cookie()

    def harvest_mature_plants(self, x, y):
        if self.next_garden_tick - time.time() <= SECONDS_UNTIL_NEXT_TICK or self.cpsMult > 1:
            seed_id = self.get_plant_id_of_tile(x, y)
            if self.get_plant_maturity_of_tile(x, y) >= self.plants_by_id[seed_id]["mature"]:
                plant = self.plants_by_id[seed_id]["name"]
                print(f'{timestamp()}: Harvesting tile ({x}, {y}) {plant} is mature.')
                try:
                    self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({x},{y})")
                except JavascriptException:
                    self.click_cookie()

    def get_plant_details(self):
        try:
            self.plants = self.driver.execute_script(f"javascript:return {self.farm_minigame}.plants")
            self.plants_by_id = self.driver.execute_script(f"javascript:return {self.farm_minigame}.plantsById")
            self.max_plants = self.driver.execute_script(f"javascript:return {self.farm_minigame}.plantsN")
            self.num_plants_unlocked = self.driver.execute_script(
                f"javascript:return {self.farm_minigame}.plantsUnlockedN")
            self.set_farm_size()
            for tile in self.farm_size:
                tile_id = self.get_plant_id_of_tile(tile["x"], tile["y"])
                if tile_id not in [self.empty_tile_plant_id, self.invalid_plant_id]:
                    if not self.plants_by_id[tile_id]["unlocked"]:
                        plant = self.plants_by_id[tile_id]['name']
                        self.plants[plant]["growing"] = True
                        age = self.get_plant_maturity_of_tile(x=tile["x"], y=tile["y"])
                        self.plants[plant]["ticks_until_mature"] = (self.plants[plant]["mature"] - age) / \
                                                                   (self.plants[plant]["ageTick"] +
                                                                    self.plants[plant]["ageTickR"] * 0.5)
                    else:
                        self.plants[plant]["growing"] = True
                        self.plants[plant]["ticks_until_mature"] = 0  # Set to zero if the plant is already unlocked
                    self.plants_by_id[tile_id]["growing"] = self.plants[plant]["growing"]
                    self.plants_by_id[tile_id]["ticks_until_mature"] = self.plants[plant]["ticks_until_mature"]
        except JavascriptException:
            self.click_cookie()

    def is_upgrade_unlocked(self, upgrade):
        try:
            return self.driver.execute_script(f"javascript:return Game.Upgrades['{upgrade}'].unlocked;")
        except JavascriptException:
            return False

    def plant_seed(self, x, y, seed_id):
        tile_plant_id = self.get_plant_id_of_tile(x=x, y=y)
        if tile_plant_id not in [self.empty_tile_plant_id,
                                 seed_id,
                                 self.invalid_plant_id] and (self.plants_by_id[tile_plant_id]["unlocked"] or (
                self.get_plant_maturity_of_tile(x=x, y=y) >= self.plants_by_id[tile_plant_id]["mature"]
        )
        ):
            print(f"{timestamp()}: Removing {self.plants_by_id[tile_plant_id]['name']} from ({x},{y}) to plant "
                  f"{self.plants_by_id[seed_id]['name']}.")
            try:
                self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({x},{y})")
            except JavascriptException:
                self.click_cookie()
                return

        if self.cpsMult >= 1 and self.next_garden_tick - time.time() > SECONDS_UNTIL_NEXT_TICK:
            return

        tile_plant_id = self.get_plant_id_of_tile(x=x, y=y)
        if tile_plant_id == seed_id:
            self.last_plant_time = time.time()
        elif tile_plant_id == self.empty_tile_plant_id:
            try:
                # self.cast_spell(spell_to_cast="conjure baked goods", exhaust_magic=True)
                self.cast_spell(spell_to_cast="hand of fate", exhaust_magic=True)
                self.last_plant_time = time.time()
                self.driver.execute_script(f"javascript:{self.farm_minigame}.useTool({seed_id}, {x}, {y});")
            except JavascriptException:
                self.click_cookie()

    def get_keenmoss_tiles(self):
        keenmoss_tiles = []
        for tile in self.farm_size:
            self.click_cookie()
            if self.get_plant_id_of_tile(tile["x"], tile["y"]) == self.plants["keenmoss"]["id"]:
                keenmoss_tiles.append(tile)

        return keenmoss_tiles

    def max_mature_keenmoss_reached(self, tiles):
        age_tick = self.plants["keenmoss"]["ageTick"]
        age_tick_r = self.plants["keenmoss"]["ageTickR"]
        mature_age = self.plants["keenmoss"]["mature"]
        min_ticks_until_mature = mature_age / (age_tick + age_tick_r * 0.5)
        min_ticks_until_decay = 100 / (age_tick + age_tick_r * 0.5)

        keenmoss_ticks_until_mature = []
        keenmoss_age = []
        keenmoss_details = []

        for tile in tiles:
            self.click_cookie()
            age = self.get_plant_maturity_of_tile(x=tile["x"], y=tile["y"])
            ticks_until_decay = (100 - age) / (age_tick + age_tick_r * 0.5)
            ticks_until_mature = (mature_age - age) / (age_tick + age_tick_r * 0.5)
            ticks_until_mature = 0 if ticks_until_mature < 0 else ticks_until_mature
            keenmoss_ticks_until_mature.append(ticks_until_mature)
            keenmoss_age.append(age)
            keenmoss_details.append({"ticks_until_decay": ticks_until_decay, "ticks_until_mature": ticks_until_mature})
            min_ticks_until_decay = min(min_ticks_until_decay, ticks_until_decay)
            min_ticks_until_mature = min(min_ticks_until_mature, ticks_until_mature)

        mature_keenmoss_count = sum(ticks["ticks_until_mature"] == 0 for ticks in keenmoss_details)
        max_mature_keenmoss_count = sum(ticks["ticks_until_mature"] - min_ticks_until_decay <= 0
                                        for ticks in keenmoss_details
                                        if ticks["ticks_until_decay"] >= min_ticks_until_decay)

        if mature_keenmoss_count >= max_mature_keenmoss_count:
            print(f"{timestamp()}: Mature keenmoss: {mature_keenmoss_count}; Max mature keenmoss: "
                  f"{max_mature_keenmoss_count}")
            return True
        else:
            print(f"{timestamp()}: Mature keenmoss: {mature_keenmoss_count}; Max mature keenmoss: "
                  f"{max_mature_keenmoss_count}")
            return False

    def harvest_keenmoss_field(self):
        only_keenmoss_plants = True
        for tile in self.farm_size:
            self.click_cookie()
            if self.is_tile_unlocked(tile["x"], tile["y"]):
                if self.get_plant_id_of_tile(tile["x"], tile["y"]) not in {self.empty_tile_plant_id,
                                                                           self.plants["keenmoss"]["id"]}:
                    only_keenmoss_plants = False
                    break

        if only_keenmoss_plants and (self.cpsMult > 1 or
                                     self.next_garden_tick - time.time() <= SECONDS_UNTIL_NEXT_TICK):
            print(f'{timestamp()}: Harvesting keenmoss field.')
            try:
                self.driver.execute_script(f"javascript:{self.farm_minigame}.harvestAll();")
            except JavascriptException:
                self.click_cookie()
            # for tile in self.farm_size:
            #     self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile['x']},{tile['y']})")

    def is_garden_empty(self):
        garden_empty = True
        for tile in self.farm_size:
            self.click_cookie()
            if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) != self.empty_tile_plant_id:
                garden_empty = False
                break
        return garden_empty

    def set_farm_size(self):
        self.get_farm_level()
        self.farm_size = []
        x_min = 2
        x_until = 4
        y_min = 2
        y_until = 4

        # Set min x
        if 4 <= self.farm_level <= 7:
            x_min = 1
        elif self.farm_level >= 8:
            x_min = 0

        # Set max x range
        if 2 <= self.farm_level <= 5:
            x_until = 5
        elif self.farm_level >= 6:
            x_until = 6

        # Set min y
        if 5 <= self.farm_level <= 8:
            y_min = 1
        elif self.farm_level >= 9:
            y_min = 0

        # Set max y range
        if 3 <= self.farm_level <= 6:
            y_until = 5
        elif self.farm_level >= 7:
            y_until = 6

        for x in range(x_min, x_until):
            for y in range(y_min, y_until):
                self.farm_size.append({"x": x, "y": y})

    def clean_garden(self, tiles):
        if self.cpsMult <= 1 and self.next_garden_tick - time.time() > SECONDS_UNTIL_NEXT_TICK:
            return
        try:
            step_t = self.driver.execute_script(f"javascript:return {self.farm_minigame}.stepT")
        except JavascriptException:
            self.click_cookie()
            return
        # print(f"Step: {step_t}. Last clean: {self.last_garden_clean}. Next garden tick: {self.next_garden_tick}")
        if self.last_garden_clean + step_t <= self.next_garden_tick:
            brown_mold_unlocked_or_growing = self.is_seed_unlocked_or_growing("brownMold")
            crumbspore_unlocked_or_growing = self.is_seed_unlocked_or_growing("crumbspore")
            for tile in tiles:
                self.click_cookie()
                self.last_garden_clean = time.time()
                plant_id_of_tile = self.get_plant_id_of_tile(x=tile["x"], y=tile["y"])
                if plant_id_of_tile in {self.empty_tile_plant_id, self.invalid_plant_id}:
                    self.click_cookie()
                    continue

                plant_name = self.plants_by_id[plant_id_of_tile]["key"]
                print(f'{timestamp()}: Found {plant_name} ({plant_id_of_tile}) at ({tile}). '
                      f'Unlocked: {self.plants_by_id[plant_id_of_tile]["unlocked"]}.')

                if not (brown_mold_unlocked_or_growing and crumbspore_unlocked_or_growing):
                    print(f'{timestamp()}: Brown Mold unlocked or growing: {brown_mold_unlocked_or_growing}. '
                          f'Crumbspore unlocked or growing: {crumbspore_unlocked_or_growing}')
                if (plant_name == "meddleweed" and
                    brown_mold_unlocked_or_growing and
                    crumbspore_unlocked_or_growing) or (
                        plant_name != "meddleweed" and self.plants_by_id[plant_id_of_tile]["unlocked"]
                ):
                    print(f'{timestamp()}: Harvesting plant '
                          f'{plant_name} ({plant_id_of_tile}) in tile ({tile["x"]}, {tile["y"]}).')
                    try:
                        self.driver.execute_script(f'javascript:{self.farm_minigame}.harvest({tile["x"]},{tile["y"]})')
                    except JavascriptException:
                        self.click_cookie()

    def stagger_planting(self, faster_group, faster_plant_id, slower_group, slower_plant_id,
                         faster_plant_ticks_to_mature):
        if self.cpsMult > 1 and self.next_garden_tick - time.time() > SECONDS_UNTIL_NEXT_TICK:
            return

        self.last_plant_time = time.time()

        sg_oldest_age_at_next_tick = 0
        sg_oldest_tile = None
        tile_age_sum = 0
        planted_tiles = 0
        # Plant slower seeds first
        for tile in slower_group:
            self.click_cookie()
            tile_plant_id = self.get_plant_id_of_tile(x=tile["x"], y=tile["y"])
            if tile_plant_id != slower_plant_id:
                print(f"{timestamp()}: Planting slower maturing plant: "
                      f"{self.plants_by_id[slower_plant_id]['name']} in tile {tile}.")
                self.plant_seed(x=tile["x"], y=tile["y"], seed_id=slower_plant_id)
            else:
                tile_age_at_next_tick = self.plant_age_at_next_tick(x=tile["x"], y=tile["y"])
                tile_age_sum += self.plant_age_at_next_tick(x=tile["x"], y=tile["y"])
                sg_oldest_age_at_next_tick = max(sg_oldest_age_at_next_tick, tile_age_at_next_tick)
                sg_oldest_tile = tile if sg_oldest_age_at_next_tick == tile_age_at_next_tick else sg_oldest_tile
            if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == slower_plant_id:
                planted_tiles += 1

        sg_avg_age_at_next_tick = tile_age_sum / planted_tiles if planted_tiles > 0 else 0

        print(f"{timestamp()}: Oldest {self.plants_by_id[slower_plant_id]['name']} at ({sg_oldest_tile}) will be "
              f"{sg_oldest_age_at_next_tick} at next tick. Mature age: {self.plants_by_id[slower_plant_id]['mature']}.")

        # if sg_oldest_age_at_next_tick > self.plants_by_id[slower_plant_id]["mature"]:
        if sg_avg_age_at_next_tick > self.plants_by_id[slower_plant_id]["mature"]:
            slower_plant_ticks_until_mature = 0
        else:
            slower_plant_ticks_until_mature = (self.plants_by_id[slower_plant_id]["mature"] -
                                               # sg_oldest_age_at_next_tick) / (
                                               sg_avg_age_at_next_tick) / (
                                                      self.plants_by_id[slower_plant_id]["ageTick"] +
                                                      self.plants_by_id[slower_plant_id]["ageTickR"] * 0.5)

        fg_oldest_age_at_next_tick = 0
        fg_oldest_tile = None
        if slower_plant_ticks_until_mature <= faster_plant_ticks_to_mature:
            for tile in faster_group:
                self.click_cookie()
                tile_plant_id = self.get_plant_id_of_tile(x=tile["x"], y=tile["y"])
                if tile_plant_id != faster_plant_id:
                    print(f"{timestamp()}: Planting faster maturing plant: "
                          f"{self.plants_by_id[faster_plant_id]['name']} in tile {tile}.")
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=faster_plant_id)
                else:
                    tile_age_at_next_tick = self.plant_age_at_next_tick(x=tile["x"], y=tile["y"])
                    fg_oldest_age_at_next_tick = max(fg_oldest_age_at_next_tick, tile_age_at_next_tick)
                    fg_oldest_tile = tile if fg_oldest_age_at_next_tick == tile_age_at_next_tick else fg_oldest_tile

        print(f"{timestamp()}: Oldest {self.plants_by_id[faster_plant_id]['name']} at ({fg_oldest_tile}) will be "
              f"{fg_oldest_age_at_next_tick} at next tick. Mature age: {self.plants_by_id[faster_plant_id]['mature']}.")

        if sg_oldest_age_at_next_tick > self.plants_by_id[slower_plant_id]["mature"] and \
                fg_oldest_age_at_next_tick > self.plants_by_id[faster_plant_id]["mature"]:
            self.switch_soil("woodchips")
        else:
            self.switch_soil("fertilizer")

    def mutation_setups(self):
        self.get_farm_level()
        if self.farm_level >= 9:
            self.same_plant_setup = []
            for y in [1, 4]:
                for x in range(6):
                    if x != 2:
                        self.same_plant_setup.append({"x": x, "y": y})
            # Plant type 1
            type_1 = []
            for y in [1, 4]:
                for x in [0, 5]:
                    type_1.append({"x": x, "y": y})
            type_1.append({"x": 2, "y": 1})
            type_1.append({"x": 3, "y": 4})
            type_2 = []
            for x in [1, 4]:
                for y in [1, 4]:
                    type_2.append({"x": x, "y": y})
            self.two_plant_setup = {"G": type_1, "Y": type_2}
        else:
            return

    def unlock_seeds(self):
        try:
            if not self.driver.execute_script('javascript:return Game.isMinigameReady(Game.Objects["Farm"])'):
                return
        except JavascriptException:
            self.click_cookie()
            return

        unlock_seed_order = [
            {"seed": "meddleweed", "parent": []},
            {"seed": "bakeberry", "parent": ["bakerWheat"]},  # 34
            {"seed": "brownMold", "parent": ["meddleweed"]},  # 5
            {"seed": "chocoroot", "parent": ["bakerWheat", "brownMold"]},  # 7
            {"seed": "queenbeet", "parent": ["chocoroot", "bakeberry"]},  # 67
            {"seed": "queenbeetLump", "parent": []},  # 1063 - Dead-end
            {"seed": "thumbcorn", "parent": ["bakerWheat"]},  # 3
            {"seed": "cronerice", "parent": ["bakerWheat", "thumbcorn"]},  # 75
            {"seed": "gildmillet", "parent": ["cronerice", "thumbcorn"]},  # 15
            {"seed": "clover", "parent": ["gildmillet", "bakerWheat"]},  # 20
            {"seed": "shimmerlily", "parent": ["clover", "gildmillet"]},  # 9
            {"seed": "elderwort", "parent": ["cronerice", "shimmerlily"]},  # 164
            {"seed": "whiteMildew", "parent": ["brownMold"]},  # 5
            {"seed": "wardlichen", "parent": ["cronerice", "whiteMildew"]},  # 10 - Dead-end
            {"seed": "whiteChocoroot", "parent": ["chocoroot", "whiteMildew"]},  # 7
            {"seed": "tidygrass", "parent": ["bakerWheat", "whiteChocoroot"]},  # 80
            {"seed": "everdaisy", "parent": []},  # 250 - Dead-end
            {"seed": "greenRot", "parent": ["clover", "whiteMildew"]},  # 4
            {"seed": "keenmoss", "parent": ["brownMold", "greenRot"]},  # 10
            {"seed": "drowsyfern", "parent": ["chocoroot", "keenmoss"]},  # 300 - Dead-end
            {"seed": "duketater", "parent": ["queenbeet"]},  # 212
            {"seed": "crumbspore", "parent": ["meddleweed"]},  # 15
            {"seed": "ichorpuff", "parent": ["elderwort", "crumbspore"]},  # 20 Maybe switch order? - Dead-end
            {"seed": "whiskerbloom", "parent": ["whiteChocoroot", "shimmerlily"]},  # 20
            {"seed": "nursetulip", "parent": ["whiskerbloom"]},  # 40 - Dead-end
            {"seed": "doughshroom", "parent": ["crumbspore"]},  # 43
            {"seed": "foolBolete", "parent": ["doughshroom", "greenRot"]},  # 3 - Dead-end
            {"seed": "wrinklegill", "parent": ["crumbspore", "brownMold"]},  # 26 - Dead-end
            {"seed": "chimerose", "parent": ["whiskerbloom", "shimmerlily"]},  # 18 - Dead-end
            {"seed": "glovemorel", "parent": ["thumbcorn", "crumbspore"]},  # 7 - Dead-end
            {"seed": "goldenClover", "parent": ["gildmillet", "bakerWheat"]},  # 5 - Dead-end
            {"seed": "shriekbulb", "parent": []},  # 18 - Dead-end
            {"seed": "cheapcap", "parent": ["crumbspore", "shimmerlily"]},  # 3 - Dead-end
        ]

        num_plants_unlocked_growing = 1  # Start at one because of Baker's Wheat

        if self.cpsMult == 1 and self.next_garden_tick - time.time() > SECONDS_UNTIL_NEXT_TICK:
            return

        self.mutation_setups()

        self.get_plant_details()

        if self.max_plants <= self.num_plants_unlocked:
            return

        self.get_dragon_auras()

        if (self.is_seed_unlocked_or_growing('queenbeetLump') and self.dragon_complete and
                self.dragon_auras[0] != self.final_wanted_aura):
            try:
                self.driver.execute_script(f"javascript:Game.SetDragonAura({self.final_wanted_aura},0);"
                                           "Game.ConfirmPrompt();")
            except JavascriptException:
                self.click_cookie()

        growing_seeds = []
        growing_seed_min_ticks = float('inf')

        for seed in unlock_seed_order:
            try:
                step_t = self.driver.execute_script(f"javascript:return {self.farm_minigame}.stepT")
            except JavascriptException:
                self.click_cookie()
                return
            cleaned_garden_this_cycle = self.last_garden_clean + step_t > self.next_garden_tick
            harvested_this_cycle = self.last_harvest_check + step_t > self.next_garden_tick
            planted_this_cycle = self.last_plant_time + step_t > self.next_garden_tick
            if cleaned_garden_this_cycle and harvested_this_cycle:
                if planted_this_cycle or (self.cpsMult >= 1 and
                                          self.next_garden_tick - time.time() > SECONDS_UNTIL_NEXT_TICK):
                    self.click_cookie()
                    break
            elif planted_this_cycle and (self.cpsMult <= 1 and
                                         self.next_garden_tick - time.time() > SECONDS_UNTIL_NEXT_TICK):
                self.click_cookie()
                break
            if not self.is_seed_unlocked_or_growing(seed["seed"]):
                print(f'{timestamp()}: Attempting to unlock {seed["seed"]}. '
                      f'This cycle: Cleaned? {cleaned_garden_this_cycle}; Harvested? {harvested_this_cycle}; '
                      f'Planted? {planted_this_cycle}')
                num_parents = len(seed["parent"])
                if num_parents == 1:
                    oldest_seed = 1
                    parent_seed = seed["parent"][0]
                    parent_seed_id = self.plants[seed["parent"][0]]["id"]
                    if not self.plants_by_id[parent_seed_id]["unlocked"]:
                        self.click_cookie()
                        continue

                    parent_seed_maturity = self.plants[parent_seed]["mature"]
                    parent_age_per_tick = self.plants[parent_seed]["ageTick"] + (self.plants[parent_seed]["ageTickR"]
                                                                                 * 0.5)
                    parent_ticks_until_mature = parent_seed_maturity / parent_age_per_tick
                    if parent_ticks_until_mature > growing_seed_min_ticks:
                        print(f'{timestamp()}: Skipping {seed["seed"]} because other seeds will mature before '
                              f'{parent_seed}.')
                        clean_tiles = [tile for tile in self.farm_size if tile not in self.same_plant_setup
                                       and tile not in self.two_plant_setup["G"]
                                       and tile not in self.two_plant_setup["Y"]]
                        self.clean_garden(tiles=clean_tiles)
                        self.click_cookie()
                        continue

                    for tile in self.same_plant_setup:
                        self.click_cookie()
                        self.plant_seed(x=tile["x"], y=tile["y"], seed_id=parent_seed_id)
                        if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == parent_seed_id:
                            oldest_seed = max(oldest_seed, self.get_plant_maturity_of_tile(x=tile["x"], y=tile["y"]))
                    clean_tiles = [tile for tile in self.farm_size if tile not in self.same_plant_setup]
                    self.clean_garden(tiles=clean_tiles)

                    if oldest_seed >= parent_seed_maturity and seed["parent"][0] != "meddleweed" and \
                            seed["seed"] != "meddleweed":
                        self.switch_soil("woodchips")
                    else:
                        self.switch_soil("fertilizer")
                elif num_parents == 2:
                    parent1_seed = seed["parent"][0]
                    parent2_seed = seed["parent"][1]

                    if not (self.plants[parent1_seed]["unlocked"] and self.plants[parent2_seed]["unlocked"]):
                        print(f"{timestamp()}: {seed['seed']}'s parents are not unlocked.")
                        if not self.plants[parent1_seed]["unlocked"]:
                            print(f"{timestamp()}: Waiting for {parent1_seed} to mature.")
                        if not self.plants[parent2_seed]["unlocked"]:
                            print(f"{timestamp()}: Waiting for {parent2_seed} to mature.")
                        self.click_cookie()
                        continue
                    parent1_seed_id = self.plants[parent1_seed]["id"]
                    parent1_maturity = self.plants[parent1_seed]["mature"]
                    parent1_age_per_tick = self.plants[parent1_seed]["ageTick"] + (self.plants[parent1_seed]["ageTickR"]
                                                                                   * 0.5)
                    parent1_ticks_until_mature = parent1_maturity / parent1_age_per_tick
                    parent2_seed_id = self.plants[parent2_seed]["id"]
                    parent2_maturity = self.plants[parent2_seed]["mature"]
                    parent2_age_per_tick = self.plants[parent2_seed]["ageTick"] + (self.plants[parent2_seed]["ageTickR"]
                                                                                   * 0.5)
                    parent2_ticks_until_mature = parent2_maturity / parent2_age_per_tick
                    maturity_difference = parent1_ticks_until_mature - parent2_ticks_until_mature

                    max_parent_ticks_until_mature = max(parent1_ticks_until_mature, parent2_ticks_until_mature)

                    if max_parent_ticks_until_mature > growing_seed_min_ticks:
                        print(f'{timestamp()}: Skipping {seed["seed"]} because other seeds will mature before '
                              f'{parent1_seed} and {parent2_seed}.')
                        clean_tiles = [tile for tile in self.farm_size if tile not in self.same_plant_setup
                                       and tile not in self.two_plant_setup["G"]
                                       and tile not in self.two_plant_setup["Y"]]
                        self.clean_garden(tiles=clean_tiles)
                        self.click_cookie()
                        continue

                    clean_tiles = [tile for tile in self.farm_size
                                   if tile not in self.two_plant_setup["G"] and tile not in self.two_plant_setup["Y"]]
                    self.clean_garden(tiles=clean_tiles)

                    if maturity_difference < 0:
                        self.stagger_planting(faster_group=self.two_plant_setup["G"], faster_plant_id=parent1_seed_id,
                                              slower_group=self.two_plant_setup["Y"], slower_plant_id=parent2_seed_id,
                                              faster_plant_ticks_to_mature=parent1_ticks_until_mature)
                    else:
                        self.stagger_planting(faster_group=self.two_plant_setup["Y"], faster_plant_id=parent2_seed_id,
                                              slower_group=self.two_plant_setup["G"], slower_plant_id=parent1_seed_id,
                                              faster_plant_ticks_to_mature=parent2_ticks_until_mature)
                elif seed["seed"] == "queenbeetLump":
                    if not self.plants["queenbeet"]["unlocked"]:
                        print(f"{timestamp()}: Waiting to unlock queenbeet.")
                        self.click_cookie()
                        continue
                    self.try_for_juicy_queenbeet()
                elif seed["seed"] == "meddleweed":
                    self.switch_soil("fertilizer")
                    self.clean_garden(tiles=self.farm_size)
                elif seed["seed"] == "everdaisy":
                    if not (self.plants["elderwort"]["unlocked"] and self.plants["tidygrass"]["unlocked"]):
                        if not self.plants["elderwort"]["unlocked"]:
                            print(f"{timestamp()}: Waiting to unlock elderwort.")
                        if not self.plants["tidygrass"]["unlocked"]:
                            print(f"{timestamp()}: Waiting to unlock tidygrass.")
                        self.click_cookie()
                        continue
                    else:
                        self.try_for_everdaisy()
                elif seed["seed"] == "shriekbulb":
                    if not self.plants["duketater"]["unlocked"]:
                        print(f"{timestamp()}: Waiting to unlock duketater.")
                        self.click_cookie()
                        continue
                    else:
                        self.try_for_shriekbulbs()
                break
            else:
                self.click_cookie()
                try:
                    if self.plants[seed["seed"]]["growing"] and not self.plants[seed["seed"]]["unlocked"]:
                        growing_seeds.append(seed["seed"])
                        growing_seed_min_ticks = min(growing_seed_min_ticks,
                                                     self.plants[seed["seed"]]["ticks_until_mature"])
                        self.save_game(path=f'./{seed["seed"]}.txt')
                except KeyError:
                    self.click_cookie()
                # print(f'{seed["seed"]} unlocked or growing. {num_plants_unlocked_growing} unlocked or growing.')
                continue

        for seed in unlock_seed_order:
            if self.is_seed_unlocked_or_growing(seed["seed"]):
                num_plants_unlocked_growing += 1
            else:
                self.click_cookie()

        if num_plants_unlocked_growing == self.max_plants:
            self.switch_soil('fertilizer')
        elif time.gmtime().tm_min % 5 == 0 and time.gmtime().tm_sec < 2:
            print(f"{timestamp()}: {num_plants_unlocked_growing} plants are unlocked or growing out of "
                  f"{self.max_plants}")

    def is_seed_unlocked_or_growing(self, seed):
        self.get_plant_details()
        if self.plants[seed]["unlocked"] or self.plants[seed]["growing"]:
            return True
        return False

    def sacrifice_garden(self):
        if self.all_garden_drops_unlocked and self.num_plants_unlocked == self.max_plants:
            try:
                self.driver.execute_script(f"javascript:{self.farm_minigame}.harvestAll();")
                self.driver.execute_script(f"javascript:{self.farm_minigame}.askConvert();Game.ConfirmPrompt();")
                self.get_plant_details()
            except JavascriptException:
                print(f"{timestamp()}: Failed to sacrifice garden.")
                self.click_cookie()
                return

    def garden_maintenance(self, plant_name):
        if self.cpsMult == 1 and self.next_garden_tick - time.time() > SECONDS_UNTIL_NEXT_TICK:
            return

        if self.all_garden_drops_unlocked and self.num_plants_unlocked == self.max_plants:
            self.get_farm_level()

            plant_id = self.plants[plant_name]["id"]
            self.switch_soil("fertilizer")

            if self.cpsMult == 0:
                print(f'{timestamp()}: Planting {plant_name}.')
                self.clean_garden(tiles=self.farm_size)
                for tile in self.farm_size:
                    self.click_cookie()
                    # if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) not in {self.empty_tile_plant_id,
                    #                                                                self.invalid_plant_id,
                    #                                                                plant_id}:
                    #     self.clean_garden(x=tile["x"], y=tile["y"])
                    if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == self.empty_tile_plant_id:
                        self.plant_seed(x=tile["x"], y=tile["y"], seed_id=plant_id)

            if self.cpsMult >= 7:
                self.switch_soil("clay")
                try:
                    self.driver.execute_script(f"javascript:{self.farm_minigame}.harvestAll(0, 1, 1);")
                except JavascriptException:
                    self.click_cookie()

    def obtain_garden_upgrades(self):
        # strategies = https://www.reddit.com/r/CookieClicker/comments/95iu08/strategies_for_random_drops_from_plants/
        garden_upgrades = [
            {"seed": "greenRot", "upgrade": "Green yeast digestives", "strategy": 1},
            {"seed": "bakerWheat", "upgrade": "Wheat slims", "strategy": 1},
            {"seed": "bakeberry", "upgrade": "Bakeberry cookies", "strategy": 1},
            {"seed": "elderwort", "upgrade": "Elderwort biscuits", "strategy": 3},
            {"seed": "ichorpuff", "upgrade": "Ichor syrup", "strategy": 5},
            {"seed": "drowsyfern", "upgrade": "Fern tea", "strategy": 4},
            {"seed": "duketater", "upgrade": "Duketater cookies", "strategy": 4}
        ]

        if self.cpsMult == 1 and self.next_garden_tick - time.time() > SECONDS_UNTIL_NEXT_TICK:
            return

        self.get_plant_details()

        if self.max_plants > self.num_plants_unlocked:
            return

        def strategy_1(upgrade):
            garden_upgrade_seed_id = self.plants[upgrade["seed"]]["id"]
            plant = self.plants[upgrade["seed"]]
            obtain_upgrade = plant["unlocked"]
            # plant_mature_age = self.plants[plant]["mature"]
            if obtain_upgrade:
                for tile in self.farm_size:
                    self.harvest_mature_plants(x=tile['x'], y=tile['y'])
                    can_plant_js = f'{self.farm_minigame}.canPlant({self.farm_minigame}.plants["{next_drop["seed"]}"]);'
                    try:
                        can_plant = self.driver.execute_script(f"javascript:return {can_plant_js}")
                    except JavascriptException:
                        can_plant = False
                    if can_plant:
                        self.plant_seed(x=tile['x'], y=tile['y'], seed_id=garden_upgrade_seed_id)

        def strategy_3(upgrade):
            self.harvest_keenmoss_field()
            if self.is_garden_empty():
                for tile in self.farm_size:
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=self.plants[upgrade["seed"]]["id"])
            else:
                # Harvest mature target plants
                try:
                    self.driver.execute_script(f"javascript:{self.farm_minigame}.harvestAll({self.farm_minigame}."
                                               f"plants['{upgrade['seed']}'], 1, 1);")
                except JavascriptException:
                    self.click_cookie()
                for tile in self.farm_size:
                    # Harvest mature target plants
                    # if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == self.plants[upgrade["seed"]]["id"]:
                    #     self.harvest_mature_plants(x=tile["x"], y=tile["y"])
                    if self.get_plant_id_of_tile(x=tile['x'], y=tile['y']) not in [self.plants["keenmoss"]["id"],
                                                                                   self.invalid_plant_id,
                                                                                   self.empty_tile_plant_id,
                                                                                   self.plants[upgrade["seed"]]["id"]]:
                        try:
                            self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile['x']},"
                                                       f"{tile['y']})")
                        except JavascriptException:
                            self.click_cookie()
                    # Replant Keenmoss if tile is now empty
                    if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == self.empty_tile_plant_id:
                        self.plant_seed(x=tile["x"], y=tile["y"], seed_id=self.plants["keenmoss"]["id"])

        def strategy_4(upgrade):
            garden_upgrade_seed_id = self.plants[upgrade["seed"]]["id"]
            self.harvest_keenmoss_field()
            keenmoss_tiles = self.get_keenmoss_tiles()
            empty_tiles = []
            keenmoss_ticks_to_mature = self.plants["keenmoss"]["mature"] / (self.plants["keenmoss"]["ageTick"] +
                                                                            self.plants["keenmoss"]["ageTickR"] * 0.5)
            sg_oldest_age_at_next_tick = 0

            if keenmoss_tiles and self.max_mature_keenmoss_reached(keenmoss_tiles):
                # Harvest mature target plants
                try:
                    self.driver.execute_script(f"javascript:{self.farm_minigame}.harvestAll({self.farm_minigame}."
                                               f"plants['{upgrade['seed']}'], 1, 1);")
                except JavascriptException:
                    self.click_cookie()
                for tile in self.farm_size:
                    plant_id = self.get_plant_id_of_tile(x=tile["x"], y=tile["y"])
                    if plant_id == garden_upgrade_seed_id:
                        # self.harvest_mature_plants(x=tile["x"], y =tile["y"])
                        sg_oldest_age_at_next_tick = max(sg_oldest_age_at_next_tick,
                                                         self.plant_age_at_next_tick(x=tile["x"], y=tile["y"]))
                    # Harvest plants from previous run
                    elif plant_id not in [self.plants["keenmoss"]["id"],
                                          self.invalid_plant_id,
                                          self.empty_tile_plant_id]:
                        try:
                            self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile['x']},"
                                                       f"{tile['y']})")
                        except JavascriptException:
                            self.click_cookie()

                    # Replant Keenmoss if tile is now empty
                    if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == self.empty_tile_plant_id:
                        empty_tiles.append(tile)

                if sg_oldest_age_at_next_tick > self.plants[upgrade["seed"]]["mature"]:
                    slower_plant_ticks_until_mature = 0
                else:
                    slower_plant_ticks_until_mature = (self.plants[upgrade["seed"]]["mature"] -
                                                       sg_oldest_age_at_next_tick) / (
                                                              self.plants[upgrade["seed"]]["ageTick"] +
                                                              self.plants[upgrade["seed"]]["ageTickR"] * 0.5)

                if slower_plant_ticks_until_mature <= keenmoss_ticks_to_mature:
                    for tile in empty_tiles:
                        self.plant_seed(x=tile["x"], y=tile["y"], seed_id=self.plants["keenmoss"]["id"])
            elif self.is_garden_empty():
                for tile in self.farm_size:
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=garden_upgrade_seed_id)
            else:
                if not keenmoss_tiles:
                    try:
                        self.driver.execute_script(f"javascript:{self.farm_minigame}.harvestAll({self.farm_minigame}."
                                                   f"plants['{upgrade['seed']}'], 1, 1);")
                    except JavascriptException:
                        self.click_cookie()
                for tile in self.farm_size:
                    plant_id = self.get_plant_id_of_tile(x=tile["x"], y=tile["y"])
                    if plant_id not in [self.empty_tile_plant_id, self.invalid_plant_id,
                                        garden_upgrade_seed_id, self.plants["keenmoss"]["id"]]:
                        try:
                            self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile['x']},"
                                                       f"{tile['y']})")
                        except JavascriptException:
                            self.click_cookie()
                    elif plant_id == garden_upgrade_seed_id:
                        # if not keenmoss_tiles:
                        #     self.harvest_mature_plants(x=tile["x"], y=tile["y"])
                        sg_oldest_age_at_next_tick = max(sg_oldest_age_at_next_tick,
                                                         self.plant_age_at_next_tick(x=tile["x"], y=tile["y"]))

                    if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == self.empty_tile_plant_id:
                        empty_tiles.append(tile)

                if sg_oldest_age_at_next_tick > self.plants[upgrade["seed"]]["mature"]:
                    slower_plant_ticks_until_mature = 0
                else:
                    slower_plant_ticks_until_mature = (self.plants[upgrade["seed"]]["mature"] -
                                                       sg_oldest_age_at_next_tick) / (
                                                              self.plants[upgrade["seed"]]["ageTick"] +
                                                              self.plants[upgrade["seed"]]["ageTickR"] * 0.5)

                if slower_plant_ticks_until_mature <= keenmoss_ticks_to_mature:
                    for tile in empty_tiles:
                        self.plant_seed(x=tile["x"], y=tile["y"], seed_id=self.plants["keenmoss"]["id"])

        def strategy_5():
            keenmoss_tiles = [
                {"x": 1, "y": 2},
                {"x": 1, "y": 3},
                {"x": 1, "y": 4},
                {"x": 2, "y": 4},
                {"x": 3, "y": 4},
                {"x": 4, "y": 2},
                {"x": 4, "y": 3},
                {"x": 4, "y": 4}
            ]
            ichorpuff_tiles = [
                {"x": 0, "y": 1},
                {"x": 0, "y": 2},
                {"x": 0, "y": 3},
                {"x": 0, "y": 4},
                {"x": 0, "y": 5},
                {"x": 1, "y": 5},
                {"x": 2, "y": 3},
                {"x": 2, "y": 5},
                {"x": 3, "y": 3},
                {"x": 3, "y": 5},
                {"x": 4, "y": 5},
                {"x": 5, "y": 1},
                {"x": 5, "y": 2},
                {"x": 5, "y": 3},
                {"x": 5, "y": 4},
                {"x": 5, "y": 5}
            ]
            if self.farm_level == 8:
                keenmoss_tiles.append({"x": 2, "y": 2})
                keenmoss_tiles.append({"x": 3, "y": 2})
                for x in range(1, 5):
                    ichorpuff_tiles.append({"x": x, "y": 1})
            else:
                for x in range(1, 5):
                    keenmoss_tiles.append({"x": x, "y": 1})
                for x in range(6):
                    ichorpuff_tiles.append({"x": x, "y": 0})
                ichorpuff_tiles.append({"x": 2, "y": 2})
                ichorpuff_tiles.append({"x": 3, "y": 2})

            for keenmoss_tile in keenmoss_tiles:
                # self.harvest_mature_plants(x=keenmoss_tile["x"], y=keenmoss_tile["y"])
                plant_id = self.get_plant_id_of_tile(x=keenmoss_tile["x"], y=keenmoss_tile["y"])
                if plant_id not in [self.empty_tile_plant_id,
                                    self.invalid_plant_id,
                                    self.plants["keenmoss"]["id"]] and self.plants_by_id[plant_id]['unlocked']:
                    try:
                        self.driver.execute_script(f"javascript:{self.farm_minigame}."
                                                   f"harvest({keenmoss_tile['x']}, {keenmoss_tile['y']})")
                    except JavascriptException:
                        self.click_cookie()
                plant_id = self.get_plant_id_of_tile(x=keenmoss_tile["x"], y=keenmoss_tile["y"])
                if plant_id == self.empty_tile_plant_id:
                    self.plant_seed(x=keenmoss_tile["x"], y=keenmoss_tile["y"], seed_id=self.plants["keenmoss"]["id"])

            for ichorpuff_tile in ichorpuff_tiles:
                self.harvest_mature_plants(x=ichorpuff_tile["x"], y=ichorpuff_tile["y"])
                plant_id = self.get_plant_id_of_tile(x=ichorpuff_tile["x"], y=ichorpuff_tile["y"])
                if plant_id not in [self.empty_tile_plant_id,
                                    self.invalid_plant_id,
                                    self.plants["ichorpuff"]["id"]] and self.plants_by_id[plant_id]['unlocked']:
                    try:
                        self.driver.execute_script(f"javascript:{self.farm_minigame}."
                                                   f"harvest({ichorpuff_tile['x']}, {ichorpuff_tile['y']})")
                    except JavascriptException:
                        self.click_cookie()

                plant_id = self.get_plant_id_of_tile(x=ichorpuff_tile["x"], y=ichorpuff_tile["y"])
                if plant_id == self.empty_tile_plant_id:
                    self.plant_seed(x=ichorpuff_tile["x"], y=ichorpuff_tile["y"],
                                    seed_id=self.plants["ichorpuff"]["id"])

        upgrade_unlocked = True
        next_drop = None
        if not self.all_garden_drops_unlocked:
            for drop in garden_upgrades:
                if not self.is_upgrade_unlocked(drop["upgrade"]) and self.plants[drop["seed"]]["unlocked"]:
                    upgrade_unlocked = False
                    next_drop = drop
                    break
            self.all_garden_drops_unlocked = upgrade_unlocked
            if self.all_garden_drops_unlocked:
                print(f"{timestamp()}: All garden upgrades unlocked. Saving game.")
                self.save_game(path=self.save_file)

        if next_drop:
            if next_drop["strategy"] == 1:
                strategy_1(next_drop)
            elif next_drop["strategy"] == 3:
                strategy_3(next_drop)
            elif next_drop["strategy"] == 4:
                strategy_4(next_drop)
            elif next_drop["strategy"] == 5:
                if self.farm_level >= 8:
                    strategy_5()

        self.get_dragon_auras()

        # wanted_aura = self.dragon_auras_lookup["No aura"]["id"]
        if not self.all_garden_drops_unlocked:
            # wanted_aura = 14  # Mind over Matter
            wanted_aura = self.dragon_auras_lookup["Mind Over Matter"]["id"]
        else:
            wanted_aura = self.final_wanted_aura
            # wanted_aura2 = 18  # reality bending

        if self.dragon_complete and self.dragon_auras[0] != wanted_aura:
            try:
                self.driver.execute_script(f"javascript:Game.SetDragonAura({wanted_aura},0);Game.ConfirmPrompt();")
            except JavascriptException:
                self.click_cookie()

    def get_farm_level(self):
        try:
            self.farm_level = self.driver.execute_script('javascript:return Game.Objects["Farm"].level;')
        except WebDriverException:
            self.reload_cookieclicker()

    def is_tile_unlocked(self, x, y):
        unlocked_js = f"javascript:return {self.farm_minigame}.isTileUnlocked({x},{y});"
        try:
            return self.driver.execute_script(unlocked_js)
        except JavascriptException:
            return False

    def get_plant_id_of_tile(self, x, y):
        try:
            plant_id = int(self.driver.execute_script(f"javascript:return {self.farm_minigame}."
                                                      f"getTile({x},{y})[0];")) - 1
        except JavascriptException:
            plant_id = self.invalid_plant_id
        return plant_id

    def get_plant_maturity_of_tile(self, x, y):
        maturity_js = f"javascript:return {self.farm_minigame}.getTile({x},{y})[1];"
        try:
            return int(self.driver.execute_script(maturity_js))
        except JavascriptException:
            return 0

    def switch_soil(self, soil):
        next_soil_time_js = f"javascript:return {self.farm_minigame}.nextSoil;"
        try:
            next_soil_time = self.driver.execute_script(next_soil_time_js) / 1000
        except JavascriptException:
            next_soil_time = time.time() + 1000
        current_time = time.time()
        if current_time >= next_soil_time:
            desired_soil_id_js = f"javascript:return {self.farm_minigame}.soils['{soil}'].id;"
            try:
                desired_soil_id = self.driver.execute_script(desired_soil_id_js)
                current_soil_id_js = f"javascript:return {self.farm_minigame}.soil;"
                current_soil_id = self.driver.execute_script(current_soil_id_js)
            except JavascriptException:
                self.click_cookie()
                return
            if current_soil_id != desired_soil_id:
                print(f"{timestamp()}: Switching soil to {soil}.")
                try:
                    self.driver.execute_script(f"javascript:FireEvent(l('gardenSoil-{desired_soil_id}'), 'click')")
                except JavascriptException:
                    print(f'{timestamp()}: Switching soils using JS failed. Attempting with mouse clicks.')
                    try:
                        self.driver.find_element(by=By.ID, value=f"gardenSoil-{desired_soil_id}").click()
                    except (NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException):
                        self.click_cookie()
                        return

    def cast_spell(self, spell_to_cast, exhaust_magic=False):
        game = "Game.Objects['Wizard tower'].minigame"
        spell = f'{game}.spells["{spell_to_cast}"]'
        fthof = f'{game}.spells["hand of fate"]'
        gfd = f'{game}.spellsById[6]'  # Gambler's Fever Dream
        gfd_green_fthof = ('<div width="100%"><b>Forecast:</b><br/><span class="green">'
                           '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Force the Hand of Fate')
        gfd_good_fthof_lucky = ('<div width="100%"><b>Forecast:</b><br/><span class="green">'
                                '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Force the Hand of Fate (Lucky)')
        gfd_good_fthof_blab = ('<div width="100%"><b>Forecast:</b><br/><span class="green">'
                               '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Force the Hand of Fate (Blab)')
        gfd_ef_fthof = ('<div width="100%"><b>Forecast:</b><br/><span class="red">'
                        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Force the Hand of Fate (Elder Frenzy)')
        gfd_red_fthof_lump = ('<div width="100%"><b>Forecast:</b><br/><span class="red">'
                              '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Free Sugar Lump')
        buffer = 21
        try:
            spell_cost = self.driver.execute_script(f"javascript:return {game}.getSpellCost({spell});")
            magic = self.driver.execute_script(f"javascript:return {game}.magic")
            magic_max = self.driver.execute_script(f"javascript:return {game}.magicM")
        except JavascriptException:
            self.click_cookie()
            return

        if spell_to_cast == "gambler's fever dream":
            try:
                fthof_half_cost = self.driver.execute_script(f"javascript:return {game}.getSpellCost({fthof})/ 2;")
            except JavascriptException:
                fthof_half_cost = magic

            if magic < (spell_cost + fthof_half_cost) * 2:
                self.click_golden_cookies = False
                print(f'{timestamp()}: Waiting for enough magic to get Four-leaf cookie')
                return
            else:
                for _ in range(2):
                    try:
                        self.driver.execute_script(f"javascript:{game}.castSpell({spell});")
                    except JavascriptException:
                        self.driver.quit()
                try:
                    self.driver.find_element(by=By.ID, value="grimoireLumpRefill").click()
                    self.driver.execute_script(f"javascript:{game}.castSpell(fthof);")
                    four_leaf_cookie_achievement = self.check_achievements('Four-leaf cookie')
                    while not four_leaf_cookie_achievement:
                        four_leaf_cookie_achievement = self.check_achievements('Four-leaf cookie')
                    self.click_golden_cookies = True
                except (JavascriptException, ElementClickInterceptedException, NoSuchElementException):
                    self.driver.quit()
        else:
            try:
                spells_cast = self.driver.execute_script(f'javascript:return {game}.spellsCastTotal')
            except JavascriptException:
                self.click_cookie()
                print(f'{timestamp()}: Error getting FTHOF cookie details.')
                return

            if spells_cast == self.spell_count_four_leaf_cookie:
                return

            try:
                f_active = self.driver.execute_script("javascript:return 'Frenzy' in Game.buffs")
                bs_active = self.driver.execute_script("javascript:return 'High-five' in Game.buffs ||"
                                                       "'Congregation' in Game.buffs ||"
                                                       "'Luxuriant harvest' in Game.buffs ||"
                                                       "'Ore vein' in Game.buffs ||"
                                                       "'Oiled-up' in Game.buffs ||"
                                                       "'Juicy profits' in Game.buffs ||"
                                                       "'Fervent adoration' in Game.buffs ||"
                                                       "'Manabloom' in Game.buffs ||"
                                                       "'Delicious lifeforms' in Game.buffs ||"
                                                       "'Breakthrough' in Game.buffs ||"
                                                       "'Righteous cataclysm' in Game.buffs ||"
                                                       "'Golden ages' in Game.buffs ||"
                                                       "'Extra cycles' in Game.buffs ||"
                                                       "'Solar flare' in Game.buffs ||"
                                                       "'Winning streak' in Game.buffs ||"
                                                       "'Macrocosm' in Game.buffs ||"
                                                       "'Refactoring' in Game.buffs ||"
                                                       "'Cosmic nursery' in Game.buffs ||"
                                                       "'Brainstorm' in Game.buffs ||"
                                                       "'Deduplication' in Game.buffs;")
                dh_active = self.driver.execute_script("javascript:return 'Dragon harvest' in Game.buffs")
                df_active = self.driver.execute_script("javascript:return 'Dragonflight' in Game.buffs")
                cf_active = self.driver.execute_script("javascript:return 'Click frenzy' in Game.buffs")
                ef_active = self.driver.execute_script("javascript:return 'Elder frenzy' in Game.buffs")
                fthof_half_cost = self.driver.execute_script(f"javascript:return {game}.getSpellCost({fthof})/ 2;")
                gfd_cost = self.driver.execute_script(f"javascript:return {game}.getSpellCost({gfd});")
                buff = f_active or bs_active or dh_active or cf_active or ef_active or df_active
            except JavascriptException:
                self.click_cookie()
                return

            if magic >= (gfd_cost + fthof_half_cost):
                try:
                    gfd_result = self.driver.execute_script(f"javascript:return FortuneCookie.spellForecast({gfd});")
                    gfd_is_good_fthof = (gfd_result.startswith(gfd_green_fthof) and
                                         not gfd_result.startswith(gfd_good_fthof_blab)
                                         ) or (gfd_result.startswith(gfd_ef_fthof) or
                                               gfd_result.startswith(gfd_red_fthof_lump))
                except JavascriptException:
                    print(f"{timestamp()}: Failed to save GFD result to variable.")
                    gfd_is_good_fthof = False
            else:
                gfd_is_good_fthof = False

            cast = (magic >= magic_max - 1) or (buff and magic >= spell_cost and
                                                spell_to_cast == "hand of fate") or gfd_is_good_fthof

            while cast:
                if spell_to_cast == "resurrect abomination":
                    self.pop_fattest_wrinkler()
                try:
                    if spell_to_cast == "hand of fate":
                        next_cookie_js = (f"FortuneCookie.FateChecker({spells_cast}, ((Game.season == 'valentines' || "
                                          f"Game.season == 'easter') ? 1 : 0), {game}.getFailChance({fthof}) + 0.15 * "
                                          f"FortuneCookie.getSimGCs(), false)")
                        next_cookie = self.driver.execute_script(f"javascript:return {next_cookie_js}")
                        clot_active = self.driver.execute_script("javascript:return 'Clot' in Game.buffs")
                        lucky = ">Lucky<" in next_cookie
                        frenzy = ">Frenzy<" in next_cookie
                        click_frenzy = ">Click Frenzy<" in next_cookie
                        cookie_storm = "Cookie Storm" in next_cookie
                        blab = ">Blab<" in next_cookie
                        building_special = ">Building Special<" in next_cookie
                        free_sugar_lump = ">Free Sugar Lump<" in next_cookie
                        clot = ">Clot<" in next_cookie
                        ruin = ">Ruin<" in next_cookie
                        cursed_finger = ">Cursed Finger<" in next_cookie
                        elder_frenzy = ">Elder Frenzy<" in next_cookie
                        fthof_best = (frenzy or click_frenzy or cookie_storm or building_special or free_sugar_lump or
                                      elder_frenzy or cursed_finger)

                        if blab or clot or ruin:
                            if magic >= (gfd_cost + (2 * fthof_half_cost)):
                                self.driver.execute_script(f'javascript:{game}.castSpell({gfd});')
                                self.save_game(path=self.save_file)
                                self.load_save()
                        elif (
                                buff and not clot_active and (lucky or frenzy or click_frenzy or cookie_storm or
                                                              building_special or elder_frenzy or cursed_finger)
                        ) or free_sugar_lump:
                            if gfd_is_good_fthof and (gfd_good_fthof_lucky and not fthof_best):
                                print(f"{timestamp()}: Casting Gambler's Fever Dream.")
                                self.driver.execute_script(f'javascript:{game}.castSpell({gfd});')
                            else:
                                print(f"{timestamp()}: Casting Force the Hand of Fate.")
                                self.driver.execute_script(f"javascript:{game}.castSpell({spell});")
                        cast = False
                    else:
                        self.driver.execute_script(f"javascript:{game}.castSpell({spell});")
                        if exhaust_magic:
                            spell_cost = self.driver.execute_script(f"javascript:return {game}.getSpellCost({spell});")
                            magic = self.driver.execute_script(f"javascript:return {game}.magic")
                            cast = magic >= spell_cost + buffer
                        else:
                            cast = False
                except JavascriptException:
                    self.click_cookie()
                    print(f"{timestamp()}: Failed to cast spell.")
                    return

            self.click_golden_cookies = True

    def try_for_shriekbulbs(self):
        duketater = self.plants["duketater"]
        duketater_tiles = []

        if self.farm_level == 1:
            duketater_tiles.append({"x": 2, "y": 2})
            duketater_tiles.append({"x": 3, "y": 2})
            duketater_tiles.append({"x": 2, "y": 3})
        elif self.farm_level == 2:
            for x in range(2, 5):
                duketater_tiles.append({"x": x, "y": 2})

            duketater_tiles.append({"x": 3, "y": 3})
        elif self.farm_level == 3:
            for x in [2, 4]:
                for y in [2, 4]:
                    duketater_tiles.append({"x": x, "y": y})

            duketater_tiles.append({"x": 3, "y": 3})
        elif self.farm_level == 4:
            for x in [1, 4]:
                for y in [2, 4]:
                    duketater_tiles.append({"x": x, "y": y})

            duketater_tiles.append({"x": 2, "y": 3})
            duketater_tiles.append({"x": 2, "y": 4})
        elif self.farm_level == 5:
            for x in [1, 4]:
                for y in [1, 4]:
                    duketater_tiles.append({"x": x, "y": y})

            for x in [2, 3]:
                for y in [2, 3]:
                    duketater_tiles.append({"x": x, "y": y})
        elif self.farm_level == 6:
            duketater_tiles.append({"x": 2, "y": 1})
            duketater_tiles.append({"x": 4, "y": 1})
            duketater_tiles.append({"x": 4, "y": 2})
            duketater_tiles.append({"x": 5, "y": 2})
            duketater_tiles.append({"x": 1, "y": 3})
            duketater_tiles.append({"x": 2, "y": 3})
            duketater_tiles.append({"x": 2, "y": 4})
            duketater_tiles.append({"x": 4, "y": 4})
        elif self.farm_level == 7:
            duketater_tiles.append({"x": 3, "y": 1})

            for x in [1, 3, 5]:
                duketater_tiles.append({"x": x, "y": 2})
            for x in [1, 2, 4, 5]:
                duketater_tiles.append({"x": x, "y": 4})

            duketater_tiles.append({"x": 2, "y": 5})
            duketater_tiles.append({"x": 4, "y": 5})
        elif self.farm_level == 8:
            for y in range(1, 6):
                for x in [1, 4]:
                    if x == 4 or y in range(2, 5):
                        duketater_tiles.append({"x": x, "y": y})

            for x in [0, 2]:
                for y in [1, 5]:
                    duketater_tiles.append({"x": x, "y": y})
        elif self.farm_level >= 9:
            for y in range(6):
                for x in [1, 4]:
                    if x == 4 or y in range(1, 5):
                        duketater_tiles.append({"x": x, "y": y})

            for x in [0, 2]:
                for y in [0, 5]:
                    duketater_tiles.append({"x": x, "y": y})

        oldest_seed = 0
        duketater_id = duketater["id"]
        parent_seed_maturity = duketater["mature"]
        for tile in duketater_tiles:
            self.click_cookie()
            self.plant_seed(x=tile["x"], y=tile["y"], seed_id=duketater_id)
            if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == duketater_id:
                oldest_seed = max(oldest_seed, self.get_plant_maturity_of_tile(x=tile["x"], y=tile["y"]))
        clean_tiles = [tile for tile in self.farm_size if tile not in duketater_tiles]
        self.clean_garden(tiles=clean_tiles)
        if oldest_seed >= parent_seed_maturity:
            self.switch_soil("woodchips")
        else:
            self.switch_soil("fertilizer")

    def try_for_everdaisy(self):
        self.get_plant_details()
        tidygrass = self.plants["tidygrass"]
        elderwort = self.plants["elderwort"]
        tidygrass_id = tidygrass["id"]
        elderwort_id = elderwort["id"]

        elderwort_tiles = []
        tidygrass_tiles = []

        if self.plants["queenbeetLump"]["growing"]:
            jqb_tile = {"x": None, "y": None}
            for jqb_x in [1, 4]:
                for jqb_y in [1, 4]:
                    if self.get_plant_id_of_tile(jqb_x, jqb_y) == self.plants["queenbeetLump"]["id"]:
                        jqb_tile = {"x": jqb_x, "y": jqb_y}
            x_offset = 0
            y_offset = 0
            if jqb_tile["x"] == 4:
                x_offset = 5
            if jqb_tile["y"] == 1:
                y_offset = 5

            elderwort_tiles.append({"x": abs(1 - x_offset), "y": abs(0 - y_offset)})
            elderwort_tiles.append({"x": abs(2 - x_offset), "y": abs(0 - y_offset)})
            elderwort_tiles.append({"x": abs(3 - x_offset), "y": abs(0 - y_offset)})
            elderwort_tiles.append({"x": abs(4 - x_offset), "y": abs(0 - y_offset)})
            elderwort_tiles.append({"x": abs(5 - x_offset), "y": abs(2 - y_offset)})
            elderwort_tiles.append({"x": abs(0 - x_offset), "y": abs(3 - y_offset)})
            elderwort_tiles.append({"x": abs(1 - x_offset), "y": abs(3 - y_offset)})
            elderwort_tiles.append({"x": abs(2 - x_offset), "y": abs(3 - y_offset)})
            elderwort_tiles.append({"x": abs(5 - x_offset), "y": abs(3 - y_offset)})
            elderwort_tiles.append({"x": abs(0 - x_offset), "y": abs(4 - y_offset)})
            elderwort_tiles.append({"x": abs(2 - x_offset), "y": abs(4 - y_offset)})
            elderwort_tiles.append({"x": abs(5 - x_offset), "y": abs(4 - y_offset)})
            elderwort_tiles.append({"x": abs(0 - x_offset), "y": abs(5 - y_offset)})
            elderwort_tiles.append({"x": abs(1 - x_offset), "y": abs(5 - y_offset)})
            elderwort_tiles.append({"x": abs(2 - x_offset), "y": abs(5 - y_offset)})
            elderwort_tiles.append({"x": abs(5 - x_offset), "y": abs(5 - y_offset)})
            tidygrass_tiles.append({"x": abs(5 - x_offset), "y": abs(0 - y_offset)})
            tidygrass_tiles.append({"x": abs(0 - x_offset), "y": abs(1 - y_offset)})
            tidygrass_tiles.append({"x": abs(1 - x_offset), "y": abs(1 - y_offset)})
            tidygrass_tiles.append({"x": abs(5 - x_offset), "y": abs(1 - y_offset)})
            tidygrass_tiles.append({"x": abs(0 - x_offset), "y": abs(2 - y_offset)})
            tidygrass_tiles.append({"x": abs(2 - x_offset), "y": abs(2 - y_offset)})
            tidygrass_tiles.append({"x": abs(3 - x_offset), "y": abs(2 - y_offset)})
            tidygrass_tiles.append({"x": abs(4 - x_offset), "y": abs(2 - y_offset)})
            tidygrass_tiles.append({"x": abs(3 - x_offset), "y": abs(3 - y_offset)})
            tidygrass_tiles.append({"x": abs(3 - x_offset), "y": abs(5 - y_offset)})
            tidygrass_tiles.append({"x": abs(4 - x_offset), "y": abs(5 - y_offset)})
        else:
            for e_x in range(6):
                for e_y in [0, 3]:
                    elderwort_tiles.append({"x": e_x, "y": e_y})

            for t_x in [0, 2, 3, 5]:
                for t_y in [1, 2, 4]:
                    if t_y == 1 or (t_y == 2 and t_x != 3) or (t_y == 4 and t_x not in [3, 4]):
                        tidygrass_tiles.append({"x": t_x, "y": t_y})

            for t_x in range(6):
                tidygrass_tiles.append({"x": t_x, "y": 5})

        elderwort_maturity = elderwort["mature"]
        elderwort_age_per_tick = elderwort["ageTick"] + elderwort["ageTickR"] * 0.5
        elderwort_ticks_until_mature = elderwort_maturity / elderwort_age_per_tick
        tidygrass_maturity = tidygrass["mature"]
        tidygrass_age_per_tick = tidygrass["ageTick"] + tidygrass["ageTickR"] * 0.5
        tidygrass_ticks_until_mature = tidygrass_maturity / tidygrass_age_per_tick
        maturity_difference = elderwort_ticks_until_mature - tidygrass_ticks_until_mature
        clean_tiles = [tile for tile in self.farm_size if tile not in elderwort_tiles and tile not in tidygrass_tiles]
        self.clean_garden(clean_tiles)
        if maturity_difference < 0:
            self.stagger_planting(faster_group=elderwort_tiles, faster_plant_id=elderwort_id,
                                  slower_group=tidygrass_tiles, slower_plant_id=tidygrass_id,
                                  faster_plant_ticks_to_mature=elderwort_ticks_until_mature)
        else:
            self.stagger_planting(faster_group=tidygrass_tiles, faster_plant_id=tidygrass_id,
                                  slower_group=elderwort_tiles, slower_plant_id=elderwort_id,
                                  faster_plant_ticks_to_mature=tidygrass_ticks_until_mature)

    def try_for_juicy_queenbeet(self):
        self.get_plant_details()
        self.set_cps_multiplier()
        queenbeet_id = self.plants["queenbeet"]["id"]

        # This is written for a level nine and above farm only
        quadrant_1 = []
        for x in range(3, 6):
            for y in range(0, 3):
                quadrant_1.append({"x": x, "y": y})

        quadrant_2 = []
        for x in range(0, 3):
            for y in range(0, 3):
                quadrant_2.append({"x": x, "y": y})

        quadrant_3 = []
        for x in range(0, 3):
            for y in range(3, 6):
                quadrant_3.append({"x": x, "y": y})

        quadrant_4 = []
        for x in range(3, 6):
            for y in range(3, 6):
                quadrant_4.append({"x": x, "y": y})

        def check_quadrant(quadrant):
            grow_coords = [
                (1, 1), (1, 4),
                (4, 1), (4, 4)
            ]
            clean_quadrant = False
            quadrant_max_maturity = 0
            qb_age_tick = self.plants["queenbeet"]["ageTick"]
            qb_age_tick_r = self.plants["queenbeet"]["ageTickR"]
            qb_age_per_tick = qb_age_tick + qb_age_tick_r * 0.5
            qb_plant_mature_age = self.plants["queenbeet"]['mature']
            queenbeet_ticks_until_mature = qb_plant_mature_age / qb_age_per_tick
            duketater_ticks_until_mature = 0
            duketater_tile = None

            for tile in quadrant:
                self.click_cookie()
                p_id = self.get_plant_id_of_tile(x=tile['x'], y=tile['y'])
                if (tile['x'], tile['y']) in grow_coords:
                    if p_id != self.plants["queenbeetLump"]["id"]:
                        remove_undesirable_plants(x=tile['x'], y=tile['y'])

                    if self.get_plant_id_of_tile(x=tile['x'], y=tile['y']) == self.plants["duketater"]["id"] and \
                            self.plants["duketater"]["growing"] and not self.plants["duketater"]["unlocked"]:
                        print(f"{timestamp()}: Found a {self.plants_by_id[p_id]['name']} at ({tile}).")
                        age_tick = self.plants["duketater"]["ageTick"]
                        age_tick_r = self.plants["duketater"]["ageTickR"]
                        age_per_tick = age_tick + age_tick_r * 0.5
                        plant_mature_age = self.plants["duketater"]['mature']
                        tile_maturity = self.get_plant_maturity_of_tile(x=tile['x'], y=tile['y'])
                        duketater_ticks_until_mature = (plant_mature_age - tile_maturity) / age_per_tick
                        duketater_tile = tile
                        print(f"{timestamp()}: Duketater ({tile}) matures in {duketater_ticks_until_mature} ticks.")
                        print(f"{timestamp()}: AgeTick {age_tick}; AgeTickR {age_tick_r}; "
                              f"Mature {plant_mature_age}; Maturity {tile_maturity}")
                else:
                    if p_id == self.empty_tile_plant_id:
                        clean_quadrant = True
                        break
                    age_at_next_tick = self.plant_age_at_next_tick(x=tile['x'], y=tile['y'])
                    if age_at_next_tick >= 100:
                        clean_quadrant = True
                    else:
                        quadrant_max_maturity = max(quadrant_max_maturity,
                                                    self.get_plant_maturity_of_tile(x=tile['x'], y=tile['y']))

            if self.cpsMult == 1 and self.next_garden_tick - time.time() > SECONDS_UNTIL_NEXT_TICK:
                return quadrant_max_maturity

            if clean_quadrant:
                quadrant_max_maturity = 0
                cost_js = f'javascript:return {self.farm_minigame}.plants["queenbeet"].cost'
                try:
                    cps = self.driver.execute_script("javascript:return Game.cookiesPs;")
                    cookies = self.driver.execute_script("javascript:return Game.cookies;")
                    cost = self.driver.execute_script(cost_js)
                except JavascriptException:
                    self.click_cookie()
                    return quadrant_max_maturity
                total_cost = cps * 60 * 8 * cost

                # if duketater_ticks_until_mature - queenbeet_ticks_until_mature <= 0:
                #     print(f"{timestamp()}: Duketater ({duketater_tile}) matures in {duketater_ticks_until_mature} "
                #           f"ticks. Queenbeet takes {queenbeet_ticks_until_mature} ticks to mature")

                if cookies >= total_cost and (duketater_ticks_until_mature - queenbeet_ticks_until_mature <= 0) and (
                        self.cpsMult <= 1 or self.next_garden_tick - time.time() <= SECONDS_UNTIL_NEXT_TICK):
                    if duketater_tile and duketater_ticks_until_mature - queenbeet_ticks_until_mature <= 0:
                        print(f"{timestamp()}: Duketater ({duketater_tile}) matures in {duketater_ticks_until_mature} "
                              f"ticks. Queenbeet takes {queenbeet_ticks_until_mature} ticks to mature")
                    replant = True
                else:
                    replant = False

                for tile in quadrant:
                    self.click_cookie()
                    if (tile['x'], tile['y']) not in grow_coords:
                        p_id = self.get_plant_id_of_tile(x=tile['x'], y=tile['y'])
                        if p_id not in {self.invalid_plant_id, self.empty_tile_plant_id
                                        } and (self.plants_by_id[p_id]["unlocked"] or
                                               self.get_plant_maturity_of_tile(x=tile['x'], y=tile['y']) >=
                                               self.plants_by_id[p_id]["mature"]) \
                                and (self.cpsMult >= 1 or
                                     self.next_garden_tick - time.time() <= SECONDS_UNTIL_NEXT_TICK):
                            try:
                                self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile['x']},"
                                                           f"{tile['y']})")
                            except JavascriptException:
                                self.click_cookie()

                        if replant and self.get_plant_id_of_tile(x=tile['x'], y=tile['y']) == self.empty_tile_plant_id:
                            self.plant_seed(x=tile['x'], y=tile['y'], seed_id=queenbeet_id)

            return quadrant_max_maturity

        def remove_undesirable_plants(x, y):
            p_id = self.get_plant_id_of_tile(x, y)
            self.last_garden_clean = time.time()
            if p_id not in {self.empty_tile_plant_id, self.plants["queenbeetLump"]["id"], self.invalid_plant_id
                            } and not self.plants["queenbeetLump"]["growing"] and (
                    self.plants_by_id[p_id]["unlocked"] or
                    self.get_plant_maturity_of_tile(x=x, y=y) >= self.plants_by_id[p_id]["mature"]):
                try:
                    print(f"{timestamp()}: {self.plants_by_id[p_id]['name']} at {x, y}. "
                          "Continuing will remove the plant.")
                    self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({x},{y})")
                except JavascriptException:
                    self.click_cookie()
            elif p_id == self.plants["queenbeetLump"]["id"]:
                self.save_game(path=self.save_file)
                self.get_plant_details()
                if self.num_plants_unlocked + 1 == self.max_plants:
                    surround_with_elderwort(x, y)

        def surround_with_elderwort(jqb_x, jqb_y):
            elderwort_id = self.plants["elderwort"]["id"]
            tiles = [
                (jqb_x - 1, jqb_y + 1), (jqb_x - 1, jqb_y), (jqb_x - 1, jqb_y - 1),
                (jqb_x, jqb_y + 1), (jqb_x, jqb_y - 1),
                (jqb_x + 1, jqb_y + 1), (jqb_x + 1, jqb_y), (jqb_x + 1, jqb_y - 1)
            ]

            for tile in tiles:
                self.click_cookie()
                p_id = self.get_plant_id_of_tile(x=tile[0], y=tile[1])
                if p_id not in {self.empty_tile_plant_id, elderwort_id} and self.plants_by_id[p_id]["unlocked"]:
                    print(f"{timestamp()}: Harvesting elderwort tiles if they don't contain elderwort.")
                    try:
                        self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile[0]},{tile[1]})")
                    except JavascriptException:
                        self.click_cookie()
                self.plant_seed(x=tile[0], y=tile[1], seed_id=elderwort_id)

        self.get_farm_level()

        if not (self.plants["queenbeetLump"]["unlocked"] or self.plants["queenbeetLump"]["growing"]):
            if self.farm_level >= 7:
                # wanted_aura = self.dragon_auras_lookup["Supreme Intellect"]["id"]
                wanted_aura = self.final_wanted_aura

                max_maturity = 0
                max_maturity = max(max_maturity, check_quadrant(quadrant_1))
                max_maturity = max(max_maturity, check_quadrant(quadrant_2))
                max_maturity = max(max_maturity, check_quadrant(quadrant_3))
                max_maturity = max(max_maturity, check_quadrant(quadrant_4))
                if max_maturity >= self.plants["queenbeet"]["mature"] and not self.plants["queenbeetLump"]["unlocked"]:
                    self.switch_soil("woodchips")
                else:
                    self.switch_soil("fertilizer")
            else:
                wanted_aura = self.final_wanted_aura
        else:
            wanted_aura = self.final_wanted_aura

        self.get_dragon_auras()

        if self.dragon_complete and self.dragon_auras[0] != wanted_aura:
            try:
                self.driver.execute_script(f"javascript:Game.SetDragonAura({wanted_aura},0);Game.ConfirmPrompt();")
            except JavascriptException:
                self.click_cookie()

    def check_veil(self):
        try:
            # self.driver.execute_script('javascript:return Game.Upgrades["Shimmering veil [on]"].canBuy();')
            self.driver.find_element(by=By.XPATH, value='//div[@id="toggleUpgrades"]/div[@data-id="564"]')
            self.is_veil_active = True
        except NoSuchElementException:
            self.is_veil_active = False

    def four_leaf_cookie(self):
        grimoire = 'Game.Objects["Wizard tower"].minigame'
        try:
            spells_cast = self.driver.execute_script(f'javascript:return {grimoire}.spellsCastTotal')
            if spells_cast == self.spell_count_four_leaf_cookie:
                print(f'{timestamp()}: Prepare for Four-leaf cookie')
                shimmers = self.driver.execute_script('javascript:return Game.shimmers')
                for s in shimmers:
                    if s["type"] != "golden":
                        print(f'{timestamp()}: Waiting for golden cookie')
                        return

                self.cast_spell(spell_to_cast="gambler's fever dream", exhaust_magic=False)
        except JavascriptException:
            return

    def is_prestige_doubled(self):
        try:
            doubled = self.driver.execute_script("javascript:return Game.prestige * 2 < Game.HowMuchPrestige("
                                                 "CookieMonsterData.Cache.RealCookiesEarned + "
                                                 "Game.cookiesReset + "
                                                 "CookieMonsterData.Cache.WrinklersTotal + "
                                                 "(Game.HasUnlocked('Chocolate egg') && !Game.Has('Chocolate egg') ? "
                                                 "CookieMonsterData.Cache.LastChoEgg : 0),)")
        except JavascriptException:
            doubled = False
            self.click_cookie()

        if doubled:
            print(f'{timestamp()}: TIME TO ASCEND - Move Skruuia to Diamond, pop all wrinklers, change Dragon '
                  f'curve to Earth Shatterer, sell all buildings, buy chocolate egg.')

    def ascend(self):
        try:
            prestige_levels = int(self.driver.execute_script("javascript:return Game.ascendMeterLevel;"))

            if prestige_levels > 0:
                self.driver.execute_script("javascript:Game.Ascend(true);")
                if self.attempt_endless_cycle:
                    time.sleep(10)
                    self.driver.execute_script("javascript:Game.Reincarnate(true);")
                    self.ascensions += 1
                    print(f'{timestamp()}: Ascended {self.ascensions} times.')
                    time.sleep(5)
                    self.save_game(path=self.save_file)
                    self.dragon_level = 0
                    self.dragon_upgrades_complete = False
            elif self.attempt_1T_achievement:
                self.driver.execute_script("javascript:Game.Ascend(true);")
                input("Waiting on user for 'When the cookies ascend just right' achievement.")
        except JavascriptException:
            return

    def trillion_cookie_ascension(self):
        if self.check_achievements("When the cookies ascend just right"):
            self.attempt_1T_achievement = False
            return
        try:
            cookie_count = self.driver.execute_script("javascript:return Math.round(Game.cookiesd);")
        except JavascriptException:
            cookie_count = 0
        if cookie_count == 1000000000000:
            self.ascend()

    def get_ascension_mode(self):
        try:
            return self.driver.execute_script("javascript:return Game.ascensionMode;")
        except (JavascriptException, WebDriverException):
            return 0

    def click_cookie(self):
        def click_golden_cookie():
            js_code = "for (var sx in Game.shimmers) {" \
                      "var s = Game.shimmers[sx];" \
                      "if (s.force == 'cookie storm drop') {s.pop};" \
                      "if (s.type != 'golden' || s.life < Game.fps || !Game.Achievements['Early bird'].won) " \
                      "{s.pop(); return;}" \
                      "if ((s.life/Game.fps)<(s.dur-2) && (Game.Achievements['Fading luck'].won)) {s.pop(); return;}}"

            try:
                self.driver.execute_script(f"javascript:{js_code}")
            except JavascriptException:
                print(f"{timestamp()}: Failed to click golden cookie.")

        shimmers = None
        cookies = 0

        try:
            if (not self.is_veil_active or self.check_season()) and (self.get_ascension_mode() != 1 or
                                                                     self.check_achievements('True Neverclick')):
                click = True
                while click:
                    self.driver.execute_script("javascript:Game.ClickCookie();")
                    if self.attempt_1T_achievement:
                        self.trillion_cookie_ascension()
                    try:
                        shimmers = self.driver.execute_script("javascript:return Game.shimmers")
                        cookies = self.driver.execute_script("javascript:return Game.cookies;")
                    except JavascriptException:
                        print(f"{timestamp()}: Error checking shimmers")

                    if shimmers and (
                            not self.attempt_1T_achievement or cookies <= 900000000000) and self.click_golden_cookies:
                        click_golden_cookie()

                    click = self.driver.execute_script("javascript:return 'Click frenzy' in Game.buffs || "
                                                       "'Dragonflight' in Game.buffs || 'Cursed finger' in Game.buffs")
                    if click:
                        self.cast_spell(spell_to_cast="hand of fate", exhaust_magic=False)
        except (JavascriptException, WebDriverException):
            print(f"{timestamp()}: Error clicking cookie.")

    def save_game(self, path):
        try:
            self.driver.execute_script("javascript:Game.ExportSave();")
            save_code = self.driver.find_element(by=By.ID, value="textareaPrompt").text
            if save_code == "":
                input("Save code corrupted. Copy save file before continuing.")
            with open(file=path, mode="w") as progress:
                progress.write(save_code)

            self.time_next_save = time.time() + 60

            self.driver.execute_script("javascript:Game.ClosePrompt();")
        except JavascriptException:
            input("Save game failed. Waiting on user.")

    def load_save(self):
        if exists(self.save_file):
            try:
                self.driver.execute_script("javascript:Game.ImportSave();")
                with open(file=self.save_file, mode="r") as progress:
                    load_save = progress.read()
                    self.driver.find_element(by=By.ID, value="textareaPrompt").send_keys(load_save)

                self.driver.find_element(by=By.ID, value="promptOption0").click()
                try:
                    upload_error_element = self.driver.find_element(by=By.ID, value="importError")
                    upload_error = False if upload_error_element.text == "" else True
                except NoSuchElementException:
                    upload_error = False

                if upload_error:
                    input("Try uploading manually. Press Return when done.")
                else:
                    pass

            except NoSuchElementException:
                self.driver.execute_script("javascript:Game.ClosePrompt();")

    def buy_products(self):
        self.check_for_upgrades()
        try:
            cookies = self.driver.execute_script("javascript:return Game.cookies;")
            cps = self.driver.execute_script("javascript:return Game.cookiesPs")
        except JavascriptException:
            self.click_cookie()
            return
        if not self.upgrades_to_buy and (not self.attempt_1T_achievement or
                                         (cookies < 900000000000 and cps < 500000000)):
            # product_to_purchase_xpath = '//div[@class="product unlocked enabled"]/div/span[starts-with(' \
            #                             '@id,"productPrice") and @style="color: rgb(0, 255, 0);"]'
            exit_time = time.time() + 3
            try:
                min_price = self.driver.execute_script(f"javascript:return Game.cookies") * 10
            except JavascriptException:
                self.click_cookie()
                return

            while not self.upgrades_to_buy and time.time() <= exit_time:
                try:
                    buildings = self.driver.execute_script("javascript:return Game.ObjectsById.map(({id, name, amount, "
                                                           "price}) => ({id, name, amount, price}))")
                except JavascriptException:
                    buildings = []
                    print(f"{timestamp()}: Unable to retrieve building list")
                    self.click_cookie()
                if self.attempt_endless_cycle:
                    try:
                        self.driver.execute_script(f"javascript:Game.storeBulkButton(4);")
                        products_available = self.driver.find_elements(by=By.XPATH,
                                                                       value='//div[@class="product unlocked enabled"]')
                    except (JavascriptException, NoSuchElementException):
                        self.click_cookie()
                        return
                    for product in products_available:
                        product_id = int(product.get_attribute("id").strip("product"))
                        try:
                            amount = int(
                                self.driver.execute_script(f"javascript:return Game.ObjectsById[{product_id}].amount;"))
                            if self.dragon_level == self.max_dragon_level - 3:
                                self.driver.execute_script(f"javascript:Game.storeBulkButton(4);"
                                                           f"Game.ObjectsById[{self.dragon_level - 5}].buy(100);")
                            elif amount < 200 and self.dragon_level < self.max_dragon_level:
                                self.driver.execute_script(f"javascript:Game.storeBulkButton(4);"
                                                           f"Game.ObjectsById[{product_id}].buy(100);")
                            else:
                                self.driver.execute_script(f"javascript:Game.storeBulkButton(3);"
                                                           f"Game.ObjectsById[{product_id}].buy(10);")
                        except JavascriptException:
                            self.click_cookie()
                            return
                else:
                    # self.get_bulk_number()
                    try:
                        self.driver.execute_script('javascript:check_obj = CookieMonsterData.Objects100;'
                                                   'for (var b in check_obj){'
                                                   'if (check_obj[b].pp < 1) {'
                                                   'Game.Objects[b].buy(100)}};')
                        self.driver.execute_script('javascript:check_obj = CookieMonsterData.Objects10;'
                                                   'for (var b in check_obj){'
                                                   'if (check_obj[b].pp < 1) {'
                                                   'Game.Objects[b].buy(10)}};')
                        self.driver.execute_script('javascript:check_obj = CookieMonsterData.Objects1;'
                                                   'for (var b in check_obj){'
                                                   'if (check_obj[b].pp < 1) {'
                                                   'Game.Objects[b].buy(1)}};')
                    except JavascriptException:
                        print(f"{timestamp()}: Failed to buy based on pp.")
                    for building in buildings:
                        self.click_cookie()
                        try:
                            cookies = self.driver.execute_script(f"javascript:return Game.cookies")
                        except JavascriptException:
                            cookies = 0
                        if building["price"] > cookies:
                            self.click_cookie()
                            continue
                        try:
                            buy1 = self.driver.execute_script('javascript:return '
                                                              f'CookieMonsterData.Objects1["{building["name"]}"]')
                            buy10 = self.driver.execute_script(f'javascript:return '
                                                               f'CookieMonsterData.Objects10["{building["name"]}"]')
                            buy100 = self.driver.execute_script(f'javascript:return '
                                                                f'CookieMonsterData.Objects100["{building["name"]}"]')
                        except JavascriptException:
                            self.click_cookie()
                            return
                        try:
                            if buy1["colour"] == "Green":
                                min_price = min(min_price, buy1["price"])
                                if buy1["price"] <= cookies:
                                    print(f"{timestamp()}: Buying one {building['name']}")
                                    self.driver.execute_script(f"javascript:Game.ObjectsById[{building['id']}]."
                                                               f"buy(1);")
                            elif buy10["colour"] == "Green":
                                min_price = min(min_price, buy10["price"])
                                if buy10["price"] <= cookies:
                                    print(f"{timestamp()}: Buying ten {building['name']}")
                                    self.driver.execute_script(f"javascript:Game.ObjectsById[{building['id']}]."
                                                               f"buy(10);")
                            elif buy100["colour"] == "Green":
                                min_price = min(min_price, buy100["price"])
                                if buy100["price"] <= cookies:
                                    print(f"{timestamp()}: Buying one hundred {building['name']}")
                                    self.driver.execute_script(f"javascript:Game.ObjectsById[{building['id']}]."
                                                               f"buy(100);")
                        except JavascriptException:
                            self.click_cookie()
                            return

                        # amount_to_buy = 400 - building["amount"]
                        # if amount_to_buy >= 100:
                        #     rough_price = buy100["price"]
                        # elif amount_to_buy >= 10:
                        #     rough_price = buy10["price"]
                        # else:
                        #     rough_price = buy1["price"]
                        #
                        # if amount_to_buy > 0 and rough_price <= cookies:
                        #     try:
                        #         self.driver.execute_script(f"Game.ObjectsById[{building['id']}].buy(400 - "
                        #                                    f"{building['amount']});")
                        #     except JavascriptException:
                        #         self.click_cookie()

                if min_price > cookies:
                    exit_time = time.time()
                self.check_for_upgrades()

    def buy_upgrades(self):
        try:
            cookies = self.driver.execute_script("javascript:return Math.round(Game.cookiesd);")
        except JavascriptException:
            cookies = float('inf')
        if not self.attempt_1T_achievement or cookies < 900000000000:
            if self.upgrades_to_buy:
                for upgrade in self.upgrades_to_buy:
                    self.click_cookie()
                    try:
                        if self.driver.execute_script(f'javascript:return Game.UpgradesById["{upgrade["id"]}"].'
                                                      f'canBuy()'):
                            self.driver.execute_script(f"javascript:Game.UpgradesById[{upgrade['id']}].buy(true);")
                    except JavascriptException:
                        self.click_cookie()

    def best_buy_overrides(self):
        avg_clicks_overrides_0_01 = [
            'Plastic mouse',
            'Iron mouse',
            'Titanium mouse',
            'Adamantium mouse',
            'Unobtainium mouse',
            'Eludium mouse',
            'Wishalloy mouse',
            'Fantasteel mouse',
            'Nevercrack mouse',
            'Armythril mouse',
            'Technobsidian mouse',
            'Plasmarble mouse'
        ]

        avg_clicks_overrides_0_1 = [
            "Santa's helpers",
            'Cookie egg'
        ]

        try:
            avg_clicks = self.driver.execute_script("javascript:return CookieMonsterData.Cache.AverageClicks")
        except JavascriptException:
            avg_clicks = 1
        avg_clicks = 1 if avg_clicks == 0 else avg_clicks

        for override in avg_clicks_overrides_0_01:
            self.overrides[override] = avg_clicks * 0.01
            # print(f"{override} click override: {self.overrides[override]}")

        for override in avg_clicks_overrides_0_1:
            self.overrides[override] = avg_clicks * 0.1
            # print(f"{override} click override: {self.overrides[override]}")

    def avoid_buy(self, upgrade_id):
        if upgrade_id in {71, 73}:
            return (self.check_achievements("Elder nap") and self.check_achievements("Grandmapocalypse") and
                    self.check_achievements("Elder slumber") and self.check_achievements("Elder calm"))
        elif upgrade_id == 74:
            return (self.check_achievements("Elder nap") and self.check_achievements("Elder slumber") and
                    self.is_upgrade_unlocked("Elder Covenant"))
        elif upgrade_id == 84:
            try:
                elder_pledge = self.driver.execute_script("javascript:return Game.Upgrades['Elder Pledge'].bought")
            except JavascriptException:
                elder_pledge = False
            avoid = (elder_pledge or self.check_achievements("Elder calm"))
            return avoid
        elif upgrade_id == 227:
            return True
        elif upgrade_id == 563:
            return self.check_achievements("Thick-skinned")
        elif upgrade_id == 331:
            return True
        else:
            return False

    def check_for_upgrades(self):
        # self.check_elder_pledge()
        try:
            upgrades_in_store = self.driver.execute_script("javascript:return Game.UpgradesInStore.map(({id, name, "
                                                           "bought}) => ({id, name, bought}))")
        except JavascriptException:
            upgrades_in_store = []
        self.upgrades_to_buy = []

        try:
            upgrades_owned = self.driver.execute_script("javascript:return Game.UpgradesOwned")
        except JavascriptException:
            upgrades_owned = 0
        if upgrades_owned != 0 or self.check_achievements('Hardcore') or self.get_ascension_mode() != 1:
            try:
                cps = self.driver.execute_script("javascript:return Game.cookiesPs")
            except JavascriptException:
                cps = 1
            for upgrade in upgrades_in_store:
                self.click_cookie()
                if '"' in upgrade['name']:
                    js = f"javascript:return CookieMonsterData.Upgrades['{upgrade['name']}']"
                else:
                    js = f'javascript:return CookieMonsterData.Upgrades["{upgrade["name"]}"]'
                # print(js)
                try:
                    cookie_monster_data = self.driver.execute_script(js)
                except JavascriptException:
                    self.click_cookie()
                    return
                # print(f"{upgrade['name']}: {CookieMonsterData}")
                price = float('inf')
                if upgrade['name'] in self.overrides:
                    self.best_buy_overrides()
                    try:
                        price = self.driver.execute_script("javascript:return "
                                                           f"Game.UpgradesById[{upgrade['id']}].getPrice()")
                        cookies = self.driver.execute_script("javascript:return Game.cookies")
                        wrinklers_total = self.driver.execute_script("javascript:return "
                                                                     "CookieMonsterData.Cache.WrinklersTotal")
                    except JavascriptException:
                        self.click_cookie()
                        return
                    cookie_monster_data["bonus"] = self.overrides[upgrade['name']] * cps
                    if cookie_monster_data["bonus"] == 0:
                        cookie_monster_data["bonus"] = cps * 0.01
                        print(f"{timestamp()}: Forced bonus for {upgrade['name']}")
                    if cps > 0:
                        cookie_monster_data["pp"] = (max(price - (cookies + wrinklers_total), 0) / cps) + (
                                price / cookie_monster_data["bonus"])
                    else:
                        cookie_monster_data["pp"] = 0
                if cookie_monster_data and cookie_monster_data["colour"] in {"Gray", "Blue"} and \
                        not self.avoid_buy(upgrade['id']) and \
                        not upgrade["bought"] and cookie_monster_data["pp"] and cookie_monster_data["pp"] > 0:
                    # print(f"{upgrade['name']} ({upgrade['id']}): {CookieMonsterData}")
                    if not self.attempt_1T_achievement or (upgrade['id'] not in self.cursor_upgrades and
                                                           upgrade['id'] not in self.clicking_upgrades and
                                                           price < 100000000000
                                                           and cps < 500000000):
                        self.upgrades_to_buy.append(upgrade)

    # def check_elder_pledge(self):
    #     elder_pledge_xpath = f'//div[@id="toggleUpgrades"]/div[@data-id="74"]/div[@class="pieTimer"]'
    #     try:
    #         self.driver.find_element(by=By.XPATH, value=elder_pledge_xpath)
    #         self.elder_pledge_active = True
    #     except NoSuchElementException:
    #         self.elder_pledge_active = False

    def check_season(self):
        try:
            return self.driver.execute_script('javascript:return Game.season')
        except JavascriptException:
            return ''

    def harvest_lumps(self):
        try:
            age = int(self.driver.execute_script("javascript:return Date.now() - Game.lumpT"))
            # lump_ripe_age = int(self.driver.execute_script("javascript:return Game.lumpRipeAge"))
            lump_mature_age = int(self.driver.execute_script("javascript:return Game.lumpMatureAge"))
            if age >= lump_mature_age:
                current_lumps = int(self.driver.execute_script("javascript:return Game.lumps"))
                lump_type = int(self.driver.execute_script("javascript:return Game.lumpCurrentType"))
                if lump_type in (1, 3):
                    new_lump_goal = current_lumps + 2
                elif lump_type == 2:
                    new_lump_goal = current_lumps + 7
                elif lump_type == 4:
                    new_lump_goal = current_lumps + 3
                else:
                    new_lump_goal = current_lumps + 1

                self.save_game(path=self.save_file)
                self.driver.execute_script("javascript:Game.clickLump();")
                new_lumps = int(self.driver.execute_script("javascript:return Game.lumps"))
                if new_lump_goal > new_lumps:
                    self.load_save()
        except JavascriptException:
            self.click_cookie()
            return

    def stock_market(self):
        market = 'Game.Objects["Bank"].minigame'
        goods_by_id = f'{market}.goodsById'
        market_achievements = {
            'Initial public offering': False,
            'Rookie numbers': False,
            'No nobility in poverty': False,
            'Full warehouses': False,
            'Make my day': False,
            'Buy buy buy': False,
            'Pyramid scheme': False,
            'Liquid assets': False,
            'Debt evasion': False,
            'Gaseous assets': False
        }

        for market_achievement in market_achievements:
            market_achievements[market_achievement] = self.check_achievements(market_achievement)

        all_market_achievements_unlocked = all(value == 1 for value in market_achievements.values())

        if not all_market_achievements_unlocked or True:
            try:
                cursor_level = int(self.driver.execute_script("javascript:return Game.Objects['Cursor'].level"))
                cursor_amount = int(self.driver.execute_script("javascript:return Game.Objects['Cursor'].amount"))
            except JavascriptException:
                print(f"{timestamp()}: Failed to determine cursor level or amount.")
                return

            try:
                office_level = self.driver.execute_script(f"javascript:return {market}.officeLevel;")
                max_office_level = self.driver.execute_script(f"javascript:return {market}.offices.length-1;")
                if office_level < max_office_level:
                    cost = self.driver.execute_script(f"javascript:return {market}.offices[{office_level}].cost;")
                    if cost and 720 >= cursor_amount >= cost[0] and cursor_level >= cost[1]:
                        self.driver.execute_script("javascript:l('bankOfficeUpgrade').click();")
            except JavascriptException:
                print(f"{timestamp()}: Failed to upgrade office.")

            try:
                next_tick = self.driver.execute_script(f'javascript:return ((Game.fps*{market}.secondsPerTick)-'
                                                       f'{market}.tickT+30)/30')
                if next_tick > 10:
                    return
                brokers = self.driver.execute_script(f"javascript:return {market}.brokers;")
                max_brokers = self.driver.execute_script(f"javascript:return {market}.getMaxBrokers();")
                if brokers < max_brokers:
                    broker_price = self.driver.execute_script(f"javascript:return {market}.getBrokerPrice();") * 100
                    cookies = self.driver.execute_script(f"javascript:return Game.cookies;")
                    if broker_price < cookies:
                        self.driver.execute_script("javascript:l('bankBrokersBuy').click();")
                overhead = 0.2 * math.pow(.95, brokers)
            except (JavascriptException, NoSuchElementException, ElementClickInterceptedException):
                print(f"{timestamp()}: Failed to buy broker.")
                overhead = 0.2
                self.click_cookie()

            try:
                bank_level = int(self.driver.execute_script("javascript:return Game.Objects['Bank'].level"))
                market_cap = 100 + 3 * (bank_level - 1)
            except JavascriptException:
                return

            try:
                number_of_goods = self.driver.execute_script(f"javascript:return {goods_by_id}.length")
            except JavascriptException:
                return

            try:
                min_shares = 10000
                for i in range(number_of_goods):
                    min_shares = min(min_shares, self.driver.execute_script(f"javascript:"
                                                                            f"return {goods_by_id}[{i}].stock"))

                for i in range(number_of_goods):
                    if self.driver.execute_script(f"javascript:return {goods_by_id}[{i}].active &&"
                                                  f"!{goods_by_id}[{i}].hidden"):
                        good_id = i
                        good_name = self.driver.execute_script(f"javascript:return {goods_by_id}[{i}].name")
                        good_symbol = self.driver.execute_script(f"javascript:return {goods_by_id}[{i}].symbol")
                        stock_price = self.driver.execute_script(f"javascript:return {goods_by_id}[{i}].val")
                        stock_shares = self.driver.execute_script(f"javascript:return {goods_by_id}[{i}].stock")
                        resting_val = 10 * (good_id + 1) + bank_level - 1
                        if resting_val <= 30:
                            buy_price = 1
                        else:
                            buy_price = resting_val / 10
                        sell_price = max(resting_val + (30 - (good_id + 3) / 2), market_cap - 5)
                        stock_max = self.driver.execute_script(f"javascript:return {market}.getGoodMaxStock({market}."
                                                               f"goodsById[{good_id}]);")

                        if (stock_price <= buy_price and stock_shares != stock_max) or (
                                not market_achievements['Buy buy buy'] and
                                stock_price * (1 + overhead) * (stock_max - stock_shares) >= 86400
                        ):
                            print(f'{timestamp()}: Buying {good_name} ({good_symbol}) at '
                                  f'{stock_price:.2f} < {buy_price}.')
                            self.driver.execute_script(f"javascript:{market}.buyGood({good_id}, 10000)")
                        elif stock_shares > 0 and stock_price >= sell_price:
                            if market_achievements['No nobility in poverty'] or min_shares >= 500 or \
                                    all_market_achievements_unlocked:
                                print(f'{timestamp()}: Selling {good_name} ({good_symbol}) at '
                                      f'{stock_price:.2f} > {sell_price}.')
                                self.driver.execute_script(f"javascript:{market}.sellGood({good_id}, 10000)")
                        else:
                            self.click_cookie()
            except (JavascriptException, WebDriverException):
                print(f"{timestamp()}: Stock market method failure.")
                self.click_cookie()

    def upgrade_santa(self):
        try:
            if self.driver.execute_script('javascript:return (Game.Upgrades["A festive hat"].bought && '
                                          '!Game.Upgrades["Santa\'s dominion"].unlocked)'):
                self.driver.execute_script('javascript:Game.specialTab = "santa"; Game.UpgradeSanta();'
                                           'Game.ToggleSpecialMenu(0);')
        except JavascriptException:
            print(f"{timestamp()}: Failed to upgraded Santa")

    def train_dragon(self):
        try:
            crumbly_egg_unlocked = self.is_upgrade_unlocked("A crumbly egg")
            if crumbly_egg_unlocked:
                self.dragon_auras_lookup = self.driver.execute_script("javascript:return Game.dragonAurasBN")
            if crumbly_egg_unlocked and not self.dragon_complete:
                self.dragon_level = int(self.driver.execute_script("javascript:return Game.dragonLevel;"))
                self.max_dragon_level = int(self.driver.execute_script("javascript:return Game.dragonLevels.length-1;"))
                self.freeze_check()
                wanted_aura = self.dragon_auras_lookup["No aura"]["id"]
                if self.dragon_level >= 5:
                    # wanted_aura = 1  # kitten (breath of milk)
                    wanted_aura = self.dragon_auras_lookup["Breath of Milk"]["id"]
                    self.get_dragon_auras()
                if self.dragon_level >= 19:
                    # wanted_aura = 15  # radiant appetite
                    wanted_aura = self.dragon_auras_lookup["Radiant Appetite"]["id"]
                if not self.attempt_endless_cycle:
                    if self.dragon_level >= 21:
                        wanted_aura = self.final_wanted_aura
                    # wanted_aura2 = 18  # reality bending
                    wanted_aura2 = self.dragon_auras_lookup["Reality Bending"]["id"]
                else:
                    # wanted_aura2 = 1
                    wanted_aura2 = self.dragon_auras_lookup["Breath of Milk"]["id"]

                self.driver.execute_script("javascript:Game.specialTab='dragon';Game.UpgradeDragon();")
                # self.driver.execute_script("javascript:Game.UpgradeDragon();")

                if self.dragon_level < 5:
                    return

                if self.dragon_auras[0] != wanted_aura:
                    self.driver.execute_script(f"javascript:Game.SetDragonAura({wanted_aura},0);Game.ConfirmPrompt();")

                if self.dragon_level >= self.max_dragon_level and self.dragon_auras[1] != wanted_aura2:
                    self.driver.execute_script(f"javascript:Game.SetDragonAura({wanted_aura2},1);Game.ConfirmPrompt();")
                elif self.dragon_level == self.max_dragon_level and self.dragon_auras[1] == wanted_aura2:
                    self.dragon_complete = True
        except JavascriptException:
            self.click_cookie()

    def pet_the_dragon(self):
        try:
            self.dragon_level = int(self.driver.execute_script("javascript:return Game.dragonLevel;"))
        except JavascriptException:
            self.dragon_level = 0
        if self.dragon_level >= 8 and not self.dragon_upgrades_complete:
            drops = ['Dragon scale', 'Dragon claw', 'Dragon fang', 'Dragon teddy bear']
            for drop in drops:
                try:
                    something_to_get = self.driver.execute_script(f"javascript:return !Game.Has('{drop}') && "
                                                                  f"!Game.HasUnlocked('{drop}');")
                except JavascriptException:
                    something_to_get = False
                if something_to_get:
                    try:
                        self.driver.execute_script("javascript:Game.specialTab = 'dragon';Game.ToggleSpecialMenu(1);"
                                                   "Game.ClickSpecialPic();Game.ToggleSpecialMenu(0);")
                    except JavascriptException:
                        print("Failed to pet dragon.")
                # else:
                #     self.dragon_upgrades_complete = True

        # if self.dragon_complete and self.dragon_upgrades_complete:
        #     self.driver.execute_script("javascript:Game.ToggleSpecialMenu(0);")

    def set_cps_multiplier(self):
        try:
            self.cpsMult = self.driver.execute_script("javascript:return Game.cookiesPs / Game.unbuffedCps")
            if not self.cpsMult:
                self.cpsMult = 0
        except JavascriptException:
            self.click_cookie()

    def all_upgrades_unlocked(self, upgrades):
        unlocked = []
        for u in upgrades:
            self.click_cookie()
            try:
                unlocked.append(self.driver.execute_script(f'javascript:return Game.UpgradesById[{u}].unlocked'))
            except JavascriptException:
                self.click_cookie()
        return all(value for value in unlocked)

    def get_season_cookies(self):
        def get_christmas_cookies(s):
            try:
                cost = self.driver.execute_script('javascript:return Game.Upgrades["Festive biscuit"].priceFunc()')
                cps = self.driver.execute_script('javascript:return Game.unbuffedCps')
                upgrade_157 = self.driver.execute_script('javascript:return Game.Has("Reindeer baking grounds")')
                upgrade_270 = self.driver.execute_script('javascript:return Game.Has("Starsnow")')
                upgrade_159 = self.driver.execute_script('javascript:return Game.Has("Ho ho ho-flavored frosting")')
                upgrade_52 = self.driver.execute_script('javascript:return Game.Has("Lucky day")')
                upgrade_53 = self.driver.execute_script('javascript:return Game.Has("Serendipity")')
                upgrade_86 = 2 if self.driver.execute_script('javascript:return Game.Has("Get lucky")') else 1
                upgrade_473 = 1.01 if self.driver.execute_script(
                    'javascript:return Game.Has("Green yeast digestives")') else 1
                upgrade_283 = 1.1 if self.driver.execute_script('javascript:return Game.Has("Lasting fortune")') else 1
                upgrade_411 = 1.01 if self.driver.execute_script('javascript:return Game.Has("Lucky digit")') else 1
                upgrade_412 = 1.01 if self.driver.execute_script('javascript:return Game.Has("Lucky number")') else 1
                upgrade_413 = 1.01 if self.driver.execute_script('javascript:return Game.Has("Lucky payout")') else 1
                effect_duration = upgrade_86 * upgrade_473 * upgrade_283 * upgrade_411 * upgrade_412 * upgrade_413
                if upgrade_52:
                    if upgrade_53:
                        avg_time_between_golden_cookies = 121.158
                    else:
                        avg_time_between_golden_cookies = 232.251
                else:
                    avg_time_between_golden_cookies = 446.562
                avg_golden_cookies_per_day = 86400 / avg_time_between_golden_cookies
                reindeer_cps = max(25, cps * 60)
                if upgrade_157:
                    if upgrade_270:
                        avg_time_between_reindeer_spawns = 114.391
                    else:
                        avg_time_between_reindeer_spawns = 120.153
                elif upgrade_270:
                    avg_time_between_reindeer_spawns = 222.484
                else:
                    avg_time_between_reindeer_spawns = 233.733
            except JavascriptException:
                cost = float('inf')
                avg_golden_cookies_per_day = 0
                upgrade_159 = False
                reindeer_cps = 0
                avg_time_between_reindeer_spawns = float('inf')
                effect_duration = 1
            if upgrade_159:
                reindeer_cps *= 2
            daily_reindeer = 86400 / avg_time_between_reindeer_spawns
            frenzy_cookies = avg_golden_cookies_per_day * .2943
            frenzy_time = frenzy_cookies * 77 * effect_duration
            frenzy_reindeer = frenzy_time / avg_time_between_reindeer_spawns
            clot_cookies = avg_golden_cookies_per_day * .09332
            clot_time = clot_cookies * 66 * effect_duration
            clot_reindeer = clot_time / avg_time_between_reindeer_spawns
            elder_frenzy_cookies = avg_golden_cookies_per_day * .02022
            elder_frenzy_time = elder_frenzy_cookies * 6 * effect_duration
            eldeer = elder_frenzy_time / avg_time_between_reindeer_spawns
            cursed_finger_cookies = avg_golden_cookies_per_day * .00779
            cursed_finger_time = cursed_finger_cookies * 10 * effect_duration
            cursed_reindeer = cursed_finger_time / avg_time_between_reindeer_spawns
            regular_reindeer = daily_reindeer - (frenzy_reindeer + clot_reindeer + eldeer + cursed_reindeer)
            reindeer_daily_cookies = (reindeer_cps * regular_reindeer) + (frenzy_reindeer * reindeer_cps * 7 * 0.75) + (
                    clot_reindeer * reindeer_cps * 0.5) + (eldeer * reindeer_cps * 666 * 0.5)
            if reindeer_daily_cookies > cost:
                try:
                    self.driver.execute_script('javascript:Game.Upgrades["Festive biscuit"].buy()')
                    print(f"{timestamp()}: Switched from {s} to Christmas season")
                except JavascriptException:
                    print(f"{timestamp()}: Error switching to Christmas season")

        def get_halloween_cookies(s):
            try:
                self.driver.execute_script('javascript:Game.Upgrades["Ghostly biscuit"].buy()')
                print(f"{timestamp()}: Switched from {s} to Halloween season")
            except JavascriptException:
                print(f"{timestamp()}: Error switching to Halloween season")

        def get_valentines_cookies(s):
            try:
                self.driver.execute_script('javascript:Game.Upgrades["Lovesick biscuit"].buy()')
                print(f"{timestamp()}: Switched from {s} to Valentine's season")
            except JavascriptException:
                print(f"{timestamp()}: Error switching to Valentine's season")

        def get_easter_cookies(s):
            try:
                self.driver.execute_script('javascript:Game.Upgrades["Bunny biscuit"].buy()')
                print(f"{timestamp()}: Switched from {s} to Easter season")
            except JavascriptException:
                print(f"{timestamp()}: Error switching to Easter season")

        def season_finished(s):
            if s == '':
                return True
            elif s == 'valentines':
                return self.all_upgrades_unlocked(valentine_upgrades)
            elif s == 'christmas':
                if self.all_upgrades_unlocked(all_season_upgrades):
                    return False
                else:
                    return self.all_upgrades_unlocked(christmas_upgrades)
            elif s == 'easter':
                easter_finished = (self.check_achievements("Hide & seek champion") and
                                   self.all_upgrades_unlocked(easter_upgrades))
                return easter_finished
            elif s == 'halloween':
                return self.all_upgrades_unlocked(halloween_upgrades)
            elif s == 'fools':
                return False
            else:
                return True

        valentine_upgrades = list(range(169, 175))
        valentine_upgrades.append(645)
        easter_upgrades = list(range(210, 230))
        halloween_upgrades = list(range(134, 141))
        christmas_upgrades = [168]
        all_season_upgrades = valentine_upgrades + christmas_upgrades + easter_upgrades + halloween_upgrades

        self.upgrade_santa()

        try:
            if self.driver.execute_script('javascript:return (!Game.Upgrades["Season switcher"].bought ||'
                                          'Game.ascensionMode==1)'):
                return
        except JavascriptException:
            return

        season = self.check_season()

        if season_finished(season):
            if season == 'christmas':
                get_valentines_cookies(season)
            elif season == 'valentines':
                get_easter_cookies(season)
            elif season == 'easter':
                get_halloween_cookies(season)
            else:
                get_christmas_cookies(season)

    def get_dragon_auras(self):
        dragon_aura = None
        dragon_aura2 = None
        if self.dragon_level >= 5:
            try:
                dragon_aura = int(self.driver.execute_script("javascript:return Game.dragonAura;"))
                dragon_aura2 = int(self.driver.execute_script("javascript:return Game.dragonAura2;"))
            except JavascriptException:
                dragon_aura = None
                dragon_aura2 = None

        self.dragon_auras = {0: dragon_aura, 1: dragon_aura2}

    def pantheon(self):
        temple = "Game.Objects['Temple'].minigame"
        use_cyclius = False
        gods_lookup = {
            "holobore": "asceticism",
            "vomitrax": "decadence",
            "godzamok": "ruin",
            "cyclius": "ages",
            "selebrak": "seasons",
            "dotjeiess": "creation",
            "skruuia": "scorn",
            "muridal": "labor",
            "mokalsium": "mother",
            "jeremy": "industry",
            "rigidel": "order"
        }

        diamond = 0
        ruby = 1
        jade = 2

        self.get_dragon_auras()

        try:
            gods = self.driver.execute_script(f"javascript:return {temple}.gods")
            swaps_left = self.driver.execute_script(f"javascript:return {temple}.swaps")
            slots = self.driver.execute_script(f"javascript:return {temple}.slot")
        except JavascriptException:
            self.click_cookie()
            return

        move_secondary = False

        if self.attempt_endless_cycle:
            try:
                if swaps_left > 0:
                    if slots[diamond] != gods[gods_lookup["holobore"]]["id"]:
                        self.driver.execute_script(f"javascript:({temple}.slotHovered = 0;"
                                                   f"{temple}.dragging = {temple}.gods[{gods_lookup['holobore']}];"
                                                   f"{temple}.dropGod(););")
                    if slots[ruby] != gods[gods_lookup["mokalsium"]]["id"]:
                        self.driver.execute_script(f"javascript:({temple}.slotHovered = 1;"
                                                   f"{temple}.dragging = {temple}.gods[{gods_lookup['mokalsium']}];"
                                                   f"{temple}.dropGod(););")
                    if slots[jade] != gods[gods_lookup["jeremy"]]["id"]:
                        self.driver.execute_script(f"javascript:({temple}.slotHovered = 2;"
                                                   f"{temple}.dragging = {temple}.gods[{gods_lookup['jeremy']}];"
                                                   f"{temple}.dropGod(););")
            except JavascriptException:
                print(f"{timestamp()}: Failed to move god.")
                return
        elif use_cyclius:
            utc_hour = time.gmtime().tm_hour
            utc_min = time.gmtime().tm_min

            if (utc_hour in {0, 12, 18, 21} and utc_min == 0) or (utc_hour == 9 and utc_min == 19):
                if 20 in {self.dragon_auras[0], self.dragon_auras[1]}:  # Supreme Intellect active
                    new_temple_slot = ruby
                else:
                    new_temple_slot = diamond
                if swaps_left == 3:
                    perform_swap = True
                else:
                    perform_swap = False
            elif utc_hour in {1, 13} and utc_min == 12:
                if 20 in {self.dragon_auras[0], self.dragon_auras[1]}:  # Supreme Intellect active
                    new_temple_slot = jade
                else:
                    new_temple_slot = ruby
                if utc_hour == 1 and swaps_left == 3:
                    perform_swap = True
                elif utc_hour == 13 and swaps_left >= 2:
                    perform_swap = True
                else:
                    perform_swap = False
            elif (utc_hour == 4 and utc_min == 0) or (utc_hour == 10 and utc_min == 20):
                if 20 in {self.dragon_auras[0], self.dragon_auras[1]}:  # Supreme Intellect active
                    new_temple_slot = -1
                else:
                    new_temple_slot = jade
                if utc_hour == 4 and swaps_left >= 2:
                    perform_swap = True
                elif utc_hour == 10 and swaps_left == 3:
                    perform_swap = True
                else:
                    perform_swap = False
            elif utc_hour in {19, 22} and utc_min == 30:
                new_temple_slot = -1
                perform_swap = True
            elif utc_hour == 8 and utc_min == 18 and 20 in {self.dragon_auras[0], self.dragon_auras[1]}:
                move_secondary = 'jeremy'
                new_temple_slot = jade
                perform_swap = False
            elif utc_hour == 14 and utc_min == 15:
                move_secondary = 'mokalsium'
                new_temple_slot = diamond
                perform_swap = False
            else:
                new_temple_slot = -1
                perform_swap = False

            if perform_swap:
                try:
                    current_slot_id = self.driver.execute_script(f"javascript:return "
                                                                 f"{temple}.gods['{gods_lookup['cyclius']}'].slot")
                    if new_temple_slot != current_slot_id:
                        if new_temple_slot != -1:
                            print(f"{timestamp()}: Moving Cyclius ({gods_lookup['cyclius']}) to slot "
                                  f"{new_temple_slot}. Previous slot {current_slot_id}")
                            self.driver.execute_script(f"javascript:{temple}.slotHovered = {new_temple_slot};"
                                                       f"{temple}.dragging = {temple}.gods['{gods_lookup['cyclius']}'];"
                                                       f"{temple}.dropGod();")
                        elif current_slot_id != -1:
                            if self.is_veil_active:
                                new_god = "holobore"
                            else:
                                new_god = "muridal"

                            if swaps_left == 3:
                                print(f"{timestamp()}: Moving {new_god} ({gods_lookup[new_god]}) to slot "
                                      f"{current_slot_id}.")
                                self.driver.execute_script(f"javascript:{temple}.slotHovered = {current_slot_id};"
                                                           f"{temple}.dragging = {temple}.gods["
                                                           f"'{gods_lookup[new_god]}'];"
                                                           f"{temple}.dropGod();")
                            else:
                                print(f"{timestamp()}: Remove Cyclius ({gods_lookup['cyclius']}).")
                                self.driver.execute_script(f"javascript:{temple}.slotHovered = -1;"
                                                           f"{temple}.dragging = {temple}.gods["
                                                           f"'{gods_lookup['cyclius']}'];"
                                                           f"{temple}.dropGod();")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to move god.")
                    return
            elif move_secondary:
                try:
                    current_slot_id = self.driver.execute_script(f"javascript:return "
                                                                 f"{temple}.gods['{gods_lookup[move_secondary]}'].slot")
                    if new_temple_slot != current_slot_id:
                        print(f"{timestamp()}: Moving {move_secondary} ({gods_lookup[move_secondary]}) to slot "
                              f"{new_temple_slot}. Previous slot {current_slot_id}")
                        self.driver.execute_script(f"javascript:{temple}.slotHovered = {new_temple_slot};"
                                                   f"{temple}.dragging = {temple}.gods['{gods_lookup[move_secondary]}']"
                                                   f";{temple}.dropGod();")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to move Jeremy.")
                    return
        else:
            slot_id = 0
            static_gods = ['mokalsium', 'jeremy', 'muridal']

            for god in static_gods:
                try:
                    god_slot_id = self.driver.execute_script(f"javascript:return {temple}.gods['{gods_lookup[god]}']."
                                                             f"slot")
                    if god_slot_id != slot_id:
                        self.driver.execute_script(f"javascript:{temple}.slotHovered = {slot_id};"
                                                   f"{temple}.dragging = {temple}.gods['{gods_lookup[god]}'];"
                                                   f"{temple}.dropGod();")
                except JavascriptException:
                    self.click_cookie()
                slot_id += 1

    def open_mini_games(self):
        minigame_rows = [2, 5, 6, 7]

        for minigame_row in minigame_rows:
            try:
                self.driver.find_element(by=By.XPATH, value=f'//div[@id="row{minigame_row}" and @class="row enabled"]')
                self.driver.execute_script(f"javascript:Game.ObjectsById[{minigame_row}].switchMinigame(-1);")
            except (JavascriptException, NoSuchElementException, WebDriverException):
                self.click_cookie()
                return

    def quit_game(self):
        self.driver.quit()

    def pop_fattest_wrinkler(self):
        try:
            js = 'Game.wrinklers[CookieMonsterData.Cache.WrinklersFattest[1]].hp = 0'
            # fattest_id = self.driver.execute_script('javascript:return CookieMonsterData.Cache.WrinklersFattest[1]')
            self.driver.execute_script(f'javascript:{js}')
            # self.driver.find_element(by=By.ID, value="PopFattestWrinklerButton").click()
            self.time_last_wrinkler_popped = time.time()
        except JavascriptException:
            self.click_cookie()

    def level_up(self):
        buildings = {}
        max_cps_per_lump = 0
        max_cps_achievements_cookies = 0
        max_cps_per_lump_achv = 0
        sum_cps = 0
        try:
            cps_by_type = self.driver.execute_script("javascript:return Game.cookiesPsByType")
            lumps = self.driver.execute_script("javascript:return Game.lumps")
        except JavascriptException:
            self.click_cookie()
            return

        for building, cps in cps_by_type.items():
            sum_cps += cps

        for building, cps in cps_by_type.items():
            if building != '"egg"':
                try:
                    level = self.driver.execute_script(f"javascript:return Game.Objects['{building}'].level")
                except JavascriptException:
                    self.click_cookie()
                    return

                if (building != 'Cursor' and level == 9) or (building == 'Cursor' and level == 19):
                    cps_per_lump = sum_cps * 0.01 / (level + 1)
                else:
                    cps_per_lump = cps * 0.01 / (level + 1)
                buildings[building] = {'cps': cps,
                                       'level': level,
                                       'cps_per_lump': cps_per_lump}
                max_cps_per_lump = max(max_cps_per_lump, cps_per_lump)
                if (building == 'Cursor' and level < 20) or (building != 'Cursor' and level < 10):
                    cps_achievements_cookies = cps
                    cps_per_lump_achv = cps_per_lump
                else:
                    cps_achievements_cookies = 0
                    cps_per_lump_achv = 0
                max_cps_achievements_cookies = max(max_cps_achievements_cookies, cps_achievements_cookies)
                max_cps_per_lump_achv = max(max_cps_per_lump_achv, cps_per_lump_achv)

        if buildings['Wizard tower']['level'] == 0:
            if lumps > 0:
                try:
                    self.driver.execute_script("javascript:Game.Objects['Wizard tower'].levelUp()")
                    return
                except JavascriptException:
                    print(f"{timestamp()}: Failed to level up Wizard tower to level "
                          f"{buildings['Wizard tower']['level'] + 1}.")
                    self.click_cookie()
        elif buildings['Temple']['level'] == 0:
            if lumps > 0:
                try:
                    self.driver.execute_script("javascript:Game.Objects['Temple'].levelUp()")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to level up Temple to level {buildings['Temple']['level'] + 1}.")
                    self.click_cookie()
        elif buildings['Farm']['level'] == 0:
            if lumps > 0:
                try:
                    self.driver.execute_script("javascript:Game.Objects['Farm'].levelUp()")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to level up Farm to level {buildings['Farm']['level'] + 1}.")
                    self.click_cookie()
        elif buildings['Bank']['level'] == 0:
            if lumps > 0:
                try:
                    self.driver.execute_script("javascript:Game.Objects['Bank'].levelUp()")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to level up Bank to level {buildings['Bank']['level'] + 1}.")
                    self.click_cookie()
        elif buildings['Farm']['level'] < 9:
            if lumps >= buildings['Farm']['level'] + 1:
                try:
                    self.driver.execute_script("javascript:Game.Objects['Farm'].levelUp()")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to level up Farm to level {buildings['Farm']['level'] + 1}.")
                    self.click_cookie()
        elif buildings['Cursor']['level'] < 4:
            lumps_credited = buildings['Cursor']['level'] * (buildings['Cursor']['level'] + 1) / 2
            lumps_needed = 4 * 5 / 2
            actual_lumps_needed = lumps_needed - lumps_credited
            if lumps >= actual_lumps_needed:
                try:
                    self.driver.execute_script("javascript:Game.Objects['Cursor'].levelUp()")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to level up Cursor to level {buildings['Cursor']['level'] + 1}.")
                    self.click_cookie()
        elif buildings['Cursor']['level'] < 10:
            lumps_credited = buildings['Cursor']['level'] * (buildings['Cursor']['level'] + 1) / 2
            lumps_needed = 10 * 11 / 2
            actual_lumps_needed = lumps_needed - lumps_credited
            if lumps >= actual_lumps_needed:
                try:
                    self.driver.execute_script("javascript:Game.Objects['Cursor'].levelUp()")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to level up Cursor to level {buildings['Cursor']['level'] + 1}.")
                    self.click_cookie()
        elif buildings['Cursor']['level'] < 12:
            lumps_credited = buildings['Cursor']['level'] * (buildings['Cursor']['level'] + 1) / 2
            lumps_needed = 12 * 13 / 2
            actual_lumps_needed = lumps_needed - lumps_credited
            if lumps >= actual_lumps_needed:
                try:
                    self.driver.execute_script("javascript:Game.Objects['Cursor'].levelUp()")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to level up Cursor to level {buildings['Cursor']['level'] + 1}.")
                    self.click_cookie()
        elif buildings['Farm']['level'] + 1 == 10:
            if lumps >= 104:
                try:
                    self.driver.execute_script("javascript:Game.Objects['Farm'].levelUp()")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to level up Farm to level {buildings['Farm']['level'] + 1}.")
                    self.click_cookie()
        elif buildings['Cursor']['level'] < 20:
            if (buildings['Cursor']['level'] + 1 == 13 and lumps >= 107) or (buildings['Cursor']['level'] + 1 <= 20
                                                                             and lumps >= 95 +
                                                                             buildings['Cursor']['level'] + 1):
                try:
                    print(f"{timestamp()}: Failed to level up Cursor to level {buildings['Cursor']['level'] + 1}.")
                    self.driver.execute_script("javascript:Game.Objects['Cursor'].levelUp()")
                except JavascriptException:
                    self.click_cookie()
        elif max_cps_achievements_cookies > 0:
            for building, values in buildings.items():
                if (values['cps'] == max_cps_achievements_cookies and self.building_level_goal == 'achievements') or (
                        values['cps_per_lump'] == max_cps_per_lump_achv and self.building_level_goal == 'cps'):
                    next_level = values['level'] + 1
                    if (next_level < 10 and lumps >= next_level + 100) or (next_level == 10 and
                                                                           lumps >= next_level + 94):
                        try:
                            self.driver.execute_script(f"javascript:Game.Objects['{building}'].levelUp()")
                            print(f"{timestamp()}: Upgraded {building} to level {next_level}.")
                        except JavascriptException:
                            print(f"{timestamp()}: Failed to level up {building} to level {next_level}.")
                            self.click_cookie()
                    elif time.gmtime().tm_min % 5 == 0 and time.gmtime().tm_sec <= 2:
                        lumps_needed = next_level + 100 if next_level < 10 else next_level + 94
                        print(f"{timestamp()}: Saving until {lumps_needed} lumps to upgrade {building} to level "
                              f"{next_level}.")
                else:
                    self.click_cookie()
        else:
            for building, values in buildings.items():
                if values['cps_per_lump'] == max_cps_per_lump:
                    next_level = values['level'] + 1
                    if lumps >= next_level + 100:
                        try:
                            self.driver.execute_script(f"javascript:Game.Objects['{building}'].levelUp()")
                            print(f"{timestamp()}: Upgraded {building} to level {next_level}.")
                        except JavascriptException:
                            print(f"{timestamp()}: Failed to level up {building} to level {next_level}.")
                            self.click_cookie()
                    elif time.gmtime().tm_min % 5 == 0 and time.gmtime().tm_sec <= 2:
                        print(f"{timestamp()}: All level achievements unlocked. "
                              f"Saving until {next_level + 100} lumps to upgrade {building} to level {next_level}.")
                else:
                    self.click_cookie()
