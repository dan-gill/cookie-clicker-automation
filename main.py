from cookie_clicker import CookieClicker
import time
from os import getenv
import psutil
from colorama import init as colorama_init
from colorama import Fore, Style

# PROGRESS_FILE = os.environ["PROGRESS_FILE"]
from dotenv import load_dotenv
load_dotenv()
colorama_init()
PROGRESS_FILE = getenv("PROGRESS_FILE")
is_game_on = True
save_and_exit = False
NUMBER_OF_HOURS_TO_RUN = 168
HOURS_BETWEEN_WRINKLER_POPS = 24
# HOURS_BETWEEN_RELOADS = 4  # This helps with the lag issue due to memory usage on Chrome
MIN_AVAILABLE_MEMORY_GB = 2.375

building_level_goal = "cps"
handle_ascension = False

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
    memory_available = psutil.virtual_memory().available / 1024 / 1024 / 1024
    if memory_available < MIN_AVAILABLE_MEMORY_GB:
        ts = time.localtime()
        print(f"{ts.tm_hour:02}:{ts.tm_min:02}:{ts.tm_sec:02}: {Fore.YELLOW}Reloading browser because memory is low. "
              f"{memory_available} < {MIN_AVAILABLE_MEMORY_GB}{Style.RESET_ALL}")
        cookie_clicker.reload_cookieclicker()
        cookie_clicker.delay_product_purchase_until_after = time.time() + 30
    cookie_clicker.check_veil()
    cookie_clicker.level_up()
    if cookie_clicker.season_active == 'halloween':
        pop_every = 0.5
    else:
        pop_every = HOURS_BETWEEN_WRINKLER_POPS
    if time.time() >= cookie_clicker.time_last_wrinkler_popped + (pop_every * 3600):
        cookie_clicker.pop_fattest_wrinkler()
    cookie_clicker.open_mini_games()
    cookie_clicker.harvest_lumps()
    cookie_clicker.train_dragon()
    # cookie_clicker.check_season_timer()
    cookie_clicker.sacrifice_garden()
    cookie_clicker.pantheon()
    cookie_clicker.get_season_cookies()
    cookie_clicker.pet_the_dragon()
    cookie_clicker.cast_spell(spell_to_cast="hand of fate", exhaust_magic=False)
    cookie_clicker.is_prestige_doubled()
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

        if time.time() >= cookie_clicker.time_next_save:
            cookie_clicker.save_game(path=PROGRESS_FILE)

        if time.gmtime().tm_sec < 5:
            # Close notes
            cookie_clicker.close_notes()

        if time.time() >= end_time:
            is_game_on = False
    else:
        # save_and_exit = ynbox(msg="Save game and exit?", title="Exit game")
        response = input("Save game and exit (Yes/No)? ")
        if response == "Yes":
            save_and_exit = True
        else:
            save_and_exit = False

    cookie_clicker.set_cps_multiplier()
    if cookie_clicker.cpsMult > cookie_clicker.cps_threshold or cookie_clicker.cpsMult <= 1:
        if cookie_clicker.farming_goal == 'lumps':
            cookie_clicker.garden_maintenance(plant_name='bakeberry')
        elif cookie_clicker.farming_goal == 'cookies':
            cookie_clicker.increase_golden_cookie_frequency()
    cookie_clicker.get_plant_details()
    if cookie_clicker.attempt_to_unlock_seeds and cookie_clicker.cpsMult <= 1:
        cookie_clicker.unlock_seeds()
    cookie_clicker.switch_soil()

cookie_clicker.save_game(path=PROGRESS_FILE)
cookie_clicker.quit_game()
