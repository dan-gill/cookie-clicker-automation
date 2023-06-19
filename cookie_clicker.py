from selenium import webdriver
from selenium.common import NoSuchElementException, WebDriverException, ElementClickInterceptedException, \
    JavascriptException, StaleElementReferenceException, ElementNotInteractableException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
from os.path import exists


class CookieClicker:
    def __init__(self, trillion_cookies, endless_cycle, save_file):
        self.chromedriver = "/opt/homebrew/bin/chromedriver"
        self.service = Service(self.chromedriver)
        self.options = Options()
        self.driver = webdriver.Chrome(service=self.service, options=self.options)

        self.UPGRADE_TYPES = ["upgrades", "techUpgrades", "toggleUpgrades", "vaultUpgrades"]

        self.attempt_1T_achievement = trillion_cookies
        self.attempt_endless_cycle = endless_cycle
        self.save_file = save_file

        self.skip_pause = False
        self.is_veil_active = False
        self.wait_to_buy_upgrade = False
        self.elder_pledge_active = False
        self.season_active = False
        self.dragon_upgrades_complete = False
        self.time_last_wrinkler_popped = time.time()
        self.time_next_save = time.time() + 60
        self.next_garden_tick = time.time()
        self.ascensions = 0
        self.dragon_level = 0
        self.buy_quantity = 1
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

    def install_ublock(self):
        self.options.add_extension("./uBlock-Origin.crx")

    def check_achievements(self):
        try:
            endless_cycle = self.driver.execute_script("javascript:return Game.Achievements['Endless cycle'].won;")
            if endless_cycle:
                self.endless_cycle_achievement_won = True
                self.attempt_endless_cycle = False
        except JavascriptException:
            pass

    def freeze_check(self):
        new_title = self.driver.title
        # print(f"New Title: {new_title}")
        # print(f"Old title: {self.title}")
        if new_title != self.title:
            self.title = new_title
        else:
            self.reload_cookieclicker()

    def reload_cookieclicker(self):
        self.save_game()
        self.driver.quit()
        time.sleep(10)
        self.load_cookieclicker()

    def load_cookieclicker(self):
        self.service = Service(self.chromedriver)
        self.options = Options()
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
        self.driver.execute_script(
            "javascript:(function() {Game.LoadMod('https://cookiemonsterteam.github.io/CookieMonster/dist/"
            "CookieMonster.js');}());")

    def accept_cookie_notification(self):
        try:
            self.driver.find_element(by=By.XPATH, value='//a[@class="cc_btn cc_btn_accept_all"]').click()
        except NoSuchElementException:
            pass

    def select_language(self):
        try:
            self.driver.find_element(by=By.ID, value="langSelect-EN").click()
        except NoSuchElementException:
            pass

    def click_fortune(self):
        try:
            ticker_effect = self.driver.execute_script("javascript:return Game.TickerEffect;")
            if ticker_effect:
                self.driver.execute_script("javascript:Game.tickerL.click();")
        except JavascriptException:
            self.click_cookie()

    def close_notes(self):
        try:
            self.driver.execute_script("javascript:Game.CloseNotes();")
        except JavascriptException:
            self.click_cookie()

    def check_for_buffs(self):
        try:
            self.driver.find_element(by=By.XPATH, value='//div[@id="buffs"]/div[@class="crate enabled buff"]')
            self.skip_pause = True
        except NoSuchElementException:
            self.skip_pause = False

    def get_next_garden_tick_in_seconds(self):
        next_tick_time_js = f"javascript:return {self.farm_minigame}.nextStep / 1000"
        self.next_garden_tick = float(self.driver.execute_script(next_tick_time_js))

    def plant_age_at_next_tick(self, x, y):
        plant_id = self.get_plant_id_of_tile(x, y)
        if plant_id != -1:
            age_tick = self.plants_by_id[plant_id]["ageTick"]
            age_tick_r = self.plants_by_id[plant_id]["ageTickR"]
            tile_maturity = self.get_plant_maturity_of_tile(x, y)
            age_per_tick = age_tick + age_tick_r * 0.5
            plant_mature_age = self.plants_by_id[plant_id]['mature']
            if tile_maturity / plant_mature_age < 1/3:
                plant_maturity = "bud"
            elif tile_maturity / plant_mature_age < 2/3:
                plant_maturity = "sprout"
            elif tile_maturity / plant_mature_age < 1:
                plant_maturity = "bloom"
            else:
                plant_maturity = "mature"
            ticks_until_mature = (plant_mature_age - tile_maturity) / age_per_tick
            ticks_until_mature = 0 if ticks_until_mature < 0 else ticks_until_mature
            print(f"{x, y} {self.plants_by_id[plant_id]['name']} stage: {plant_maturity}; "
                  f"Age at next tick: {tile_maturity + age_per_tick}; Mature at {plant_mature_age}; "
                  f"{ticks_until_mature} ticks until mature.")
            return age_per_tick + tile_maturity
        else:
            return 0

    def harvest_fading_plants(self):
        if self.cpsMult > 1 or self.next_garden_tick - time.time() <= 15:
            for tile in self.farm_size:
                if self.plant_age_at_next_tick(x=tile["x"], y=tile["y"]) >= 100:
                    ts = time.localtime()
                    print(f'{ts.tm_hour:02}:{ts.tm_min:02}:{ts.tm_sec:02}: Harvesting tile {tile} before decay.')
                    self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile['x']},{tile['y']})")

    def harvest_mature_plants(self, x, y):
        if self.next_garden_tick - time.time() <= 15 or self.cpsMult > 1:
            seed_id = self.get_plant_id_of_tile(x, y)
            if self.get_plant_maturity_of_tile(x, y) > self.plants_by_id[seed_id]["mature"]:
                plant = self.plants_by_id[seed_id]["name"]
                ts = time.localtime()
                print(f'{ts.tm_hour:02}:{ts.tm_min:02}:{ts.tm_sec:02}: Harvesting tile ({x}, {y}) {plant} is mature.')
                self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({x},{y})")

    def get_plant_details(self):
        try:
            self.plants = self.driver.execute_script(f"javascript:return {self.farm_minigame}.plants")
            self.plants_by_id = self.driver.execute_script(f"javascript:return {self.farm_minigame}.plantsById")
            self.max_plants = self.driver.execute_script(f"javascript:return {self.farm_minigame}.plantsN")
            self.num_plants_unlocked = self.driver.execute_script(
                f"javascript:return {self.farm_minigame}.plantsUnlockedN")
            self.set_farm_size()
        except JavascriptException:
            pass

    def is_upgrade_unlocked(self, upgrade):
        return self.driver.execute_script(f"javascript:return Game.Upgrades['{upgrade}'].unlocked;")

    def get_plant_mature_age(self, x, y):
        plant_id = self.get_plant_id_of_tile(x, y)
        if plant_id == -1:
            return True
        else:
            return int(self.driver.execute_script(f"javascript:return {self.farm_minigame}.plantsById[{plant_id}]."
                                                  f"mature;"))

    def plant_seed(self, x, y, seed_id):
        tile_plant_id = self.get_plant_id_of_tile(x=x, y=y)
        if tile_plant_id not in [-1, seed_id, self.invalid_plant_id] and (
                self.plants_by_id[tile_plant_id]["unlocked"] or (
                self.get_plant_maturity_of_tile(x=x, y=y) > self.plants_by_id[tile_plant_id]["mature"]
        )
        ):
            print(f"Removing {self.plants_by_id[tile_plant_id]}['name'] from ({x},{y}) to plant "
                  f"{self.plants_by_id[seed_id]}.")
            self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({x},{y})")
        if tile_plant_id == -1 and (self.next_garden_tick - time.time() <= 15 or self.cpsMult < 1):
            try:
                self.cast_spell(spell_to_cast="conjure baked goods", exhaust_magic=True)
                self.driver.execute_script(f"javascript:{self.farm_minigame}.useTool({seed_id}, {x}, {y});")
            except JavascriptException:
                pass

    def is_keenmoss_in_garden(self):
        keenmoss_found = False
        for tile in self.farm_size:
            if self.is_tile_unlocked(tile["x"], tile["y"]):
                if self.get_plant_id_of_tile(tile["x"], tile["y"]) == self.plants["keenmoss"]["id"]:
                    keenmoss_found = True
                    break
        return keenmoss_found

    def are_all_keenmoss_mature(self):
        mature = True
        for tile in self.farm_size:
            if self.is_tile_unlocked(tile["x"], tile["y"]):
                if self.get_plant_id_of_tile(tile["x"], tile["y"]) == self.plants["keenmoss"]["id"]:
                    mature = self.get_plant_maturity_of_tile(tile["x"], tile["y"]) < self.plants["keenmoss"]["mature"]
                    break

        return mature

    def harvest_keenmoss_field(self):
        only_keenmoss_plants = True
        for tile in self.farm_size:
            if self.is_tile_unlocked(tile["x"], tile["y"]):
                if self.get_plant_id_of_tile(tile["x"], tile["y"]) not in {-1, self.plants["keenmoss"]["id"]}:
                    only_keenmoss_plants = False
                    break

        if only_keenmoss_plants and (self.cpsMult > 1 or self.next_garden_tick - time.time() <= 15):
            ts = time.localtime()
            print(f'{ts.tm_hour:02}:{ts.tm_min:02}:{ts.tm_sec:02}: Harvesting keenmoss field.')
            for tile in self.farm_size:
                self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile['x']},{tile['y']})")

    def is_garden_empty(self):
        garden_empty = True
        for tile in self.farm_size:
            if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) != -1:
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

    def clean_garden(self, x, y):
        plant_id_of_tile = self.get_plant_id_of_tile(x=x, y=y)
        brown_mold_and_crumbspore_unlocked = self.plants["brownMold"]["unlocked"] and \
                                             self.plants["crumbspore"]["unlocked"]

        if (self.plants_by_id[plant_id_of_tile] == "meddleweed" and brown_mold_and_crumbspore_unlocked) or (
                self.plants_by_id[plant_id_of_tile]["unlocked"] and self.plants_by_id[plant_id_of_tile] != "meddleweed"
        ):
            ts = time.localtime()
            print(f'{ts.tm_hour:02}:{ts.tm_min:02}:{ts.tm_sec:02}: Harvesting plant '
                  f'{self.plants_by_id[plant_id_of_tile]["name"]} in tile ({x}, {y}).')
            self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({x},{y})")
        elif self.plants_by_id[plant_id_of_tile] != "meddleweed" or brown_mold_and_crumbspore_unlocked:
            self.harvest_mature_plants(x=x, y=y)

    def stagger_planting(self, faster_group, faster_plant_id, slower_group, slower_plant_id,
                         faster_plant_ticks_to_mature):
        sg_oldest_age_at_next_tick = 0
        # Plant slower seeds first
        for tile in slower_group:
            tile_plant_id = self.get_plant_id_of_tile(x=tile["x"], y=tile["y"])
            if tile_plant_id != slower_plant_id:
                print(f"Planting slower maturing plant: {self.plants_by_id[slower_plant_id]['name']} in "
                      f"tile {tile}.")
                self.plant_seed(x=tile["x"], y=tile["y"], seed_id=slower_plant_id)
            else:
                tile_age_at_next_tick = self.plant_age_at_next_tick(x=tile["x"], y=tile["y"])
                sg_oldest_age_at_next_tick = max(sg_oldest_age_at_next_tick, tile_age_at_next_tick)

        print(f"Oldest {self.plants_by_id[slower_plant_id]['name']} will be {sg_oldest_age_at_next_tick} at next tick.")

        if sg_oldest_age_at_next_tick > self.plants_by_id[slower_plant_id]["mature"]:
            slower_plant_ticks_until_mature = 0
        else:
            slower_plant_ticks_until_mature = (self.plants_by_id[slower_plant_id]["mature"] -
                                               sg_oldest_age_at_next_tick) / (
                                                      self.plants_by_id[slower_plant_id]["ageTick"] +
                                                      self.plants_by_id[slower_plant_id]["ageTickR"] * 0.5)

        fg_oldest_age_at_next_tick = 0
        if slower_plant_ticks_until_mature <= faster_plant_ticks_to_mature:
            for tile in faster_group:
                tile_plant_id = self.get_plant_id_of_tile(x=tile["x"], y=tile["y"])
                if tile_plant_id != faster_plant_id:
                    print(f"Planting faster maturing plant: {self.plants_by_id[faster_plant_id]['name']} in "
                          f"tile {tile}.")
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=faster_plant_id)
                else:
                    tile_age_at_next_tick = self.plant_age_at_next_tick(x=tile["x"], y=tile["y"])
                    fg_oldest_age_at_next_tick = max(fg_oldest_age_at_next_tick, tile_age_at_next_tick)

        print(f"Oldest {self.plants_by_id[faster_plant_id]['name']} will be {fg_oldest_age_at_next_tick} at next tick.")

        if sg_oldest_age_at_next_tick > self.plants_by_id[slower_plant_id]["mature"] and \
                fg_oldest_age_at_next_tick > self.plants_by_id[faster_plant_id]["mature"]:
            self.switch_soil("woodchips")
        else:
            self.switch_soil("fertilizer")

    def mutation_setups(self):
        self.get_farm_level()
        if self.farm_level == 9:
            self.same_plant_setup = []
            for x in [1, 4]:
                for y in range(6):
                    if y != 4:
                        self.same_plant_setup.append({"x": x, "y": y})
            # Plant type 1
            type_1 = []
            for x in [1, 4]:
                for y in [0, 5]:
                    type_1.append({"x": x, "y": y})
            type_1.append({"x": 4, "y": 2})
            type_1.append({"x": 1, "y": 3})
            type_2 = []
            for x in [1, 4]:
                for y in [1, 4]:
                    type_2.append({"x": x, "y": y})
            self.two_plant_setup = {"G": type_1, "Y": type_2}
        else:
            return

    def unlock_seeds(self):
        unlock_seed_order = [
            {"seed": "bakeberry", "parent": ["bakerWheat"]},  # 34
            {"seed": "meddleweed", "parent": []},
            {"seed": "brownMold", "parent": ["meddleweed"]},  # 5
            {"seed": "chocoroot", "parent": ["bakerWheat", "brownMold"]},  # 7
            {"seed": "queenbeet", "parent": ["chocoroot", "bakeberry"]},  # 67
            {"seed": "queenbeetLump", "parent": []},  # 1063
            {"seed": "thumbcorn", "parent": ["bakerWheat"]},  # 3
            {"seed": "cronerice", "parent": ["bakerWheat", "thumbcorn"]},  # 75
            {"seed": "gildmillet", "parent": ["thumbcorn", "cronerice"]},  # 15
            {"seed": "clover", "parent": ["bakerWheat", "gildmillet"]},  # 20
            {"seed": "shimmerlily", "parent": ["gildmillet", "clover"]},  # 9
            {"seed": "elderwort", "parent": ["cronerice", "shimmerlily"]},  # 164
            {"seed": "whiteMildew", "parent": ["brownMold"]},  # 5
            {"seed": "greenRot", "parent": ["whiteMildew", "clover"]},  # 4
            {"seed": "keenmoss", "parent": ["brownMold", "greenRot"]},  # 10
            {"seed": "drowsyfern", "parent": ["chocoroot", "keenmoss"]},  # 300
            {"seed": "whiteChocoroot", "parent": ["chocoroot", "whiteMildew"]},  # 7
            {"seed": "tidygrass", "parent": ["bakerWheat", "whiteChocoroot"]},  # 80
            {"seed": "duketater", "parent": ["queenbeet"]},  # 212
            {"seed": "everdaisy", "parent": []},  # 250
            {"seed": "crumbspore", "parent": ["meddleweed"]},  # 15
            {"seed": "doughshroom", "parent": ["crumbspore"]},  # 43
            {"seed": "whiskerbloom", "parent": ["whiteChocoroot", "shimmerlily"]},  # 20
            {"seed": "nursetulip", "parent": ["whiskerbloom"]},  # 40
            {"seed": "wrinklegill", "parent": ["crumbspore", "brownMold"]},  # 26
            {"seed": "ichorpuff", "parent": ["crumbspore", "elderwort"]},  # 20
            {"seed": "chimerose", "parent": ["whiskerbloom", "shimmerlily"]},  # 18
            {"seed": "shriekbulb", "parent": []},  # 18
            {"seed": "wardlichen", "parent": ["cronerice", "whiteMildew"]},  # 10
            {"seed": "glovemorel", "parent": ["thumbcorn", "crumbspore"]},  # 7
            {"seed": "goldenClover", "parent": ["bakerWheat", "gildmillet"]},  # 5
            {"seed": "cheapcap", "parent": ["crumbspore", "shimmerlily"]},  # 3
            {"seed": "foolBolete", "parent": ["doughshroom", "greenRot"]}  # 3
        ]
        self.mutation_setups()

        self.get_plant_details()

        for seed in unlock_seed_order:
            if not self.is_seed_unlocked_or_growing(seed["seed"]):
                ts = time.localtime()
                print(f'{ts.tm_hour:02}:{ts.tm_min:02}:{ts.tm_sec:02}: Attempting to unlock {seed["seed"]}')
                num_parents = len(seed["parent"])
                if num_parents == 1:
                    oldest_seed = 1
                    parent_seed_id = self.plants[seed["parent"][0]]["id"]
                    parent_seed_maturity = self.plants[seed["parent"][0]]["mature"]
                    for tile in self.same_plant_setup:
                        tile_plant_id = self.get_plant_id_of_tile(x=tile["x"], y=tile["y"])
                        if tile_plant_id == -1:
                            self.plant_seed(x=tile["x"], y=tile["y"], seed_id=parent_seed_id)
                        if tile_plant_id == self.plants[seed["seed"]]["id"]:
                            oldest_seed = max(oldest_seed, self.get_plant_maturity_of_tile(x=tile["x"], y=tile["y"]))
                    for tile in self.farm_size:
                        if tile not in self.same_plant_setup:
                            self.clean_garden(x=tile["x"], y=tile["y"])
                    if oldest_seed >= parent_seed_maturity and seed["parent"][0] != "meddleweed" and \
                            seed["seed"] != "meddleweed":
                        self.switch_soil("woodchips")
                    else:
                        self.switch_soil("fertilizer")
                elif num_parents == 2:
                    parent1_seed = seed["parent"][0]
                    parent2_seed = seed["parent"][1]
                    if not (self.plants[parent1_seed]["unlocked"] and self.plants[parent2_seed]["unlocked"]):
                        print(f"{seed['seed']}'s parents are not unlocked.")
                        if not self.plants[parent1_seed]["unlocked"]:
                            print(f"Waiting for {parent1_seed} to mature.")
                        if not self.plants[parent2_seed]["unlocked"]:
                            print(f"Waiting for {parent2_seed} to mature.")
                        for tile in self.farm_size:
                            self.clean_garden(x=tile["x"], y=tile["y"])
                        self.switch_soil("fertilizer")
                        break
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
                    for tile in self.farm_size:
                        if tile not in self.two_plant_setup["G"] and tile not in self.two_plant_setup["Y"]:
                            self.clean_garden(x=tile["x"], y=tile["y"])
                    if maturity_difference < 0:
                        self.stagger_planting(faster_group=self.two_plant_setup["G"], faster_plant_id=parent1_seed_id,
                                              slower_group=self.two_plant_setup["Y"], slower_plant_id=parent2_seed_id,
                                              faster_plant_ticks_to_mature=parent1_ticks_until_mature)
                    else:
                        self.stagger_planting(faster_group=self.two_plant_setup["Y"], faster_plant_id=parent2_seed_id,
                                              slower_group=self.two_plant_setup["G"], slower_plant_id=parent1_seed_id,
                                              faster_plant_ticks_to_mature=parent2_ticks_until_mature)
                elif seed["seed"] == "queenbeetLump":
                    # for tile in self.farm_size:
                    #     self.clean_garden(x=tile["x"], y=tile["y"])
                    self.try_for_juicy_queenbeet()
                elif seed["seed"] == "meddleweed":
                    self.switch_soil("fertilizer")
                    for tile in self.farm_size:
                        self.clean_garden(x=tile["x"], y=tile["y"])
                elif seed["seed"] == "everdaisy":
                    # for tile in self.farm_size:
                    #     self.clean_garden(x=tile["x"], y=tile["y"])
                    self.try_for_everdaisy()
                elif seed["seed"] == "shriekbulb":
                    # for tile in self.farm_size:
                    #     self.clean_garden(x=tile["x"], y=tile["y"])
                    self.try_for_shriekbulbs()
                break
            else:
                continue

    def is_seed_unlocked_or_growing(self, seed):
        if self.plants[seed]["unlocked"]:
            return True
        for tile in self.farm_size:
            if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == self.plants[seed]["id"]:
                return True
        return False

    def obtain_garden_upgrades(self):
        # seeds = {
        #     "greenRot": "Green yeast digestives",
        #     "bakerWheat": "Wheat slims",
        #     "bakeberry": "Bakeberry cookies"
        # }

        # strategies = https://www.reddit.com/r/CookieClicker/comments/95iu08/strategies_for_random_drops_from_plants/
        garden_upgrades = [
            {"seed": "greenRot", "upgrade": "Green yeast digestives", "strategy": 1},
            {"seed": "bakerWheat", "upgrade": "Wheat slims", "strategy": 1},
            {"seed": "bakeberry", "upgrade": "Bakeberry cookies", "strategy": 1},
            {"seed": "elderwort", "upgrade": "Elderwort biscuits", "strategy": 3},
            {"seed": "ichorpuff", "upgrade": "Ichor syrup", "strategy": 5},
            {"seed": "drowsyfern", "upgrade": "Fern tea", "strategy": 4},
            {"seed": "duketater", "upgrade": "Duketater cookies", "strategy": 3}
        ]

        self.get_plant_details()

        if self.max_plants > self.num_plants_unlocked:
            return

        def strategy_1(upgrade):
            for tile in self.farm_size:
                plant = self.plants[upgrade["seed"]]
                obtain_upgrade = plant["unlocked"]
                if obtain_upgrade:
                    can_plant_js = f'{self.farm_minigame}.canPlant({self.farm_minigame}.plants["{next_drop["seed"]}"]);'
                    can_plant = self.driver.execute_script(f"javascript:return {can_plant_js}")
                    if can_plant:
                        print(f"{tile}")

        def strategy_3(upgrade):
            self.harvest_keenmoss_field()
            if self.is_garden_empty():
                for tile in self.farm_size:
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=self.plants[upgrade["seed"]]["id"])
            else:
                for tile in self.farm_size:
                    # Harvest mature target plants
                    if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == self.plants[upgrade["seed"]]["id"]:
                        self.harvest_mature_plants(x=tile["x"], y=tile["y"])
                    # Replant Keenmoss if tile is now empty
                    if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == -1:
                        self.plant_seed(x=tile["x"], y=tile["y"], seed_id=self.plants["keenmoss"]["id"])

        def strategy_4(upgrade):
            if self.is_keenmoss_in_garden() and self.are_all_keenmoss_mature():
                pass
            self.harvest_keenmoss_field()
            if self.is_garden_empty():
                for tile in self.farm_size:
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=self.plants[upgrade["seed"]]["id"])
            else:
                for tile in self.farm_size:
                    # Harvest mature target plants
                    if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == self.plants[upgrade["seed"]]["id"]:
                        self.harvest_mature_plants(x=tile["x"], y=tile["y"])
                    # Replant Keenmoss if tile is now empty
                    if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == -1:
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
                self.harvest_mature_plants(x=keenmoss_tile["x"], y=keenmoss_tile["y"])
                if self.get_plant_id_of_tile(x=keenmoss_tile["x"], y=keenmoss_tile["y"]) == -1:
                    self.plant_seed(x=keenmoss_tile["x"], y=keenmoss_tile["y"], seed_id=self.plants["keenmoss"]["id"])

            for ichorpuff_tile in ichorpuff_tiles:
                self.harvest_mature_plants(x=ichorpuff_tile["x"], y=ichorpuff_tile["y"])
                if self.get_plant_id_of_tile(x=ichorpuff_tile["x"], y=ichorpuff_tile["y"]) == -1:
                    self.plant_seed(x=ichorpuff_tile["x"], y=ichorpuff_tile["y"],
                                    seed_id=self.plants["ichorpuff"]["id"])

        def plant_seeds(plant, upgrade):
            # plants = self.driver.execute_script(f'javascript: return {self.farm_minigame}.plants;')
            # js = f'!Game.Upgrades["{upgrade}"].unlocked && {self.farm_minigame}.plants["{plant}"].unlocked'
            # obtain_upgrade = self.driver.execute_script(f'javascript:return {js}')
            # if obtain_upgrade:
            if not self.is_upgrade_unlocked(upgrade) and self.plants[plant]["unlocked"]:
                can_plant_js = f'{self.farm_minigame}.canPlant({self.farm_minigame}.plants["{plant}"]);'
                can_plant = self.driver.execute_script(f"javascript:return {can_plant_js}")
                if can_plant:
                    for tile in self.farm_size:
                        # unlocked_js = f"javascript:return {self.farm_minigame}.isTileUnlocked({x},{y});"
                        # is_tile_unlocked = self.driver.execute_script(unlocked_js)
                        elderwort_id = 7
                        if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) != elderwort_id or \
                                plant == "elderwort":
                            self.harvest_mature_plants(x=tile["x"], y=tile["y"])
                        # empty_js = f"javascript:return {self.farm_minigame}.getTile({x},{y})[0];"
                        # empty = int(self.driver.execute_script(empty_js))
                        if self.get_plant_id_of_tile(x=tile["x"], y=tile["y"]) == -1:
                            try:
                                plant_seed = f"javascript:{self.farm_minigame}." \
                                             f"useTool({self.plants[plant]['id']}, {tile['x']}, {tile['y']});"
                                self.driver.execute_script(plant_seed)
                            except JavascriptException:
                                pass

        upgrade_unlocked = True
        next_drop = None
        if not self.all_garden_drops_unlocked:
            for drop in garden_upgrades:
                if not self.is_upgrade_unlocked(drop["upgrade"]) and self.plants[drop["seed"]]["unlocked"]:
                    upgrade_unlocked = False
                    next_drop = drop
                    break
            self.all_garden_drops_unlocked = upgrade_unlocked

        if next_drop["strategy"] == 1:
            pass
            strategy_1(next_drop)
        elif next_drop["strategy"] == 3:
            strategy_3(next_drop)
        elif next_drop["strategy"] == 4:
            pass
        elif next_drop["strategy"] == 5:
            if self.farm_level >= 8:
                strategy_5()

        # if not self.all_garden_drops_unlocked and (
        #     plants_num == plants_unlocked_num or (
        #         plants_num - 1 == plants_unlocked_num and (
        #             self.plants["queenbeetLump"]["unlocked"] or self.is_juicy_queenbeet_growing()
        #         )
        #     )
        # ):
        #     for seed, garden_upgrade in seeds.items():
        #         plant_seeds(seed, garden_upgrade)

        # dragon_aura = int(self.driver.execute_script("javascript:return Game.dragonAura;"))
        #     self.driver.execute_script(f"javascript:Game.SetDragonAura({wanted_aura},0);Game.ConfirmPrompt();")
        dragon_aura = int(self.driver.execute_script("javascript:return Game.dragonAura;"))

        wanted_aura = None
        if self.dragon_complete and not self.all_garden_drops_unlocked:
            wanted_aura = 14  # Mind over Matter
        elif self.dragon_complete and self.all_garden_drops_unlocked:
            wanted_aura = 17  # dragon's curve
            # wanted_aura2 = 18  # reality bending

        if self.dragon_complete and dragon_aura != wanted_aura:
            self.driver.execute_script(f"javascript:Game.SetDragonAura({wanted_aura},0);Game.ConfirmPrompt();")

    def get_farm_level(self):
        try:
            self.farm_level = self.driver.execute_script('javascript:return Game.Objects["Farm"].level;')
        except WebDriverException:
            self.reload_cookieclicker()

    def is_tile_unlocked(self, x, y):
        unlocked_js = f"javascript:return {self.farm_minigame}.isTileUnlocked({x},{y});"
        return self.driver.execute_script(unlocked_js)

    def get_plant_id_of_tile(self, x, y):
        try:
            plant_id = int(self.driver.execute_script(f"javascript:return {self.farm_minigame}."
                                                      f"getTile({x},{y})[0];")) - 1
        except JavascriptException:
            plant_id = self.invalid_plant_id
        return plant_id

    def get_plant_maturity_of_tile(self, x, y):
        maturity_js = f"javascript:return {self.farm_minigame}.getTile({x},{y})[1];"
        return int(self.driver.execute_script(maturity_js))

    def switch_soil(self, soil):
        next_soil_time_js = f"javascript:return {self.farm_minigame}.nextSoil;"
        next_soil_time = self.driver.execute_script(next_soil_time_js) / 1000
        current_time = time.time()
        if current_time >= next_soil_time:
            desired_soil_id_js = f"javascript:return {self.farm_minigame}.soils['{soil}'].id;"
            desired_soil_id = self.driver.execute_script(desired_soil_id_js)
            current_soil_id_js = f"javascript:return {self.farm_minigame}.soil;"
            current_soil_id = self.driver.execute_script(current_soil_id_js)
            if current_soil_id != desired_soil_id:
                print(f"Switching soil to {soil}.")
                try:
                    self.driver.find_element(by=By.ID, value=f"gardenSoil-{desired_soil_id}").click()
                except (NoSuchElementException, ElementClickInterceptedException):
                    pass

    def cast_spell(self, spell_to_cast, exhaust_magic=False):
        game = "Game.Objects['Wizard tower'].minigame"
        spell = f"{game}.spells['{spell_to_cast}']"
        spell_cost = self.driver.execute_script(f"javascript:return {game}.getSpellCost({spell});")
        magic = self.driver.execute_script(f"javascript:return {game}.magic")
        cast = magic >= spell_cost
        while cast:
            if spell_to_cast == "resurrect abomination":
                self.pop_fattest_wrinkler()
            self.driver.execute_script(f"javascript:{game}.castSpell({spell});")
            if exhaust_magic:
                spell_cost = self.driver.execute_script(f"javascript:return {game}.getSpellCost({spell});")
                magic = self.driver.execute_script(f"javascript:return {game}.magic")
                cast = magic >= spell_cost
            else:
                cast = False

    def is_juicy_queenbeet_growing(self):
        for tile in self.farm_size:
                if self.get_plant_id_of_tile(tile["x"], tile["y"]) == self.plants["queenbeetLump"]["id"]:
                    return True
        return False

    def try_for_shriekbulbs(self):
        duketater = self.plants["duketater"]
        duketater_tiles = []

        if self.farm_level != 9 or not duketater["unlocked"]:
            for tile in self.farm_size:
                self.clean_garden(x=tile["x"], y=tile["y"])
            self.switch_soil("fertilizer")
            return

        for y in range(6):
            for x in [1, 4]:
                if x == 4 or y in range(1, 5):
                    duketater_tiles.append({"x": x, "y": y})

        for x in [0, 2]:
            for y in [0, 5]:
                duketater_tiles.append({"x": x, "y": y})

        oldest_seed = 1
        parent_seed_id = duketater["id"]
        parent_seed_maturity = duketater["mature"]
        for tile in duketater_tiles:
            tile_plant_id = self.get_plant_id_of_tile(x=tile["x"], y=tile["y"])
            oldest_seed = max(oldest_seed, self.get_plant_maturity_of_tile(x=tile["x"], y=tile["y"]))
            if tile_plant_id == -1:
                self.plant_seed(x=tile["x"], y=tile["y"], seed_id=parent_seed_id)
        for tile in self.farm_size:
            if tile not in duketater_tiles:
                self.clean_garden(x=tile["x"], y=tile["y"])
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
        if not (elderwort["unlocked"] and tidygrass["unlocked"]):
            if not elderwort["unlocked"]:
                print("Waiting for elderwort to mature.")
            if not tidygrass["unlocked"]:
                print("Waiting for tidygrass to mature.")
            for tile in self.farm_size:
                self.clean_garden(x=tile["x"], y=tile["y"])
            self.switch_soil("fertilizer")
            return

        elderwort_tiles = []
        tidygrass_tiles = []

        if self.is_juicy_queenbeet_growing():
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

        if not (elderwort["unlocked"] and tidygrass["unlocked"]):
            print("Parents not unlocked.")
            if not elderwort["unlocked"]:
                print(f"Waiting for elderwort to mature.")
            if not tidygrass["unlocked"]:
                print(f"Waiting for tidygrass to mature.")
            for tile in self.farm_size:
                self.clean_garden(x=tile["x"], y=tile["y"])
            self.switch_soil("fertilizer")
            return
        elderwort_maturity = elderwort["mature"]
        elderwort_age_per_tick = elderwort["ageTick"] + elderwort["ageTickR"] * 0.5
        elderwort_ticks_until_mature = elderwort_maturity / elderwort_age_per_tick
        tidygrass_maturity = tidygrass["mature"]
        tidygrass_age_per_tick = tidygrass["ageTick"] + tidygrass["ageTickR"] * 0.5
        tidygrass_ticks_until_mature = tidygrass_maturity / tidygrass_age_per_tick
        maturity_difference = elderwort_ticks_until_mature - tidygrass_ticks_until_mature
        for tile in self.farm_size:
            if tile not in elderwort_tiles and tile not in tidygrass_tiles:
                self.clean_garden(x=tile["x"], y=tile["y"])
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
        if not self.plants["queenbeet"]["unlocked"]:
            self.switch_soil("fertilizer")
            return

        def remove_undesirable_plants(x, y):
            plant_id = self.get_plant_id_of_tile(x, y)
            if plant_id not in {-1, self.plants["queenbeetLump"]["id"],
                                self.invalid_plant_id} and not self.is_juicy_queenbeet_growing():
                try:
                    input("An undesirable plant is present. Continuing will remove the plant.")
                    self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({x},{y})")
                except JavascriptException:
                    pass
            elif plant_id == self.plants["queenbeetLump"]["id"]:
                surround_with_elderwort(x, y)

        def harvest_zone(x, y):
            if self.farm_level == 8:
                vertical_coords = {n for n in range(6)}
            elif y <= 2:
                vertical_coords = {n for n in range(3)}
            else:
                vertical_coords = {3, 4, 5}

            if x <= 2:
                horizontal_coords = {n for n in range(3)}
            else:
                horizontal_coords = {3, 4, 5}

            skip = None

            if self.farm_level == 8:
                skip = [(n, 0) for n in range(6)]
                skip.append((2, 1))
                skip.append((2, 4))
                skip.append((4, 1))
                skip.append((4, 4))
            elif self.farm_level >= 9:
                skip = [
                    (1, 1), (1, 4),
                    (4, 1), (4, 4)
                ]

            for x in horizontal_coords:
                for y in vertical_coords:
                    if (x, y) not in skip:
                        print("Harvesting JQB zone.")
                        self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({x},{y})")

        def surround_with_elderwort(x, y):
            elderwort_id = self.plants["elderwort"]["id"]
            tiles = [
                (x - 1, y + 1), (x - 1, y), (x - 1, y - 1),
                (x, y + 1), (x, y - 1),
                (x + 1, y + 1), (x + 1, y), (x + 1, y - 1)
            ]

            for tile in tiles:
                plant_id = self.get_plant_id_of_tile(x=tile[0], y=tile[1])
                if plant_id not in {-1, elderwort_id}:
                    print("Harvesting elderwort tiles if they don't contain elderwort.")
                    self.driver.execute_script(f"javascript:{self.farm_minigame}.harvest({tile})")
                self.plant_seed(x=tile[0], y=tile[1], seed_id=elderwort_id)

        self.get_farm_level()

        planting_pattern = {
            7: {
                "x_coords": [1, 3, 5],
                "y_coords": [1, 3, 5],
                "total_plants": 21
            },
            8: {
                "x_coords": [0, 2, 3, 5],
                "y_coords": [1, 3, 5],
                "total_plants": 26
            },
            9: {
                "x_coords": [0, 2, 3, 5],
                "y_coords": [0, 2, 3, 5],
                "total_plants": 32
            }
        }

        if not (self.plants["queenbeetLump"]["unlocked"] or self.is_juicy_queenbeet_growing()):
            if self.farm_level >= 7:
                x_coords = planting_pattern[self.farm_level]["x_coords"]
                y_coords = planting_pattern[self.farm_level]["y_coords"]
                total_plants = planting_pattern[self.farm_level]["total_plants"]

                can_plant_js = f'{self.farm_minigame}.canPlant({self.farm_minigame}.plants["queenbeet"]);'
                can_plant = self.driver.execute_script(f"javascript:return {can_plant_js}")

                if can_plant:
                    cost_js = f'javascript:return {self.farm_minigame}.plants["queenbeet"].cost'
                    cps = self.driver.execute_script("javascript:return Game.cookiesPs;")
                    cookies = self.driver.execute_script("javascript:return Game.cookies;")
                    cost = self.driver.execute_script(cost_js)
                    total_cost = cps * 60 * total_plants * cost
                    max_maturity = 0
                    max_plant_id = -1
                    if cookies >= total_cost:
                        replant = False
                        queenbeet_id = self.plants["queenbeet"]["id"]
                        for coord in self.farm_size:
                            if coord["y"] in y_coords or coord["x"] in x_coords:
                                max_plant_id = max(max_plant_id, self.get_plant_id_of_tile(coord["x"], coord["y"]))
                                plant_maturity = int(self.get_plant_maturity_of_tile(coord["x"], coord["y"]))
                                age_at_next_tick = self.plant_age_at_next_tick(coord["x"], coord["y"])
                                if self.farm_level >= 8 and (age_at_next_tick >= 100 or age_at_next_tick == 0):
                                    harvest_zone(x=coord["x"], y=coord["y"])
                                    replant = True
                                    max_maturity = 0
                                elif self.farm_level == 7 and (
                                        age_at_next_tick >= 100 or age_at_next_tick == 0
                                ) and coord["x"] == 3 and coord["y"] == 3:
                                    for clear in self.farm_size:
                                        if clear["y"] in y_coords or clear["x"] in x_coords:
                                            self.driver.execute_script(f"javascript:Game.Objects['Farm'].minigame."
                                                                       f"harvest({clear['x']},{clear['y']})")
                                    max_maturity = 0
                                    replant = True
                                else:
                                    max_maturity = max(max_maturity, plant_maturity)
                            else:
                                remove_undesirable_plants(coord["x"], coord["y"])

                        if max_plant_id == -1 or replant:
                            for coord in self.farm_size:
                                if coord["y"] in y_coords:
                                    self.plant_seed(coord["x"], coord["y"], queenbeet_id)
                                elif coord["x"] in x_coords:
                                    self.plant_seed(coord["x"], coord["y"], queenbeet_id)

                        if max_maturity >= self.plants["queenbeet"]["mature"] and \
                                not self.plants["queenbeetLump"]["unlocked"]:
                            self.switch_soil("woodchips")
                        else:
                            self.switch_soil("fertilizer")
        elif self.is_juicy_queenbeet_growing():
            self.switch_soil("fertilizer")

    def check_veil(self):
        try:
            # self.driver.execute_script('javascript:return Game.Upgrades["Shimmering veil [on]"].canBuy();')
            self.driver.find_element(by=By.XPATH, value='//div[@id="toggleUpgrades"]/div[@data-id="564"]')
            self.is_veil_active = True
        except NoSuchElementException:
            self.is_veil_active = False

    def ascend(self):
        try:
            # prestige_levels = int(self.driver.find_element(by=By.ID,
            #                                                value="ascendNumber").text.strip('+').replace(",", ""))
            prestige_levels = int(self.driver.execute_script("javascript:return Game.ascendMeterLevel;"))

            # print(prestige_levels)
            if prestige_levels > 0:
                self.driver.execute_script("javascript:Game.Ascend(true);")
                if self.attempt_endless_cycle:
                    time.sleep(10)
                    self.driver.execute_script("javascript:Game.Reincarnate(true);")
                    self.ascensions += 1
                    ts = time.localtime()
                    print(f'{ts.tm_hour:02}:{ts.tm_min:02}:{ts.tm_sec:02}: Ascended {self.ascensions} times.')
                    time.sleep(5)
                    self.save_game()
                    self.driver.execute_script("javascript:Game.toSave=true;")
                    self.dragon_level = 0
                    self.dragon_upgrades_complete = False
                    # time.sleep(1)
                    # self.reload_cookieclicker()
                    # self.load_save()
                    # time.sleep(5)
        except JavascriptException:
            pass

    def trillion_cookie_ascension(self):
        cookie_count = int(self.driver.find_element(by=By.ID, value="cookies").text.split()[0].replace(",", ""))
        if cookie_count == 1000000000000:
            self.ascend()

    def click_cookie(self):
        # shimmer_types = ["Golden cookie", "Reindeer", "Wrath cookie"]
        xpath = '//div[@id="shimmers"]/div[@alt="Golden cookie" or @alt="Reindeer" or @alt="Wrath cookie"]'
        try:
            if not self.is_veil_active or self.season_active:
                self.driver.execute_script("javascript:Game.ClickCookie();")
            # Click shimmer types
            shimmers = self.driver.execute_script("javascript:return Game.shimmers")
            if shimmers:
                try:
                    early_bird_won = self.driver.execute_script(
                        "javascript:return Game.Achievements['Early bird'].won")
                    fading_luck_won = self.driver.execute_script(
                        "javascript:return Game.Achievements['Fading luck']."
                        "won")
                    fps = self.driver.execute_script("javascript:return Game.fps")
                    # print(f"Fading Luck Won: {fading_luck_won}\nEarly Bird Won: {early_bird_won}\nFPS: {fps}")
                    # print(type(shimmers))
                    # print(shimmers)
                    for s in shimmers:
                        # print(f"Shimmer Type: {s['type']}")
                        # print(f"Shimmer life: {s['life']}")
                        # print(f"Shimmer duration: {s['dur']}")
                        # print(f"Shimmer force: {s['force']}")
                        if s["type"] != "golden" or s["life"] < fps or not early_bird_won:
                            self.driver.find_element(by=By.XPATH, value=xpath).click()
                            # print("popping from first if")
                            # self.driver.execute_script(f"javascript:(function() {{{s}.pop();}})")
                        elif s["life"] / fps < (s["dur"] - 2) and fading_luck_won:
                            self.driver.find_element(by=By.XPATH, value=xpath).click()
                            # print("popping from first elif")
                            # self.driver.execute_script(f"javascript:(function() {{{s}.pop();}})")
                        elif s["force"] == "cookie storm drop":
                            self.driver.find_element(by=By.XPATH, value=xpath).click()
                            # print("popping from second elif")
                            # self.driver.execute_script(f"javascript:(function() {{{s}.pop();}})")
                    # self.driver.find_element(by=By.XPATH,
                    #                          value=f'//div[@id="shimmers"]/div[@alt="{shimmer_type}"]').click()
                except (JavascriptException, NoSuchElementException, ElementClickInterceptedException,
                        StaleElementReferenceException, ElementNotInteractableException):
                    pass

            if self.attempt_1T_achievement:
                self.trillion_cookie_ascension()
        except JavascriptException:
            pass

    def save_game(self):
        try:
            self.driver.execute_script("javascript:Game.ExportSave();")
            save_code = self.driver.find_element(by=By.ID, value="textareaPrompt").text
            if save_code == "":
                input("Save code corrupted. Copy save file before continuing.")
            with open(file=self.save_file, mode="w") as progress:
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

    def get_bulk_number(self):
        bulk_xpath = '//div[@id="storeBulk"]/div[@style="color: rgb(0, 255, 0);"]'
        try:
            bulk_mode = self.driver.find_element(by=By.XPATH, value=bulk_xpath)
            self.buy_quantity = bulk_mode.text
            if bulk_mode.get_attribute("class") != "storePreButton storeBulkAmount selected":
                game_command = bulk_mode.get_attribute("onclick")
                self.driver.execute_script(f"javascript:{game_command}")
        except (JavascriptException, NoSuchElementException):
            pass

    def buy_products(self):
        if not self.wait_to_buy_upgrade and not self.attempt_1T_achievement:
            product_to_purchase_xpath = '//div[@class="product unlocked enabled"]/div/span[starts-with(' \
                                        '@id,"productPrice") and @style="color: rgb(0, 255, 0);"]'
            exit_time = time.time() + 3

            while not self.wait_to_buy_upgrade and time.time() <= exit_time:
                try:
                    if self.attempt_endless_cycle:
                        self.driver.execute_script(f"javascript:Game.storeBulkButton(4);")
                        products_available = self.driver.find_elements(by=By.XPATH,
                                                                       value='//div[@class="product unlocked enabled"]')
                        for product in products_available:
                            product_id = int(product.get_attribute("id").strip("product"))
                            amount = int(
                                self.driver.execute_script(f"javascript:return Game.ObjectsById[{product_id}].amount;"))
                            if self.dragon_level == self.max_dragon_level - 3:
                                self.driver.execute_script(f"Game.storeBulkButton(4);"
                                                           f"Game.ObjectsById[{self.dragon_level - 5}].buy(100);")
                            elif amount < 200 and self.dragon_level < self.max_dragon_level:
                                self.driver.execute_script(f"Game.storeBulkButton(4);"
                                                           f"Game.ObjectsById[{product_id}].buy(100);")
                            else:
                                self.driver.execute_script(f"Game.storeBulkButton(3);"
                                                           f"Game.ObjectsById[{product_id}].buy(10);")

                    else:
                        self.get_bulk_number()
                        product_id = int(self.driver.find_element(by=By.XPATH,
                                                                  value=product_to_purchase_xpath
                                                                  ).get_attribute("id").strip("productPrice"))
                        amount = int(
                            self.driver.execute_script(f"javascript:return Game.ObjectsById[{product_id}].amount;"))
                        if self.dragon_level == self.max_dragon_level - 3:
                            self.driver.execute_script(f"Game.storeBulkButton(4);"
                                                       f"Game.ObjectsById[{self.dragon_level - 5}].buy(100);")
                        elif amount < 200 and self.dragon_level < self.max_dragon_level:
                            self.driver.execute_script(f"Game.storeBulkButton(4);"
                                                       f"Game.ObjectsById[{product_id}].buy(100);")
                        else:
                            self.driver.execute_script(
                                f"javascript:Game.ObjectsById[{product_id}].buy({self.buy_quantity});")
                except (JavascriptException, NoSuchElementException):
                    self.click_cookie()
                    break

                self.check_for_upgrades()

    def buy_upgrades(self):
        if not self.attempt_1T_achievement:
            div_crate_class = 'div[@class="crate upgrade enabled"]'

            for upgrade_type in self.UPGRADE_TYPES:
                if upgrade_type == "upgrades":
                    div_color_class = 'div[@class="CMBackBlue" or @class="CMBackGray"]'
                else:
                    div_color_class = 'div[@class="CMBackBlue"]'
                upgrade_enabled_xpath = f'//div[@id="{upgrade_type}"]/{div_crate_class}/{div_color_class}/..'
                try:
                    desired_upgrades = self.driver.find_elements(by=By.XPATH, value=upgrade_enabled_xpath)
                    for desired_upgrade in desired_upgrades:
                        data_id = int(desired_upgrade.get_attribute("data-id"))
                        if data_id not in {71, 74, 452, 331, 563} and not (data_id in {182, 183, 184, 185, 209} and
                                                                           self.season_active):
                            self.driver.execute_script(f"javascript:Game.UpgradesById[{data_id}].buy(true);")
                            if data_id == 563:
                                self.is_veil_active = True
                            elif data_id in {182, 183, 184, 185, 209}:
                                self.season_active = True
                            elif data_id == 69:
                                self.driver.execute_script("javascript:Game.ClosePrompt();")
                        else:
                            self.click_cookie()
                except (JavascriptException, NoSuchElementException, WebDriverException):
                    self.click_cookie()

    def check_for_upgrades(self):
        div_crate_class = 'div[@class="crate upgrade" or @class="crate upgrade enabled"]'
        div_color_class = 'div[@class="CMBackBlue"]'
        self.check_elder_pledge()

        for upgrade_type in self.UPGRADE_TYPES:
            upgrades_xpath = f'//div[@id="{upgrade_type}"]/{div_crate_class}/{div_color_class}/..'
            try:
                upgrade = self.driver.find_element(by=By.XPATH, value=upgrades_xpath)
                # if (int(upgrade.get_attribute("data-id")) not in {452, 331, 563} and
                #         not (int(upgrade.get_attribute("data-id")) == 74 and self.elder_pledge_active)):
                if int(upgrade.get_attribute("data-id")) not in {452, 331, 563, 74, 71}:
                    self.wait_to_buy_upgrade = True
                    break
                else:
                    self.wait_to_buy_upgrade = False
            except NoSuchElementException:
                self.wait_to_buy_upgrade = False
                self.click_cookie()

    def check_elder_pledge(self):
        elder_pledge_xpath = f'//div[@id="toggleUpgrades"]/div[@data-id="74"]/div[@class="pieTimer"]'
        try:
            self.driver.find_element(by=By.XPATH, value=elder_pledge_xpath)
            self.elder_pledge_active = True
        except NoSuchElementException:
            self.elder_pledge_active = False

    def check_season_timer(self):
        season_ids = '@data-id="182" or @data-id="183" or @data-id="184" or @data-id="185" or @data-id="209"'

        season_xpath = f'//div[@id="toggleUpgrades"]/div[{season_ids}]/div[@class="pieTimer"]'
        try:
            self.driver.find_element(by=By.XPATH, value=season_xpath)
            self.season_active = True
        except NoSuchElementException:
            self.season_active = False

    def harvest_lumps(self):
        try:
            # lump = self.driver.find_element(by=By.ID, value="lumpsIcon2")
            # opacity = float(lump.get_attribute("style").split("opacity: ")[1].split(";")[0])
            lump_time = int(self.driver.execute_script("javascript:return Game.lumpT"))
            lump_ripe_age = int(self.driver.execute_script("javascript:return Game.lumpRipeAge"))
            age = time.time() - lump_time
            if age >= lump_ripe_age:
                self.driver.execute_script("javascript:Game.clickLump();")
            # if opacity == 1:
            #     self.driver.execute_script("javascript:Game.clickLump();")
        except JavascriptException:
            pass

    def stock_market(self):
        market = "Game.Objects['Bank'].minigame"
        try:
            brokers = self.driver.execute_script(f"javascript:return {market}.brokers;")
            max_brokers = self.driver.execute_script(f"javascript:return {market}.getMaxBrokers();")
            if brokers < max_brokers:
                broker_price = self.driver.execute_script(f"javascript:return {market}.getBrokerPrice();") * 100
                cookies = self.driver.execute_script(f"javascript:return Game.cookies;")
                if broker_price < cookies:
                    self.driver.find_element(by=By.ID, value="bankBrokersBuy").click()
        except (JavascriptException, NoSuchElementException, ElementClickInterceptedException):
            self.click_cookie()

        try:
            bank_level = int(self.driver.find_element(by=By.ID, value="productLevel5").text.split()[1])
            number_of_goods = len(self.driver.find_elements(by=By.XPATH, value='//div[@class="bankGood"]'))
            for i in range(number_of_goods - 1):
                try:
                    stock_price = float(self.driver.find_element(by=By.ID, value=f"bankGood-{i}-val").text.replace("$",
                                                                                                                   ""))
                    stock_shares = int(self.driver.find_element(by=By.ID, value=f"bankGood-{i}-stock").text)
                    stock_max = int(self.driver.find_element(by=By.ID, value=f"bankGood-{i}-stockMax").text.replace("/",
                                                                                                                    ""))
                    if stock_price <= (10 * (i + 1) + bank_level - 1) / 5 and stock_shares != stock_max:
                        self.driver.find_element(by=By.ID, value=f"bankGood-{i}_Max").click()
                    elif stock_shares > 0 and stock_price >= (10 * (i + 1) + bank_level - 1):
                        self.driver.find_element(by=By.ID, value=f"bankGood-{i}_-All").click()
                    else:
                        self.click_cookie()
                except (ElementClickInterceptedException, NoSuchElementException):
                    self.click_cookie()
        except NoSuchElementException:
            self.click_cookie()

    def upgrade_santa(self):
        try:
            self.driver.execute_script("javascript:Game.UpgradeSanta();")
        except JavascriptException:
            pass

    def train_dragon(self):
        try:
            # crumbly_egg_unlocked = self.driver.execute_script("javascript:"
            #                                                   "return Game.Upgrades['A crumbly egg'].unlocked")
            crumbly_egg_unlocked = self.is_upgrade_unlocked("A crumbly egg")
            if crumbly_egg_unlocked and not self.dragon_complete:
                self.dragon_level = int(self.driver.execute_script("javascript:return Game.dragonLevel;"))
                self.max_dragon_level = int(self.driver.execute_script("javascript:return Game.dragonLevels.length-1;"))
                self.freeze_check()
                dragon_aura = 0
                dragon_aura2 = 0
                wanted_aura = 0
                if self.dragon_level >= 5:
                    wanted_aura = 1  # kitten (breath of milk)
                    dragon_aura = int(self.driver.execute_script("javascript:return Game.dragonAura;"))
                    dragon_aura2 = int(self.driver.execute_script("javascript:return Game.dragonAura2;"))
                if self.dragon_level >= 19:
                    wanted_aura = 15  # radiant appetite
                if not self.attempt_endless_cycle:
                    if self.dragon_level >= 21:
                        wanted_aura = 17  # dragon's curve
                    wanted_aura2 = 18  # reality bending
                else:
                    wanted_aura2 = 1  #

                self.driver.execute_script("javascript:Game.specialTab='dragon'")
                self.driver.execute_script("javascript:Game.UpgradeDragon();")

                if dragon_aura != wanted_aura:
                    self.driver.execute_script(f"javascript:Game.SetDragonAura({wanted_aura},0);Game.ConfirmPrompt();")

                if self.dragon_level >= self.max_dragon_level and dragon_aura2 != wanted_aura2:
                    self.driver.execute_script(f"javascript:Game.SetDragonAura({wanted_aura2},1);Game.ConfirmPrompt();")
                elif self.dragon_level == self.max_dragon_level and dragon_aura2 == wanted_aura2:
                    self.dragon_complete = True
        except JavascriptException:
            pass

    def pet_the_dragon(self):
        if self.dragon_level >= 8 and not self.dragon_upgrades_complete:
            drops = ['Dragon scale', 'Dragon claw', 'Dragon fang', 'Dragon teddy bear']
            for drop in drops:
                something_to_get = self.driver.execute_script(f"javascript:return !Game.Has('{drop}');"
                                                              f"!Game.HasUnlocked('{drop}');")
                if something_to_get:
                    try:
                        self.driver.execute_script("javascript:Game.ClickSpecialPic();")
                    except JavascriptException:
                        pass
                else:
                    self.dragon_upgrades_complete = True

        if self.dragon_complete and self.dragon_upgrades_complete:
            self.driver.execute_script("javascript:Game.ToggleSpecialMenu(0);")

    def set_cps_multiplier(self):
        try:
            self.cpsMult = self.driver.execute_script("javascript:return Game.cookiesPs / Game.unbuffedCps")
        except JavascriptException:
            pass

    def pantheon(self):
        gods = {
            "holobore": "templeGodDrag0",
            "vomitrax": "templeGodDrag1",
            "godzamok": "templeGodDrag2",
            "cyclius": "templeGodDrag3",
            "selebrak": "templeGodDrag4",
            "dotjeiess": "templeGodDrag5",
            "skruuia": "templeGodDrag9",
            "muridal": "templeGodDrag6",
            "mokalsium": "templeGodDrag8",
            "jeremy": "templeGodDrag7",
            "rigidel": "templeGodDrag10"
        }

        diamond = "templeSlot0"  # Diamond
        ruby = "templeSlot1"  # Diamond
        jade = "templeSlot2"  # Diamond

        self.close_notes()
        try:
            swaps_left = int(self.driver.find_element(by=By.XPATH,
                                                      value="//div[@id='templeSwaps']/span[@class='titleFont']"
                                                      ).text.split('/')[0])
        except (NoSuchElementException, StaleElementReferenceException):
            return

        if self.attempt_endless_cycle:
            try:
                if swaps_left > 0:
                    mokalsium = self.driver.find_element(by=By.ID, value=gods["mokalsium"])
                    jeremy = self.driver.find_element(by=By.ID, value=gods["jeremy"])
                    holobore = self.driver.find_element(by=By.ID, value=gods["holobore"])
                    diamond = self.driver.find_element(by=By.ID, value=diamond)  # Diamond
                    ruby = self.driver.find_element(by=By.ID, value=ruby)  # Ruby
                    jade = self.driver.find_element(by=By.ID, value=jade)  # Jade
                    ActionChains(self.driver).drag_and_drop(source=holobore, target=diamond).perform()
                    ActionChains(self.driver).drag_and_drop(source=mokalsium, target=ruby).perform()
                    ActionChains(self.driver).drag_and_drop(source=jeremy, target=jade).perform()
            except NoSuchElementException:
                pass
        else:
            utc_hour = time.gmtime().tm_hour
            utc_min = time.gmtime().tm_min

            if (utc_hour in {0, 12, 18, 21} and utc_min == 0) or (utc_hour == 9 and utc_min == 19):
                new_temple_slot = diamond  # Diamond
                if swaps_left == 3:
                    perform_swap = True
                else:
                    perform_swap = False
            elif utc_hour in {1, 13} and utc_min == 12:
                new_temple_slot = ruby  # Ruby
                if utc_hour == 1 and swaps_left == 3:
                    perform_swap = True
                elif utc_hour == 13 and swaps_left >= 2:
                    perform_swap = True
                else:
                    perform_swap = False
            elif (utc_hour == 4 and utc_min == 0) or (utc_hour == 10 and utc_min == 20):
                new_temple_slot = jade  # Jade
                if utc_hour == 4 and swaps_left >= 2:
                    perform_swap = True
                elif utc_hour == 10 and swaps_left == 3:
                    perform_swap = True
                else:
                    perform_swap = False
            elif utc_hour in {19, 22} and utc_min == 30:
                new_temple_slot = "None"
                perform_swap = True
            else:
                new_temple_slot = ""
                perform_swap = False

            if perform_swap:
                try:
                    current_slot = self.driver.find_element(by=By.XPATH, value=f'//div[@id="{gods["cyclius"]}"]/../..')
                    current_slot_id = current_slot.get_attribute("id")
                    cyclius = self.driver.find_element(by=By.ID, value=gods["cyclius"])
                    if new_temple_slot != current_slot_id:
                        if new_temple_slot != "None":
                            new_slot = self.driver.find_element(by=By.ID, value=new_temple_slot)
                            ActionChains(self.driver).drag_and_drop(source=cyclius, target=new_slot).perform()
                        elif current_slot_id == diamond:
                            if self.is_veil_active:
                                new_slot = self.driver.find_element(by=By.ID, value=gods["holobore"])
                            else:
                                new_slot = self.driver.find_element(by=By.ID, value=gods["skruuia"])

                            if swaps_left == 3:
                                ActionChains(self.driver).drag_and_drop(source=new_slot, target=current_slot).perform()
                            else:
                                ActionChains(self.driver).drag_and_drop(source=cyclius, target=new_slot).perform()
                except NoSuchElementException:
                    pass

    def open_mini_games(self):
        minigame_rows = [2, 5, 6, 7]

        for minigame_row in minigame_rows:
            try:
                self.driver.find_element(by=By.XPATH, value=f'//div[@id="row{minigame_row}" and @class="row enabled"]')
                self.driver.execute_script(f"javascript:Game.ObjectsById[{minigame_row}].switchMinigame(-1);")
            except (JavascriptException, NoSuchElementException):
                pass

    def quit_game(self):
        self.driver.quit()

    def pop_fattest_wrinkler(self):
        try:
            self.driver.find_element(by=By.ID, value="PopFattestWrinklerButton").click()
            self.time_last_wrinkler_popped = time.time()
        except (NoSuchElementException, ElementClickInterceptedException):
            pass
