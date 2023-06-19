from cookie_clicker import CookieClicker
from easygui import *
import time
import os

PROGRESS_FILE = os.environ["PROGRESS_FILE"]
is_game_on = True
save_and_exit = False
NUMBER_OF_HOURS_TO_RUN = 12

# response = input("Attempt trillion cookie achievement (Yes/No)? ")
response = "No"
if response == "Yes":
    trillion_cookies = True
else:
    trillion_cookies = False

# response = input("Attempt Endless Cycle achievement (Yes/No)? ")
if response == "Yes":
    endless_cycle = True
else:
    endless_cycle = False

# trillion_cookies = ynbox(msg="Do you wish to attempt the trillion cookie ascension achievement?",
#                          title="Trillion cookie achievement")

cookie_clicker = CookieClicker(trillion_cookies=trillion_cookies, endless_cycle=endless_cycle, save_file=PROGRESS_FILE)

# Load game
cookie_clicker.load_cookieclicker()

end_time = time.time() + (3600 * NUMBER_OF_HOURS_TO_RUN)
structured_end_time = time.localtime(end_time)
print(f"Game will quit on {structured_end_time.tm_mon}/{structured_end_time.tm_mday} at {structured_end_time.tm_hour}:"
      f"{structured_end_time.tm_min:02}:{structured_end_time.tm_sec:02}.")
response = input("Do you want a manual run this round (Yes/No)? ")
if response == "Yes":
    prompt_for_save = True
else:
    prompt_for_save = False
# prompt_for_save = ynbox(msg="Do you want a manual run this round?", title="Manual run")

counter = 0
while is_game_on and not save_and_exit:
    cookie_clicker.set_cps_multiplier()
    cookie_clicker.get_plant_details()
    cookie_clicker.is_juicy_queenbeet_growing()
    cookie_clicker.check_achievements()
    if cookie_clicker.attempt_endless_cycle:
        cookie_clicker.ascend()
    cookie_clicker.check_veil()
    if time.time() >= cookie_clicker.time_last_wrinkler_popped + (2 * 3600):
        cookie_clicker.pop_fattest_wrinkler()
    cookie_clicker.open_mini_games()
    cookie_clicker.harvest_lumps()
    cookie_clicker.train_dragon()
    cookie_clicker.check_season_timer()
    time_until_next_click = cookie_clicker.next_garden_tick - time.time()
    if time_until_next_click < 0:
        cookie_clicker.get_next_garden_tick_in_seconds()
    if cookie_clicker.cpsMult != 1 or cookie_clicker.next_garden_tick - time.time() <= 15:
        if cookie_clicker.max_plants > cookie_clicker.num_plants_unlocked:
            cookie_clicker.unlock_seeds()
        else:
            cookie_clicker.obtain_garden_upgrades()
    cookie_clicker.harvest_fading_plants()
    cookie_clicker.pantheon()
    cookie_clicker.pet_the_dragon()
    cookie_clicker.upgrade_santa()
    cookie_clicker.cast_spell(spell_to_cast="resurrect abomination", exhaust_magic=True)

    if not prompt_for_save:
        cookie_clicker.click_cookie()

        # Check for buffs
        cookie_clicker.check_for_buffs()

        # Buy upgrades and products
        cookie_clicker.buy_upgrades()
        cookie_clicker.check_for_upgrades()
        cookie_clicker.buy_products()

        # Click fortune
        cookie_clicker.click_fortune()

        cookie_clicker.stock_market()

        if time.time() >= cookie_clicker.time_next_save:
            cookie_clicker.save_game()

        if time.gmtime().tm_sec < 5:
            # if not cookie_clicker.skip_pause:
            #     time.sleep(5)
            # Close notes
            cookie_clicker.close_notes()

        if time.time() >= end_time and not cookie_clicker.skip_pause:
            is_game_on = False

    else:
        # save_and_exit = ynbox(msg="Save game and exit?", title="Exit game")
        response = input("Save game and exit (Yes/No)? ")
        if response == "Yes":
            save_and_exit = True
        else:
            save_and_exit = False

    counter += 1

cookie_clicker.save_game()
cookie_clicker.quit_game()
