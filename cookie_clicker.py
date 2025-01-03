import math
import time
from collections import OrderedDict
from itertools import count
from os import getenv, remove
from os.path import exists

import traceback, gc, psutil, os, signal

import humanize
import numpy as np
from colorama import Fore, Style
from colorama import init as colorama_init
# CHROME_BINARY_FULL_PATH = environ["CHROME_BINARY_FULL_PATH"]
from dotenv import load_dotenv
from scipy.fft import ifft2
from selenium import webdriver
from selenium.common import NoSuchElementException, WebDriverException, ElementClickInterceptedException, \
    JavascriptException, InvalidSessionIdException, TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import urllib3.exceptions
from http.client import RemoteDisconnected

load_dotenv()
colorama_init()
CHROME_BINARY_FULL_PATH = getenv("CHROME_BINARY_FULL_PATH")
SECONDS_UNTIL_NEXT_TICK = 20
SECONDS_BTWN_SAVES = 45
CPS_THRESHOLD = 1
MAX_SAVES = 90  # Retain the last 90 backups
AC_CLICKS = 30 # 17 seems to be the upper limit for CPS, but 3 seems to be the upper limit for cookies from clicking/s
AC_MS = 1 # However, Avg cookies/s seems to be highest with 20 in AC_CLICKS
# Define buff categories
CLICK_BUFFS = {'Click frenzy', 'Dragonflight', 'Elder frenzy'}
BUILDING_SPECIALS = {
    'High-five', 'Congregation', 'Luxuriant harvest', 'Ore vein',
    'Oiled-up', 'Juicy profits', 'Fervent adoration', 'Manabloom',
    'Delicious lifeforms', 'Breakthrough', 'Righteous cataclysm',
    'Golden ages', 'Extra cycles', 'Solar flare', 'Winning streak',
    'Macrocosm', 'Refactoring', 'Cosmic nursery', 'Brainstorm',
    'Deduplication'
}
STACKING_BUFFS = CLICK_BUFFS | {'Building Special', 'Dragon Harvest', 'Frenzy'}
MAX_BUILDINGS = {
    0: 5071,
    1: 5053,
    2: 5031,
    3: 5014,
    4: 4996,
    5: 4979,
    6: 4960,
    7: 4940,
    8: 4921,
    9: 4902,
    10: 4883,
    11: 4864,
    12: 4846,
    13: 4828,
    14: 4810,
    15: 4793,
    16: 4754,
    17: 4717,
    18: 4681,
    19: 4640
}


def timestamp():
    ts = time.localtime()
    return f'{ts.tm_hour:02}:{ts.tm_min:02}:{ts.tm_sec:02}'


def terminate_chrome_processes(timeout=5):
    """
    Gracefully terminate Chrome processes, and forcefully kill them if they don't exit within the timeout.
    """
    chrome_processes = []

    # Step 1: Identify all Chrome processes
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        try:
            if "chrome" in proc.info['name'].lower():
                chrome_processes.append(proc)
                print(f"{Fore.LIGHTYELLOW_EX}Attempting to terminate process {proc.info['name']} "
                      f"(PID: {proc.info['pid']}){Style.RESET_ALL}")
                proc.terminate()  # Request graceful termination
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # Step 2: Wait for processes to terminate gracefully
    start_time = time.time()
    while time.time() - start_time < timeout:
        still_running = []
        for proc in chrome_processes:
            if proc.is_running():
                still_running.append(proc)

        if not still_running:  # All processes terminated gracefully
            print(f"{Fore.LIGHTBLUE_EX}All Chrome processes terminated gracefully.{Style.RESET_ALL}")
            return
        time.sleep(0.5)  # Check every 0.5 seconds

    # Step 3: Forcefully kill any remaining processes
    for proc in chrome_processes:
        try:
            if proc.is_running():
                print(f"{Fore.LIGHTRED_EX}Forcefully killing process {proc.info['name']} "
                      f"(PID: {proc.info['pid']}){Style.RESET_ALL}")
                os.kill(proc.pid, signal.SIGKILL)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    print(f"{Fore.LIGHTMAGENTA_EX}All Chrome processes have been terminated.{Style.RESET_ALL}")


