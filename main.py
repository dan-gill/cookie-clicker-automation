from cookie_clicker import CookieClicker
import time
from os import getenv
import psutil
from colorama import init as colorama_init
from colorama import Fore, Style

from dotenv import load_dotenv
load_dotenv()
colorama_init()
is_game_on = True
save_and_exit = False
PROGRESS_FILE = getenv("PROGRESS_FILE")
NUMBER_OF_HOURS_TO_RUN = 24 * 7
HOURS_BETWEEN_WRINKLER_POPS = 24
MIN_AVAILABLE_MEMORY_GB = 1.75 * 1024 * 1024 * 1024  # Pre-calculate bytes
# HOURS_BETWEEN_RELOADS = 4  # This helps with the lag issue due to memory usage on Chrome

building_level_goal = "cps"
handle_ascension = True

cookie_clicker = CookieClicker(save_file=PROGRESS_FILE, building_level_goal=building_level_goal,
                               handle_ascension=handle_ascension)

# Load game
cookie_clicker.load_cookieclicker()
# input("pause")

end_time = time.time() + (3600 * NUMBER_OF_HOURS_TO_RUN)
structured_end_time = time.localtime(end_time)
print(f"Game will quit on {structured_end_time.tm_mon}/{structured_end_time.tm_mday} at {structured_end_time.tm_hour}:"
      f"{structured_end_time.tm_min:02}:{structured_end_time.tm_sec:02}.")
# response = input("Do you want a manual run this round (Yes/No)? ")
response = "No"
if response == "Yes":
    prompt_for_save = True
else:
    prompt_for_save = False
# prompt_for_save = ynbox(msg="Do you want a manual run this round?", title="Manual run")

while is_game_on and not save_and_exit:
    current_time = time.time()

    # Check memory less frequently (e.g., every 5 minutes)
    if current_time >= getattr(cookie_clicker, 'next_memory_check', 0):
        cookie_clicker.clear_memory()
        if psutil.virtual_memory().available < MIN_AVAILABLE_MEMORY_GB:
            ts = time.localtime()
            print(f"{ts.tm_hour:02}:{ts.tm_min:02}:{ts.tm_sec:02}: {Fore.YELLOW}Reloading browser because memory is low."
                  f"{Style.RESET_ALL}")
            cookie_clicker.reload_cookieclicker()
            cookie_clicker.delay_product_purchase_until_after = current_time + 30
        cookie_clicker.next_memory_check = current_time + 300  # Check every 5 minutes

    # Batch similar operations together
    # State checks
    cookie_clicker.check_veil()
    cookie_clicker.is_prestige_doubled()
    cookie_clicker.set_cps_multiplier()

    # Timer-based actions
    if cookie_clicker.season_active == 'halloween':
        wrinkler_interval = 1800  # 0.5 hours in seconds
    else:
        wrinkler_interval = HOURS_BETWEEN_WRINKLER_POPS * 3600

    if current_time >= cookie_clicker.time_last_wrinkler_popped + wrinkler_interval:
        cookie_clicker.pop_fattest_wrinkler()

    # Batch mini-game related actions
    if current_time >= getattr(cookie_clicker, 'next_minigame_check', 0):
        cookie_clicker.open_mini_games()
        cookie_clicker.sacrifice_garden()
        cookie_clicker.pantheon()
        cookie_clicker.get_season_cookies()
        cookie_clicker.next_minigame_check = current_time + 60  # Check every minute

    # Batch garden related actions
    if current_time >= getattr(cookie_clicker, 'next_garden_check', 0):
        if cookie_clicker.cpsMult > cookie_clicker.cps_threshold or cookie_clicker.cpsMult <= 1:
            if cookie_clicker.farming_goal == 'lumps':
                cookie_clicker.garden_maintenance(plant_name='bakeberry')
            elif cookie_clicker.farming_goal == 'cookies':
                cookie_clicker.increase_golden_cookie_frequency()
        cookie_clicker.get_plant_details()
        if cookie_clicker.attempt_to_unlock_seeds and cookie_clicker.cpsMult <= 1:
            cookie_clicker.unlock_seeds()
        cookie_clicker.switch_soil()
        cookie_clicker.next_garden_check = current_time + 30  # Check every 30 seconds

    # cookie_clicker.level_up()
    cookie_clicker.harvest_lumps()
    cookie_clicker.train_dragon()
    cookie_clicker.pet_the_dragon()
    cookie_clicker.cast_spell(spell_to_cast="hand of fate", exhaust_magic=False)
    cookie_clicker.four_leaf_cookie()
    if cookie_clicker.attempt_endless_cycle:
        cookie_clicker.ascend()

    # cookie_clicker.cast_spell(spell_to_cast="resurrect abomination", exhaust_magic=False)

    if not prompt_for_save:
        cookie_clicker.click_cookie()

        # Buy upgrades and products
        cookie_clicker.buy_products()
        cookie_clicker.buy_upgrades()

        cookie_clicker.stock_market()

        if current_time >= cookie_clicker.time_next_save:
            cookie_clicker.save_game(path=PROGRESS_FILE)

        # Only check time once per second for these operations
        if current_time >= getattr(cookie_clicker, 'next_second_check', 0):
            if time.gmtime().tm_sec < 5:
                cookie_clicker.close_notes()
            cookie_clicker.next_second_check = current_time + 1

        if current_time >= end_time:
            is_game_on = False
    else:
        # save_and_exit = ynbox(msg="Save game and exit?", title="Exit game")
        response = input("Save game and exit (Yes/No)? ")
        if response == "Yes":
            save_and_exit = True
            break

cookie_clicker.quit_game(click_cookie=not save_and_exit)