class CookieClicker:
    def __init__(self, save_file, building_level_goal, handle_ascension):
        self.is_reloading = self.cheat = False
        self.handle_ascension = handle_ascension
        self.cookie_click_errors = self.reset_bonus_percent = self.prestige = self.new_prestige = 0
        self.current_soil_id = self.ascension_mode = None
        self.debuff_active = self.cursed_finger_active = self.planted_this_tick = self.harvested_this_tick = False
        self.f_active = self.bs_active = self.dh_active = self.df_active = self.cf_active = self.ef_active = None
        self.f_count = self.bs_count = self.dh_count = self.df_count = self.cf_count = self.ef_count = self.cursed_finger_count = self.debuff_count = 0
        self.delay_aura_change = self.time_last_wrinkler_popped = self.next_cps_update = time.time()
        self.upgrades_to_buy = self.active_debuffs = self.active_buffs =[]
        self.dragon_auras = self.dragon_auras_lookup = self.driver = self.buildings_owned = None
        self.cps_threshold = 50
        self.print_prestige = float('inf')
        self.chromedriver = "/opt/homebrew/bin/chromedriver"
        # Install Chrome for testing: npx @puppeteer/browsers install chrome@stable
        self.service = Service(self.chromedriver)
        self.options = webdriver.ChromeOptions()
        self.options.binary_location = CHROME_BINARY_FULL_PATH
        self.options.add_argument("--start-maximized")
        self.options.add_argument("--mute-audio")
        self.options.add_extension("./Adblock-for-Chrome-Chrome-Web-Store.crx")
        # self.driver = webdriver.Chrome(service=self.service, options=self.options)

        self.attempt_1T_achievement = self.attempt_endless_cycle = True
        self.building_level_goal = building_level_goal
        self.save_file = save_file
        self.final_wanted_aura = self.final_wanted_aura2 = self.desired_soil = None
        self.is_veil_active = self.season_active = self.dragon_upgrades_complete = self.sugar_frenzy_spend = False
        self.delay_product_purchase_until_after = self.cursed_finger_upgrades_next_time = time.time()
        self.time_next_save = time.time() + SECONDS_BTWN_SAVES
        # Add cleanup interval
        self.next_cleanup = time.time() + 600  # 10 minutes
        self.harvest_when_mature = ['bakeberry', 'chocoroot', 'whiteChocoroot', 'queenbeet', 'duketater']
        self.harvest_before_decay = ['crumbspore', 'doughshroom']
        self.next_garden_tick = self.swaps_left = 0
        self.previous_garden_tick = self.last_spell_status_print = 0
        self.plot_boost = None
        self.plot = None
        self.next_soil_time = self.next_market_check = 0
        self.attempt_to_unlock_seeds = True
        self.last_garden_check_time = self.last_buffed_harvest = self.last_debuffed_planting = time.time() - (60 * 15)
        self.last_harvest_check = self.last_garden_clean = self.last_plant_time = time.time() - (60 * 15)
        self.ascensions = 0
        self.dragon_level = 0
        self.max_dragon_level = 0
        self.endless_cycle_achievement_won = self.crafty_pixies = self.true_neverclick = False
        self.dragon_complete = self.godzamok_ascension_delay = False
        self.title = self.interval_id = None
        self.farm_level = 0
        self.all_garden_drops_unlocked = False
        self.farm_minigame = "Game.Objects['Farm'].minigame"
        self.farm_size = None
        self.occupied_tiles = None
        self.plants = None
        self.plants_by_id = None
        self.max_plants = 34
        self.num_plants_unlocked = 0
        self.num_locked_plants_growing = 0
        self.same_plant_setup = None
        self.two_plant_setup = None
        self.invalid_plant_id = 9999
        self.empty_tile_plant_id = -1
        self.cpsMult = 1
        self.spell_count_four_leaf_cookie = float(
            'inf')  # https://mylaaan.github.io/FtHoF-Planner-v4/ Two FTHOF from 5897
        # Gambler's Dream
        self.click_golden_cookies = True
        self.farming_goal = 'lumps'
        self.soils = {
            'clay': 2,
            'dirt': 0,
            'fertilizer': 1,
            'pebbles': 3,
            'woodchips': 4
        }
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
        self.unlock_seed_od = OrderedDict([
            ("bakeberry", ["bakerWheat"]),  # 34
            ("meddleweed", []),
            ("brownMold", ["meddleweed"]),  # 5
            ("chocoroot", ["bakerWheat", "brownMold"]),  # 7
            ("queenbeet", ["chocoroot", "bakeberry"]),  # 67
            ("queenbeetLump", []),  # 1063 - Dead-end
            ("thumbcorn", ["bakerWheat"]),  # 3
            ("cronerice", ["bakerWheat", "thumbcorn"]),  # 75
            ("gildmillet", ["cronerice", "thumbcorn"]),  # 15
            ("clover", ["gildmillet", "bakerWheat"]),  # 20
            ("shimmerlily", ["clover", "gildmillet"]),  # 9
            ("elderwort", ["cronerice", "shimmerlily"]),  # 164
            ("whiteMildew", ["brownMold"]),  # 5
            ("wardlichen", ["cronerice", "whiteMildew"]),  # 10 - Dead-end
            ("whiteChocoroot", ["chocoroot", "whiteMildew"]),  # 7
            ("tidygrass", ["bakerWheat", "whiteChocoroot"]),  # 80
            ("everdaisy", []),  # 250 - Dead-end
            ("greenRot", ["clover", "whiteMildew"]),  # 4
            ("keenmoss", ["brownMold", "greenRot"]),  # 10
            ("drowsyfern", ["chocoroot", "keenmoss"]),  # 300 - Dead-end
            ("duketater", ["queenbeet"]),  # 212
            ("crumbspore", ["meddleweed"]),  # 15
            ("ichorpuff", ["elderwort", "crumbspore"]),  # 20 Maybe switch order? - Dead-end
            ("whiskerbloom", ["whiteChocoroot", "shimmerlily"]),  # 20
            ("nursetulip", ["whiskerbloom"]),  # 40 - Dead-end
            ("doughshroom", ["crumbspore"]),  # 43
            ("foolBolete", ["doughshroom", "greenRot"]),  # 3 - Dead-end
            ("wrinklegill", ["crumbspore", "brownMold"]),  # 26 - Dead-end
            ("chimerose", ["whiskerbloom", "shimmerlily"]),  # 18 - Dead-end
            ("glovemorel", ["crumbspore", "thumbcorn"]),  # 7 - Dead-end
            ("goldenClover", ["gildmillet", "bakerWheat"]),  # 5 - Dead-end
            ("shriekbulb", []),  # 18 - Dead-end
            ("cheapcap", ["crumbspore", "shimmerlily"]),  # 3 - Dead-end
        ])
        self.buildings_to_sell = [
            # Wizard tower should be first in this list
            # Order the list ascending by the combined synergy and building cps provided
            {'name': 'Wizard tower', 'id': 7, 'buy_back_quantity': 0},
            {'name': 'Bank', 'id': 5, 'buy_back_quantity': 0},
            {'name': 'Factory', 'id': 4, 'buy_back_quantity': 0},
            {'name': 'Antimatter condenser', 'id': 12, 'buy_back_quantity': 0},
            {'name': 'Alchemy lab', 'id': 9, 'buy_back_quantity': 0},
            # {'name': 'Mine', 'id': 3, 'buy_back_quantity': 0},
            {'name': 'Portal', 'id': 10, 'buy_back_quantity': 0},
            {'name': 'Idleverse', 'id': 17, 'buy_back_quantity': 0},
            {'name': 'Farm', 'id': 2, 'buy_back_quantity': 0},
            {'name': 'Temple', 'id': 6, 'buy_back_quantity': 0},
            {'name': 'Shipment', 'id': 8, 'buy_back_quantity': 0},
            {'name': 'Prism', 'id': 13, 'buy_back_quantity': 0},
            {'name': 'Cortex baker', 'id': 18, 'buy_back_quantity': 0},
            # {'name': 'Cursor', 'id': 0, 'buy_back_quantity': 0},
            {'name': 'Chancemaker', 'id': 14, 'buy_back_quantity': 0},
            {'name': 'Time machine', 'id': 11, 'buy_back_quantity': 0},
            # {'name': 'Fractal engine', 'id': 15, 'buy_back_quantity': 0},
        ]
        self.cursor_upgrades = [0, 1, 2, 3, 4, 5, 6, 43, 82, 109, 188, 189, 660, 764, 873]
        self.clicking_upgrades = [75, 76, 77, 78, 119, 190, 191, 366, 367, 427, 460, 461, 661, 765, 874]
        self.cost_scaling_upgrades = [648, 649, 650, 651, 473, 474, 475]

    def autoclicker(self, amount_of_clicks, ms_interval):
        if self.interval_id:
            stack = traceback.extract_stack()
            filename, lineno, function_name, code = stack[-2]
            # print(f"{timestamp()}: Called from {filename}, line {lineno}, in {function_name}: {code}")

            print(f"{timestamp()}: {Fore.LIGHTCYAN_EX}Interval ID: {self.interval_id} needs to be cleared first. "
                  f"Called from line {lineno} in {function_name}.{Style.RESET_ALL}")
            return

        script=f"""
        var autoClicker = function(clicksAtOnce, repeatInterval) {{
          var cheated = false;
          var intoTheAbyss = function() {{
            if(!cheated) {{
              cheated = true;
              for(var i = 0; i < clicksAtOnce; i++) {{
                Game.ClickCookie();
                Game.lastClick = 0;
              }}
              cheated = false;
            }}
          }};
          return setInterval(intoTheAbyss, repeatInterval);
        }};
        return autoClicker({amount_of_clicks}, {ms_interval});
        """

        if (not self.is_veil_active or self.season_active) and (self.ascension_mode == 0 or
                                                                self.true_neverclick):
            self.interval_id = self.driver.execute_script(f"javascript:{script}")
            print(f"{timestamp()}: Interval ID for autoclicker: {self.interval_id}")

    def exec_js(self, script, default_return=None):
        click_cookie = (not self.is_veil_active or self.season_active) and (self.ascension_mode == 0 or
                                                                            self.true_neverclick)

        try:
            if click_cookie:
                if not self.interval_id:
                    self.autoclicker(amount_of_clicks=AC_CLICKS, ms_interval=AC_MS)
                return self.driver.execute_script(f"javascript:Game.ClickCookie(); {script}")
            else:
                return self.driver.execute_script(f"javascript:{script}")
        except JavascriptException:
            print(f"{timestamp()}: Failed to execute script: {script}")
            return default_return
        except TimeoutException:
            print(f"{timestamp()}: Script timed out running: {script}")
            print(f"{timestamp()}: Reloading.")
            self.reload_cookieclicker(skip_save=True)
        except (Exception, WebDriverException, urllib3.exceptions.ProtocolError, RemoteDisconnected) as e:
            if not self.is_reloading:
                # Handle specific exceptions related to session crashes
                if "session deleted" in str(e) or "page crash" in str(e):
                    print(f"{timestamp()}: Detected page crash: {e}. Reloading without saving...")
                    self.reload_cookieclicker(skip_save=True)
                elif isinstance(e, (urllib3.exceptions.ProtocolError, RemoteDisconnected)):
                    print(f"{timestamp()}: Connection error: {str(e)}. Reloading.")
                    self.reload_cookieclicker(skip_save=True)
                else:
                    print(f"{timestamp()}: Unexpected error: {str(e)}. Reloading.")
                    self.reload_cookieclicker(skip_save=self.time_next_save - time.time() > 30)
                self.is_reloading = False
            else:
                print(f"{timestamp()}: Reload already in progress. Skipping.")
            return default_return

    def cleanup(self):
        """Clear cached data periodically"""
        current_time = time.time()
        if current_time >= self.next_cleanup:
            # Get memory info before cleanup
            process = psutil.Process(os.getpid())
            before_python_mem = process.memory_info().rss / (1024 * 1024)  # RSS in MB
            before_count = gc.get_count()
            before_stats = self.exec_js('return window.performance.memory;')

            # Perform cleanup
            collected = gc.collect()

            # Get memory info after cleanup
            after_python_mem = process.memory_info().rss / (1024 * 1024)
            after_count = gc.get_count()
            after_stats = self.exec_js('return window.performance.memory;')

            # Check Chrome's memory usage
            chrome_mem = self.get_chrome_memory_usage()

            # Print cleanup results
            print(f"{timestamp()}: Memory cleanup completed:")
            print(f"  Python process memory: {before_python_mem:.1f}MB → {after_python_mem:.1f}MB")
            print(f"  Python objects collected: {collected}")
            print(f"  GC count before: {before_count}, after: {after_count}")
            print(f"  Chrome memory: {chrome_mem:.1f}MB")
            if before_stats and after_stats:  # Chrome-only stats
                before_mb = before_stats.get('usedJSHeapSize', 0) / (1024 * 1024)
                after_mb = after_stats.get('usedJSHeapSize', 0) / (1024 * 1024)
                print(f"  JS Heap memory: {before_mb:.1f}MB → {after_mb:.1f}MB")

                # If Python process memory is too high, do a full reload
                if after_python_mem > 1000 or after_mb > 2000:  # 1GB and 2GB threshold
                    print(f"{timestamp()}: Python memory usage too high ({after_python_mem:.1f}MB), performing full reload...")
                    self.reload_cookieclicker()
                    after_stats = self.exec_js('return window.performance.memory;')
                    if after_stats:
                        after_mb = after_stats.get('usedJSHeapSize', 0) / (1024 * 1024)
                        print(f"  JS Heap memory after reset: {after_mb:.1f}MB")
                    after_python_mem = process.memory_info().rss / (1024 * 1024)
                    print(f"{timestamp()}: Python memory usage after reload: {after_python_mem:.1f}MB")

            # If Chrome's memory exceeds 4GB, reload it
            if chrome_mem > 4000:  # 4GB threshold
                print(
                    f"{timestamp()}: {Fore.YELLOW}Chrome memory usage too high ({chrome_mem:.1f}MB), "
                    f"performing full reload...{Style.RESET_ALL}")
                self.reload_cookieclicker()

            self.next_cleanup = current_time + 600

    def get_chrome_memory_usage(self):
        """Get total memory usage of all Chrome processes."""
        total_memory = 0
        for proc in psutil.process_iter(attrs=['pid', 'name', 'memory_info']):
            try:
                if "chrome" in proc.info['name'].lower():
                    total_memory += proc.info['memory_info'].rss / (1024 * 1024)  # Convert to MB
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return total_memory

    def clear_memory(self):
        """Clear browser memory periodically"""
        try:
            self.exec_js(script="""
                // Force garbage collection
                window.gc && window.gc();
            """)
        except JavascriptException:
            print(f"{timestamp()}: Failed to clear memory")

    def assign_permanent_slot(self, slot, options):
        if self.exec_js(f"return !Game.UpgradesById[264+{slot}].bought;"):
            return

    def check_achievements(self, achievement):
        script = f"return Game.Achievements['{achievement}'].won;"
        if achievement != 'True Neverclick':
            return self.exec_js(script=script, default_return=False)
        else:
            if not self.true_neverclick:
                try:
                    self.true_neverclick = self.driver.execute_script(f"javascript:{script}") == 1
                except JavascriptException:
                    print(f"{timestamp()}: Unable to read True Neverclick achievement status.")
                    return self.true_neverclick
            return self.true_neverclick

    def freeze_check(self):
        new_title = self.driver.title
        if new_title != self.title:
            self.title = new_title
        else:
            self.reload_cookieclicker()

    def reload_cookieclicker(self, skip_save=False):
        self.interval_id = None
        try:
            print(f"{timestamp()}: Reloading the game.")
            if not skip_save:
                self.save_game(path=self.save_file)

            # Try to quit the WebDriver
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()

            # Ensure Chrome is terminated
            terminate_chrome_processes(timeout=5)

            # Restart the WebDriver and reload the game
            self.load_cookieclicker()

        except Exception as e:
            print(f"{timestamp()}: Error during reload: {e}")

    def load_cookieclicker(self):
        self.driver = webdriver.Chrome(service=self.service, options=self.options)

        # Load game webpage
        self.driver.get("https://orteil.dashnet.org/cookieclicker/")
        # input("Pause")

        # Select language if not already selected
        self.select_language()

        # Close save progress notification
        self.close_notes()

        try:
            # Wait for CookieMonster to load by checking for its presence
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return typeof Game.ImportSaveCode == 'function';")
            )
        except TimeoutException:
            self.reload_cookieclicker(skip_save=True)

        self.load_save()

        # Load mods
        self.load_mods()

        # Click to accept cookie notification
        self.accept_cookie_notification()

        try:
            if self.interval_id:
                self.driver.execute_script(f"javascript:clearInterval({self.interval_id});")
                self.interval_id = None
                self.autoclicker(amount_of_clicks=AC_CLICKS, ms_interval=AC_MS)
        except JavascriptException:
            print(f"{timestamp()}: Failed to clear autoclicker.")

        if self.attempt_1T_achievement:
            self.attempt_1T_achievement = self.check_achievements("When the cookies ascend just right") == 0

        self.get_ascension_mode()
        self.check_season()

        if self.buildings_owned is None:
            self.set_buildings_owned()
            self.level_up()

        if self.plants is None:
            self.get_plant_details(ignore_tick=True)

        self.get_active_buffs()
        if self.is_upgrade_unlocked("A crumbly egg"):
            self.dragon_auras_lookup = self.exec_js(script="return Game.dragonAurasBN;", default_return={})

        # Once all achievements are unlocked, hack in some cookies and max out all buildings
        # Realistically, the And a little extra achievement should be the last one to obtain
        if self.check_achievements("And a little extra"):
            self.cheat = True

    def cheating(self):
        buildings = self.exec_js(
            script="""
            if (Game.lumps !== Infinity) {
                Game.lumps = 2 ** 1024;
            };
            return Game.ObjectsById
                .filter(({ price }) => price !== Infinity)
                .map(({id, name, amount, price, locked, highest}) =>
                    ({id, name, amount, price, locked, highest})
                );
            """,
            default_return=[]
        )

        # If no candidates, skip
        if buildings:
            for building in buildings:
                # You can easily get the building name and ID:
                name = building['name']
                building_id = building['id']

                buy = max(MAX_BUILDINGS[building_id] - building['amount'], 0)
                if buy > 0:
                    # Hack in some cookies and max out the next building
                    self.exec_js(script=f"Game.cookies = 2 ** 1024;Game.ObjectsById[{building_id}].buy({buy});")
                    print(f"{timestamp()}: {Fore.LIGHTGREEN_EX}Buying {buy} {name} after hacking in some cookies."
                          f"{Style.RESET_ALL}")
                    continue

        self.level_up()

    def load_mods(self):
        mods_to_load = {
            "FortuneCookie": "https://klattmose.github.io/CookieClicker/FortuneCookie.js",
            "CookieMonsterData": "https://cookiemonsterteam.github.io/CookieMonster/dist/CookieMonster.js"
        }

        try:
            # Wait for Game.LoadMod to load by checking for its presence
            WebDriverWait(self.driver, 2).until(
                lambda d: d.execute_script("return typeof Game.LoadMod == 'function';")
            )
        except TimeoutException:
            self.reload_cookieclicker(skip_save=True)

        for mod, mod_url in mods_to_load.items():
            try:
                if self.driver.execute_script(f"javascript:return typeof {mod} == 'undefined';"):
                    exec_js = f"javascript:Game.LoadMod('{mod_url}');"
                    # Load FortuneCookie mod
                    print(f"{timestamp()}: Load module script: {mod_url}")
                    self.driver.execute_script(exec_js)

                    # Wait for modules to load by checking for their presence
                    WebDriverWait(self.driver, 1).until(
                        lambda d: d.execute_script(f"return typeof {mod} == 'object';")
                    )
            except TimeoutException:
                self.load_mods()
            except JavascriptException:
                self.reload_cookieclicker()

    def accept_cookie_notification(self):
        try:
            self.driver.execute_script("javascript:document.querySelector('a.cc_btn.cc_btn_accept_all').click();")
        except JavascriptException:
            print(f"{timestamp()}: Failed to accept browser cookie.")

    def select_language(self):
        try:
            # Wait for language selection to load by checking for its presence
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.ID, "langSelect-EN"))
            )
            self.driver.execute_script("localStorageSet('CookieClickerLang','EN'); Game.toSave=true;"
                                       "Game.toReload=true;")
        except JavascriptException:
            return
        except TimeoutException:
            self.reload_cookieclicker(skip_save=True)

    def close_notes(self):
        self.exec_js(script="Game.CloseNotes();")

    def get_next_garden_tick_in_seconds(self):
        if self.next_garden_tick == 0 or self.next_garden_tick - time.time() < 0:
            try:
                previous_garden_tick = self.next_garden_tick
                self.next_garden_tick = float(
                    self.exec_js(script=f"return {self.farm_minigame}.nextStep / 1000", default_return=0))

                if self.previous_garden_tick == 0:
                    step_t = self.exec_js(script=f"return {self.farm_minigame}.stepT", default_return=0)

                    self.previous_garden_tick = self.next_garden_tick - step_t
                else:
                    self.previous_garden_tick = previous_garden_tick
            except JavascriptException:
                self.next_garden_tick = 0
                self.previous_garden_tick = 0
                self.click_cookie()

    def plant_ticks_until_mature(self, plant, x=-1, y=-1, dragon_boost=1.0):
        # aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
        # dragon_boost = 1 / (1 + 0.05 * aura_multi)

        age_tick = self.plants[plant]["ageTick"]
        age_tick_r = self.plants[plant]["ageTickR"]
        if x < 0 or y < 0:
            return math.ceil(
                (100 / ((age_tick + age_tick_r / 2) / dragon_boost)) * ((self.plants[plant]['mature']) / 100))
        else:
            tile_maturity = self.get_plant_maturity_of_tile(x=x, y=y)
            if tile_maturity >= self.plants[plant]['mature']:
                return 0
            else:
                return math.ceil((100 / (self.plot_boost[y][x][0] * (age_tick + age_tick_r / 2) / dragon_boost)) * (
                        (self.plants[plant]['mature'] - tile_maturity) / 100))

    def plant_ticks_until_decayed(self, plant, x=-1, y=-1):
        aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
        dragon_boost = 1 / (1 + 0.05 * aura_multi)

        age_tick = self.plants[plant]["ageTick"]
        age_tick_r = self.plants[plant]["ageTickR"]
        try:
            if self.plants[plant]['immortal']:
                return float('inf')

            if x < 0 or y < 0:
                return math.ceil((100 / ((age_tick + age_tick_r / 2) / dragon_boost)))

            tile_maturity = self.get_plant_maturity_of_tile(x=x, y=y)
            return math.ceil((100 / (self.plot_boost[y][x][0] * (age_tick + age_tick_r / 2) / dragon_boost)) * (
                    (100 - tile_maturity) / 100))
        except KeyError:
            if x < 0 or y < 0:
                return math.ceil((100 / ((age_tick + age_tick_r / 2) / dragon_boost)))

            tile_maturity = self.get_plant_maturity_of_tile(x=x, y=y)
            return math.ceil((100 / (self.plot_boost[y][x][0] * (age_tick + age_tick_r / 2) / dragon_boost)) * (
                    (100 - tile_maturity) / 100))

    def plant_age_at_next_tick(self, x, y):
        try:
            plant_data = self.occupied_tiles[(x, y)]
        except KeyError:
            return 0

        aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
        dragon_boost = 1 / (1 + 0.05 * aura_multi)

        plant_id = self.plants[plant_data['name']]['id']
        age_tick = self.plants_by_id[plant_id]["ageTick"]
        age_tick_r = self.plants_by_id[plant_id]["ageTickR"]
        tile_maturity = plant_data['maturity']
        avg_age_per_tick = (age_tick + age_tick_r / 2) * self.plot_boost[y][x][0] * dragon_boost
        max_age_per_tick = (age_tick + age_tick_r) * self.plot_boost[y][x][0] * dragon_boost
        plant_mature_age = self.plants_by_id[plant_id]['mature']
        if tile_maturity / plant_mature_age < 1 / 3:
            plant_maturity = "bud"
        elif tile_maturity / plant_mature_age < 2 / 3:
            plant_maturity = "sprout"
        elif tile_maturity / plant_mature_age < 1:
            plant_maturity = "bloom"
        else:
            plant_maturity = "mature"
        ticks_until_mature = self.plant_ticks_until_mature(plant=plant_data['name'], x=x, y=y, dragon_boost=dragon_boost)
        age_at_next_tick = tile_maturity + max_age_per_tick if tile_maturity + max_age_per_tick >= 100 \
            else tile_maturity + avg_age_per_tick

        if age_at_next_tick >= 100 or 0 < ticks_until_mature <= 1:
            print(f"{timestamp()}: {x, y} {self.plants_by_id[plant_id]['name']} stage: {plant_maturity}; "
                  f"Age at next tick: {tile_maturity + avg_age_per_tick}; Mature at {plant_mature_age}; "
                  f"{ticks_until_mature} ticks until mature.")
        return age_at_next_tick

    def harvest_mature_plants(self, x, y):
        try:
            plant_data = self.occupied_tiles[x, y]
            seed_id = self.plants[plant_data['name']]['id']
        except KeyError:
            self.click_cookie()
            return

        if plant_data['maturity'] >= self.plants_by_id[seed_id]["mature"]:
            plant = plant_data["name"]
            print(f'{timestamp()}: Harvesting tile ({x}, {y}) {plant} is mature.')
            self.exec_js(script=f"{self.farm_minigame}.harvest({x},{y});")
            self.get_plot_details()
            del self.occupied_tiles[x, y]
            if self.cpsMult > 1:
                self.last_buffed_harvest = time.time()

    def get_plot_details(self):
        self.plot, self.plot_boost = self.exec_js(script=f'return [{self.farm_minigame}.plot, '
                                                         f'{self.farm_minigame}.plotBoost];',
                                                  default_return=[None, None])
        if self.plot is None or self.plot_boost is None:
            self.reload_cookieclicker()

    def get_plant_details(self, ignore_tick=False):
        self.get_next_garden_tick_in_seconds()
        current_time = time.time()

        # Fetch next soil time if it hasn't been set
        if self.next_soil_time == 0:
            self.next_soil_time = float(self.exec_js(script=f"return {self.farm_minigame}.nextSoil / 1000;",
                                                     default_return=current_time + 1000))

        # Early return if within the tick boundaries
        if not ignore_tick and (self.previous_garden_tick < self.last_garden_check_time < self.next_garden_tick or
                                current_time - 2 <= self.next_soil_time <= current_time + 2):
            return

        if self.previous_garden_tick < self.last_garden_check_time < self.next_garden_tick:
            self.planted_this_tick = False
            self.harvested_this_tick = False

        self.attempt_to_unlock_seeds = True
        self.last_garden_check_time = current_time

        # Print next tick details
        seconds_until_next_tick = self.next_garden_tick - current_time
        time_of_next_tick_struct = time.localtime(self.next_garden_tick)
        time_of_next_tick = (f'{time_of_next_tick_struct.tm_hour:02}:{time_of_next_tick_struct.tm_min:02}:'
                             f'{time_of_next_tick_struct.tm_sec:02}')
        print(f'{timestamp()}: Updating plant details in self.plants and self.plants_by_id. '
              f'Next garden tick in {seconds_until_next_tick:.0f} seconds at {time_of_next_tick}.')

        # current_soil_id_js = f"{self.farm_minigame}.soil"
        garden_data = self.exec_js(script=f"""
                                return {{
                                    plants: {self.farm_minigame}.plants,
                                    plantsById: {self.farm_minigame}.plantsById,
                                    plantsN: {self.farm_minigame}.plantsN,
                                    currentSoilId: {self.farm_minigame}.soil,
                                    auraMult: Game.auraMult('Supreme Intellect'),
                                    plot: {self.farm_minigame}.plot,
                                    plotBoost: {self.farm_minigame}.plotBoost
                                    }}
                                """)

        if garden_data:
            self.plants = garden_data['plants']
            self.plants_by_id = garden_data['plantsById']
            self.max_plants = garden_data['plantsN']
            self.current_soil_id = garden_data['currentSoilId']
            aura_multi = garden_data['auraMult']
            dragon_boost = 1 / (1 + 0.05 * aura_multi)
            self.plot = garden_data['plot']
            self.plot_boost = garden_data['plotBoost']
        else:
            self.click_cookie()
            return

        try:
            # Reset plant states
            inf_val = float('inf')
            for plant in self.plants.values():
                plant.update({
                    'growing': False,
                    'ticks_until_mature': inf_val,
                    'ticks_until_decayed': inf_val
                })
            # for key in self.plants:
            #     self.plants[key]['growing'] = False
            #     self.plants[key]["ticks_until_mature"] = float('inf')
            #     self.plants[key]["ticks_until_decayed"] = float('inf')

            self.set_farm_size()
            self.occupied_tiles = {}

            for tile in self.farm_size:
                x, y = tile['x'], tile['y']
                tile_id = self.get_plant_id_of_tile(x, y)
                if tile_id in [self.empty_tile_plant_id, self.invalid_plant_id]:
                    continue

                plant = self.plants_by_id[tile_id]['key']
                age = self.get_plant_maturity_of_tile(x=x, y=y)
                plot_boost_value = self.plot_boost[y][x][0] * dragon_boost
                max_age_per_tick = (self.plants[plant]["ageTick"] + self.plants[plant]["ageTickR"]) * plot_boost_value
                avg_age_per_tick = (self.plants[plant]["ageTick"] + self.plants[plant][
                    "ageTickR"] / 2) * plot_boost_value
                age_at_next_tick = age + max_age_per_tick if age + max_age_per_tick >= 100 else age + avg_age_per_tick

                ticks_until_mature = self.plant_ticks_until_mature(plant=plant, x=x, y=y, dragon_boost=dragon_boost)
                ticks_until_decayed = self.plant_ticks_until_decayed(plant=plant, x=x, y=y)

                if not self.plants[plant]["unlocked"]:
                    if (plant != 'meddleweed' and age >= self.plants[plant]["mature"]) or (
                            plant == 'meddleweed' and age_at_next_tick >= 100):
                        print(f'{timestamp()}: Harvesting tile {tile} to unlock seed. {plant} is mature.')
                        self.exec_js(script=f"{self.farm_minigame}.harvest({x},{y});")

                        self.get_plot_details()
                        self.plants[plant]["unlocked"] = True
                        self.plants[plant]["ticks_until_mature"] = float('inf')
                        self.plants[plant]["growing"] = False
                        self.save_game(path=f'./{plant}_unlocked.txt')
                        if plant == 'meddleweed':
                            tile_id = self.get_plant_id_of_tile(x, y)
                            if tile_id in [self.empty_tile_plant_id, self.invalid_plant_id]:
                                continue
                            plant = self.plants_by_id[tile_id]['key']
                            age = self.get_plant_maturity_of_tile(x=x, y=y)
                            max_age_per_tick = (self.plants[plant]["ageTick"] + self.plants[plant][
                                "ageTickR"]) * plot_boost_value
                            avg_age_per_tick = (self.plants[plant]["ageTick"] + self.plants[plant][
                                "ageTickR"] / 2) * plot_boost_value
                            age_at_next_tick = (
                                age + max_age_per_tick if age + max_age_per_tick >= 100 else age + avg_age_per_tick)
                            ticks_until_mature = self.plant_ticks_until_mature(plant=plant, x=x, y=y, dragon_boost=dragon_boost)
                            ticks_until_decayed = self.plant_ticks_until_decayed(plant=plant, x=x, y=y)
                            self.plants[plant]["ticks_until_mature"] = min(self.plants[plant]["ticks_until_mature"],
                                                                           ticks_until_mature)
                            self.plants[plant]["ticks_until_decayed"] = min(self.plants[plant]["ticks_until_decayed"],
                                                                            ticks_until_decayed)
                            self.plants[plant]["growing"] = True
                            self.occupied_tiles[x, y] = {
                                "name": plant,
                                "id": tile_id,
                                "ticks_until_mature": ticks_until_mature,
                                "ticks_until_decayed": ticks_until_decayed,
                                "maturity": age,
                                "age_at_next_tick": age_at_next_tick
                            }
                    else:
                        self.plants[plant]["ticks_until_mature"] = min(self.plants[plant]["ticks_until_mature"],
                                                                       ticks_until_mature)
                        self.plants[plant]["ticks_until_decayed"] = min(self.plants[plant]["ticks_until_decayed"],
                                                                        ticks_until_decayed)
                        self.plants[plant]["growing"] = True
                        self.occupied_tiles[x, y] = {
                            "name": plant,
                            "id": tile_id,
                            "ticks_until_mature": ticks_until_mature,
                            "ticks_until_decayed": ticks_until_decayed,
                            "maturity": age,
                            "age_at_next_tick": age_at_next_tick
                        }
                elif age_at_next_tick >= 100:
                    print(f'{timestamp()}: Harvesting {plant} at tile {tile} before decay.')
                    self.exec_js(script=f"{self.farm_minigame}.harvest({x},{y});")

                    self.get_plot_details()
                    if self.cpsMult > 1:
                        self.last_buffed_harvest = current_time
                    if plant == 'meddleweed':
                        tile_id = self.get_plant_id_of_tile(x, y)
                        if tile_id in [self.empty_tile_plant_id, self.invalid_plant_id]:
                            continue
                        plant = self.plants_by_id[tile_id]['key']
                        age = self.get_plant_maturity_of_tile(x=x, y=y)
                        max_age_per_tick = (self.plants[plant]["ageTick"] + self.plants[plant][
                            "ageTickR"]) * plot_boost_value
                        avg_age_per_tick = (self.plants[plant]["ageTick"] + self.plants[plant][
                            "ageTickR"] / 2) * plot_boost_value
                        age_at_next_tick = (
                            age + max_age_per_tick if age + max_age_per_tick >= 100 else age + avg_age_per_tick)
                        ticks_until_mature = self.plant_ticks_until_mature(plant=plant, x=x, y=y, dragon_boost=dragon_boost)
                        ticks_until_decayed = self.plant_ticks_until_decayed(plant=plant, x=x, y=y)
                        self.plants[plant]["ticks_until_mature"] = min(self.plants[plant]["ticks_until_mature"],
                                                                       ticks_until_mature)
                        self.plants[plant]["ticks_until_decayed"] = min(self.plants[plant]["ticks_until_decayed"],
                                                                        ticks_until_decayed)
                        self.plants[plant]["growing"] = True
                        self.occupied_tiles[x, y] = {
                            "name": plant,
                            "id": tile_id,
                            "ticks_until_mature": ticks_until_mature,
                            "ticks_until_decayed": ticks_until_decayed,
                            "maturity": age,
                            "age_at_next_tick": age_at_next_tick
                        }
                else:
                    self.plants[plant]["ticks_until_mature"] = 0  # Set to zero if the plant is already unlocked
                    self.plants[plant]["ticks_until_decayed"] = min(self.plants[plant]["ticks_until_decayed"],
                                                                    ticks_until_decayed)
                    self.plants[plant]["growing"] = True
                    age_at_next_tick = (
                        age + max_age_per_tick if age + max_age_per_tick >= 100 else age + avg_age_per_tick)

                    self.occupied_tiles[x, y] = {
                        "name": plant,
                        "id": tile_id,
                        "ticks_until_mature": ticks_until_mature,
                        "ticks_until_decayed": ticks_until_decayed,
                        "maturity": age,
                        "age_at_next_tick": age_at_next_tick
                    }

                self.plants_by_id[tile_id]["unlocked"] = self.plants[plant]["unlocked"]
                self.plants_by_id[tile_id]["growing"] = self.plants[plant]["growing"]
                self.plants_by_id[tile_id]["ticks_until_mature"] = self.plants[plant]["ticks_until_mature"]
                self.plants_by_id[tile_id]["ticks_until_decayed"] = self.plants[plant]["ticks_until_decayed"]
        except JavascriptException:
            self.click_cookie()
            return

        self.num_plants_unlocked = self.exec_js(script=f"return {self.farm_minigame}.plantsUnlockedN;",
                                                default_return=0)

        locked_plants_growing = [
            p for p in self.plants if self.plants[p]["growing"] and not self.plants[p]["unlocked"]
        ]
        plants_left_to_unlock = [
            s for s, p in self.unlock_seed_od.items() if
            not self.plants[s]["growing"] and not self.plants[s]["unlocked"]
        ]
        self.num_locked_plants_growing = len(locked_plants_growing)

        for key in locked_plants_growing:
            self.save_game(path=f'./{key}.txt')

        print(f"{timestamp()}: {self.num_plants_unlocked} plants are unlocked and "
              f"{self.num_locked_plants_growing} {locked_plants_growing} are growing out of {self.max_plants}. "
              f"Trying to unlock {plants_left_to_unlock}.")

        if self.cpsMult <= 1:
            self.unlock_seeds()
        self.obtain_garden_upgrades()
        if self.farming_goal == 'lumps':
            self.garden_maintenance(plant_name='bakeberry')
        elif self.farming_goal == 'cookies':
            self.increase_golden_cookie_frequency()

    def is_upgrade_unlocked(self, upgrade):
        return self.exec_js(script=f"return Game.Upgrades['{upgrade}'].unlocked;", default_return=False)

    def plant_seed(self, x, y, seed_id):
        try:
            plant_data = self.occupied_tiles[x, y]
            tile_plant_id = plant_data['id']
            plant_age = plant_data['maturity']
            plant_unlocked = self.plants_by_id[tile_plant_id]["unlocked"]
            plant_mature_age = self.plants_by_id[tile_plant_id]["mature"]
            if tile_plant_id != seed_id and (plant_unlocked or plant_age >= plant_mature_age):
                print(f"{timestamp()}: Removing {self.plants_by_id[tile_plant_id]['name']} from ({x},{y}) to plant "
                      f"{self.plants_by_id[seed_id]['name']}.")
                self.exec_js(script=f"{self.farm_minigame}.harvest({x},{y});")
                self.get_plot_details()
                del self.occupied_tiles[x, y]
                if self.cpsMult > 1:
                    self.last_buffed_harvest = time.time()
        except KeyError:
            self.click_cookie()

        try:
            plant_data = self.occupied_tiles[x, y]
            tile_plant_id = plant_data['id']
            if tile_plant_id == seed_id:
                self.last_plant_time = time.time()
            else:
                print(f"{timestamp()}: {Fore.LIGHTMAGENTA_EX}Occupied tile {x, y} contains: {plant_data}. "
                      f"Unable to plant.{Style.RESET_ALL}")
        except KeyError:
            aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
            dragon_boost = 1 / (1 + 0.05 * aura_multi)

            try:
                print(f"{timestamp()}: {x, y} is empty. Planting {self.plants_by_id[seed_id]['name']}.")
                plant = self.plants_by_id[seed_id]['key']
                age = 0
                age_at_next_tick = (self.plants[plant]["ageTick"] +
                                    self.plants[plant]["ageTickR"] / 2) * self.plot_boost[y][x][0] * dragon_boost

                self.cast_spell(spell_to_cast="hand of fate", exhaust_magic=True)
                self.last_plant_time = time.time()
                self.exec_js(script=f"{self.farm_minigame}.useTool({seed_id}, {x}, {y});")

                self.get_plot_details()
                ticks_until_mature = self.plant_ticks_until_mature(plant=plant, dragon_boost=dragon_boost)
                self.occupied_tiles[x, y] = {"name": plant,
                                             "id": seed_id,
                                             "ticks_until_mature": ticks_until_mature,
                                             "maturity": age,
                                             "age_at_next_tick": age_at_next_tick}
                if self.cpsMult < 1:
                    self.last_debuffed_planting = time.time()
            except JavascriptException:
                self.click_cookie()

    def get_keenmoss_tiles(self):
        keenmoss_tiles = []
        for tile, seed in self.occupied_tiles.items():
            self.click_cookie()
            if seed["name"] == "keenmoss":
                keenmoss_tiles.append(tile)

        return keenmoss_tiles

    def max_mature_keenmoss_reached(self, tiles):
        aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
        dragon_boost = 1 / (1 + 0.05 * aura_multi)
        age_tick = self.plants["keenmoss"]["ageTick"]
        age_tick_r = self.plants["keenmoss"]["ageTickR"]
        min_ticks_until_mature = self.plant_ticks_until_mature(plant="keenmoss", dragon_boost=dragon_boost)
        min_ticks_until_decay = 100 / (age_tick + age_tick_r * 0.5)

        keenmoss_ticks_until_mature = []
        keenmoss_age = []
        keenmoss_details = []

        for tile in tiles:
            self.click_cookie()
            try:
                age = self.occupied_tiles[tile["x"], tile["y"]]['maturity']
            except KeyError:
                age = 0
            ticks_until_decay = (100 - age) / (age_tick + age_tick_r * 0.5)
            ticks_until_mature = self.plant_ticks_until_mature(plant="keenmoss", x=tile[0], y=tile[1], dragon_boost=dragon_boost)
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
        for tile, seed in self.occupied_tiles.items():
            self.click_cookie()
            if seed["name"] != "keenmoss":
                only_keenmoss_plants = False
                break

        if only_keenmoss_plants:  # and (self.cpsMult > 1 or
            # self.next_garden_tick - time.time() <= SECONDS_UNTIL_NEXT_TICK):
            print(f'{timestamp()}: Harvesting keenmoss field.')
            self.exec_js(script=f"{self.farm_minigame}.harvestAll();")
            self.get_plant_details(ignore_tick=True)
            if self.cpsMult > 1:
                self.last_buffed_harvest = time.time()

    def is_garden_empty(self):
        if not self.occupied_tiles:
            return True
        else:
            return False

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
                self.click_cookie()
                self.farm_size.append({"x": x, "y": y})

    def clean_garden(self, tiles):
        if self.last_garden_clean <= self.previous_garden_tick:
            brown_mold_and_crumbspore_unlocked_or_growing = self.is_seed_unlocked_or_growing("brownMold") and \
                                                            self.is_seed_unlocked_or_growing("crumbspore")
            delete = []
            for tile, plant in tiles.items():
                self.click_cookie()
                self.last_garden_clean = time.time()

                plant_name = plant['name']
                plant_id = self.plants[plant_name]["id"]
                plant_unlocked = self.plants[plant_name]["unlocked"]
                print(f'{timestamp()}: {Fore.LIGHTMAGENTA_EX}Found {plant_name} ({plant_id}) at {tile}. Unlocked: '
                      f'{plant_unlocked}. Ticks until mature: {plant["ticks_until_mature"]}.{Style.RESET_ALL}')

                if not brown_mold_and_crumbspore_unlocked_or_growing:
                    print(f'{timestamp()}: Brown Mold unlocked or growing: '
                          f'{self.is_seed_unlocked_or_growing("brownMold")}. Crumbspore unlocked or growing: '
                          f'{self.is_seed_unlocked_or_growing("crumbspore")}')
                if (plant_name == "meddleweed" and brown_mold_and_crumbspore_unlocked_or_growing) \
                        or (plant_name != "meddleweed" and plant_unlocked):
                    print(f'{timestamp()}: Harvesting plant {plant_name} ({plant_id}) in tile {tile}.')
                    self.exec_js(script=f"{self.farm_minigame}.harvest({tile[0]},{tile[1]});")
                    delete.append(tile)

            try:
                for i in delete:
                    self.click_cookie()
                    del self.occupied_tiles[i]
            except KeyError:
                self.click_cookie()

            self.get_plot_details()
            if self.cpsMult > 1:
                self.last_buffed_harvest = time.time()

    def stagger_planting(self, faster_group, faster_plant_id, slower_group, slower_plant_id,
                         faster_plant_ticks_to_mature):
        print(f'{timestamp()}: Faster plant ticks until mature: {faster_plant_ticks_to_mature}')

        self.last_plant_time = time.time()

        sg_oldest_age_at_next_tick = 0
        sg_oldest_tile = None
        tile_age_sum = 0
        ticks_until_mature_sum = 0
        planted_tiles = 0
        planted_immature_tiles = 0
        slowest_sg_age = 0
        aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
        dragon_boost = 1 / (1 + 0.05 * aura_multi)
        sg_min_ticks_until_mature = self.plant_ticks_until_mature(plant=self.plants_by_id[slower_plant_id]['key'], dragon_boost=dragon_boost)
        # Plant slower seeds first
        for tile in slower_group:
            self.click_cookie()
            try:
                plant_data = self.occupied_tiles[tile["x"], tile["y"]]
                tile_plant_id = plant_data['id']
            except KeyError:
                tile_plant_id = self.empty_tile_plant_id

            if tile_plant_id != slower_plant_id:
                print(f"{timestamp()}: Planting slower maturing plant: "
                      f"{self.plants_by_id[slower_plant_id]['name']} in tile {tile}.")
                self.plant_seed(x=tile["x"], y=tile["y"], seed_id=slower_plant_id)
            else:
                try:
                    tile_age_at_next_tick = self.occupied_tiles[tile["x"], tile["y"]]['age_at_next_tick']
                    tile_age_sum += self.occupied_tiles[tile["x"], tile["y"]]['age_at_next_tick']
                    sg_oldest_age_at_next_tick = max(sg_oldest_age_at_next_tick, tile_age_at_next_tick)
                    sg_oldest_tile = tile if sg_oldest_age_at_next_tick == tile_age_at_next_tick else sg_oldest_tile
                except KeyError:
                    self.click_cookie()

            try:
                plant_data = self.occupied_tiles[tile["x"], tile["y"]]
                tile_plant_id = plant_data['id']
            except KeyError:
                tile_plant_id = self.empty_tile_plant_id

            if tile_plant_id == slower_plant_id:
                ticks_until_mature_sum += self.occupied_tiles[tile["x"], tile["y"]]['ticks_until_mature']
                slowest_sg_age = max(slowest_sg_age,
                                     self.occupied_tiles[tile["x"], tile["y"]]['age_at_next_tick']
                                     if self.occupied_tiles[tile["x"], tile["y"]]['ticks_until_mature'] > 0
                                     else self.occupied_tiles[tile["x"], tile["y"]]['maturity'] + 1)
                planted_immature_tiles += 1 if self.occupied_tiles[tile["x"], tile["y"]][
                                                   'ticks_until_mature'] > 0 else 0
                planted_tiles += 1

        sg_avg_age_at_next_tick = tile_age_sum / planted_tiles if planted_tiles > 0 else 0
        if planted_tiles == 0:
            sg_avg_ticks_until_mature = self.plant_ticks_until_mature(plant=self.plants_by_id[slower_plant_id]['key'], dragon_boost=dragon_boost)
        else:
            if planted_immature_tiles == 0:
                sg_avg_ticks_until_mature = 0
            else:
                sg_avg_ticks_until_mature = ticks_until_mature_sum / planted_immature_tiles

        if sg_oldest_tile:
            sg_min_ticks_until_mature = self.plant_ticks_until_mature(plant=self.plants_by_id[slower_plant_id]['key'],
                                                                      x=sg_oldest_tile['x'], y=sg_oldest_tile['y'], dragon_boost=dragon_boost)
            print(f"{timestamp()}: Oldest {self.plants_by_id[slower_plant_id]['name']} at "
                  f"{sg_oldest_tile['x'], sg_oldest_tile['y']} will mature in {sg_min_ticks_until_mature} ticks. Avg "
                  f"ticks until mature: {sg_avg_ticks_until_mature}. Immature plants remaining: "
                  f"{planted_immature_tiles}.")

        if sg_avg_age_at_next_tick > self.plants_by_id[slower_plant_id]["mature"]:
            slower_plant_ticks_until_mature = 0
        else:
            slower_plant_ticks_until_mature = sg_avg_ticks_until_mature

        fg_oldest_age_at_next_tick = 0
        ticks_until_mature_sum = 0
        planted_tiles = 0
        planted_immature_tiles = 0
        fg_oldest_tile = None
        slowest_fg_age = 0
        fg_min_ticks_until_mature = self.plant_ticks_until_mature(plant=self.plants_by_id[faster_plant_id]['key'], dragon_boost=dragon_boost)
        if slower_plant_ticks_until_mature <= faster_plant_ticks_to_mature:
            if not sg_oldest_tile:
                print(f'{timestamp()}: Slower plant ticks until mature: {slower_plant_ticks_until_mature}')
            for tile in faster_group:
                self.click_cookie()
                try:
                    plant_data = self.occupied_tiles[tile["x"], tile["y"]]
                    tile_plant_id = plant_data['id']
                except KeyError:
                    tile_plant_id = self.empty_tile_plant_id

                if tile_plant_id != faster_plant_id:
                    print(f"{timestamp()}: Planting faster maturing plant: "
                          f"{self.plants_by_id[faster_plant_id]['name']} in tile {tile}.")
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=faster_plant_id)
                else:
                    try:
                        tile_age_at_next_tick = self.occupied_tiles[tile["x"], tile["y"]]['age_at_next_tick']
                        tile_age_sum += self.occupied_tiles[tile["x"], tile["y"]]['age_at_next_tick']
                        fg_oldest_age_at_next_tick = max(fg_oldest_age_at_next_tick, tile_age_at_next_tick)
                        fg_oldest_tile = tile if fg_oldest_age_at_next_tick == tile_age_at_next_tick else fg_oldest_tile
                    except KeyError:
                        self.click_cookie()

                try:
                    plant_data = self.occupied_tiles[tile["x"], tile["y"]]
                    tile_plant_id = plant_data['id']
                except KeyError:
                    tile_plant_id = self.empty_tile_plant_id

                if tile_plant_id == faster_plant_id:
                    ticks_until_mature_sum += self.occupied_tiles[tile["x"], tile["y"]]['ticks_until_mature']
                    slowest_fg_age = max(slowest_fg_age,
                                         self.occupied_tiles[tile["x"], tile["y"]]['age_at_next_tick']
                                         if self.occupied_tiles[tile["x"], tile["y"]]['ticks_until_mature'] > 0
                                         else self.occupied_tiles[tile["x"], tile["y"]]['maturity'] + 1)
                    planted_immature_tiles += 1 if self.occupied_tiles[tile["x"], tile["y"]][
                                                       'ticks_until_mature'] > 0 else 0
                    planted_tiles += 1

        if planted_tiles == 0:
            fg_avg_ticks_until_mature = self.plant_ticks_until_mature(plant=self.plants_by_id[faster_plant_id]['key'], dragon_boost=dragon_boost)
        else:
            if planted_immature_tiles == 0:
                fg_avg_ticks_until_mature = 0
            else:
                fg_avg_ticks_until_mature = ticks_until_mature_sum / planted_immature_tiles

        if fg_oldest_tile:
            fg_min_ticks_until_mature = self.plant_ticks_until_mature(plant=self.plants_by_id[faster_plant_id]['key'],
                                                                      x=fg_oldest_tile['x'], y=fg_oldest_tile['y'], dragon_boost=dragon_boost)
            print(f"{timestamp()}: Oldest {self.plants_by_id[faster_plant_id]['name']} at "
                  f"{fg_oldest_tile['x'], fg_oldest_tile['y']} will mature in {fg_min_ticks_until_mature} ticks. Avg "
                  f"ticks until mature: {fg_avg_ticks_until_mature}. Immature plants remaining "
                  f"{planted_immature_tiles}.")

        if self.plants_by_id[faster_plant_id]['key'] == 'tidygrass' and \
                self.plants_by_id[slower_plant_id]['key'] == 'elderwort':
            sg_comparison_ticks = sg_avg_ticks_until_mature
            fg_comparison_ticks = fg_avg_ticks_until_mature
        else:
            sg_comparison_ticks = sg_min_ticks_until_mature
            fg_comparison_ticks = fg_min_ticks_until_mature

        if sg_comparison_ticks <= 1 and fg_comparison_ticks <= 1:
            self.desired_soil = "woodchips"
        else:
            self.desired_soil = "fertilizer"

    def mutation_setups(self):
        self.same_plant_setup = type_1 = type_2 = []
        if self.farm_level == 1:
            # One plant configuration
            for x in [2, 3]:
                self.same_plant_setup.append({"x": x, "y": 2})
            # Two plant configuration
            type_1.append({"x": 3, "y": 2})
            type_2.append({"x": 2, "y": 2})
        elif self.farm_level == 2:
            # One plant configuration
            for y in [2, 3]:
                self.same_plant_setup.append({"x": 3, "y": y})
            # Two plant configuration
            type_1.append({"x": 3, "y": 2})
            type_2.append({"x": 3, "y": 3})
        elif self.farm_level == 3:
            # One plant configuration
            for x in range(2, 5):
                self.same_plant_setup.append({"x": x, "y": 3})
            # Two plant configuration
            type_1.append({"x": 2, "y": 3})
            type_1.append({"x": 4, "y": 3})
            type_2.append({"x": 3, "y": 3})
        elif self.farm_level == 4:
            # One plant configuration
            for x in range(1, 5):
                self.same_plant_setup.append({"x": x, "y": 3})
            # Two plant configuration
            type_1.append({"x": 2, "y": 3})
            type_1.append({"x": 3, "y": 3})
            type_2.append({"x": 1, "y": 3})
            type_2.append({"x": 4, "y": 3})
        elif self.farm_level == 5:
            # One plant configuration
            for x in [1, 4]:
                for y in [1, 4]:
                    self.same_plant_setup.append({"x": x, "y": y})
            self.same_plant_setup.append({"x": 3, "y": 2})
            self.same_plant_setup.append({"x": 2, "y": 3})
            # Two plant configuration
            type_1.append({"x": 2, "y": 2})
            type_1.append({"x": 3, "y": 3})
            for x in [1, 4]:
                for y in [1, 4]:
                    type_2.append({"x": x, "y": y})
        elif self.farm_level == 6:
            # One plant configuration
            for x in range(1, 6):
                for y in [1, 3]:
                    if (x, y) not in [(2, 1), (4, 1), (3, 3)]:
                        self.same_plant_setup.append({"x": x, "y": y})
            # Two plant configuration
            type_1.append({"x": 2, "y": 3})
            type_1.append({"x": 3, "y": 1})
            type_1.append({"x": 5, "y": 3})
            type_2.append({"x": 1, "y": 1})
            type_2.append({"x": 1, "y": 4})
            type_2.append({"x": 4, "y": 3})
            type_2.append({"x": 5, "y": 1})
        elif self.farm_level == 7:
            # One plant configuration
            for x in [1, 2, 4, 5]:
                for y in [1, 4]:
                    self.same_plant_setup.append({"x": x, "y": y})
            # Two plant configuration
            for x in [2, 5]:
                for y in [1, 4]:
                    type_1.append({"x": x, "y": y})
            for x in [1, 4]:
                for y in [1, 4]:
                    type_2.append({"x": x, "y": y})
        elif self.farm_level == 8:
            # One plant configuration
            for y in [1, 2, 4, 5]:
                for x in [1, 4]:
                    self.same_plant_setup.append({"x": x, "y": y})
            # Two plant configuration
            for x in [1, 4]:
                for y in [1, 4]:
                    type_1.append({"x": x, "y": y})
            for x in [1, 4]:
                for y in [2, 5]:
                    type_2.append({"x": x, "y": y})
        elif self.farm_level >= 9:
            # One plant configuration
            for y in [1, 4]:
                for x in range(6):
                    self.click_cookie()
                    if x != 2:
                        self.same_plant_setup.append({"x": x, "y": y})
            # Two plant configuration
            for y in [1, 4]:
                for x in [0, 5]:
                    self.click_cookie()
                    type_1.append({"x": x, "y": y})
            type_1.append({"x": 2, "y": 1})
            type_1.append({"x": 3, "y": 4})

            for x in [1, 4]:
                for y in [1, 4]:
                    self.click_cookie()
                    type_2.append({"x": x, "y": y})
        else:
            return

        self.two_plant_setup = {"G": type_1, "Y": type_2}

    def unlock_seeds(self):
        if not self.exec_js(script='return Game.isMinigameReady(Game.Objects["Farm"]);'):
            return

        self.mutation_setups()

        if self.max_plants <= self.num_plants_unlocked:
            return

        if self.is_seed_unlocked_or_growing('queenbeetLump') and self.dragon_complete:
            self.set_dragon_auras(dragon_aura=self.final_wanted_aura)

        growing_seeds = {plant: self.plants[plant]["ticks_until_mature"]
                         for plant in self.plants
                         if not self.plants[plant]['unlocked'] and self.plants[plant]['growing']}
        parent_seeds_to_unlock = []
        seed_processed = False
        aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
        dragon_boost = 1 / (1 + 0.05 * aura_multi)

        for seed, parent in self.unlock_seed_od.items():
            self.click_cookie()
            cleaned_garden_this_cycle = self.last_garden_clean > self.previous_garden_tick
            harvested_this_cycle = self.last_harvest_check > self.previous_garden_tick
            planted_this_cycle = self.last_plant_time > self.previous_garden_tick

            if not self.is_seed_unlocked_or_growing(seed):
                num_parents = len(parent)
                if num_parents == 1:
                    oldest_seed = 1
                    parent_seed = parent[0]
                    parent_seed_id = self.plants[parent_seed]["id"]
                    if not self.plants_by_id[parent_seed_id]["unlocked"]:
                        print(f"{timestamp()}: {Fore.BLUE}{seed}'s parent is not unlocked. "
                              f"Waiting to unlock {parent_seed}.{Style.RESET_ALL}")
                        self.click_cookie()
                        if parent_seed not in parent_seeds_to_unlock:
                            parent_seeds_to_unlock.append(parent_seed)
                        continue

                    parent_seed_maturity = self.plants[parent_seed]["mature"]

                    parent_tiles = [plant['ticks_until_mature'] for (tile, plant) in self.occupied_tiles.items()
                                    if {'x': tile[0], 'y': tile[1]} in self.same_plant_setup
                                    and plant['name'] == parent_seed]

                    parent_ticks_until_mature = self.plant_ticks_until_mature(plant=parent_seed, dragon_boost=dragon_boost) if len(
                        parent_tiles) == 0 \
                        else sum(parent_tiles) / len(parent_tiles)

                    parent_dict = {p_seed: growing_seeds[p_seed]
                                   for p_seed in parent_seeds_to_unlock
                                   if p_seed in growing_seeds}

                    try:
                        growing_seed_min_ticks = min(parent_dict.values())
                    except ValueError:
                        growing_seed_min_ticks = float('inf')

                    if parent_ticks_until_mature > growing_seed_min_ticks and \
                            self.num_locked_plants_growing + self.num_plants_unlocked != self.max_plants - 1 and \
                            (not self.plants['meddleweed']['growing'] or self.plants['meddleweed']['unlocked']):
                        print(f'{timestamp()}: {Fore.MAGENTA}Skipping {seed} because other seeds will mature before '
                              f'{parent_seed}.{Style.RESET_ALL}')
                        clean_tiles = {tile: plant for (tile, plant) in self.occupied_tiles.items()
                                       if {'x': tile[0], 'y': tile[1]} not in self.same_plant_setup
                                       and {'x': tile[0], 'y': tile[1]} not in self.two_plant_setup["G"]
                                       and {'x': tile[0], 'y': tile[1]} not in self.two_plant_setup["Y"]}
                        self.clean_garden(tiles=clean_tiles)
                        self.click_cookie()
                        continue

                    print(f'{timestamp()}: {Fore.GREEN}Attempting to unlock {seed}. '
                          f'This cycle: Cleaned? {cleaned_garden_this_cycle}; Harvested? {harvested_this_cycle}; '
                          f'Planted? {planted_this_cycle}{Style.RESET_ALL}')

                    sum_seed_age_next_tick = num_parent_seeds = 0

                    if parent_seed == "meddleweed":
                        beginning_pattern = [tile for (tile, plant) in self.occupied_tiles.items()
                                             if plant['name'] not in {'meddleweed', 'crumbspore', 'brownMold'}]
                        exclude_pattern = []
                        for tile in beginning_pattern:
                            exclude_pattern.append({'x': tile[0], 'y': tile[1]})
                            exclude_pattern.append({'x': tile[0] - 1, 'y': tile[1]})
                            exclude_pattern.append({'x': tile[0] + 1, 'y': tile[1]})
                            exclude_pattern.append({'x': tile[0], 'y': tile[1] - 1})
                            exclude_pattern.append({'x': tile[0], 'y': tile[1] + 1})

                        planting_pattern = [tile for tile in self.farm_size
                                            if tile not in exclude_pattern]

                    else:
                        planting_pattern = self.same_plant_setup

                    for tile in planting_pattern:
                        self.click_cookie()
                        self.plant_seed(x=tile["x"], y=tile["y"], seed_id=parent_seed_id)
                        try:
                            plant_data = self.occupied_tiles[tile['x'], tile['y']]
                            if plant_data['id'] == parent_seed_id:
                                sum_seed_age_next_tick += plant_data['age_at_next_tick']
                                num_parent_seeds += 1
                                oldest_seed = max(oldest_seed, plant_data['maturity'])
                        except KeyError:
                            self.click_cookie()

                    parent_tiles = [plant['ticks_until_mature'] for (tile, plant) in self.occupied_tiles.items()
                                    if {'x': tile[0], 'y': tile[1]} in self.same_plant_setup
                                    and plant['name'] == parent_seed]

                    parent_ticks_until_mature = self.plant_ticks_until_mature(plant=parent_seed, dragon_boost=dragon_boost) if len(
                        parent_tiles) == 0 \
                        else sum(parent_tiles) / len(parent_tiles)

                    print(f"{timestamp()}: {parent_seed} average ticks until mature: {parent_ticks_until_mature}.")

                    avg_seed_age = 0 if num_parent_seeds == 0 else sum_seed_age_next_tick / num_parent_seeds

                    clean_tiles = {tile: plant for (tile, plant) in self.occupied_tiles.items()
                                   if {'x': tile[0], 'y': tile[1]} not in planting_pattern}
                    if clean_tiles:
                        self.clean_garden(tiles=clean_tiles)
                    elif self.cpsMult > 1:
                        self.last_buffed_harvest = time.time()

                    if avg_seed_age >= parent_seed_maturity and parent_seed != "meddleweed" and \
                            seed != "meddleweed":
                        self.desired_soil = "woodchips"
                    else:
                        self.desired_soil = "fertilizer"
                    seed_processed = True
                elif num_parents == 2:
                    parent1_seed = parent[0]
                    parent2_seed = parent[1]

                    if not (self.plants[parent1_seed]["unlocked"] and self.plants[parent2_seed]["unlocked"]):
                        locked_parents = ' & '.join([p for p in parent if not self.plants[p]['unlocked']])
                        print(f"{timestamp()}: {Fore.BLUE}{seed}'s parent(s) are not unlocked. "
                              f"Waiting to unlock {locked_parents}.{Style.RESET_ALL}")
                        if not self.plants[parent1_seed]["unlocked"] and parent1_seed not in parent_seeds_to_unlock:
                            parent_seeds_to_unlock.append(parent1_seed)
                        if not self.plants[parent2_seed]["unlocked"] and parent2_seed not in parent_seeds_to_unlock:
                            parent_seeds_to_unlock.append(parent2_seed)
                        self.click_cookie()
                        continue
                    parent1_seed_id = self.plants[parent1_seed]["id"]
                    parent1_ticks_until_mature = self.plant_ticks_until_mature(plant=parent1_seed, dragon_boost=dragon_boost)
                    parent2_seed_id = self.plants[parent2_seed]["id"]
                    parent2_ticks_until_mature = self.plant_ticks_until_mature(plant=parent2_seed, dragon_boost=dragon_boost)
                    maturity_difference = parent1_ticks_until_mature - parent2_ticks_until_mature

                    parent1_tiles = [plant['ticks_until_mature'] for (tile, plant) in self.occupied_tiles.items()
                                     if {'x': tile[0], 'y': tile[1]} in self.two_plant_setup["G"]
                                     and plant['name'] == parent1_seed]

                    parent1_ticks_left = parent1_ticks_until_mature if len(parent1_tiles) == 0 \
                        else sum(parent1_tiles) / len(parent1_tiles)

                    parent2_tiles = [plant['ticks_until_mature'] for (tile, plant) in self.occupied_tiles.items()
                                     if {'x': tile[0], 'y': tile[1]} in self.two_plant_setup["Y"]
                                     and plant['name'] == parent2_seed]

                    parent2_ticks_left = parent2_ticks_until_mature if len(parent2_tiles) == 0 \
                        else sum(parent2_tiles) / len(parent2_tiles)

                    max_parent_ticks_until_mature = max(parent1_ticks_left, parent2_ticks_left)

                    parent_dict = {p_seed: growing_seeds[p_seed]
                                   for p_seed in parent_seeds_to_unlock
                                   if p_seed in growing_seeds}

                    try:
                        growing_seed_min_ticks = min(parent_dict.values())
                    except ValueError:
                        growing_seed_min_ticks = float('inf')

                    if max_parent_ticks_until_mature > growing_seed_min_ticks and \
                            self.num_locked_plants_growing + self.num_plants_unlocked != self.max_plants - 1:
                        print(f'{timestamp()}: {Fore.MAGENTA}Skipping {seed} because other seeds will mature before '
                              f'{parent1_seed} and {parent2_seed}.{Style.RESET_ALL}')
                        clean_tiles = {tile: plant for (tile, plant) in self.occupied_tiles.items()
                                       if {'x': tile[0], 'y': tile[1]} not in self.same_plant_setup
                                       and {'x': tile[0], 'y': tile[1]} not in self.two_plant_setup["G"]
                                       and {'x': tile[0], 'y': tile[1]} not in self.two_plant_setup["Y"]}
                        self.clean_garden(tiles=clean_tiles)
                        self.click_cookie()
                        continue

                    print(f'{timestamp()}: {Fore.GREEN}Attempting to unlock {seed}. '
                          f'This cycle: Cleaned? {cleaned_garden_this_cycle}; Harvested? {harvested_this_cycle}; '
                          f'Planted? {planted_this_cycle}{Style.RESET_ALL}')

                    clean_tiles = {tile: plant for (tile, plant) in self.occupied_tiles.items()
                                   if {'x': tile[0], 'y': tile[1]} not in self.two_plant_setup["G"]
                                   and {'x': tile[0], 'y': tile[1]} not in self.two_plant_setup["Y"]}

                    if clean_tiles:
                        self.clean_garden(tiles=clean_tiles)
                    elif self.cpsMult > 1:
                        self.last_buffed_harvest = time.time()

                    if maturity_difference < 0:
                        self.stagger_planting(faster_group=self.two_plant_setup["G"], faster_plant_id=parent1_seed_id,
                                              slower_group=self.two_plant_setup["Y"], slower_plant_id=parent2_seed_id,
                                              faster_plant_ticks_to_mature=parent1_ticks_until_mature)
                    else:
                        self.stagger_planting(faster_group=self.two_plant_setup["Y"], faster_plant_id=parent2_seed_id,
                                              slower_group=self.two_plant_setup["G"], slower_plant_id=parent1_seed_id,
                                              faster_plant_ticks_to_mature=parent2_ticks_until_mature)

                    seed_processed = True
                elif seed == "queenbeetLump":
                    if self.farm_level < 3:
                        print(f"{timestamp()}: Farm level is not high enough to try for JQB.")
                        continue
                    if not self.plants["queenbeet"]["unlocked"]:
                        parent_seeds_to_unlock.append('queenbeet')
                        print(f"{timestamp()}: {Fore.BLUE}queenbeetLumps parent is not unlocked. "
                              f"Waiting to unlock queenbeet.{Style.RESET_ALL}")
                        self.click_cookie()
                        continue
                    print(f'{timestamp()}: {Fore.GREEN}Attempting to unlock {seed}. '
                          f'This cycle: Cleaned? {cleaned_garden_this_cycle}; Harvested? {harvested_this_cycle}; '
                          f'Planted? {planted_this_cycle}{Style.RESET_ALL}')

                    self.try_for_juicy_queenbeet()
                    seed_processed = True
                elif seed == "meddleweed":
                    print(f'{timestamp()}: {Fore.GREEN}Attempting to unlock {seed}. '
                          f'This cycle: Cleaned? {cleaned_garden_this_cycle}; Harvested? {harvested_this_cycle}; '
                          f'Planted? {planted_this_cycle}{Style.RESET_ALL}')

                    self.desired_soil = "fertilizer"
                    self.clean_garden(tiles=self.occupied_tiles)
                    seed_processed = True
                elif seed == "everdaisy":
                    if self.farm_level < 3:
                        print(f"{timestamp()}: Farm level is not high enough to try for Everdaisy.")
                        continue
                    elif self.farm_level < 7 and self.plants["queenbeetLump"]["growing"]:
                        print(f"{timestamp()}: Unable to get Everdaisy while JQB growing with farm level < 7.")
                        continue
                    parents = ['elderwort', 'tidygrass']
                    if not (self.plants["elderwort"]["unlocked"] and self.plants["tidygrass"]["unlocked"]):
                        locked_parents = ' & '.join([parent for parent in parents
                                                     if not self.plants[parent]['unlocked']])
                        print(f"{timestamp()}: {Fore.BLUE}{seed}'s parent(s) are not unlocked. "
                              f"Waiting to unlock {locked_parents}.{Style.RESET_ALL}")
                        if not self.plants["elderwort"]["unlocked"] and "elderwort" not in parent_seeds_to_unlock:
                            parent_seeds_to_unlock.append("elderwort")
                        if not self.plants["tidygrass"]["unlocked"] and "tidygrass" not in parent_seeds_to_unlock:
                            parent_seeds_to_unlock.append("tidygrass")
                        self.click_cookie()
                        continue
                    print(f'{timestamp()}: {Fore.GREEN}Attempting to unlock {seed}. '
                          f'This cycle: Cleaned? {cleaned_garden_this_cycle}; Harvested? {harvested_this_cycle}; '
                          f'Planted? {planted_this_cycle}{Style.RESET_ALL}')

                    self.try_for_everdaisy()
                    seed_processed = True
                elif seed == "shriekbulb":
                    if not self.plants["duketater"]["unlocked"]:
                        parent_seeds_to_unlock.append('duketater')
                        print(f"{timestamp()}: {Fore.BLUE}shriekbulb's parent is not unlocked. "
                              f"Waiting to unlock duketater.{Style.RESET_ALL}")
                        self.click_cookie()
                        continue
                    print(f'{timestamp()}: {Fore.GREEN}Attempting to unlock {seed}. '
                          f'This cycle: Cleaned? {cleaned_garden_this_cycle}; Harvested? {harvested_this_cycle}; '
                          f'Planted? {planted_this_cycle}{Style.RESET_ALL}')

                    self.try_for_shriekbulbs()
                    seed_processed = True
                break
            else:
                self.click_cookie()
                continue

        self.attempt_to_unlock_seeds = False

        if not seed_processed:
            self.desired_soil = "fertilizer"
            if (self.num_locked_plants_growing + self.num_plants_unlocked) != self.max_plants:
                self.clean_garden(tiles=self.occupied_tiles)
                if self.cpsMult > 1:
                    self.last_buffed_harvest = time.time()
                elif self.cpsMult < 1:
                    self.last_debuffed_planting = time.time()
                print(f"{timestamp()}: {Fore.LIGHTBLUE_EX}Unable to try for another seed. "
                      f"Cleaning garden and switching to fertilizer.{Style.RESET_ALL}")

        if (self.num_locked_plants_growing + self.num_plants_unlocked) == self.max_plants:
            self.desired_soil = "fertilizer"
            print(f"{timestamp()}: All seeds either unlocked or growing. Switching to fertilizer.")

    def is_seed_unlocked_or_growing(self, seed):
        if self.plants[seed]["unlocked"] or self.plants[seed]["growing"]:
            return True
        return False

    def sacrifice_garden(self):
        if self.farming_goal == 'lumps' and self.all_garden_drops_unlocked and \
                self.num_plants_unlocked == self.max_plants:
            self.save_game(path=self.save_file)
            self.exec_js(script=f"{self.farm_minigame}.harvestAll();")
            if self.cpsMult > 1:
                self.last_buffed_harvest = time.time()

            previous_lumps = self.exec_js(script='return Game.lumps;', default_return=0)
            if previous_lumps is None:
                previous_lumps = float('inf')
            self.exec_js(script=f"{self.farm_minigame}.askConvert();Game.ConfirmPrompt();")
            self.check_and_level_up(previous_lumps)
            for plant in self.plants:
                try:
                    remove(f"./{plant}.txt")
                    remove(f"./{plant}_unlocked.txt")
                except FileNotFoundError:
                    self.click_cookie()
            self.get_plant_details(ignore_tick=True)

    def increase_golden_cookie_frequency(self):
        if not (self.all_garden_drops_unlocked and (self.num_plants_unlocked +
                                                    self.num_locked_plants_growing) == self.max_plants):
            return

        result = self.exec_js(script=f"""
            return {{
                gcCost: {self.farm_minigame}.plants["goldenClover"].cost,
                ntCost: {self.farm_minigame}.plants["nursetulip"].cost,
                cookies: Game.cookies,
                cps: Game.cookiesPs,
                auraMult: Game.auraMult('Supreme Intellect')
            }};
        """, default_return={
            'gcCost': float('inf'),
            'ntCost': float('inf'),
            'cookies': 0,
            'cps': 0,
            'auraMult': 0
        })

        gc_cost = result['gcCost']
        nt_cost = result['ntCost']
        cookies = result['cookies']
        cps = result['cps']
        if cps is None:
            print(f"{timestamp()}: CPS is NoneType. Returning.")
            return
        dragon_boost = 1 / (1 + 0.05 * result['auraMult'])

        if (gc_cost + nt_cost) * 18 * 60 * cps > cookies:
            return

        nursetulip_layout = []
        golden_clover_layout = []
        for y in range(6):
            for x in range(6):
                self.click_cookie()
                if y in [0, 2, 4]:
                    nursetulip_layout.append({"x": x, "y": y})
                else:
                    golden_clover_layout.append({"x": x, "y": y})

        two_plant_setup = {"GC": golden_clover_layout, "NT": nursetulip_layout}
        # Plant
        if self.cpsMult <= 1:
            gc_id = self.plants['goldenClover']['id']
            nt_id = self.plants['nursetulip']['id']
            clean_tiles = {tile: plant for tile, plant in self.occupied_tiles.items()
                           if plant['name'] not in ['goldenClover', 'nursetulip'] and
                           self.plants[plant['name']]['unlocked']}
            self.clean_garden(tiles=clean_tiles)

            self.last_plant_time = time.time()

            # Plant nursetulips
            for tile in two_plant_setup['NT']:
                self.click_cookie()
                try:
                    plant_data = self.occupied_tiles[tile["x"], tile["y"]]
                    tile_plant_id = plant_data['id']
                except KeyError:
                    tile_plant_id = self.empty_tile_plant_id

                if tile_plant_id != nt_id:
                    print(f"{timestamp()}: Planting slower maturing plant: "
                          f"{self.plants_by_id[nt_id]['name']} in tile {tile}.")
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=nt_id)

            # Plant golden clovers
            for tile in two_plant_setup['GC']:
                self.click_cookie()
                try:
                    plant_data = self.occupied_tiles[tile["x"], tile["y"]]
                    tile_plant_id = plant_data['id']
                except KeyError:
                    tile_plant_id = self.empty_tile_plant_id

                if tile_plant_id != gc_id:
                    print(f"{timestamp()}: Planting faster maturing plant: "
                          f"{self.plants_by_id[gc_id]['name']} in tile {tile}.")
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=gc_id)

        gc_min_ticks_until_mature = min([plant['ticks_until_mature'] for tile, plant in self.occupied_tiles.items()
                                         if plant['name'] == 'goldenClover'],
                                        default=self.plant_ticks_until_mature('goldenClover', dragon_boost=dragon_boost))

        if gc_min_ticks_until_mature <= 1:
            self.desired_soil = "clay"
        else:
            self.desired_soil = "fertilizer"

    def garden_maintenance(self, plant_name):
        if self.all_garden_drops_unlocked and (self.num_plants_unlocked +
                                               self.num_locked_plants_growing) == self.max_plants:
            aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
            dragon_boost = 1 / (1 + 0.05 * aura_multi)
            # Don't exclude target plant in attempt to mature all plants at once.
            max_plant_ticks_until_mature = max([plant['ticks_until_mature']
                                                for tile, plant in self.occupied_tiles.items()], default=0)
            goal_plant_ticks_until_mature = self.plant_ticks_until_mature(plant=plant_name, dragon_boost=dragon_boost)

            plant_id = self.plants[plant_name]["id"]
            self.desired_soil = "fertilizer"

            if self.cpsMult <= 1 and goal_plant_ticks_until_mature <= max_plant_ticks_until_mature:
                clean_tiles = {tile: plant for tile, plant in self.occupied_tiles.items()
                               if plant['name'] != plant_name and self.plants[plant['name']]['unlocked']}
                self.clean_garden(tiles=clean_tiles)
                for tile in self.farm_size:
                    self.click_cookie()
                    try:
                        self.occupied_tiles[tile['x'], tile['y']]
                    except KeyError:
                        print(f"{timestamp()}: Attempting garden maintenance while final seeds unlock. "
                              f"Planting {plant_name}.")
                        self.plant_seed(x=tile["x"], y=tile["y"], seed_id=plant_id)

            if self.cpsMult > self.cps_threshold:
                desired_plants_min_age = min([plant['maturity'] for tile, plant in self.occupied_tiles.items()
                                              if plant['name'] == plant_name], default=0)
                desired_plants_max_age = max([plant['maturity'] for tile, plant in self.occupied_tiles.items()
                                              if plant['name'] == plant_name], default=0)
                if desired_plants_min_age >= self.plants[plant_name]["mature"] or (
                        self.cpsMult > 665 and desired_plants_max_age >= self.plants[plant_name]["mature"]):
                    self.desired_soil = "clay"
                    self.switch_soil()
                    self.exec_js(script=f"{self.farm_minigame}.harvestAll({self.farm_minigame}."
                                        f"plants['{plant_name}'], 1, 1);")
                    print(f"{timestamp()}: Attempting garden maintenance while final seeds unlock. "
                          f"Harvesting {plant_name} because cps is {self.cpsMult}.")
                    self.get_plant_details(ignore_tick=True)
                    self.last_buffed_harvest = time.time()
                    self.desired_soil = "fertilizer"

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

        if self.max_plants > self.num_plants_unlocked + self.num_locked_plants_growing:
            return

        def strategy_1(upgrade):
            garden_upgrade_seed_id = self.plants[upgrade["seed"]]["id"]
            plant = self.plants[upgrade["seed"]]
            obtain_upgrade = plant["unlocked"]
            if obtain_upgrade:
                for tile in self.farm_size:
                    self.click_cookie()
                    self.harvest_mature_plants(x=tile['x'], y=tile['y'])
                    can_plant_js = f'{self.farm_minigame}.canPlant({self.farm_minigame}.plants["{next_drop["seed"]}"]);'
                    can_plant = self.exec_js(script=f"return {can_plant_js}", default_return=False)

                    if can_plant:
                        self.plant_seed(x=tile['x'], y=tile['y'], seed_id=garden_upgrade_seed_id)

        def strategy_3(upgrade):
            self.harvest_keenmoss_field()
            if self.is_garden_empty():
                for tile in self.farm_size:
                    self.click_cookie()
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=self.plants[upgrade["seed"]]["id"])
            else:
                # Harvest mature target plants
                self.exec_js(script=f"{self.farm_minigame}.harvestAll({self.farm_minigame}."
                                    f"plants['{upgrade['seed']}'], 1, 1);")
                if self.cpsMult > 1:
                    self.last_buffed_harvest = time.time()
                self.get_plant_details(ignore_tick=True)

                for tile in self.farm_size:
                    self.click_cookie()
                    try:
                        plant_data = self.occupied_tiles[tile['x'], tile['y']]
                        if plant_data['id'] not in [self.plants["keenmoss"]["id"], self.plants[upgrade["seed"]]["id"]]:
                            self.exec_js(script=f"{self.farm_minigame}.harvest({tile['x']},{tile['y']})")
                            self.get_plot_details()
                            del self.occupied_tiles[tile]
                            if self.cpsMult > 1:
                                self.last_buffed_harvest = time.time()
                    except KeyError:
                        self.click_cookie()
                    try:
                        self.occupied_tiles[tile['x'], tile['y']]
                    except KeyError:
                        self.plant_seed(x=tile["x"], y=tile["y"], seed_id=self.plants["keenmoss"]["id"])

        def strategy_4(upgrade):
            aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
            dragon_boost = 1 / (1 + 0.05 * aura_multi)
            garden_upgrade_seed_id = self.plants[upgrade["seed"]]["id"]
            self.harvest_keenmoss_field()
            keenmoss_tiles = self.get_keenmoss_tiles()
            empty_tiles = []
            keenmoss_ticks_to_mature = self.plant_ticks_until_mature(plant='keenmoss', dragon_boost=dragon_boost)
            sg_oldest_age_at_next_tick = 0

            if keenmoss_tiles and self.max_mature_keenmoss_reached(keenmoss_tiles):
                # Harvest mature target plants
                self.exec_js(script=f"{self.farm_minigame}.harvestAll({self.farm_minigame}."
                                    f"plants['{upgrade['seed']}'], 1, 1);")
                if self.cpsMult > 1:
                    self.last_buffed_harvest = time.time()
                self.get_plant_details(ignore_tick=True)

                for tile in self.farm_size:
                    self.click_cookie()
                    try:
                        plant_data = self.occupied_tiles[tile['x'], tile['y']]
                        if plant_data['id'] == garden_upgrade_seed_id:
                            sg_oldest_age_at_next_tick = max(sg_oldest_age_at_next_tick,
                                                             plant_data['age_at_next_tick'])
                        elif plant_data['id'] != self.plants["keenmoss"]["id"]:
                            self.exec_js(script=f"{self.farm_minigame}.harvest({tile['x']},{tile['y']})")
                            self.get_plot_details()
                            del self.occupied_tiles[tile['x'], tile['y']]
                            if self.cpsMult > 1:
                                self.last_buffed_harvest = time.time()
                    except KeyError:
                        self.click_cookie()

                    # Replant Keenmoss if tile is now empty
                    try:
                        self.occupied_tiles[tile['x'], tile['y']]
                    except KeyError:
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
                        self.click_cookie()
                        self.plant_seed(x=tile["x"], y=tile["y"], seed_id=self.plants["keenmoss"]["id"])
            elif self.is_garden_empty():
                for tile in self.farm_size:
                    self.click_cookie()
                    self.plant_seed(x=tile["x"], y=tile["y"], seed_id=garden_upgrade_seed_id)
            else:
                if not keenmoss_tiles:
                    self.exec_js(script=f"{self.farm_minigame}.harvestAll({self.farm_minigame}."
                                        f"plants['{upgrade['seed']}'], 1, 1);")
                    self.get_plant_details(ignore_tick=True)
                    if self.cpsMult > 1:
                        self.last_buffed_harvest = time.time()

                for tile in self.farm_size:
                    self.click_cookie()
                    try:
                        plant_data = self.occupied_tiles[tile['x'], tile['y']]
                        if plant_data['id'] not in [garden_upgrade_seed_id, self.plants["keenmoss"]["id"]]:
                            self.exec_js(script=f"{self.farm_minigame}.harvest({tile['x']},{tile['y']});")
                            self.get_plot_details()
                            del self.occupied_tiles[tile['x'], tile['y']]
                            if self.cpsMult > 1:
                                self.last_buffed_harvest = time.time()

                        elif plant_data['id'] == garden_upgrade_seed_id:
                            sg_oldest_age_at_next_tick = max(sg_oldest_age_at_next_tick, plant_data['age_at_next_tick'])
                    except KeyError:
                        self.click_cookie()

                    try:
                        self.occupied_tiles[tile['x'], tile['y']]
                    except KeyError:
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
                        self.click_cookie()
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
                    self.click_cookie()
                    ichorpuff_tiles.append({"x": x, "y": 1})
            else:
                for x in range(1, 5):
                    self.click_cookie()
                    keenmoss_tiles.append({"x": x, "y": 1})
                for x in range(6):
                    self.click_cookie()
                    ichorpuff_tiles.append({"x": x, "y": 0})
                ichorpuff_tiles.append({"x": 2, "y": 2})
                ichorpuff_tiles.append({"x": 3, "y": 2})

            for keenmoss_tile in keenmoss_tiles:
                self.click_cookie()
                self.harvest_mature_plants(x=keenmoss_tile["x"], y=keenmoss_tile["y"])
                try:
                    plant_data = self.occupied_tiles[keenmoss_tile["x"], keenmoss_tile["y"]]
                    plant_id = plant_data['id']
                    if plant_id != self.plants["keenmoss"]["id"] and self.plants_by_id[plant_id]['unlocked']:
                        self.exec_js(script=f"{self.farm_minigame}.harvest({keenmoss_tile['x']}, {keenmoss_tile['y']})")
                        del self.occupied_tiles[keenmoss_tile['x'], keenmoss_tile['y']]
                        if self.cpsMult > 1:
                            self.last_buffed_harvest = time.time()
                except KeyError:
                    self.click_cookie()

                try:
                    self.occupied_tiles[keenmoss_tile["x"], keenmoss_tile["y"]]
                except KeyError:
                    self.click_cookie()
                    self.plant_seed(x=keenmoss_tile["x"], y=keenmoss_tile["y"], seed_id=self.plants["keenmoss"]["id"])

            for ichorpuff_tile in ichorpuff_tiles:
                self.click_cookie()
                self.harvest_mature_plants(x=ichorpuff_tile["x"], y=ichorpuff_tile["y"])
                try:
                    plant_data = self.occupied_tiles[ichorpuff_tile["x"], ichorpuff_tile["y"]]
                    plant_id = plant_data['id']
                    if plant_id != self.plants["ichorpuff"]["id"] and self.plants_by_id[plant_id]['unlocked']:
                        self.exec_js(script=f"{self.farm_minigame}.harvest("
                                            f"{ichorpuff_tile['x']}, {ichorpuff_tile['y']});")
                        del self.occupied_tiles[ichorpuff_tile['x'], ichorpuff_tile['y']]
                        if self.cpsMult > 1:
                            self.last_buffed_harvest = time.time()
                except KeyError:
                    self.click_cookie()

                try:
                    self.occupied_tiles[ichorpuff_tile["x"], ichorpuff_tile["y"]]
                except KeyError:
                    self.click_cookie()
                    self.plant_seed(x=ichorpuff_tile["x"], y=ichorpuff_tile["y"],
                                    seed_id=self.plants["ichorpuff"]["id"])

        upgrade_unlocked = True
        next_drop = None
        if not self.all_garden_drops_unlocked:
            for drop in garden_upgrades:
                self.click_cookie()
                if not self.is_upgrade_unlocked(drop["upgrade"]) and self.plants[drop["seed"]]["unlocked"]:
                    upgrade_unlocked = False
                    next_drop = drop
                    break
            self.all_garden_drops_unlocked = upgrade_unlocked
            if self.all_garden_drops_unlocked and time.time() - self.delay_aura_change > 15:
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

        if not self.all_garden_drops_unlocked:
            wanted_aura = self.dragon_auras_lookup["Mind Over Matter"]["id"]
        else:
            wanted_aura = self.final_wanted_aura
            # wanted_aura2 = 18  # reality bending

        if self.dragon_complete:
            self.set_dragon_auras(dragon_aura=wanted_aura)

    def get_farm_level(self):
        self.farm_level = self.exec_js(script='return Game.Objects["Farm"].level;', default_return=-1)
        if self.farm_level == -1:
            self.reload_cookieclicker()

    def is_tile_unlocked(self, x, y):
        return self.exec_js(script=f"return {self.farm_minigame}.isTileUnlocked({x},{y});", default_return=False)

    def get_plant_id_of_tile(self, x, y):
        try:
            plant_id = self.plot[y][x][0] - 1
        except (IndexError, TypeError):
            plant_id = self.invalid_plant_id
        except InvalidSessionIdException:
            plant_id = self.invalid_plant_id
            self.reload_cookieclicker()
        return plant_id

    def get_plant_maturity_of_tile(self, x, y):
        try:
            return self.plot[y][x][1]
        except JavascriptException:
            return 0

    def switch_soil(self):
        if not self.desired_soil:
            return

        desired_soil_id = self.soils[self.desired_soil]

        if time.time() >= self.next_soil_time and self.current_soil_id != desired_soil_id:
            print(f"{timestamp()}: Switching soil to {self.desired_soil}.")
            self.exec_js(script=f"FireEvent(l('gardenSoil-{desired_soil_id}'), 'click');")
            self.current_soil_id = desired_soil_id

            self.next_soil_time = time.time() + (10 * 60)

            self.get_next_garden_tick_in_seconds()

    def get_active_buffs(self):
        script = """
            const buffs = Object.values(Game.buffs);
            const fps = Game.fps;
            let minBuffTime = buffs.length ? Infinity : null;  // null if no buffs

            const buildingSpecials = new Set([
                'High-five', 'Congregation', 'Luxuriant harvest', 'Ore vein',
                'Oiled-up', 'Juicy profits', 'Fervent adoration', 'Manabloom',
                'Delicious lifeforms', 'Breakthrough', 'Righteous cataclysm',
                'Golden ages', 'Extra cycles', 'Solar flare', 'Winning streak',
                'Macrocosm', 'Refactoring', 'Cosmic nursery', 'Brainstorm',
                'Deduplication'
            ]);
            const debuffs = new Set([
                'Clot', 'Slap to the face', 'Senility', 'Locusts', 'Cave-in',
                'Jammed machinery', 'Recession', 'Crisis of faith', 'Magivores',
                'Black holes', 'Lab disaster', 'Dimensional calamity', 'Time jam',
                'Predictable tragedy', 'Eclipse', 'Dry spell', 'Microcosm',
                'Antipattern', 'Big crunch', 'Brain freeze', 'Clone strike'
            ]);

            // Single pass through buffs to collect all data
            const result = {
                counts: [0, 0, 0, 0, 0, 0, 0, 0],
                activeDebuffs: [],
                activeBuffs: []
            };

            for (const buff of buffs) {
                const time = buff.time / fps;
                const name = buff.name;

                // Track minimum buff time (excluding permanent effects)
                if (time < minBuffTime && time > 0) {
                    minBuffTime = time;
                }

                // Count specific buffs
                if (name === 'Frenzy') result.counts[0]++;
                else if (buildingSpecials.has(name)) result.counts[1]++;
                else if (name === 'Dragon Harvest') result.counts[2]++;
                else if (name === 'Dragonflight') result.counts[3]++;
                else if (name === 'Click frenzy') result.counts[4]++;
                else if (name === 'Elder frenzy') result.counts[5]++;
                else if (name === 'Cursed finger') result.counts[6]++;

                // Track debuffs and regular buffs
                if (debuffs.has(name)) {
                    result.counts[7]++;
                    result.activeDebuffs.push(`${name} (${time.toFixed(1)}s)`);
                } else {
                    result.activeBuffs.push(`${name} (${time.toFixed(1)}s)`);
                }
            }

            result.minBuffTime = minBuffTime === Infinity ? null : minBuffTime;  // Convert Infinity to null
            return result;
        """

        result = self.exec_js(script=script,
                              default_return={'counts': [0] * 8,
                                              'activeDebuffs': [],
                                              'activeBuffs': [],
                                              'minBuffTime': None})

        (self.f_count, self.bs_count, self.dh_count, self.df_count,
         self.cf_count, self.ef_count, self.cursed_finger_count,
         self.debuff_count) = result['counts']

        self.active_debuffs = result['activeDebuffs']
        self.active_buffs = result['activeBuffs']

        # Set boolean flags
        self.f_active = self.f_count > 0
        self.bs_active = self.bs_count > 0
        self.dh_active = self.dh_count > 0
        self.df_active = self.df_count > 0
        self.cf_active = self.cf_count > 0
        self.ef_active = self.ef_count > 0
        self.cursed_finger_active = self.cursed_finger_count > 0
        self.debuff_active = self.debuff_count > 0

        # Schedule next CPS multiplier update
        if result['minBuffTime'] is not None:
            self.next_cps_update = time.time() + result['minBuffTime']

        return sum([
            self.f_count,
            self.bs_count,
            self.dh_count,
            self.df_count,
            self.cf_count,
            self.ef_count
        ])

    def cast_spell(self, spell_to_cast, exhaust_magic=False):
        """Cast spells optimally for maximum combo potential"""

        grimoire = "Game.Objects['Wizard tower'].minigame"

        try:
            # Get all relevant state including next spell forecasts with proper season index and backfire
            state = self.exec_js(script=f"""
                return {{
                    magic: {grimoire}.magic,
                    maxMagic: {grimoire}.magicM,
                    lumps: Game.lumps,
                    lumpRefill: Game.lumpRefill,
                    hasGoldenCookie: Game.shimmers.some(s => s.type=="golden"),
                    buffs: Object.values(Game.buffs).map(b => ({{
                        name: b.name,
                        time: b.time / Game.fps  // Convert frames to seconds
                    }})),
                    spellCosts: {{
                        fthof: {grimoire}.getSpellCost({grimoire}.spellsById[1]),
                        gfd: {grimoire}.getSpellCost({grimoire}.spellsById[6]),
                        scp: {grimoire}.getSpellCost({grimoire}.spellsById[5])
                    }},
                    forecasts: {{
                        fthof1: FortuneCookie.FateChecker(
                            {grimoire}.spellsCastTotal,
                            ((Game.season == "valentines" || Game.season == "easter") ? 1 : 0),
                            {grimoire}.getFailChance({grimoire}.spellsById[1]) + 0.15 * FortuneCookie.getSimGCs(),
                            false
                        ),
                        fthof2: FortuneCookie.FateChecker(
                            {grimoire}.spellsCastTotal + 1,
                            ((Game.season == "valentines" || Game.season == "easter") ? 1 : 0),
                            {grimoire}.getFailChance({grimoire}.spellsById[1]) + 0.15 * FortuneCookie.getSimGCs(),
                            false
                        ),
                        gfd: FortuneCookie.spellForecast({grimoire}.spellsById[6])
                    }}
                }}
            """)

            if not state or state['hasGoldenCookie']:
                return
            if state['lumps'] is None:
                state['lumps'] = float('inf')
            # Handle specific spells first
            if spell_to_cast == "summon crafty pixies":
                print(f"{timestamp()}: Summon Crafty Pixies costs {state['spellCosts']['scp']}. Have {state['magic']} magic.")
                if state['magic'] >= state['spellCosts']['scp']:
                    scp_success = ('<div width="100%"><b>Forecast:</b><br/><span class="green">'
                                   '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Success</span><br/>')
                    scp_result = self.exec_js(script=f"return FortuneCookie.spellForecast({grimoire}.spellsById[5]);",
                                              default_return="Failed")
                    if scp_result and scp_result.startswith(scp_success):
                        print(f"{timestamp()}: Casting Summon Crafty Pixies")
                        self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[5])")
                    else:
                        print(f"{timestamp()}: Spell would backfire; not casting.")
                return

            elif spell_to_cast == "gambler's fever dream":
                # Check if we can attempt Four-leaf cookie achievement
                fthof_cost = state['spellCosts']['fthof']
                gfd_cost = state['spellCosts']['gfd']
                half_fthof = fthof_cost / 2

                # Need enough magic for GFD + half FTHOF cost and enough lumps for refill
                if (state['magic'] >= (gfd_cost + half_fthof) and
                        state['lumps'] > 101 and not state['lumpRefill']):

                    # Look for good outcomes in next few casts
                    good_outcomes = 0
                    for i in range(1, 4):  # Check next 3 potential casts
                        forecast = self.exec_js(
                            script=f"""
                            return FortuneCookie.FateChecker(
                                {grimoire}.spellsCastTotal + {i},
                                ((Game.season == "valentines" || Game.season == "easter") ? 1 : 0),
                                {grimoire}.getFailChance({grimoire}.spellsById[1]) + 0.15 * FortuneCookie.getSimGCs(),
                                false
                            );
                            """
                        )
                        if any(buff in forecast for buff in
                               ['Click Frenzy', 'Building Special', 'Elder Frenzy', 'Dragon Harvest']):
                            good_outcomes += 1

                    # If we see multiple good outcomes, try for Four-leaf cookie
                    if good_outcomes >= 2:
                        print(f"{timestamp()}: Attempting Four-leaf cookie achievement")
                        # Cast GFD twice
                        self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[6])")
                        self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[6])")
                        # Refill magic
                        self.exec_js(script="FireEvent(l('grimoireLumpRefill'), 'click');")
                        print(f"{timestamp()}: Spending one lump to refill Grimoire (had {state['lumps']} lumps).")
                        # Cast FTHOF
                        self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[1])")
                        # Wait for achievement
                        while not self.check_achievements('Four-leaf cookie'):
                            pass
                        return
                return

            elif spell_to_cast == "hand of fate":
                def parse_buff_from_forecast(forecast_line):
                    """Extract buff type from forecast line"""
                    if not forecast_line:
                        return None

                    # Handle all bad spells
                    if 'Blab' in forecast_line:  # Catches both red and green Blabs
                        return 'Blab'
                    if 'Clot' in forecast_line:
                        return 'Clot'
                    if 'Ruin' in forecast_line:
                        return 'Ruin'

                    # Special cases for beneficial red outcomes
                    if 'Elder Frenzy' in forecast_line:
                        return 'Elder frenzy'
                    if 'Free Sugar Lump' in forecast_line:
                        return 'Free Sugar Lump'

                    # Skip other red outcomes that aren't FTHOF predictions
                    if 'red' in forecast_line and 'Force the Hand of Fate' not in forecast_line:
                        return None

                    if 'Click Frenzy' in forecast_line:
                        return 'Click frenzy'
                    elif 'Building Special' in forecast_line:
                        return 'Building Special'
                    elif 'Dragon Harvest' in forecast_line:
                        return 'Dragon Harvest'
                    elif 'Dragonflight' in forecast_line:
                        return 'Dragonflight'
                    elif 'Frenzy' in forecast_line and 'Elder' not in forecast_line:
                        return 'Frenzy'
                    elif 'Lucky' in forecast_line:
                        return 'Lucky'
                    elif 'Cookie Storm' in forecast_line:
                        return 'Cookie Storm'
                    return None
                # Parse forecasts
                fthof1_buff = parse_buff_from_forecast(state['forecasts']['fthof1'])
                fthof2_buff = parse_buff_from_forecast(state['forecasts']['fthof2'])

                gfd_forecast = state['forecasts']['gfd']
                gfd_lines = gfd_forecast.split('<br/>')
                gfd1_buff = parse_buff_from_forecast(gfd_lines[1] if len(gfd_lines) > 1 else None)
                gfd2_buff = parse_buff_from_forecast(gfd_lines[2] if len(gfd_lines) > 2 else None)

                # Get costs and state
                fthof_cost = state['spellCosts']['fthof']
                gfd_cost = state['spellCosts']['gfd']
                half_fthof = fthof_cost / 2
                can_refill = state['lumps'] > 101 and not state['lumpRefill']
                near_max_magic = state['magic'] >= (state['maxMagic'] - 1)

                # Get active buffs and check for building special and frenzy
                active_buffs = [buff['name'] for buff in state['buffs']]
                has_active_bs = any(buff['name'] in BUILDING_SPECIALS for buff in state['buffs'])
                has_active_frenzy = 'Frenzy' in active_buffs
                has_active_cb = any(buff['name'] in CLICK_BUFFS for buff in state['buffs'])
                min_buff_time = min((buff['time'] for buff in state['buffs']), default=0)

                # Check if any combo will give Building Special + Click Buff
                def has_bs_and_cb(buff1, buff2):
                    has_bs = any(b == 'Building Special' for b in (buff1, buff2))
                    has_cb = any(cb in (buff1, buff2) for cb in CLICK_BUFFS)
                    return has_bs and has_cb

                # Helper function to format active buffs for printing
                def format_active_buffs():
                    if not state['buffs']:
                        return "no active buffs"
                    buff_list = [f"{buff['name']} ({buff['time']:.1f}s)" for buff in state['buffs']]
                    return f"active buffs: {', '.join(buff_list)}"

                # Order combos by magic cost (lowest to highest)
                combo_buffs = [
                    ('gfd+gfd', (gfd1_buff, gfd2_buff)),
                    ('gfd+fthof', (gfd1_buff, fthof2_buff)),
                    ('fthof+gfd', (fthof1_buff, gfd2_buff)),
                    ('fthof+fthof', (fthof1_buff, fthof2_buff))
                ]

                # First check if any combo could give BS+CB or BS+BS
                has_potential_combo = False
                best_combo = None
                best_combo_buffs = None
                combo_type = None  # Track whether it's a BS+CB or BS+BS combo

                 # Check combos in order of magic cost
                for combo_name, (buff1, buff2) in combo_buffs:
                    # Check for BS+CB combo
                    if has_bs_and_cb(buff1, buff2):
                        has_potential_combo = True
                        best_combo = combo_name
                        best_combo_buffs = (buff1, buff2)
                        combo_type = "BS+CB"
                        break  # Take first valid combo

                if not has_potential_combo:
                    for combo_name, (buff1, buff2) in combo_buffs:
                        # Check for BS+BS combo
                        if buff1 == 'Building Special' and buff2 == 'Building Special':
                            has_potential_combo = True
                            best_combo = combo_name
                            best_combo_buffs = (buff1, buff2)
                            combo_type = "BS+BS"
                            break  # Take first valid combo

                if has_potential_combo:
                    # Adjust conditions based on combo type
                    conditions_met = False
                    if combo_type == "BS+CB":
                        conditions_met = (
                            has_active_frenzy and
                            has_active_bs and
                            min_buff_time > 13 and
                            self.swaps_left == 3
                        )
                    elif combo_type == "BS+BS":
                        conditions_met = (
                            has_active_frenzy and
                            has_active_cb and
                            min_buff_time > 13 and
                            self.swaps_left == 3
                        )

                    if conditions_met:
                        # Calculate magic costs for combo
                        first_cost = {
                            'fthof+fthof': fthof_cost,
                            'gfd+gfd': gfd_cost + half_fthof,
                            'fthof+gfd': fthof_cost,
                            'gfd+fthof': gfd_cost + half_fthof
                        }[best_combo]

                        second_cost = {
                            'fthof+fthof': fthof_cost,
                            'gfd+gfd': gfd_cost + half_fthof,
                            'fthof+gfd': gfd_cost + half_fthof,
                            'gfd+fthof': fthof_cost
                        }[best_combo]

                        def click_golden_cookies():
                            """Click any golden cookies on screen"""
                            self.exec_js(script="""
                                for (var sx in Game.shimmers) {
                                    var s = Game.shimmers[sx];
                                    if (s.type == "golden") {
                                        s.pop();
                                    }
                                };
                            """)

                        # Check if we can execute combo with refill
                        if state['magic'] >= first_cost and can_refill:
                            magic_after_first = state['magic'] - first_cost
                            refill_amount = min(100, state['maxMagic'] - magic_after_first)
                            magic_after_refill = magic_after_first + refill_amount

                            if magic_after_refill >= second_cost:
                                print(f"{timestamp()}: {Fore.GREEN}Executing {best_combo} {combo_type} combo "
                                      f"({best_combo_buffs[0]}+{best_combo_buffs[1]}) with {format_active_buffs()}{Style.RESET_ALL}")

                                def wait_for_new_buff(previous_buffs):
                                    """Wait for a new buff to appear and become active"""
                                    max_attempts = 50  # Prevent infinite loop
                                    attempts = 0
                                    while attempts < max_attempts:
                                        self.exec_js(script='Game.ClickCookie();')
                                        click_golden_cookies()
                                        current_buffs = self.exec_js(script='return Object.values(Game.buffs).map(b => ({name: b.name, time: b.time / Game.fps}));')
                                        new_active_buffs = [buff['name'] for buff in current_buffs]
                                        if len(new_active_buffs) > len(previous_buffs):
                                            # Format and print current buffs with times
                                            buff_str = ', '.join(f"{buff['name']} ({buff['time']:.1f}s)" for buff in current_buffs)
                                            print(f"{timestamp()}: Active buffs: {buff_str}")
                                            return new_active_buffs
                                        attempts += 1
                                    return False  # Failed to get new buff

                                # First cast
                                if best_combo.startswith('fthof'):
                                    self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[1])")
                                else:  # gfd
                                    self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[6])")

                                # Wait for first buff to become active
                                new_buffs = wait_for_new_buff(active_buffs)
                                if not new_buffs:
                                    print(f"{timestamp()}: {Fore.RED}Failed to get first buff active, aborting combo{Style.RESET_ALL}")
                                    return

                                # Refill if needed
                                if magic_after_first < second_cost:
                                    self.exec_js(script="FireEvent(l('grimoireLumpRefill'), 'click');")
                                    print(f"{timestamp()}: Spending one lump to refill Grimoire (had {state['lumps']} lumps).")

                                # Second cast
                                if best_combo.endswith('fthof'):
                                    self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[1])")
                                else:  # gfd
                                    self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[6])")

                                # Wait for second buff to become active
                                if not wait_for_new_buff(new_buffs):
                                    print(f"{timestamp()}: {Fore.RED}Failed to get second buff active{Style.RESET_ALL}")

                                # Switch pantheon
                                self.pantheon()
                    else:
                        if near_max_magic:
                            current_time = time.time()
                            if current_time - self.last_spell_status_print >= 300:  # 300 seconds = 5 minutes
                                if self.swaps_left != 3:
                                    print(f"{timestamp()}: {Fore.YELLOW}Not enough swaps left ({self.swaps_left}) to execute {combo_type} combo. "
                                      f"Next combo available: {best_combo} ({best_combo_buffs[0]}+{best_combo_buffs[1]}). "
                                      f"Current {format_active_buffs()}{Style.RESET_ALL}")
                                else:
                                    print(f"{timestamp()}: {Fore.YELLOW}Holding spells for perfect {combo_type} combo conditions. "
                                        f"Next combo available: {best_combo} ({best_combo_buffs[0]}+{best_combo_buffs[1]}). "
                                        f"Current {format_active_buffs()}{Style.RESET_ALL}")
                                self.last_spell_status_print = current_time
                        return

                else:
                    # Check for single click buff outcomes
                    next_is_cb = (
                        fthof1_buff in CLICK_BUFFS or
                        gfd1_buff in CLICK_BUFFS
                    )

                    if next_is_cb:
                        # Only cast if we already have two buffs to stack with
                        have_buff_to_stack = (
                            has_active_frenzy and
                            has_active_bs
                        )

                        if have_buff_to_stack:
                            # Prefer GFD if it gives click buff (costs less)
                            if gfd1_buff in CLICK_BUFFS and state['magic'] >= (gfd_cost + half_fthof):
                                print(f"{timestamp()}: {Fore.GREEN}Casting GFD for {gfd1_buff}. {format_active_buffs()}{Style.RESET_ALL}")
                                self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[6])")
                            elif fthof1_buff in CLICK_BUFFS and state['magic'] >= fthof_cost:
                                print(f"{timestamp()}: {Fore.GREEN}Casting FTHOF for {fthof1_buff}. {format_active_buffs()}{Style.RESET_ALL}")
                                self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[1])")
                        else:
                            if near_max_magic:
                                # Only print holding message once every 5 minutes
                                current_time = time.time()
                                if not hasattr(self, 'last_hold_print') or current_time - self.last_hold_print >= 300:
                                    print(f"{timestamp()}: Holding click buff for potential stacking despite max magic")
                                    self.last_hold_print = current_time
                            return
                    else:
                        # Helper function to check for bad outcomes
                        def is_bad_spell(forecast):
                            if not forecast:
                                return True
                            return forecast in {'Blab', 'Clot', 'Ruin'}

                        # Helper function to rank buff outcomes
                        def get_buff_value(buff):
                            if buff == 'Free Sugar Lump':
                                return 4  # Highest priority
                            if buff in CLICK_BUFFS:
                                return 3  # Click buffs are very valuable
                            if buff in STACKING_BUFFS:
                                return 2  # Other stacking buffs
                            if buff in ['Cookie Storm', 'Lucky']:
                                return 1  # Lucky/Cookie Storm
                            return -1    # None or backfire

                        # For all other outcomes, check for stacking opportunities or cast when near max magic
                        def can_stack_buff(buff):
                            """Check if a buff can stack (not already active and is stackable)"""
                            if not buff or buff in {'Skip', 'Blab', 'Clot', 'Ruin'}:
                                return False
                            # No buff stacks with itself
                            if buff in active_buffs:
                                return False
                            # Only certain buffs can stack
                            return buff in STACKING_BUFFS

                        # Get minimum active buff time
                        active_buff_time = float('inf')
                        for buff in state['buffs']:
                            active_buff_time = min(active_buff_time, buff['time'])

                        # Check if we have good stacking conditions
                        can_stack = (
                            90 > active_buff_time > 55 and  # Enough time on current buffs
                            (can_stack_buff(fthof1_buff) or can_stack_buff(gfd1_buff)) and  # Have stackable buff
                            len(state['buffs']) > 0  # Have at least one active buff
                        )

                        if can_stack or near_max_magic:
                            # Check for bad outcomes in both spells
                            fthof_is_bad = is_bad_spell(fthof1_buff)
                            gfd_is_bad = is_bad_spell(gfd1_buff)

                            if fthof_is_bad:
                                print(f"{timestamp()}: {Fore.RED}Casting GFD for {gfd1_buff} to avoid FTHOF {fthof1_buff}. "
                                    f"Magic was {state['magic']}.{Style.RESET_ALL}")
                                self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[6])")
                                if gfd_is_bad:
                                    self.save_game(path=self.save_file)
                                    time.sleep(1)
                                    self.load_save()
                                    # Run cleanup periodically
                                    self.cleanup()

                                return

                            # Otherwise proceed with normal spell evaluation
                            fthof_value = get_buff_value(fthof1_buff)
                            gfd_value = get_buff_value(gfd1_buff)
                            previous_lumps = self.exec_js(script='return Game.lumps;', default_return=0)
                            if previous_lumps is None:
                                previous_lumps = float('inf')

                            # Cast spell if we have any good outcome
                            if max(fthof_value, gfd_value) > 0:
                                # cast_reason = "stacking opportunity" if can_stack else "near max magic"
                                # If GFD result matches FTHOF, prefer GFD as it costs less
                                if gfd_value >= fthof_value and state['magic'] >= (gfd_cost + half_fthof):
                                    print(f"{timestamp()}: {Fore.GREEN}Casting GFD for {gfd1_buff}. {format_active_buffs()}{Style.RESET_ALL}")
                                    self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[6])")
                                elif fthof_value > 0 and state['magic'] >= fthof_cost:
                                    print(f"{timestamp()}: {Fore.GREEN}Casting FTHOF for {fthof1_buff}. {format_active_buffs()}{Style.RESET_ALL }")
                                    self.exec_js(script=f"{grimoire}.castSpell({grimoire}.spellsById[1])")

                                if fthof1_buff == 'Free Sugar Lump' or gfd1_buff == 'Free Sugar Lump':
                                    self.check_and_level_up(previous_lumps)
                                    print(f"{timestamp()}: Got Free Sugar Lump!")

            else:
                print(f"{timestamp()}: Unknown spell: {spell_to_cast}")
                return

        except JavascriptException:
            print(f"{timestamp()}: Failed to cast spell")

    def try_for_shriekbulbs(self):
        duketater = self.plants["duketater"]
        duketater_tiles = []

        if self.farm_level == 1:
            duketater_tiles.append({"x": 2, "y": 2})
            duketater_tiles.append({"x": 3, "y": 2})
            duketater_tiles.append({"x": 2, "y": 3})
        elif self.farm_level == 2:
            for x in range(2, 5):
                self.click_cookie()
                duketater_tiles.append({"x": x, "y": 2})

            duketater_tiles.append({"x": 3, "y": 3})
        elif self.farm_level == 3:
            for x in [2, 4]:
                for y in [2, 4]:
                    self.click_cookie()
                    duketater_tiles.append({"x": x, "y": y})

            duketater_tiles.append({"x": 3, "y": 3})
        elif self.farm_level == 4:
            for x in [1, 4]:
                for y in [2, 4]:
                    self.click_cookie()
                    duketater_tiles.append({"x": x, "y": y})

            duketater_tiles.append({"x": 2, "y": 3})
            duketater_tiles.append({"x": 2, "y": 4})
        elif self.farm_level == 5:
            for x in [1, 4]:
                for y in [1, 4]:
                    self.click_cookie()
                    duketater_tiles.append({"x": x, "y": y})

            for x in [2, 3]:
                for y in [2, 3]:
                    self.click_cookie()
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
                self.click_cookie()
                duketater_tiles.append({"x": x, "y": 2})
            for x in [1, 2, 4, 5]:
                self.click_cookie()
                duketater_tiles.append({"x": x, "y": 4})

            duketater_tiles.append({"x": 2, "y": 5})
            duketater_tiles.append({"x": 4, "y": 5})
        elif self.farm_level == 8:
            for y in range(1, 6):
                for x in [1, 4]:
                    self.click_cookie()
                    if x == 4 or y in range(2, 5):
                        duketater_tiles.append({"x": x, "y": y})

            for x in [0, 2]:
                for y in [1, 5]:
                    self.click_cookie()
                    duketater_tiles.append({"x": x, "y": y})
        elif self.farm_level >= 9:
            for y in range(6):
                for x in [1, 4]:
                    self.click_cookie()
                    if x == 4 or y in range(1, 5):
                        duketater_tiles.append({"x": x, "y": y})

            for x in [0, 2]:
                for y in [0, 5]:
                    self.click_cookie()
                    duketater_tiles.append({"x": x, "y": y})

        oldest_seed = 0
        duketater_id = duketater["id"]
        parent_seed_maturity = duketater["mature"]
        for tile in duketater_tiles:
            self.click_cookie()
            self.plant_seed(x=tile["x"], y=tile["y"], seed_id=duketater_id)
            try:
                plant_data = self.occupied_tiles[tile["x"], tile["y"]]
                if plant_data['id'] == duketater_id:
                    oldest_seed = max(oldest_seed, plant_data['maturity'])
            except KeyError:
                self.click_cookie()

        clean_tiles = {tile: plant for (tile, plant) in self.occupied_tiles.items()
                       if {'x': tile[0], 'y': tile[1]} not in duketater_tiles}
        self.clean_garden(tiles=clean_tiles)
        if oldest_seed >= parent_seed_maturity:
            self.desired_soil = "woodchips"
        else:
            self.desired_soil = "fertilizer"

    def try_for_everdaisy(self):
        tidygrass = self.plants["tidygrass"]
        elderwort = self.plants["elderwort"]
        tidygrass_id = tidygrass["id"]
        elderwort_id = elderwort["id"]

        elderwort_tiles = []
        tidygrass_tiles = []

        aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
        dragon_boost = 1 / (1 + 0.05 * aura_multi)

        if self.plants["queenbeetLump"]["growing"]:
            jqb_tile = {"x": None, "y": None}
            if self.farm_level == 7:
                for jqb_x in [2, 4]:
                    for jqb_y in [2, 4]:
                        self.click_cookie()
                        try:
                            plant_data = self.occupied_tiles[jqb_x, jqb_y]
                            if plant_data['id'] == self.plants["queenbeetLump"]["id"]:
                                jqb_tile = {"x": jqb_x, "y": jqb_y}
                                break
                        except KeyError:
                            self.click_cookie()

                x_offset = 0
                y_offset = 0
                if jqb_tile["x"] == 4:
                    x_offset = 6
                if jqb_tile["y"] == 2:
                    y_offset = 6

                # First row
                tidygrass_tiles.append({"x": abs(1 - x_offset), "y": abs(1 - y_offset)})
                tidygrass_tiles.append({"x": abs(2 - x_offset), "y": abs(1 - y_offset)})
                tidygrass_tiles.append({"x": abs(3 - x_offset), "y": abs(1 - y_offset)})
                tidygrass_tiles.append({"x": abs(4 - x_offset), "y": abs(1 - y_offset)})
                # Second Row
                tidygrass_tiles.append({"x": abs(1 - x_offset), "y": abs(2 - y_offset)})
                elderwort_tiles.append({"x": abs(4 - x_offset), "y": abs(2 - y_offset)})
                tidygrass_tiles.append({"x": abs(5 - x_offset), "y": abs(2 - y_offset)})
                # Third row
                elderwort_tiles.append({"x": abs(1 - x_offset), "y": abs(3 - y_offset)})
                elderwort_tiles.append({"x": abs(2 - x_offset), "y": abs(3 - y_offset)})
                elderwort_tiles.append({"x": abs(3 - x_offset), "y": abs(3 - y_offset)})
                tidygrass_tiles.append({"x": abs(5 - x_offset), "y": abs(3 - y_offset)})
                # Fourth row
                elderwort_tiles.append({"x": abs(1 - x_offset), "y": abs(4 - y_offset)})
                elderwort_tiles.append({"x": abs(3 - x_offset), "y": abs(4 - y_offset)})
                tidygrass_tiles.append({"x": abs(5 - x_offset), "y": abs(4 - y_offset)})
                # Fifth row
                elderwort_tiles.append({"x": abs(1 - x_offset), "y": abs(5 - y_offset)})
                elderwort_tiles.append({"x": abs(2 - x_offset), "y": abs(5 - y_offset)})
                elderwort_tiles.append({"x": abs(3 - x_offset), "y": abs(5 - y_offset)})
                tidygrass_tiles.append({"x": abs(4 - x_offset), "y": abs(5 - y_offset)})
                tidygrass_tiles.append({"x": abs(5 - x_offset), "y": abs(5 - y_offset)})
            elif self.farm_level == 8:
                for jqb_x in [1, 4]:
                    for jqb_y in [2, 4]:
                        self.click_cookie()
                        try:
                            plant_data = self.occupied_tiles[jqb_x, jqb_y]
                            if plant_data['id'] == self.plants["queenbeetLump"]["id"]:
                                jqb_tile = {"x": jqb_x, "y": jqb_y}
                                break
                        except KeyError:
                            self.click_cookie()

                x_offset = 0
                y_offset = 0
                if jqb_tile["x"] == 4:
                    x_offset = 5
                if jqb_tile["y"] == 2:
                    y_offset = 6

                # First row
                elderwort_tiles.append({"x": abs(0 - x_offset), "y": abs(1 - y_offset)})
                tidygrass_tiles.append({"x": abs(1 - x_offset), "y": abs(1 - y_offset)})
                tidygrass_tiles.append({"x": abs(2 - x_offset), "y": abs(1 - y_offset)})
                elderwort_tiles.append({"x": abs(3 - x_offset), "y": abs(1 - y_offset)})
                elderwort_tiles.append({"x": abs(4 - x_offset), "y": abs(1 - y_offset)})
                tidygrass_tiles.append({"x": abs(2 - x_offset), "y": abs(1 - y_offset)})
                # Second row
                tidygrass_tiles.append({"x": abs(0 - x_offset), "y": abs(2 - y_offset)})
                tidygrass_tiles.append({"x": abs(5 - x_offset), "y": abs(2 - y_offset)})
                # Third row
                elderwort_tiles.append({"x": abs(0 - x_offset), "y": abs(3 - y_offset)})
                elderwort_tiles.append({"x": abs(1 - x_offset), "y": abs(3 - y_offset)})
                elderwort_tiles.append({"x": abs(2 - x_offset), "y": abs(3 - y_offset)})
                tidygrass_tiles.append({"x": abs(3 - x_offset), "y": abs(3 - y_offset)})
                tidygrass_tiles.append({"x": abs(4 - x_offset), "y": abs(3 - y_offset)})
                elderwort_tiles.append({"x": abs(5 - x_offset), "y": abs(3 - y_offset)})
                # Fourth row
                elderwort_tiles.append({"x": abs(0 - x_offset), "y": abs(4 - y_offset)})
                elderwort_tiles.append({"x": abs(2 - x_offset), "y": abs(4 - y_offset)})
                elderwort_tiles.append({"x": abs(5 - x_offset), "y": abs(4 - y_offset)})
                # Fifth row
                elderwort_tiles.append({"x": abs(0 - x_offset), "y": abs(5 - y_offset)})
                elderwort_tiles.append({"x": abs(1 - x_offset), "y": abs(5 - y_offset)})
                elderwort_tiles.append({"x": abs(2 - x_offset), "y": abs(5 - y_offset)})
                tidygrass_tiles.append({"x": abs(3 - x_offset), "y": abs(5 - y_offset)})
                tidygrass_tiles.append({"x": abs(4 - x_offset), "y": abs(5 - y_offset)})
                elderwort_tiles.append({"x": abs(5 - x_offset), "y": abs(5 - y_offset)})
            elif self.farm_level >= 9:
                for jqb_x in [1, 4]:
                    for jqb_y in [1, 4]:
                        self.click_cookie()
                        try:
                            plant_data = self.occupied_tiles[jqb_x, jqb_y]
                            if plant_data['id'] == self.plants["queenbeetLump"]["id"]:
                                jqb_tile = {"x": jqb_x, "y": jqb_y}
                                break
                        except KeyError:
                            self.click_cookie()

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
            if self.farm_level == 3:
                for e_x in range(2, 5):
                    self.click_cookie()
                    elderwort_tiles.append({"x": e_x, "y": 4})

                for t_x in range(2, 5):
                    for t_y in [2, 3]:
                        self.click_cookie()
                        if not (t_x == 3 and t_y == 3):
                            tidygrass_tiles.append({"x": t_x, "y": t_y})
            elif self.farm_level == 4:
                for e_x in range(1, 5):
                    self.click_cookie()
                    elderwort_tiles.append({"x": e_x, "y": 4})

                for t_x in range(1, 5):
                    for t_y in [2, 3]:
                        self.click_cookie()
                        if not (t_x in [2, 3] and t_y == 3):
                            tidygrass_tiles.append({"x": t_x, "y": t_y})
            elif self.farm_level == 5:
                for e_x in range(1, 5):
                    for e_y in [1, 4]:
                        self.click_cookie()
                        if not (e_x == 1 and e_y == 4):
                            elderwort_tiles.append({"x": e_x, "y": e_y})

                for t_x in [1, 4]:
                    for t_y in [2, 3]:
                        self.click_cookie()
                        tidygrass_tiles.append({"x": t_x, "y": t_y})

                tidygrass_tiles.append({"x": 1, "y": 4})
                tidygrass_tiles.append({"x": 2, "y": 3})
            elif self.farm_level == 6:
                for e_y in range(1, 5):
                    self.click_cookie()
                    elderwort_tiles.append({"x": 3, "y": e_y})

                for t_x in [1, 5]:
                    for t_y in range(1, 5):
                        self.click_cookie()
                        tidygrass_tiles.append({"x": t_x, "y": t_y})

                for t_x in [2, 4]:
                    for t_y in [1, 4]:
                        self.click_cookie()
                        tidygrass_tiles.append({"x": t_x, "y": t_y})
            elif self.farm_level == 7:
                for e_x in range(1, 6):
                    self.click_cookie()
                    elderwort_tiles.append({"x": 3, "y": 3})

                for t_x in range(1, 6):
                    for t_y in [1, 5]:
                        self.click_cookie()
                        tidygrass_tiles.append({"x": t_x, "y": t_y})

                for t_x in [1, 5]:
                    for t_y in [2, 4]:
                        self.click_cookie()
                        tidygrass_tiles.append({"x": t_x, "y": t_y})
            elif self.farm_level == 8:
                for e_x in range(0, 6):
                    self.click_cookie()
                    elderwort_tiles.append({"x": 3, "y": 3})

                for t_x in range(0, 6):
                    for t_y in [1, 5]:
                        self.click_cookie()
                        tidygrass_tiles.append({"x": t_x, "y": t_y})

                for t_x in [0, 5]:
                    for t_y in [2, 4]:
                        self.click_cookie()
                        tidygrass_tiles.append({"x": t_x, "y": t_y})
            else:
                for e_x in range(6):
                    for e_y in [0, 3]:
                        self.click_cookie()
                        elderwort_tiles.append({"x": e_x, "y": e_y})

                for t_x in [0, 2, 3, 5]:
                    for t_y in [1, 2, 4]:
                        self.click_cookie()
                        if t_y == 1 or (t_y == 2 and t_x != 3) or (t_y == 4 and t_x not in [3, 4]):
                            tidygrass_tiles.append({"x": t_x, "y": t_y})

                for t_x in range(6):
                    self.click_cookie()
                    tidygrass_tiles.append({"x": t_x, "y": 5})

        elderwort_ticks_until_mature = self.plant_ticks_until_mature(plant='elderwort', dragon_boost=dragon_boost)
        tidygrass_ticks_until_mature = self.plant_ticks_until_mature(plant='tidygrass', dragon_boost=dragon_boost)
        maturity_difference = elderwort_ticks_until_mature - tidygrass_ticks_until_mature
        clean_tiles = {tile: plant for (tile, plant) in self.occupied_tiles.items()
                       if {'x': tile[0], 'y': tile[1]} not in elderwort_tiles
                       and {'x': tile[0], 'y': tile[1]} not in tidygrass_tiles}
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
        queenbeet_id = self.plants["queenbeet"]["id"]
        aura_multi = self.exec_js(script="return Game.auraMult('Supreme Intellect');", default_return=0)
        dragon_boost = 1 / (1 + 0.05 * aura_multi)

        if 3 <= self.farm_level <= 5:
            quadrants = {
                1: []
            }
        elif self.farm_level == 6:
            quadrants = {
                1: [],
                2: []
            }
        else:
            quadrants = {
                1: [],
                2: [],
                3: [],
                4: []
            }

        for quadrant, q_coords in quadrants.items():
            if 3 <= self.farm_level <= 5:
                x_range = range(2, 5)
                y_range = range(2, 5)
            elif self.farm_level == 6:
                if quadrant == 1:
                    x_range = range(3, 6)
                else:
                    x_range = range(1, 4)

                y_range = range(1, 4)
            elif self.farm_level == 7:
                if quadrant in {1, 2}:
                    y_range = range(1, 4)
                else:
                    y_range = range(3, 6)

                if quadrant in {1, 4}:
                    x_range = range(3, 6)
                else:
                    x_range = range(1, 4)
            elif self.farm_level == 8:
                if quadrant in {1, 2}:
                    y_range = range(1, 4)
                else:
                    y_range = range(3, 6)

                if quadrant in {1, 4}:
                    x_range = range(3, 6)
                else:
                    x_range = range(0, 3)
            else:
                if quadrant in {1, 2}:
                    y_range = range(0, 3)
                else:
                    y_range = range(3, 6)

                if quadrant in {1, 4}:
                    x_range = range(3, 6)
                else:
                    x_range = range(0, 3)

            for x_coord in x_range:
                for y_coord in y_range:
                    self.click_cookie()
                    q_coords.append({'x': x_coord, 'y': y_coord})

        def check_quadrant(coords):
            if 3 <= self.farm_level <= 5:
                grow_coords = [
                    (3, 3)
                ]
            elif self.farm_level == 6:
                grow_coords = [
                    (2, 2), (4, 2)
                ]
            elif self.farm_level == 7:
                grow_coords = [
                    (2, 2), (4, 2),
                    (2, 4), (4, 4)
                ]
            elif self.farm_level == 8:
                grow_coords = [
                    (1, 2), (4, 2),
                    (1, 4), (4, 4)
                ]
            else:
                grow_coords = [
                    (1, 1), (1, 4),
                    (4, 1), (4, 4)
                ]


            mutation_coords = [coord for coord in coords if (coord['x'], coord['y']) in grow_coords][0]

            clean_quadrant = False
            queenbeet_ticks_until_mature = self.plant_ticks_until_mature(plant='queenbeet', dragon_boost=dragon_boost)
            duketater_ticks_until_mature = 0
            duketater_tile = None

            quadrant_age_at_next_tick = [plant['age_at_next_tick'] for (tile, plant) in self.occupied_tiles.items()
                                         if {'x': tile[0], 'y': tile[1]} in coords and plant['name'] == 'queenbeet']

            quadrant_avg_age_next_tick = (sum(quadrant_age_at_next_tick) / len(quadrant_age_at_next_tick)
                                          if len(quadrant_age_at_next_tick) != 0 else 0)
            quadrant_ticks_until_mature = [plant['ticks_until_mature'] for (tile, plant) in self.occupied_tiles.items()
                                           if {'x': tile[0], 'y': tile[1]} in coords and plant['name'] == 'queenbeet']
            quadrant_ticks_until_decayed = [plant['ticks_until_decayed'] for (tile, plant) in
                                            self.occupied_tiles.items()
                                            if {'x': tile[0], 'y': tile[1]} in coords and plant['name'] == 'queenbeet']

            print(f"{timestamp()}: Quadrant maximum ticks until mature: {max(quadrant_ticks_until_mature, default=0)}. "
                  f"Minimum ticks until decayed: {min(quadrant_ticks_until_decayed, default=0)}")

            try:
                p_id = self.occupied_tiles[mutation_coords['x'], mutation_coords['y']]['id']
                if p_id != self.plants["queenbeetLump"]["id"]:
                    remove_undesirable_plants(x=mutation_coords['x'], y=mutation_coords['y'])

                try:
                    p_id = self.occupied_tiles[mutation_coords['x'], mutation_coords['y']]['id']
                except KeyError:
                    p_id = self.empty_tile_plant_id

                if p_id == self.plants["duketater"]["id"] and self.plants["duketater"]["growing"] and \
                        not self.plants["duketater"]["unlocked"]:
                    print(f"{timestamp()}: Found a {self.plants_by_id[p_id]['name']} at {mutation_coords}.")
                    duketater_ticks_until_mature = self.occupied_tiles[mutation_coords['x'], mutation_coords['y']][
                        'ticks_until_mature']
                    duketater_tile = mutation_coords
                    print(
                        f"{timestamp()}: Duketater {mutation_coords} matures in {duketater_ticks_until_mature} ticks.")
            except KeyError:
                self.click_cookie()

            for tile in coords:
                self.click_cookie()
                try:
                    p_id = self.occupied_tiles[tile['x'], tile['y']]['id']
                except KeyError:
                    p_id = self.empty_tile_plant_id

                if tile != mutation_coords:
                    if p_id == self.empty_tile_plant_id:
                        clean_quadrant = True
                        break
                    age_at_next_tick = self.occupied_tiles[tile['x'], tile['y']]['age_at_next_tick']
                    if age_at_next_tick >= 100:
                        clean_quadrant = True
                        break

            if clean_quadrant:
                quadrant_avg_age_next_tick = 0
                (cps, cookies, cost) = self.exec_js(script="return [Game.cookiesPs, Game.cookies,"
                                                           f'{self.farm_minigame}.plants["queenbeet"].cost];',
                                                    default_return=[0, 0, float('inf')])
                total_cost = cps * 60 * 8 * cost
                if math.isnan(total_cost):
                    return quadrant_avg_age_next_tick

                if cookies >= total_cost and (duketater_ticks_until_mature - queenbeet_ticks_until_mature <= 0):
                    if duketater_tile and duketater_ticks_until_mature - queenbeet_ticks_until_mature <= 0:
                        print(f"{timestamp()}: Duketater ({duketater_tile}) matures in {duketater_ticks_until_mature} "
                              f"ticks. Queenbeet takes {queenbeet_ticks_until_mature} ticks to mature")
                    replant = True
                else:
                    replant = False

                for tile in coords:
                    self.click_cookie()
                    if (tile['x'], tile['y']) not in grow_coords:
                        try:
                            p_id = self.occupied_tiles[tile['x'], tile['y']]['id']
                            plant_age = self.occupied_tiles[tile['x'], tile['y']]['maturity']
                            plant_unlocked = self.plants_by_id[p_id]["unlocked"]
                            plant_mature_age = self.plants_by_id[p_id]["mature"]

                            if plant_unlocked or plant_age >= plant_mature_age:
                                self.exec_js(script=f"{self.farm_minigame}.harvest({tile['x']},{tile['y']})")
                                self.get_plot_details()
                                del self.occupied_tiles[tile['x'], tile['y']]
                                if self.cpsMult > 1:
                                    self.last_buffed_harvest = time.time()
                        except KeyError:
                            self.click_cookie()

                        try:
                            p_id = self.occupied_tiles[tile['x'], tile['y']]['id']
                        except KeyError:
                            p_id = self.empty_tile_plant_id

                        if replant and p_id == self.empty_tile_plant_id:
                            self.plant_seed(x=tile['x'], y=tile['y'], seed_id=queenbeet_id)

            return quadrant_avg_age_next_tick

        def remove_undesirable_plants(x, y):
            try:
                p_id = self.occupied_tiles[x, y]['id']
                plant_age = self.occupied_tiles[x, y]['maturity']
                plant_unlocked = self.plants_by_id[p_id]["unlocked"]
                plant_mature_age = self.plants_by_id[p_id]["mature"]
            except KeyError:
                p_id = self.empty_tile_plant_id
                plant_age = 0
                plant_unlocked = False
                plant_mature_age = float('inf')

            self.last_garden_clean = time.time()
            if p_id not in {self.empty_tile_plant_id, self.plants["queenbeetLump"]["id"], self.invalid_plant_id
                            } and not self.plants["queenbeetLump"]["growing"] and (plant_unlocked or
                                                                                   plant_age >= plant_mature_age):
                try:
                    print(f"{timestamp()}: {self.plants_by_id[p_id]['name']} at {x, y}. "
                          "Continuing will remove the plant.")
                    self.exec_js(script=f"{self.farm_minigame}.harvest({x},{y})")
                    self.get_plot_details()
                    del self.occupied_tiles[x, y]
                    if self.cpsMult > 1:
                        self.last_buffed_harvest = time.time()
                except JavascriptException:
                    self.click_cookie()
            elif p_id == self.plants["queenbeetLump"]["id"]:
                self.save_game(path=self.save_file)
                if self.num_plants_unlocked + self.num_locked_plants_growing == self.max_plants:
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
                try:
                    p_id = self.occupied_tiles[tile]['id']
                    plant_unlocked = self.plants_by_id[p_id]["unlocked"]
                except KeyError:
                    p_id = self.empty_tile_plant_id
                    plant_unlocked = False

                if p_id not in {self.empty_tile_plant_id, elderwort_id} and plant_unlocked:
                    print(f"{timestamp()}: Harvesting elderwort tiles if they don't contain elderwort.")
                    self.exec_js(script=f"{self.farm_minigame}.harvest({tile[0]},{tile[1]});")
                    self.get_plot_details()
                    del self.occupied_tiles[tile]
                    if self.cpsMult > 1:
                        self.last_buffed_harvest = time.time()
                self.plant_seed(x=tile[0], y=tile[1], seed_id=elderwort_id)

        if not (self.plants["queenbeetLump"]["unlocked"] or self.plants["queenbeetLump"]["growing"]):
            if self.farm_level >= 7:
                wanted_aura = self.final_wanted_aura

                max_maturity = 0
                for quadrant, q_coords in quadrants.items():
                    self.click_cookie()
                    max_maturity = max(max_maturity, check_quadrant(q_coords))

                if max_maturity >= self.plants["queenbeet"]["mature"] and not self.plants["queenbeetLump"]["unlocked"]:
                    self.desired_soil = "woodchips"
                else:
                    self.desired_soil = "fertilizer"
            else:
                wanted_aura = self.final_wanted_aura
        else:
            wanted_aura = self.final_wanted_aura

        if self.dragon_complete:
            self.set_dragon_auras(dragon_aura=wanted_aura)

    def check_veil(self):
        try:
            self.is_veil_active = True if self.driver.execute_script(
                f"javascript:return Game.Has('Shimmering veil [off]')") else False
        except JavascriptException:
            self.is_veil_active = False

    def four_leaf_cookie(self):
        grimoire = 'Game.Objects["Wizard tower"].minigame'
        spells_cast = self.exec_js(script=f"return {grimoire}.spellsCastTotal;", default_return=float('inf'))
        try:
            if spells_cast == self.spell_count_four_leaf_cookie:
                print(f'{timestamp()}: Prepare for Four-leaf cookie')

                shimmers = self.exec_js(script='return Game.shimmers', default_return=[])
                for s in shimmers:
                    if s["type"] != "golden":
                        print(f'{timestamp()}: Waiting for golden cookie')
                        return

                self.cast_spell(spell_to_cast="gambler's fever dream", exhaust_magic=False)
        except JavascriptException:
            return

    def is_prestige_doubled(self):
        self.prestige, self.new_prestige = self.exec_js(script="return [Game.prestige, "
                                                               "Game.HowMuchPrestige("
                                                               "CookieMonsterData.Cache.RealCookiesEarned + "
                                                               "Game.cookiesReset + "
                                                               "CookieMonsterData.Cache.WrinklersTotal + "
                                                               "(Game.HasUnlocked('Chocolate egg') && "
                                                               "!Game.Has('Chocolate egg') ? "
                                                               "CookieMonsterData.Cache.LastChoEgg : 0),)];",
                                                        default_return=[float('inf'), 0])

        if self.new_prestige is None:
            print(f"{timestamp()}: New prestige is NoneType. Skipping.")
            return

        doubled = self.prestige * 2 < self.new_prestige
        halfway = self.prestige * 1.5 < self.new_prestige
        previous_reset_bonus = self.reset_bonus_percent
        if self.prestige == 0:
            return
        self.reset_bonus_percent = abs(1 - self.new_prestige/self.prestige)

        if self.print_prestige <= time.time():
            print(f'{timestamp()}: Prestige after Godzamok click bonus: {self.new_prestige}. '
                  f'Reset bonus: {self.reset_bonus_percent * 100:.2f}%. '
                  f'Previous bonus: {previous_reset_bonus * 100:.2f}%')
            self.print_prestige = float('inf')
            self.godzamok_ascension_delay = False
            try:
                if self.interval_id:
                    self.driver.execute_script(f"javascript:clearInterval({self.interval_id});")
                    self.interval_id = None
            except JavascriptException:
                print(f"{timestamp()}: Failed to clear autoclicker.")

            if not self.interval_id:
                self.autoclicker(amount_of_clicks=AC_CLICKS, ms_interval=AC_MS)

        if halfway:
            self.sugar_frenzy_spend = True

        if doubled:
            print(f'{timestamp()}: {Fore.GREEN}TIME TO ASCEND - Move Skruuia to Diamond, pop all wrinklers, change '
                  f'auras to Earth Shatterer and Reality Bending, sell all stock market goods, sell all buildings, '
                  f'buy chocolate egg.{Style.RESET_ALL}')
            if self.handle_ascension and not self.godzamok_ascension_delay:
                self.ascend()

    def ascend(self):
        if self.handle_ascension:
            self.save_game(path=f"{self.save_file}_pre_ascend.txt")
            temple = "Game.Objects['Temple'].minigame"

            try:
                self.driver.execute_script(f"javascript:{temple}.slotHovered = 0;"
                                           f"{temple}.dragging = {temple}.gods['scorn'];"
                                           f"{temple}.dropGod();")
                print(f"{timestamp()}: Moved Skruuia to Diamond slot.")
                self.driver.execute_script("Object.keys(Game.wrinklers).forEach((i) => {"
                                           "    if (Game.wrinklers[i].sucked > 0 && Game.wrinklers[i].type === 0) {"
                                           "        Game.wrinklers[i].hp = 0;"
                                           "    }"
                                           "});")
                print(f"{timestamp()}: Popped all normal wrinklers.")
            except JavascriptException:
                input("Failed to move Skruuia to diamond and/or pop wrinklers. Perform manually then press Return.")

            market = 'Game.Objects["Bank"].minigame'
            goods_by_id = f'{market}.goodsById'
            number_of_goods = self.exec_js(script=f"return {goods_by_id}.length;", default_return=0)
            if number_of_goods == 0:
                input("Failed to get stock info. Sell all stocks before proceeding.")

            for good_id in range(number_of_goods):
                good_name = self.exec_js(script=f"return {goods_by_id}[{good_id}].name")
                if good_name:
                    try:
                        stock_max = f"{market}.getGoodMaxStock({market}.goodsById[{good_id}])"

                        self.driver.execute_script(f"javascript:{market}.sellGood({good_id}, {stock_max})")
                        print(f'{timestamp()}: {Fore.RED}Selling {good_name}.{Style.RESET_ALL}')
                    except JavascriptException:
                        input(f"Failed to sell stock {good_id}. Sell stock before proceeding.")
                else:
                    input(f"Failed to sell stock {good_id}. Sell stock before proceeding.")

            self.set_dragon_auras(dragon_aura=self.dragon_auras_lookup["Earth Shatterer"]["id"],
                                  dragon_aura2=self.dragon_auras_lookup["Reality Bending"]["id"])
            buildings = self.exec_js(script="return Game.ObjectsById.map(({id, name, amount, price, locked}) => "
                                            "({id, name, amount, price, locked}));", default_return=[])

            if not buildings:
                input(f"{timestamp()}: Unable to retrieve building list. Sell all buildings.")

            for building in buildings:
                try:
                    self.driver.execute_script(f"javascript:Game.ObjectsById[{building['id']}]."
                                               f"sell({building['amount']});")
                    print(f'{timestamp()}: {Fore.RED}Selling {building["amount"]} {building["name"]}s.'
                          f'{Style.RESET_ALL}')
                except JavascriptException:
                    input(f"Failed to sell {building['name']}. Sell all manually, then press Return.")

            try:
                print(f"{timestamp()}: {Fore.GREEN}Buying chocolate egg.{Style.RESET_ALL}")
                self.driver.execute_script("javascript:Game.UpgradesById[227].buy(true);")
            except JavascriptException:
                input("Buy chocolate egg, then press Return to continue.")

            try:
                if self.interval_id:
                    self.driver.execute_script(f"javascript:clearInterval({self.interval_id});")
                    self.interval_id = None
            except JavascriptException:
                print(f"{timestamp()}: Failed to clear autoclicker.")

            try:
                self.driver.execute_script("javascript:Game.Ascend(true);")
            except JavascriptException:
                input("Failed to ascend. Ascend manually.")
            self.dragon_level = 0
            self.dragon_upgrades_complete = False
            self.dragon_complete = False
            self.handle_ascension = False
            self.ascension_mode = None
            # TODO: Figure out how to handle permanent upgrades
            # input("Select Permanent Upgrade options and press Return to continue.")
            time.sleep(5)
            try:
                self.driver.execute_script("javascript:Game.Reincarnate(true);")
            except JavascriptException:
                input("Failed to reincarnate. Perform manually and press Return to continue.")
            time.sleep(5)
            self.get_ascension_mode()
            self.save_game(path=self.save_file)
            if not self.interval_id:
                self.autoclicker(amount_of_clicks=AC_CLICKS, ms_interval=AC_MS)
            return

        prestige_levels = int(self.exec_js(script="return Game.ascendMeterLevel;", default_return=0))
        try:
            if prestige_levels > 0:
                self.driver.execute_script("javascript:Game.Ascend(true);")
                self.ascension_mode = None
                if self.attempt_endless_cycle:
                    time.sleep(10)
                    self.driver.execute_script("javascript:Game.Reincarnate(true);")
                    self.get_ascension_mode()
                    self.ascensions += 1
                    print(f'{timestamp()}: Ascended {self.ascensions} times.')
                    time.sleep(5)
                    self.save_game(path=self.save_file)
                    self.dragon_level = 0
                    self.dragon_upgrades_complete = False
            elif self.attempt_1T_achievement:
                self.driver.execute_script("javascript:Game.Ascend(true);")
                self.ascension_mode = None
                input("Waiting on user for 'When the cookies ascend just right' achievement.")
                self.get_ascension_mode()
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
        if self.ascension_mode is None:
            try:
                self.ascension_mode = self.driver.execute_script("javascript:return Game.ascensionMode;")
            except JavascriptException:
                return None

    def click_cookie(self):
        def click_golden_cookie():
            js_code = "for (var sx in Game.shimmers) {" \
                      f"var s = Game.shimmers[sx];" \
                      "if (s.force == 'cookie storm drop') {s.pop();}" \
                      "else if (s.type != 'golden' || s.life < Game.fps || !Game.Achievements['Early bird'].won) " \
                      "{s.pop(); return;}" \
                      "else if ((s.life/Game.fps)<(s.dur-2) && (Game.Achievements['Fading luck'].won)) {" \
                      "s.pop(); return;}}"

            if self.time_next_save - (SECONDS_BTWN_SAVES - 5) < time.time():
                # Avoid multiple saves per second with every golden cookie
                self.save_game(path=self.save_file)

            try:
                self.driver.execute_script(f"javascript:{js_code}")
            except JavascriptException:
                print(f"{timestamp()}: Failed to click golden cookie.")

        try:
            # Check for page crashes
            if self.driver.title == "Error":  # Check if the title indicates a crash
                print(f"{timestamp()}: Page crashed, reloading without saving...")
                self.reload_cookieclicker(skip_save=True)
                return

            if (not self.is_veil_active or self.season_active) and (self.ascension_mode == 0 or self.true_neverclick):
                # Initialize buff state when starting fresh
                click = True
                while click:
                    try:
                        # Batch JavaScript execution into a single call
                        result = self.driver.execute_script("""
                            Game.ClickCookie();
                            if (Game.TickerEffect) Game.tickerL.click();
                            return {
                                shimmers: Game.shimmers,
                                cookies: Game.cookies,
                                craftyPixies: 'Crafty pixies' in Game.buffs
                            };
                        """)

                        shimmers = result['shimmers']
                        cookies = result['cookies']
                        self.crafty_pixies = result['craftyPixies']
                        self.cookie_click_errors = 0
                    except JavascriptException:
                        print(f"{timestamp()}: Error clicking cookie or checking shimmers.")
                        self.cookie_click_errors += 1
                        if self.cookie_click_errors >= 5:
                            self.reload_cookieclicker(skip_save=self.time_next_save - time.time() > 30)
                        continue
                    except (Exception, WebDriverException, urllib3.exceptions.ProtocolError, RemoteDisconnected) as e:
                        # Handle specific exceptions related to session crashes
                        if "session deleted" in str(e) or "page crash" in str(e):
                            print(f"{timestamp()}: Detected page crash: {e}. Reloading without saving...")
                            self.reload_cookieclicker(skip_save=True)
                            return
                        elif isinstance(e, (urllib3.exceptions.ProtocolError, RemoteDisconnected)):
                            print(f"{timestamp()}: Connection error: {str(e)}. Reloading.")
                            self.reload_cookieclicker(skip_save=True)
                            return
                        else:
                            print(f"{timestamp()}: Unexpected error: {str(e)}. Reloading.")
                            self.reload_cookieclicker(skip_save=self.time_next_save - time.time() > 30)
                            return

                    # Handle golden cookies and update buff state only when needed
                    if shimmers and self.click_golden_cookies:
                        if self.attempt_1T_achievement:
                            if cookies <= 900000000000:
                                click_golden_cookie()
                            self.trillion_cookie_ascension()
                        else:
                            click_golden_cookie()

                        active_buff_count = self.get_active_buffs()

                        # Store previous buff counts if not initialized
                        if not hasattr(self, 'previous_buff_counts'):
                            self.previous_buff_counts = {
                                'f': self.f_count,
                                'bs': self.bs_count,
                                'dh': self.dh_count,
                                'df': self.df_count,
                                'cf': self.cf_count,
                                'ef': self.ef_count,
                                'cursed': self.cursed_finger_count,
                                'debuff': self.debuff_count
                            }

                        # Check if any buff counts changed
                        buffs_changed = (
                            self.f_count != self.previous_buff_counts['f'] or
                            self.bs_count != self.previous_buff_counts['bs'] or
                            self.dh_count != self.previous_buff_counts['dh'] or
                            self.df_count != self.previous_buff_counts['df'] or
                            self.cf_count != self.previous_buff_counts['cf'] or
                            self.ef_count != self.previous_buff_counts['ef'] or
                            self.cursed_finger_count != self.previous_buff_counts['cursed'] or
                            self.debuff_count != self.previous_buff_counts['debuff']
                        )

                        if self.debuff_active:
                            print(f"{timestamp()}: {Fore.LIGHTRED_EX}Reloading to avoid debuffs: {', '.join(self.active_debuffs)}"
                                  f"{Style.RESET_ALL}")
                            self.load_save()
                            # Run cleanup periodically
                            self.cleanup()
                            self.get_active_buffs()
                            print(f"{timestamp()}: {Fore.LIGHTGREEN_EX}Active buffs after reload: {', '.join(self.active_buffs)}"
                                  f"{Style.RESET_ALL}")
                        elif buffs_changed:
                            if self.cursed_finger_count > self.previous_buff_counts['cursed']:
                                # Find Cursed Finger buff time from active_buffs
                                for buff in self.active_buffs:
                                    if buff.startswith('Cursed finger'):
                                        # Extract time from "Cursed finger (123.4s)"
                                        time_str = buff.split('(')[1].rstrip('s)')
                                        buff_time = float(time_str)
                                        self.delay_product_purchase_until_after = time.time() + buff_time
                                        print(f"{timestamp()}: Delaying purchases for {buff_time:.1f}s due to Cursed Finger buff")
                                        break
                            self.next_cps_update = time.time()
                            self.set_cps_multiplier()
                            if self.active_buffs:
                                print(f"{timestamp()}: {Fore.LIGHTGREEN_EX}Active buffs: {', '.join(self.active_buffs)}"
                                      f"{Style.RESET_ALL}")

                                # Batch pantheon and spell checks together
                                if not self.debuff_active and active_buff_count >= 2 and self.swaps_left == 3:
                                    self.cast_spell(spell_to_cast="hand of fate", exhaust_magic=False)
                                    self.pantheon()

                            # Update previous buff counts
                            self.previous_buff_counts.update({
                                'f': self.f_count,
                                'bs': self.bs_count,
                                'dh': self.dh_count,
                                'df': self.df_count,
                                'cf': self.cf_count,
                                'ef': self.ef_count,
                                'cursed': self.cursed_finger_count,
                                'debuff': self.debuff_count
                            })

                    click = any([self.cf_active, self.df_active, self.cursed_finger_active])

                    # Handle cursed finger upgrades
                    if self.cursed_finger_active and self.cursed_finger_upgrades_next_time <= time.time():
                        self.cursed_finger_upgrades_next_time = time.time() + 40
                        self.buy_upgrades()

                    if self.crafty_pixies:
                        self.buy_products()
            elif not self.check_achievements('True Neverclick'):
                shimmers, cookies = self.driver.execute_script("javascript:return [Game.shimmers, Game.cookies]")

                if shimmers and self.click_golden_cookies:
                    if self.attempt_1T_achievement:
                        if cookies <= 900000000000:
                            click_golden_cookie()
                        self.trillion_cookie_ascension()
                    else:
                        click_golden_cookie()
        except (Exception, WebDriverException, urllib3.exceptions.ProtocolError, RemoteDisconnected) as e:
            # Handle specific exceptions related to session crashes
            if "session deleted" in str(e) or "page crash" in str(e):
                print(f"{timestamp()}: Detected page crash: {e}. Reloading without saving...")
                self.reload_cookieclicker(skip_save=True)
            elif isinstance(e, (urllib3.exceptions.ProtocolError, RemoteDisconnected)):
                print(f"{timestamp()}: Connection error: {str(e)}. Reloading.")
                self.reload_cookieclicker(skip_save=True)
            else:
                print(f"{timestamp()}: Unexpected error: {str(e)}. Reloading.")
                self.reload_cookieclicker(skip_save=self.time_next_save - time.time() > 30)

    def save_game(self, path, click_cookie=True):
        """Save the game and retain the last 60 numbered backup versions."""
        if click_cookie:
            save_code = self.exec_js(script="return Game.WriteSave(1);", default_return="")
        else:
            try:
                save_code = self.driver.execute_script("javascript:return Game.WriteSave(1);")
            except JavascriptException:
                save_code = ""

        if not save_code:
            input("Save code corrupted. Copy save file before continuing.")
            return

        # Ensure the save directory exists
        save_dir = os.path.dirname(path)
        base_name = os.path.basename(path).rsplit('.', 1)[0]  # Remove extension
        extension = path.split('.')[-1] if '.' in path else 'txt'

        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # Rotate backups to retain the last 60 versions
        for i in range(MAX_SAVES - 1, 0, -1):
            old_backup = os.path.join(save_dir, f"{base_name}_{i}.{extension}")
            new_backup = os.path.join(save_dir, f"{base_name}_{i + 1}.{extension}")
            if os.path.exists(old_backup):
                os.rename(old_backup, new_backup)

        # Create a backup of the current save as `progress_1.txt`
        backup_path = os.path.join(save_dir, f"{base_name}_1.{extension}")
        if os.path.exists(path):  # Only back up if the current save exists
            os.replace(path, backup_path)

        # Write the new save to the main save file
        with open(path, mode="w") as progress:
            progress.write(save_code)

        # Update save timing if this is the main save file
        if path == self.save_file:
            self.time_next_save = time.time() + SECONDS_BTWN_SAVES

        # Print save confirmation
        stack = traceback.extract_stack()
        filename, lineno, function_name, code = stack[-2]
        print(
            f"{timestamp()}: {Fore.LIGHTCYAN_EX}Saved game to {path}. Backup created as {backup_path}. Called from line {lineno} "
            f"in {function_name}.{Style.RESET_ALL}")

    def load_save(self):
        if exists(self.save_file):
            try:
                # Read the save file
                with open(file=self.save_file, mode="r") as progress:
                    load_save = progress.read()

                if load_save == "":
                    return

                # Wait for CookieMonster to load by checking for its presence
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.execute_script("return typeof Game.LoadSave == 'function';")
                )

                self.driver.execute_script(f'javascript:Game.LoadSave("{load_save}");')
                print(f"{timestamp()}: Loaded save file.")
            except (JavascriptException, TimeoutException) as e:
                print(f"{timestamp()}: Error loading save: {str(e)}")
                self.reload_cookieclicker(skip_save=True)

    def buy_products(self):
        def refresh_all_buildings():
            return self.exec_js(script="""
                var data = {};
                var buildings = Game.ObjectsById;
                for (var i = 0; i < buildings.length; i++) {
                    var name = buildings[i].name;
                    data[name] = {
                        buy1: CookieMonsterData.Objects1[name] || {},
                        buy10: CookieMonsterData.Objects10[name] || {},
                        buy100: CookieMonsterData.Objects100[name] || {}
                    };
                }
                return data;
            """, default_return={})

        def get_candidates(buildings, building_data):
            blue_candidates = []
            green_candidates = []
            for building in buildings:
                name = building['name']
                b_data = building_data.get(name, {})

                # Extract the colour info from buy100, buy10, and buy1
                buy100_colour = b_data.get('buy100', {}).get('colour')
                buy10_colour = b_data.get('buy10', {}).get('colour')
                buy1_colour = b_data.get('buy1', {}).get('colour')

                # Check for Blue/Green priority from top to bottom (100, 10, 1)
                if buy100_colour == 'Blue':
                    blue_candidates.append((building, 'buy100'))
                elif buy100_colour == 'Green' and not self.upgrades_to_buy:
                    green_candidates.append((building, 'buy100'))
                elif buy10_colour == 'Blue':
                    blue_candidates.append((building, 'buy10'))
                elif buy10_colour == 'Green' and not self.upgrades_to_buy:
                    green_candidates.append((building, 'buy10'))
                elif buy1_colour == 'Blue':
                    blue_candidates.append((building, 'buy1'))
                elif buy1_colour == 'Green' and not self.upgrades_to_buy:
                    green_candidates.append((building, 'buy1'))

            return blue_candidates, green_candidates

        if not self.crafty_pixies:
            self.buy_upgrades()
        else:
            self.upgrades_to_buy = []

        if self.cheat or self.delay_product_purchase_until_after > time.time():
            return

        if self.attempt_endless_cycle and self.check_achievements('Endless cycle'):
            self.endless_cycle_achievement_won = True
            self.attempt_endless_cycle = False

        cookies, cps, min_cookies = self.exec_js(script="return [Game.cookies, "
                                                        "Game.cookiesPs, "
                                                        "CookieMonsterData.Cache['ChainFrenzyRequired']]",
                                                 default_return=[0] * 3)
        if (cookies == 0 and cps == 0) or (min_cookies > cookies):
            return

        if not self.attempt_1T_achievement or (cookies < 900000000000 and cps < 500000000):
            while True:
                if self.attempt_endless_cycle:
                    buildings = self.exec_js(
                        script="return Game.ObjectsById.map(({id, name, amount, price, locked}) => "
                               "({id, name, amount, price, locked}));",
                        default_return=[])
                    # Include amount in products_available
                    products_available = [
                        (building["id"], building["amount"]) for building in buildings
                        if not building["locked"] and building["price"] <= cookies
                    ]

                    for product_id, amount in products_available:
                        if self.dragon_level == self.max_dragon_level - 3:
                            self.exec_js(script=f"Game.ObjectsById[{self.dragon_level - 5}].buy(100);")
                        elif amount < 200 and self.dragon_level < self.max_dragon_level:
                            self.exec_js(script=f"Game.ObjectsById[{product_id}].buy(100);")
                        else:
                            self.exec_js(script=f"Game.ObjectsById[{product_id}].buy(10);")

                    if (time.time() > self.next_garden_tick) or (time.time() > self.time_next_save):
                        break
                else:
                    # Determine blue_candidates and green_candidates based on current data
                    building_data = refresh_all_buildings()
                    buildings = self.exec_js(
                        script="return Game.ObjectsById.map(({id, name, amount, price, locked}) => "
                               "({id, name, amount, price, locked}));",
                        default_return=[])

                    blue_candidates, green_candidates = get_candidates(buildings, building_data)

                    # If no candidates, break out of the while loop
                    if not blue_candidates and (not green_candidates or self.upgrades_to_buy):
                        break

                    purchased = False

                    if (not self.is_veil_active or self.season_active) and (self.ascension_mode == 0 or
                                                                            self.true_neverclick):
                        third_line = 'Game.ClickCookie(); if (check_obj[b].pp < 3600) {'
                    else:
                        third_line = 'if (check_obj[b].pp < 3600) {'

                    script = f"""
                    javascript:
                    function attemptPurchases(check_obj, amount) {{
                        for (var b in check_obj) {{
                            {third_line}
                                Game.Objects[b].buy(amount);
                            }}
                        }}
                    }}
                    attemptPurchases(CookieMonsterData.Objects100, 100);
                    attemptPurchases(CookieMonsterData.Objects10, 10);
                    attemptPurchases(CookieMonsterData.Objects1, 1);
                    """
                    try:
                        self.driver.execute_script(script)
                    except JavascriptException:
                        print(f"{timestamp()}: Failed to execute script: {script}")
                        print(f"{timestamp()}: Failed to buy based on pp.")

                    buildings_to_sell_dict = {building['name']: building for building in self.buildings_to_sell}
                    for building, tier in blue_candidates + green_candidates:
                        # building is an element from your buildings list
                        # tier is one of 'buy1', 'buy10', or 'buy100'

                        # You can easily get the building name and ID:
                        name = building['name']
                        building_id = building['id']

                        # If you need the price or other data:
                        b_data = building_data[name]
                        price = b_data[tier].get('price', float('inf'))

                        if self.crafty_pixies and name in buildings_to_sell_dict:
                            buy_back_quantity = buildings_to_sell_dict[name]['buy_back_quantity']
                            buy = max(buy_back_quantity - building['amount'], 0)
                            if buy > 0:
                                self.exec_js(script=f"Game.ObjectsById[{building_id}].buy({buy});")
                                print(f"{timestamp()}: {Fore.LIGHTGREEN_EX}Buying back {buy} {name}."
                                      f"{Style.RESET_ALL}")
                                continue

                        cookies, min_cookies = self.exec_js(script="return [Game.cookies, "
                                                                   "CookieMonsterData.Cache['ChainFrenzyRequired']]",
                                                            default_return=0)
                        if min_cookies > cookies:
                            print(f"{timestamp()}: Don't purchase buildings until I have more cookies in bank.")
                            return
                        if price <= cookies:
                            amount = 100 if tier == 'buy100' else (10 if tier == 'buy10' else 1)
                            print(f"{timestamp()}: {Fore.GREEN}Buying {amount} {name}(s).{Style.RESET_ALL}")
                            self.exec_js(script=f"Game.ObjectsById[{building_id}].buy({amount});")
                            self.set_buildings_owned()
                            purchased = True
                            # We made a purchase that might change candidates—break out
                            break

                    # If we bought something, re-check candidates with updated data
                    if purchased:
                        if not self.crafty_pixies:
                            self.buy_upgrades()
                        if (time.time() > self.next_garden_tick) or (time.time() > self.time_next_save):
                            break
                        continue
                    else:
                        # No purchases were made, so break out of the outer while loop
                        break

    def buy_upgrades(self):
        self.check_for_upgrades()
        cookies = self.exec_js(script="return Math.round(Game.cookiesd);", default_return=float('inf'))
        if not self.attempt_1T_achievement or cookies < 900000000000:
            if self.upgrades_to_buy:
                for upgrade in self.upgrades_to_buy:
                    if self.exec_js(script=f'return Game.UpgradesById["{upgrade["id"]}"].canBuy();',
                                    default_return=False):
                        print(f"{timestamp()}: {Fore.GREEN}Buying upgrade {upgrade['name']}.{Style.RESET_ALL}")
                        self.exec_js(script=f"Game.UpgradesById[{upgrade['id']}].buy(true);")
                    if not self.cursed_finger_active:
                        self.click_cookie()

    def check_for_upgrades(self):
        def best_buy_overrides():
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

            avg_clicks = self.exec_js(script="return CookieMonsterData.Cache.AverageClicks", default_return=1)

            avg_clicks = 1 if avg_clicks == 0 else avg_clicks

            for override in avg_clicks_overrides_0_01:
                self.click_cookie()
                self.overrides[override] = avg_clicks * 0.01

            for override in avg_clicks_overrides_0_1:
                self.click_cookie()
                self.overrides[override] = avg_clicks * 0.1

        def avoid_buy(upgrade_id):
            if upgrade_id in {71, 73}:
                return (self.check_achievements("Elder nap") and self.check_achievements("Grandmapocalypse") and
                        self.check_achievements("Elder slumber") and self.check_achievements("Elder calm"))
            elif upgrade_id == 74:
                return (self.check_achievements("Elder nap") and self.check_achievements("Elder slumber") and
                        self.is_upgrade_unlocked("Elder Covenant"))
            elif upgrade_id == 84:
                elder_pledge = self.exec_js(script="return Game.Upgrades['Elder Pledge'].bought", default_return=False)
                avoid = (elder_pledge or self.check_achievements("Elder calm"))
                return avoid
            elif upgrade_id == 227:
                return True
            elif upgrade_id == 563:
                return self.check_achievements("Thick-skinned")
            elif upgrade_id == 331:
                return True
            elif upgrade_id in {182, 183, 184, 185, 209}:  # Avoid buying seasons as an upgrade.
                return True
            else:
                return False

        upgrades_in_store = self.exec_js(script="return Game.UpgradesInStore.map(({id, name, bought}) => "
                                                "({id, name, bought}));", default_return=[])

        self.upgrades_to_buy = []

        if self.attempt_1T_achievement or not upgrades_in_store:
            return

        upgrades_owned = self.exec_js(script="return Game.UpgradesOwned;", default_return=0)

        if upgrades_owned != 0 or self.check_achievements('Hardcore') or self.ascension_mode == 0:
            cps = self.exec_js(script="return Game.cookiesPs", default_return=1)
            if cps is None:
                cps = float('inf')
            for upgrade in upgrades_in_store:
                if self.cursed_finger_active:
                    if upgrade['id'] in self.cost_scaling_upgrades:
                        self.upgrades_to_buy.append(upgrade)
                    continue

                self.click_cookie()

                if upgrade['bought']:
                    continue

                if '"' in upgrade['name']:
                    js = f"return CookieMonsterData.Upgrades['{upgrade['name']}'];"
                else:
                    js = f'return CookieMonsterData.Upgrades["{upgrade["name"]}"];'

                cookie_monster_data = self.exec_js(script=js)
                if not cookie_monster_data:
                    print(f"{timestamp()}: {Fore.LIGHTRED_EX}CookieMonsterData is None for {upgrade['name']}."
                          f"{Style.RESET_ALL}")
                    return

                if upgrade['name'] in self.overrides:
                    best_buy_overrides()
                    (price,
                     cookies,
                     wrinklers_total) = self.exec_js(script="return ["
                                                            f"Game.UpgradesById[{upgrade['id']}].getPrice(),"
                                                            "Game.cookies,"
                                                            "CookieMonsterData.Cache.WrinklersTotal]",
                                                     default_return=[float('inf'), 0, 0])

                    if price == float('inf'):
                        return

                    if cookies is None:
                        cookies = float('inf')

                    try:
                        cookie_monster_data["bonus"] = self.overrides[upgrade['name']] * cps
                    except TypeError:
                        print(f"{timestamp()}: Error calculating bonus for {upgrade['name']}. CPS: {cps}.")
                    try:
                        if cookie_monster_data["bonus"] is None or cookie_monster_data["bonus"] == 0:
                            cookie_monster_data["bonus"] = cps * 0.01
                            print(f"{timestamp()}: Forced bonus for {upgrade['name']}")
                    except KeyError:
                        cookie_monster_data["bonus"] = cps * 0.01
                        print(f"{timestamp()}: KeyError bonus for {upgrade['name']}")
                    if cps > 0:
                        cookie_monster_data["pp"] = (max(price - (cookies + wrinklers_total), 0) / cps) + (
                                price / cookie_monster_data["bonus"])
                    else:
                        cookie_monster_data["pp"] = 0
                if cookie_monster_data and cookie_monster_data["colour"] in {"Gray", "Blue"} and \
                        not avoid_buy(upgrade['id']) and \
                        not upgrade["bought"]:
                    if upgrade['id'] in self.cursor_upgrades or upgrade['id'] in self.clicking_upgrades or (
                            cookie_monster_data["pp"] and cookie_monster_data["pp"] > 0):
                        self.upgrades_to_buy.append(upgrade)

    def check_season(self):
        try:
            self.season_active = self.driver.execute_script('javascript:return Game.season')
        except JavascriptException:
            self.season_active = ''
        return self.season_active

    def harvest_lumps(self):
        (age,
         lump_mature_age,
         current_lumps,
         lump_type) = self.exec_js(script="return [Date.now() - Game.lumpT, Game.lumpMatureAge, Game.lumps, "
                                          "Game.lumpCurrentType];", default_return=[0, float('inf'), float('inf'), 0])

        if current_lumps is None:
            current_lumps = float('inf')

        if age >= lump_mature_age:
            if lump_type in (1, 3):
                new_lump_goal = current_lumps + 2
            elif lump_type == 2:
                new_lump_goal = current_lumps + 7
            elif lump_type == 4:
                new_lump_goal = current_lumps + 3
            else:
                new_lump_goal = current_lumps + 1

            self.save_game(path=self.save_file)
            self.exec_js(script="Game.clickLump();")
            new_lumps = int(self.exec_js(script="return Game.lumps;", default_return=float('inf')))
            if new_lumps is None:
                new_lumps = float('inf')
            if new_lump_goal > new_lumps:
                self.load_save()
            else:
                self.check_and_level_up(current_lumps)

    def stock_market(self):
        market = 'Game.Objects["Bank"].minigame'

        # Only check market every 1 minute unless specific conditions are met
        current_time = time.time()
        if current_time < getattr(self, 'next_market_check', 0):
            return
        self.next_market_check = current_time + 60  # 1 minute

        goods_by_id = f'{market}.goodsById'
        goods_price_list = {
            1: {
                0: [5.715947633009222, 58.21594763300922],
                1: [5.463224287314716, 67.96322428731472],
                2: [4.685619073199035, 72.18561907319904],
                3: [6.6360689548138225, 79.13606895481382],
                4: [6.48394593462271, 81.48394593462271],
                5: [6.275280183235054, 91.27528018323505],
                6: [6.508468838821159, 99.00846883882116],
                7: [8.628925211703006, 101.128925211703],
                8: [11.664012884841895, 101.6640128848419],
                9: [16.52489407557823, 104.02489407557823],
                10: [21.597884359806926, 106.59788435980693],
                11: [23.2777804001052, 110.7777804001052],
                12: [26.690503641517694, 119.1905036415177],
                13: [36.53516565208167, 124.03516565208167],
                14: [42.54936417881606, 135.04936417881606],
                15: [52.00008711317622, 142.00008711317622],
                16: [59.751634095020904, 152.2516340950209],
                17: [70.56943831982994, 163.06943831982994]
            },
            2: {
                0: [5.518431451349812, 60.51843145134981],
                1: [4.840774523718409, 67.34077452371841],
                2: [4.732555070334826, 77.23255507033483],
                3: [4.684166420893291, 84.68416642089329],
                4: [6.067860464626904, 88.5678604646269],
                5: [5.575513362811932, 93.07551336281193],
                6: [5.495895368007098, 102.9958953680071],
                7: [6.832513686492973, 101.83251368649297],
                8: [10.583587029272849, 105.58358702927285],
                9: [15.888693896578161, 108.38869389657816],
                10: [20.178824627383733, 110.17882462738373],
                11: [25.553033423223326, 113.05303342322333],
                12: [37.202938958684854, 119.70293895868485],
                13: [45.08484145042354, 127.58484145042354],
                14: [43.28441917757101, 138.284419177571],
                15: [53.50007875678858, 146.00007875678858],
                16: [55.54456952865246, 155.54456952865246],
                17: [63.57495493680062, 168.57495493680062]
            },
            3: {
                0: [4.5241061749019025, 59.5241061749019],
                1: [4.316879164492434, 66.81687916449243],
                2: [5.987938062910473, 75.98793806291047],
                3: [6.992633210810112, 74.49263321081011],
                4: [5.109849329366426, 85.10984932936643],
                5: [7.039696844821549, 92.03969684482155],
                6: [5.941803472686843, 103.44180347268684],
                7: [7.960675748269864, 105.46067574826986],
                8: [9.579376671169541, 107.07937667116954],
                9: [11.701240882630088, 109.20124088263009],
                10: [25.180312458373578, 110.18031245837358],
                11: [25.239864674985597, 117.7398646749856],
                12: [35.4663653868289, 122.9663653868289],
                13: [42.580567007560944, 125.08056700756094],
                14: [49.04778934190023, 136.54778934190023],
                15: [60.42053715312284, 145.42053715312284],
                16: [66.23680483289922, 153.73680483289922],
                17: [68.27153795624054, 158.27153795624054]
            },
            4: {
                0: [6.0010398169646635, 61.00103981696466],
                1: [4.561514007923591, 64.56151400792359],
                2: [5.482400246757777, 77.98240024675778],
                3: [6.43200829572973, 83.93200829572973],
                4: [7.2721635363676, 87.2721635363676],
                5: [6.961616681151554, 96.96161668115155],
                6: [11.64575478567383, 96.64575478567383],
                7: [8.055681827972762, 108.05568182797276],
                8: [7.616569142236273, 112.61656914223627],
                9: [8.597258851587526, 111.09725885158753],
                10: [16.518265682331446, 114.01826568233145],
                11: [13.778261125368886, 118.77826112536889],
                12: [32.65241343950987, 122.65241343950987],
                13: [35.771115519400496, 130.7711155194005],
                14: [39.34868526073575, 141.84868526073575],
                15: [50.84272457471212, 148.34272457471212],
                16: [74.72387931218827, 162.22387931218827],
                17: [76.19305223611923, 166.19305223611923]
            },
            5: {
                0: [4.128331499479231, 64.12833149947923],
                1: [4.8803772160297285, 64.88037721602973],
                2: [5.986283751720123, 73.48628375172012],
                3: [6.119771971158826, 81.11977197115883],
                4: [5.986882598930833, 85.98688259893083],
                5: [6.320868450971005, 93.820868450971],
                6: [5.7214431826141094, 103.22144318261411],
                7: [8.742373127661438, 111.24237312766144],
                8: [10.581826142922921, 113.08182614292292],
                9: [15.444881907719719, 115.44488190771972],
                10: [23.65668261064411, 116.15668261064411],
                11: [30.0238089823913, 120.0238089823913],
                12: [37.22229781474425, 127.22229781474425],
                13: [43.619712304573625, 131.11971230457362],
                14: [58.04367584815361, 140.5436758481536],
                15: [55.547019619433854, 143.04701961943385],
                16: [69.70385521895446, 159.70385521895446],
                17: [70.22082803045794, 162.72082803045794]
            },
            6: {
                0: [4.27338733150313, 59.27338733150313],
                1: [4.95428336700877, 72.45428336700877],
                2: [6.221337336476239, 71.22133733647624],
                3: [4.762999299324747, 79.76299929932475],
                4: [6.152052562956953, 91.15205256295695],
                5: [4.676659545085499, 89.6766595450855],
                6: [6.456871477210882, 108.95687147721088],
                7: [10.1878395667772, 115.1878395667772],
                8: [6.918109250829502, 114.4181092508295],
                9: [10.372978039991096, 117.8729780399911],
                10: [15.085541727658438, 120.08554172765844],
                11: [26.09399593254102, 116.09399593254102],
                12: [43.10521905915266, 123.10521905915266],
                13: [35.88256493102267, 135.88256493102267],
                14: [58.76074064279811, 143.7607406427981],
                15: [66.58051965695864, 146.58051965695864],
                16: [59.05073399360214, 159.05073399360214],
                17: [72.84696704971458, 172.84696704971458]
            },
            7: {
                0: [5.90659199661161, 63.40659199661161],
                1: [5.955336317504674, 73.45533631750467],
                2: [6.021847180888386, 73.52184718088839],
                3: [5.392729060549129, 77.89272906054913],
                4: [6.846764030814711, 86.84676403081471],
                5: [5.794921382881512, 95.79492138288151],
                6: [7.319597942154985, 107.31959794215499],
                7: [8.020498127148244, 113.02049812714824],
                8: [10.641827351949246, 115.64182735194925],
                9: [16.397534206445073, 118.89753420644507],
                10: [34.21901953777274, 121.71901953777274],
                11: [33.57408691257717, 123.57408691257717],
                12: [40.82401883254124, 130.82401883254124],
                13: [48.28910648830396, 130.78910648830396],
                14: [52.93154451564726, 140.43154451564726],
                15: [66.03550350724782, 148.53550350724782],
                16: [74.71399911053663, 157.21399911053663],
                17: [83.60157893222237, 168.60157893222237]
            },
            8: {
                0: [5.076744452100911, 62.57674445210091],
                1: [4.415209552283045, 64.41520955228305],
                2: [5.786154137855533, 70.78615413785553],
                3: [5.155872785555232, 82.65587278555523],
                4: [7.0623387555228305, 89.56233875552283],
                5: [6.336574608593253, 98.83657460859325],
                6: [7.37871474510257, 102.37871474510257],
                7: [6.9168116732480485, 116.91681167324805],
                8: [12.601971520820655, 122.60197152082065],
                9: [23.11966985097763, 123.11966985097763],
                10: [29.60415738096043, 127.10415738096043],
                11: [38.092452929648005, 125.592452929648],
                12: [41.74348403735297, 131.74348403735297],
                13: [49.11053864624108, 136.61053864624108],
                14: [51.020271900688044, 141.02027190068804],
                15: [59.99462084547855, 147.49462084547855],
                16: [63.6101000376737, 156.1101000376737],
                17: [77.91406152561206, 170.41406152561206]
            },
            9: {
                0: [5.458099280051101, 65.4580992800511],
                1: [6.081215851965538, 73.58121585196554],
                2: [5.158056664400135, 75.15805666440014],
                3: [6.528383024817515, 89.02838302481751],
                4: [6.39671451422862, 91.39671451422862],
                5: [6.930644916184633, 99.43064491618463],
                6: [8.239151901815859, 108.23915190181586],
                7: [10.873544833321944, 120.87354483332194],
                8: [12.410402853703829, 124.91040285370383],
                9: [16.881019970963848, 126.88101997096385],
                10: [34.65682339635657, 127.15682339635657],
                11: [46.74100051983379, 126.74100051983379],
                12: [50.89722865615437, 130.89722865615437],
                13: [51.042466166954796, 138.5424661669548],
                14: [45.438242563710105, 145.4382425637101],
                15: [69.75972594915811, 149.7597259491581],
                16: [74.42423257889942, 164.42423257889942],
                17: [71.22242123955863, 176.22242123955863]
            },
            10: {
                0: [4.58697871502298, 64.58697871502298],
                1: [4.286992717823267, 66.78699271782327],
                2: [5.766769167703984, 78.26676916770398],
                3: [5.942155205691961, 83.44215520569196],
                4: [6.3293083837086215, 91.32930838370862],
                5: [5.190370858630274, 97.69037085863027],
                6: [5.4492767486305524, 112.94927674863055],
                7: [14.387725061349784, 124.38772506134978],
                8: [13.311971915674008, 123.31197191567401],
                9: [25.281707701780704, 127.7817077017807],
                10: [27.397320736852976, 127.39732073685298],
                11: [36.79752333872676, 131.79752333872676],
                12: [42.537004292388644, 137.53700429238864],
                13: [57.26604971311457, 139.76604971311457],
                14: [59.635889833514966, 144.63588983351497],
                15: [66.44513890329159, 156.4451389032916],
                16: [80.57786638256164, 163.07786638256164],
                17: [85.95233427465638, 175.95233427465638]
            },
            11: {
                0: [5.987860888679791, 60.98786088867979],
                1: [6.443988953163824, 71.44398895316382],
                2: [5.5869212673126185, 73.08692126731262],
                3: [6.282697717172027, 81.28269771717203],
                4: [7.025794380483433, 89.52579438048343],
                5: [7.243167775463405, 97.2431677754634],
                6: [8.335208234921652, 108.33520823492165],
                7: [7.703679606527885, 112.70367960652788],
                8: [25.696125754056766, 123.19612575405677],
                9: [20.023506294144113, 132.5235062941441],
                10: [33.78496779103665, 131.28496779103665],
                11: [42.66408072772691, 137.6640807277269],
                12: [45.60268069906857, 138.10268069906857],
                13: [53.86669620127901, 143.866696201279],
                14: [59.42945255468834, 146.92945255468834],
                15: [67.43502317778751, 154.9350231777875],
                16: [76.96415021326754, 161.96415021326754],
                17: [82.16247152132644, 169.66247152132644]
            }
        }


        # Cache achievement checks in one call
        achievements = self.exec_js(script="""
            return {
                ipo: Game.Achievements['Initial public offering'].won,
                rookie: Game.Achievements['Rookie numbers'].won,
                nobility: Game.Achievements['No nobility in poverty'].won,
                warehouses: Game.Achievements['Full warehouses'].won,
                makeDay: Game.Achievements['Make my day'].won,
                buyBuy: Game.Achievements['Buy buy buy'].won,
                pyramid: Game.Achievements['Pyramid scheme'].won,
                liquid: Game.Achievements['Liquid assets'].won,
                debt: Game.Achievements['Debt evasion'].won,
                gaseous: Game.Achievements['Gaseous assets'].won
            }
        """, default_return={})

        all_achieved = all(value == 1 for value in achievements.values())

        if not all_achieved or True:
            cursor_level, cursor_amount = self.exec_js(script="return [Game.Objects['Cursor'].level, "
                                                              "Game.Objects['Cursor'].amount]", default_return=[-1, -1])

            if cursor_level == -1 or cursor_amount == -1:
                return

            office_level, max_office_level = self.exec_js(script=f"return [{market}.officeLevel, "
                                                                 f"{market}.offices.length-1]", default_return=[2, 1])

            try:
                if office_level < max_office_level:
                    cost = self.exec_js(script=f"return {market}.offices[{office_level}].cost;", default_return=False)
                    if cost and 820 >= cursor_amount >= cost[0] and cursor_level >= cost[1]:
                        self.exec_js(script="l('bankOfficeUpgrade').click();")
            except JavascriptException:
                print(f"{timestamp()}: Failed to upgrade office.")

            state = self.exec_js(
                f"""
                return {{
                    next_tick: ((Game.fps*{market}.secondsPerTick)-{market}.tickT+30)/30,
                    brokers: {market}.brokers,
                    max_brokers: {market}.getMaxBrokers(),
                    broker_price: {market}.getBrokerPrice() * 100,
                    cookies: Game.cookies,
                    lumps: Game.lumps
                    }}
                """
            )

            if state:
                next_tick = state['next_tick']
                brokers = state['brokers']
                max_brokers = state['max_brokers']
                broker_price = state['broker_price']
                cookies = state['cookies']
                lumps = state['lumps'] if state['lumps'] is not None else float('inf')
            else:
                return

            if cookies is None:
                return
            try:
                if lumps == float('inf') and brokers <= 1300:
                    self.exec_js(f"""
                        for (let i = {market}.brokers; i <= {market}.getMaxBrokers(); i++) {{
                            l('bankBrokersBuy').click();
                        }};
                    """)
                if brokers < max_brokers and brokers <= 1300:
                    if broker_price < cookies:
                        self.exec_js(script="l('bankBrokersBuy').click();")
                        print(f"{timestamp()}: Bought a broker.")
                    # else:
                    #     print(f"{timestamp()}: Broker price: {broker_price / 100}; Cookies: {cookies}.")
                overhead = 0.2 * math.pow(.95, brokers)

                if next_tick > 10:
                    return
            except (JavascriptException, NoSuchElementException, ElementClickInterceptedException):
                print(f"{timestamp()}: Failed to buy broker.")
                overhead = 0.2
                self.click_cookie()

            bank_level = int(self.exec_js(script="return Game.Objects['Bank'].level"))
            if not bank_level:
                return
            elif bank_level > 11:
                bank_level = 11

            number_of_goods = self.exec_js(script=f"return {goods_by_id}.length")
            if not number_of_goods:
                return

            try:
                min_shares = 10000
                for i in range(number_of_goods):
                    self.click_cookie()
                    min_shares = min(min_shares,
                                     self.exec_js(script=f"return {goods_by_id}[{i}].stock", default_return=10000))

                for i in range(number_of_goods):
                    self.click_cookie()
                    if self.exec_js(script=f"return {goods_by_id}[{i}].active && !{goods_by_id}[{i}].hidden"):
                        good_id = i
                        (good_name, good_symbol, stock_price, stock_shares,
                         stock_max) = self.exec_js(script=f"return [{goods_by_id}[{i}].name, "
                                                          f"{goods_by_id}[{i}].symbol, "
                                                          f"{goods_by_id}[{i}].val, "
                                                          f"{goods_by_id}[{i}].stock, "
                                                          f"{market}.getGoodMaxStock({market}.goodsById[{good_id}])];",
                                                   default_return=[None, None, float('inf'), -1, -1])

                        buy_price = goods_price_list[bank_level][good_id][0]
                        sell_price = goods_price_list[bank_level][good_id][1]

                        if (stock_price <= buy_price and stock_shares != stock_max) or (
                                not achievements['buyBuy'] and
                                stock_price * (1 + overhead) * (stock_max - stock_shares) >= 86400
                        ):
                            print(f'{timestamp()}: {Fore.GREEN}Buying {good_name} ({good_symbol}) at '
                                  f'{stock_price:.2f} < {buy_price}.{Style.RESET_ALL}')
                            self.exec_js(script=f"{market}.buyGood({good_id}, {stock_max});")
                        elif stock_shares > 0 and stock_price >= sell_price:
                            if achievements['nobility'] or min_shares >= 500 or all_achieved:
                                print(f'{timestamp()}: {Fore.RED}Selling {good_name} ({good_symbol}) at '
                                      f'{stock_price:.2f} > {sell_price}.{Style.RESET_ALL}')
                                self.exec_js(script=f"{market}.sellGood({good_id}, {stock_max});")
                        else:
                            self.click_cookie()
            except (JavascriptException, WebDriverException):
                print(f"{timestamp()}: Stock market method failure.")
                self.click_cookie()

    def upgrade_santa(self):
        if self.exec_js(script='return (Game.Upgrades["A festive hat"].bought && '
                               '!Game.Upgrades["Santa\'s dominion"].unlocked);'):
            self.exec_js(script='Game.specialTab = "santa"; Game.UpgradeSanta(); Game.ToggleSpecialMenu(0);')

    def train_dragon(self):
        if self.farming_goal == "lumps":
            self.final_wanted_aura = 17  # dragon's curve
        else:
            self.final_wanted_aura = 1  # Breath of Milk
            # if self.buildings_owned > 12000:
            #     self.final_wanted_aura = 3  # Elder Battalion
            # else:
            #     self.final_wanted_aura = 1  # Breath of Milk

        if self.attempt_endless_cycle and self.check_achievements('Endless cycle'):
            self.endless_cycle_achievement_won = True
            self.attempt_endless_cycle = False

        try:
            crumbly_egg_unlocked = self.is_upgrade_unlocked("A crumbly egg")
            if crumbly_egg_unlocked:
                self.dragon_auras_lookup = self.exec_js(script="return Game.dragonAurasBN;", default_return={})
            if crumbly_egg_unlocked and not self.dragon_complete:
                (self.dragon_level,
                 self.max_dragon_level) = self.exec_js(script="return [Game.dragonLevel, Game.dragonLevels.length-1];",
                                                       default_return=[0, -1])
                self.freeze_check()
                wanted_aura = self.dragon_auras_lookup["No aura"]["id"]
                if self.dragon_level >= 5:
                    wanted_aura = self.dragon_auras_lookup["Breath of Milk"]["id"]
                if self.dragon_level >= 19:
                    wanted_aura = self.dragon_auras_lookup["Radiant Appetite"]["id"]
                if not self.attempt_endless_cycle:
                    if self.dragon_level >= 21:
                        wanted_aura = self.final_wanted_aura

                    if self.final_wanted_aura == self.dragon_auras_lookup["Dragon's Curve"]["id"]:
                        wanted_aura2 = self.dragon_auras_lookup["Reality Bending"]["id"]
                    else:
                        wanted_aura2 = self.dragon_auras_lookup["Radiant Appetite"]["id"]
                else:
                    wanted_aura2 = self.dragon_auras_lookup["Breath of Milk"]["id"]

                self.exec_js(script="Game.specialTab='dragon'; Game.UpgradeDragon();")

                if self.dragon_level < 5:
                    return

                self.set_dragon_auras(dragon_aura=wanted_aura, dragon_aura2=wanted_aura2)
                self.final_wanted_aura2 = wanted_aura2

                if self.dragon_level == self.max_dragon_level and self.dragon_auras[1] == wanted_aura2:
                    self.dragon_complete = True
        except (JavascriptException, KeyError):
            self.click_cookie()

    def pet_the_dragon(self):
        self.dragon_level = int(self.exec_js(script="return Game.dragonLevel;", default_return=0))
        if self.dragon_level >= 8 and not self.dragon_upgrades_complete:
            drops = ['Dragon scale', 'Dragon claw', 'Dragon fang', 'Dragon teddy bear']
            for drop in drops:
                self.click_cookie()
                something_to_get = self.exec_js(script=f"return !Game.Has('{drop}') && !Game.HasUnlocked('{drop}');",
                                                default_return=False)

                if something_to_get:
                    self.exec_js(script="Game.specialTab = 'dragon'; Game.ToggleSpecialMenu(1); Game.ClickSpecialPic();"
                                        "Game.ToggleSpecialMenu(0);")

    def set_cps_multiplier(self):
        """Check if we need to update CPS multiplier based on buff expiration"""
        if time.time() >= self.next_cps_update:
            self.cpsMult = self.exec_js(script="return Game.cookiesPs / Game.unbuffedCps;", default_return=1)
            if self.cpsMult is None:
                self.cpsMult = 1
            self.get_active_buffs()  # Get new buff times and schedule next update


    def set_buildings_owned(self):
        self.buildings_owned = self.exec_js(script="return Game.BuildingsOwned;")

    def all_upgrades_unlocked(self, upgrades):
        unlocked = []
        for u in upgrades:
            self.click_cookie()
            unlocked.append(self.exec_js(script=f'return Game.UpgradesById[{u}].unlocked', default_return=False))

        return all(value for value in unlocked)

    def get_season_cookies(self):
        def get_christmas_cookies(s):
            (cost,
             cps,
             upgrade_157,
             upgrade_270,
             upgrade_159,
             upgrade_52,
             upgrade_53) = self.exec_js(script='return [Game.Upgrades["Festive biscuit"].priceFunc(),'
                                               'Game.unbuffedCps,'
                                               'Game.Has("Reindeer baking grounds"),'
                                               'Game.Has("Starsnow"),'
                                               'Game.Has("Ho ho ho-flavored frosting"),'
                                               'Game.Has("Lucky day"),'
                                               'Game.Has("Serendipity")]',
                                        default_return=[float('inf'), 0, False, False, False, False, False])
            upgrade_86 = 2 if self.exec_js(script='return Game.Has("Get lucky")') else 1
            upgrade_473 = 1.01 if self.exec_js(script='return Game.Has("Green yeast digestives")') else 1
            upgrade_283 = 1.1 if self.exec_js(script='return Game.Has("Lasting fortune")') else 1
            upgrade_411 = 1.01 if self.exec_js(script='return Game.Has("Lucky digit")') else 1
            upgrade_412 = 1.01 if self.exec_js(script='return Game.Has("Lucky number")') else 1
            upgrade_413 = 1.01 if self.exec_js(script='return Game.Has("Lucky payout")') else 1
            try:
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
            clot_cookies = avg_golden_cookies_per_day * .09332 * 0 # Eliminated clots by reloading from save
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
                self.exec_js(script='Game.Upgrades["Festive biscuit"].buy();')
                print(f"{timestamp()}: Switched from {s} to Christmas season")

        def get_halloween_cookies(s):
            self.exec_js(script='Game.Upgrades["Ghostly biscuit"].buy();')
            print(f"{timestamp()}: Switched from {s} to Halloween season")

        def get_valentines_cookies(s):
            self.exec_js(script='Game.Upgrades["Lovesick biscuit"].buy();')
            print(f"{timestamp()}: Switched from {s} to Valentine's season")

        def get_easter_cookies(s):
            self.exec_js(script='Game.Upgrades["Bunny biscuit"].buy();')
            print(f"{timestamp()}: Switched from {s} to Easter season")

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

        if self.exec_js(script='return (!Game.Upgrades["Season switcher"].bought || Game.ascensionMode==1);',
                        default_return=True):
            return

        self.check_season()

        if season_finished(self.season_active):
            if self.season_active == 'christmas' and not season_finished('valentines'):
                get_valentines_cookies(self.season_active)
            elif self.season_active == 'valentines' and not season_finished('easter'):
                get_easter_cookies(self.season_active)
            elif self.season_active == 'easter' and not season_finished('halloween'):
                get_halloween_cookies(self.season_active)
            else:
                get_christmas_cookies(self.season_active)

    def get_dragon_auras(self):
        dragon_aura = None
        dragon_aura2 = None
        if self.dragon_level >= 5:
            dragon_aura, dragon_aura2 = self.exec_js(script="return [Game.dragonAura, Game.dragonAura2];",
                                                     default_return=[None, None])

        self.dragon_auras = {0: dragon_aura, 1: dragon_aura2}

    def set_dragon_auras(self, dragon_aura, dragon_aura2=None):
        if self.delay_aura_change > time.time():
            return

        if self.dragon_level >= 5:
            self.get_dragon_auras()

            try:
                if self.dragon_auras[0] != dragon_aura:
                    self.exec_js(script=f"Game.SetDragonAura({dragon_aura},0);Game.ConfirmPrompt();")

                if not dragon_aura2:
                    return

                if self.dragon_level >= self.max_dragon_level and self.dragon_auras[1] != dragon_aura2:
                    self.exec_js(script=f"Game.SetDragonAura({dragon_aura2},1);Game.ConfirmPrompt();")
            except JavascriptException:
                self.click_cookie()

            self.get_dragon_auras()

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

        gods, self.swaps_left, slots = self.exec_js(script=f"return [{temple}.gods, {temple}.swaps, {temple}.slot];",
                                                    default_return=[None] * 3)

        if any(var is None for var in (gods, self.swaps_left, slots)):
            return

        move_secondary = False

        if self.attempt_endless_cycle and self.check_achievements('Endless cycle'):
            self.endless_cycle_achievement_won = True
            self.attempt_endless_cycle = False

        if self.attempt_endless_cycle:
            try:
                if self.swaps_left > 0:
                    if slots[diamond] != gods[gods_lookup["holobore"]]["id"]:
                        self.exec_js(script=f"{temple}.slotHovered = 0;"
                                            f"{temple}.dragging = {temple}.gods[{gods_lookup['holobore']}];"
                                            f"{temple}.dropGod();")
                    if slots[ruby] != gods[gods_lookup["mokalsium"]]["id"]:
                        self.exec_js(script=f"{temple}.slotHovered = 1;"
                                            f"{temple}.dragging = {temple}.gods[{gods_lookup['mokalsium']}];"
                                            f"{temple}.dropGod();")
                    if slots[jade] != gods[gods_lookup["jeremy"]]["id"]:
                        self.exec_js(script=f"{temple}.slotHovered = 2;"
                                            f"{temple}.dragging = {temple}.gods[{gods_lookup['jeremy']}];"
                                            f"{temple}.dropGod();")
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
                if self.swaps_left == 3:
                    perform_swap = True
                else:
                    perform_swap = False
            elif utc_hour in {1, 13} and utc_min == 12:
                if 20 in {self.dragon_auras[0], self.dragon_auras[1]}:  # Supreme Intellect active
                    new_temple_slot = jade
                else:
                    new_temple_slot = ruby
                if utc_hour == 1 and self.swaps_left == 3:
                    perform_swap = True
                elif utc_hour == 13 and self.swaps_left >= 2:
                    perform_swap = True
                else:
                    perform_swap = False
            elif (utc_hour == 4 and utc_min == 0) or (utc_hour == 10 and utc_min == 20):
                if 20 in {self.dragon_auras[0], self.dragon_auras[1]}:  # Supreme Intellect active
                    new_temple_slot = -1
                else:
                    new_temple_slot = jade
                if utc_hour == 4 and self.swaps_left >= 2:
                    perform_swap = True
                elif utc_hour == 10 and self.swaps_left == 3:
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
                current_slot_id = self.exec_js(script=f"return Number({temple}.gods['{gods_lookup['cyclius']}'].slot);",
                                               default_return=-2)
                try:
                    if new_temple_slot != current_slot_id:
                        if new_temple_slot != -1:
                            print(f"{timestamp()}: Moving Cyclius ({gods_lookup['cyclius']}) to slot "
                                  f"{new_temple_slot}. Previous slot {current_slot_id}")
                            self.exec_js(script=f"{temple}.slotHovered = {new_temple_slot};"
                                                f"{temple}.dragging = {temple}.gods['{gods_lookup['cyclius']}'];"
                                                f"{temple}.dropGod();")
                        elif current_slot_id != -1:
                            if self.is_veil_active:
                                new_god = "holobore"
                            else:
                                new_god = "muridal"

                            if self.swaps_left == 3:
                                print(f"{timestamp()}: Moving {new_god} ({gods_lookup[new_god]}) to slot "
                                      f"{current_slot_id}.")
                                self.exec_js(script=f"{temple}.slotHovered = {current_slot_id};"
                                             f"{temple}.dragging = {temple}.gods['{gods_lookup[new_god]}'];"
                                             f"{temple}.dropGod();")
                            else:
                                print(f"{timestamp()}: Remove Cyclius ({gods_lookup['cyclius']}).")
                                self.exec_js(script=f"{temple}.slotHovered = -1;"
                                             f"{temple}.dragging = {temple}.gods['{gods_lookup['cyclius']}'];"
                                             f"{temple}.dropGod();")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to move god.")
                    return
            elif move_secondary:
                current_slot_id = self.exec_js(script=f"return Number({temple}.gods['{gods_lookup[move_secondary]}']."
                                                      f"slot;", default_return=-2)
                try:
                    if new_temple_slot != current_slot_id:
                        print(f"{timestamp()}: Moving {move_secondary} ({gods_lookup[move_secondary]}) to slot "
                              f"{new_temple_slot}. Previous slot {current_slot_id}")
                        self.exec_js(script=f"{temple}.slotHovered = {new_temple_slot};"
                                            f"{temple}.dragging = {temple}.gods['{gods_lookup[move_secondary]}']"
                                            f";{temple}.dropGod();")
                except JavascriptException:
                    print(f"{timestamp()}: Failed to move Jeremy.")
                    return
        else:
            diamond_god = default_god1 = 'vomitrax'
            mokalsium = gods_lookup['mokalsium']
            active_buff_count = self.get_active_buffs()
            # Check for click buff and total buff count
            has_click_buff = self.cf_count + self.df_count + self.ef_count > 0

            if not self.debuff_active and has_click_buff and self.swaps_left == 3:
                if active_buff_count >= 4:
                    diamond_god = 'godzamok'

            static_gods = [diamond_god, 'muridal', 'selebrak']

            slot_id = 0
            for god in static_gods:
                (god_slot_id,
                 self.swaps_left,
                 skruuia_slot) = self.exec_js(script=f"return [Number({temple}.gods['{gods_lookup[god]}'].slot), "
                                                     f"{temple}.swaps, "
                                                     f"Number({temple}.gods['{gods_lookup['skruuia']}'].slot)];",
                                              default_return=[-1, 0, -1])
                try:
                    if god_slot_id != slot_id:
                        if god == 'godzamok':
                            self.save_game(path="./before_godzamok.txt")
                        elif self.swaps_left < 3 and (self.time_last_wrinkler_popped + (5 * 60) >= time.time()
                                                      or skruuia_slot == -1):
                            return
                        self.exec_js(script=f"{temple}.slotHovered = {slot_id};"
                                            f"{temple}.dragging = {temple}.gods['{gods_lookup[god]}'];"
                                            f"{temple}.dropGod();")
                        print(f"{timestamp()}: Moved {god} from {god_slot_id} to slot {slot_id}.")
                        if god == 'godzamok':
                            self.godzamok_click_bonus()
                            self.exec_js(script=f"{temple}.slotHovered = {slot_id};"
                                                f"{temple}.dragging = {temple}.gods['{mokalsium}'];"
                                                f"{temple}.dropGod();")
                            print(f"{timestamp()}: Moved mokalsium to slot {slot_id}.")
                except JavascriptException:
                    self.click_cookie()
                self.click_cookie()
                slot_id += 1

    def godzamok_click_bonus(self):
        (cookies, lumps, sugar_frenzy, self.cpsMult,
         buildings) = self.exec_js(script="return [Game.cookies, Game.lumps, Game.Upgrades['Sugar frenzy'].unlocked && "
                                          "!Game.Upgrades['Sugar frenzy'].bought, Game.cookiesPs / Game.unbuffedCps,"
                                          "Game.ObjectsById.map(({id, name, amount, level, price, locked}) => "
                                          "({id, name, amount, level, price, locked}))]",
                                   default_return=['Unknown', 100, False, 0, []])

        print(f"{timestamp()}: Attempting Godzamok Click bonus. CPS multi:{self.cpsMult}; "
              f"Possible prestige after ascending: {self.new_prestige}")

        if lumps is None:
            lumps = float('inf')

        self.godzamok_ascension_delay = True

        if self.sugar_frenzy_spend:
            if sugar_frenzy and lumps > 100:
                self.exec_js(script="l('bankLoan1').click();l('bankLoan2').click();l('bankLoan3').click();")
                print(f"{timestamp()}: Activating all three bank loans.")
                if self.exec_js(script="return Game.Upgrades['Sugar frenzy'].buy()") is not None:
                    print(f"{timestamp()}: {Fore.GREEN}Activated sugar frenzy.{Style.RESET_ALL}")
                else:
                    print(f"{timestamp()}: {Fore.RED}Failed to activate sugar frenzy.{Style.RESET_ALL}")
            elif lumps <= 100:
                print(f"{timestamp()}: {Fore.YELLOW}Need more than 100 lumps for sugar frenzy.{Style.RESET_ALL}")
            else:
                print(f"{timestamp()}: {Fore.YELLOW}Sugar frenzy is unavailable.{Style.RESET_ALL}")
        else:
            print(
                f"{timestamp()}: {Fore.YELLOW}Waiting until 50% of the way toward doubling prestige.{Style.RESET_ALL}")

        print(f"{timestamp()}: {Fore.GREEN}Cookies in bank: {humanize.scientific(cookies, precision=5)}."
              f"{Style.RESET_ALL}")

        self.print_prestige = time.time() + 10

        for building in self.buildings_to_sell:
            building_id = building['id']
            self.exec_js(script="") # Forces a cookie click
            if not buildings[building_id]["locked"]:
                if building["name"] == 'Temple':
                    sell_quantity = buildings[building_id]['amount'] - 1
                elif building["name"] == 'Wizard tower':
                    try:
                        if self.interval_id:
                            self.driver.execute_script(f"javascript:clearInterval({self.interval_id});")
                            self.interval_id = None
                    except JavascriptException:
                        print(f"{timestamp()}: Failed to clear autoclicker.")

                    if not self.interval_id:
                        self.autoclicker(amount_of_clicks=150, ms_interval=1)

                    m = self.exec_js(script="return Game.Objects['Wizard tower'].minigame.magic", default_return=0)
                    l = buildings[building_id]["level"]
                    min_magic = np.floor(4 + np.power(1, 0.6) + 15 * np.log(1 + (1 + 10 * (l - 1)) / 15))
                    if m >= min_magic:
                        def magic_at_towers(t):
                            return np.floor(4 + np.power(t, 0.6) + 15 * np.log(1 + (t + 10 * (l - 1)) / 15))

                        # Set bounds for binary search
                        left, right = 1, 1000  # Upper bound handles up to ~150 magic at level 10
                        t_solution = 20  # default fallback

                        # Check if magic requirement is achievable
                        max_possible_magic = magic_at_towers(right)
                        if m > max_possible_magic:
                            print(f"{timestamp()}: {Fore.YELLOW}Warning: Required magic {m} exceeds maximum possible "
                                  f"({max_possible_magic}) at level {l}{Style.RESET_ALL}")
                            t_solution = right
                        else:
                            # Binary search for optimal tower count
                            for _ in range(20):
                                mid = (left + right) // 2
                                magic_mid = magic_at_towers(mid)

                                if magic_mid == m:
                                    t_solution = mid
                                    break
                                elif magic_mid < m:
                                    left = mid + 1
                                else:
                                    right = mid - 1
                                    t_solution = mid  # keep last value that gives enough magic

                        t_solution = max(int(t_solution), 1)
                    else:
                        # Magic is below minimum threshold for current level. Sell all but one Wizard tower
                        t_solution = 1
                        print(f"{timestamp()}: Selling all but one Wizard tower.")
                    sell_quantity = max(buildings[building_id]['amount'] - t_solution, 0)
                    # Wizard tower must be first item in array. This waits to switch the aura until after calculations.
                    print(f"{timestamp()}: {Fore.GREEN}Switching dragon aura to Earth Shatterer."
                          f"{Style.RESET_ALL}")
                    self.set_dragon_auras(dragon_aura=self.dragon_auras_lookup["Earth Shatterer"]["id"])

                else:
                    sell_quantity = buildings[building_id]['amount']

                building['buy_back_quantity'] = max(sell_quantity, 0)

                self.exec_js(script=f"Game.ObjectsById[{building_id}].sell({sell_quantity})")
                print(f"{timestamp()}: {Fore.LIGHTRED_EX}Selling {sell_quantity} {building['name']}."
                      f"{Style.RESET_ALL}")

        print(f"{timestamp()}: {Fore.GREEN}Switching aura back to default.{Style.RESET_ALL}")
        self.set_dragon_auras(dragon_aura=self.final_wanted_aura, dragon_aura2=self.final_wanted_aura2)

        self.cast_spell(spell_to_cast='summon crafty pixies')

        self.exec_js(script="Game.Objects['You'].buy(2);")
        print(f"{timestamp()}: {Fore.LIGHTGREEN_EX}Buying back 2 You.{Style.RESET_ALL}")

        for building in self.buildings_to_sell[::-1]:
            self.exec_js(script="") # Forces a cookie click

            building_id = building['id']
            if buildings[building_id]["locked"]:
                continue

            if building['buy_back_quantity'] > 0:
                self.exec_js(script=f"Game.ObjectsById[{building_id}].buy({building['buy_back_quantity']})")
                print(
                    f"{timestamp()}: {Fore.LIGHTGREEN_EX}Buying back {building['buy_back_quantity']} "
                    f"{building['name']}.{Style.RESET_ALL}")
        self.exec_js(script="Game.Objects['You'].buy(2);")

    def open_mini_games(self):
        minigame_rows = [2, 5, 6, 7]

        for minigame_row in minigame_rows:
            self.click_cookie()
            building = f"Game.ObjectsById[{minigame_row}]"
            self.exec_js(script=f"if (Game.isMinigameReady({building}) && !{building}.onMinigame) "
                                f"{building}.switchMinigame(-1);")

    def quit_game(self, click_cookie=True):
        self.save_game(path=self.save_file, click_cookie=click_cookie)
        self.driver.quit()

    def pop_fattest_wrinkler(self):
        temple = "Game.Objects['Temple'].minigame"
        skruuia = "scorn"

        (self.swaps_left,
         skruuia_slot,
         cookies_before) = self.exec_js(script=f"return [{temple}.swaps, Number({temple}.gods['{skruuia}'].slot), "
                                        f"Game.cookies];", default_return=[0, 0, 0])

        move_gods = self.swaps_left == 3 and skruuia_slot != 0

        if move_gods:
            self.exec_js(script=f"{temple}.slotHovered = 0; {temple}.dragging = {temple}.gods['{skruuia}']; "
                                f"{temple}.dropGod();")
        elif self.season_active != 'halloween':
            return

        if (not self.is_veil_active or self.season_active) and (self.ascension_mode == 0 or self.true_neverclick):
            second_line = 'Game.ClickCookie(); if (Game.wrinklers[i].sucked > 0 && Game.wrinklers[i].type === 0) {'
        else:
            second_line = 'if (Game.wrinklers[i].sucked > 0 && Game.wrinklers[i].type === 0) {'
        js = ('Object.keys(Game.wrinklers).forEach((i) => {'
              f'{second_line}'
              'Game.wrinklers[i].hp = 0;'
              '}'
              '});')

        try:
            self.driver.execute_script(f'javascript:{js}')
            cookies_after = self.exec_js(script='return Game.cookies;', default_return=0)

            print(f"{timestamp()}: {Fore.LIGHTCYAN_EX}Cookies before popping all wrinklers: "
                  f"{humanize.scientific(cookies_before, precision=5)}. Cookies after popping all wrinklers: "
                  f"{humanize.scientific(cookies_after, precision=5)}.{Style.RESET_ALL}")
            self.time_last_wrinkler_popped = time.time()
        except JavascriptException:
            self.click_cookie()

    def check_and_level_up(self, previous_lumps):
        """Check if lumps increased and level up if needed"""
        current_lumps = self.exec_js(script='return Game.lumps;', default_return=0)
        if current_lumps is None:
            current_lumps = float('inf')
        if current_lumps > previous_lumps:
            counter = 0
            # Keep leveling up while we have enough lumps
            while True:
                pre_level_lumps = self.exec_js(script='return Game.lumps;', default_return=0)
                if pre_level_lumps is None:
                    pre_level_lumps = float('inf')
                self.level_up()
                post_level_lumps = self.exec_js(script='return Game.lumps;', default_return=0)
                if post_level_lumps is None:
                    post_level_lumps = float('inf')
                counter+=1
                # Stop if no lumps were spent
                if pre_level_lumps == post_level_lumps and (post_level_lumps != float('inf') or counter < 20):
                    break

    def level_up(self):
        buildings = {}
        max_cps_per_lump = 0
        max_cps_achievements_cookies = 0
        max_cps_per_lump_achv = 0
        min_level = float('inf')
        sum_cps = 0
        cps_by_type, lumps = self.exec_js(script='return [Game.cookiesPsByType, Game.lumps];',
                                          default_return=[{}, 0])

        if not cps_by_type:
            return

        for building, cps in cps_by_type.items():
            self.click_cookie()
            sum_cps += cps

        for building, cps in cps_by_type.items():
            self.click_cookie()
            if building != '"egg"':
                level = self.exec_js(script=f"return Game.Objects['{building}'].level;", default_return=-1)

                if (building != 'Cursor' and level == 9) or (building == 'Cursor' and level == 19):
                    cps_per_lump = sum_cps * 0.01 / (level + 1)
                elif level == -1:
                    return
                else:
                    cps_per_lump = cps * 0.01 / (level + 1)
                buildings[building] = {'cps': cps,
                                       'level': level,
                                       'cps_per_lump': cps_per_lump}
                max_cps_per_lump = max(max_cps_per_lump, cps_per_lump)
                min_level = min(min_level, level)
                if (building == 'Cursor' and level < 20) or (building != 'Cursor' and level < 10):
                    cps_achievements_cookies = cps
                    cps_per_lump_achv = cps_per_lump
                else:
                    cps_achievements_cookies = 0
                    cps_per_lump_achv = 0
                max_cps_achievements_cookies = max(max_cps_achievements_cookies, cps_achievements_cookies)
                max_cps_per_lump_achv = max(max_cps_per_lump_achv, cps_per_lump_achv)

        if lumps is None:
            self.farming_goal = 'cookies'
            # script = """
            # for (const objectName in Game.Objects) {
            #     const gameObject = Game.Objects[objectName];
            #     for (let i = 0; i < 200; i++) {
            #         gameObject.levelUp();
            #     }
            # }
            # """
            if min_level < math.pow(2, 32):
                script = """
                for (const objectName in Game.Objects) {
                    Game.Objects[objectName].level = 2 ** 32;
                    Game.recalculateGains=1;
                };
                """
                self.exec_js(script)
            return

        if buildings['Wizard tower']['level'] == 0:
            if lumps > 0:
                self.exec_js(script="Game.Objects['Wizard tower'].levelUp();")
        elif buildings['Temple']['level'] == 0:
            if lumps > 0:
                self.exec_js(script="Game.Objects['Temple'].levelUp();")
        elif buildings['Farm']['level'] == 0:
            if lumps > 0:
                self.exec_js(script="Game.Objects['Farm'].levelUp();")
        elif buildings['Bank']['level'] == 0:
            if lumps > 0:
                self.exec_js(script="Game.Objects['Bank'].levelUp();")
        elif buildings['Farm']['level'] < 9:
            if lumps >= buildings['Farm']['level'] + 1:
                self.exec_js(script="Game.Objects['Farm'].levelUp();")
        elif buildings['Cursor']['level'] < 4:
            lumps_credited = buildings['Cursor']['level'] * (buildings['Cursor']['level'] + 1) / 2
            lumps_needed = 4 * 5 / 2
            actual_lumps_needed = lumps_needed - lumps_credited
            if lumps >= actual_lumps_needed:
                self.exec_js(script="Game.Objects['Cursor'].levelUp();")
        elif buildings['Cursor']['level'] < 10:
            lumps_credited = buildings['Cursor']['level'] * (buildings['Cursor']['level'] + 1) / 2
            lumps_needed = 10 * 11 / 2
            actual_lumps_needed = lumps_needed - lumps_credited
            if lumps >= actual_lumps_needed:
                self.exec_js(script="Game.Objects['Cursor'].levelUp();")
        elif buildings['Cursor']['level'] < 12:
            lumps_credited = buildings['Cursor']['level'] * (buildings['Cursor']['level'] + 1) / 2
            lumps_needed = 12 * 13 / 2
            actual_lumps_needed = lumps_needed - lumps_credited
            if lumps >= actual_lumps_needed:
                self.exec_js(script="Game.Objects['Cursor'].levelUp();")
        elif buildings['Farm']['level'] + 1 == 10:
            if lumps >= 104:
                self.exec_js(script="Game.Objects['Farm'].levelUp();")
        elif buildings['Cursor']['level'] < 20:
            if (buildings['Cursor']['level'] + 1 == 13 and lumps >= 107) or (buildings['Cursor']['level'] + 1 <= 20
                                                                             and lumps >= 95 +
                                                                             buildings['Cursor']['level'] + 1):
                self.exec_js(script="Game.Objects['Cursor'].levelUp();")
        elif max_cps_achievements_cookies > 0:
            for building, values in buildings.items():
                self.click_cookie()
                if (values['cps'] == max_cps_achievements_cookies and self.building_level_goal == 'achievements') or (
                        values['cps_per_lump'] == max_cps_per_lump_achv and self.building_level_goal == 'cps'):
                    next_level = values['level'] + 1
                    if (next_level < 10 and lumps >= next_level + 100) or (next_level == 10 and
                                                                           lumps >= next_level + 94):
                        self.exec_js(script=f"Game.Objects['{building}'].levelUp();")
                    elif time.gmtime().tm_min % 5 == 0 and time.gmtime().tm_sec <= 2:
                        lumps_needed = next_level + 100 if next_level < 10 else next_level + 94
                        print(f"{timestamp()}: Saving until {lumps_needed} lumps to upgrade {building} to level "
                              f"{next_level}.")
                else:
                    self.click_cookie()
        else:
            self.farming_goal = 'cookies'
            for building, values in buildings.items():
                self.click_cookie()
                if values['cps_per_lump'] == max_cps_per_lump:
                    next_level = values['level'] + 1
                    reserve_lumps = next_level + 154
                    if lumps >= reserve_lumps:
                        self.exec_js(script=f"Game.Objects['{building}'].levelUp();")
                        print(f"{timestamp()}: Leveled up {building} to {next_level}.")
                    else:
                        print(f"{timestamp()}: All level achievements unlocked. "
                              f"Saving until {reserve_lumps} lumps to upgrade {building} to level {next_level}.")
                else:
                    self.click_cookie()
