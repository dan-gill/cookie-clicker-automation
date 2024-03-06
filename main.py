from cookie_clicker import CookieClicker
# from dotenv import load_dotenv
import time
import os

# load_dotenv()
PROGRESS_FILE = os.environ["PROGRESS_FILE"]
is_game_on = True
save_and_exit = False
NUMBER_OF_HOURS_TO_RUN = 168
HOURS_BETWEEN_WRINKLER_POPS = 2
HOURS_BETWEEN_RELOADS = 2  # This helps with the lag issue due to memory usage on Chrome

# response = input("Attempt trillion cookie achievement (Yes/No)? ")
farm_goal = "lumps"
response = "No"
building_level_goal = "cps"
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

cookie_clicker = CookieClicker(trillion_cookies=trillion_cookies, endless_cycle=endless_cycle, save_file=PROGRESS_FILE,
                               farming_goal=farm_goal, building_level_goal=building_level_goal)

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
memory_leak_reset_time = time.time() + (3600 * HOURS_BETWEEN_RELOADS)
while is_game_on and not save_and_exit:
    if time.time() > memory_leak_reset_time:
        memory_leak_reset_time = time.time() + (3600 * HOURS_BETWEEN_RELOADS)
        cookie_clicker.reload_cookieclicker()
    cookie_clicker.set_cps_multiplier()
    cookie_clicker.get_plant_details()
    if cookie_clicker.attempt_endless_cycle and cookie_clicker.check_achievements('Endless cycle'):
        cookie_clicker.endless_cycle_achievement_won = True
        cookie_clicker.attempt_endless_cycle = False
    if cookie_clicker.attempt_endless_cycle:
        cookie_clicker.ascend()
    cookie_clicker.check_veil()
    if time.time() >= cookie_clicker.time_last_wrinkler_popped + (HOURS_BETWEEN_WRINKLER_POPS * 3600):
        cookie_clicker.pop_fattest_wrinkler()
    cookie_clicker.open_mini_games()
    cookie_clicker.harvest_lumps()
    cookie_clicker.train_dragon()
    # cookie_clicker.check_season_timer()
    time_until_next_click = cookie_clicker.next_garden_tick - time.time()
    if farm_goal == "lumps":
        cookie_clicker.sacrifice_garden()
    if time_until_next_click < 0:
        cookie_clicker.get_next_garden_tick_in_seconds()
    cookie_clicker.harvest_plants()
    cookie_clicker.unlock_seeds()
    cookie_clicker.obtain_garden_upgrades()
    if farm_goal == "cookies":
        cookie_clicker.garden_maintenance(plant_name="bakeberry")
    cookie_clicker.pantheon()
    cookie_clicker.get_season_cookies()
    cookie_clicker.pet_the_dragon()
    cookie_clicker.cast_spell(spell_to_cast="hand of fate", exhaust_magic=False)
    cookie_clicker.is_prestige_doubled()
    cookie_clicker.four_leaf_cookie()
    cookie_clicker.level_up()
    # cookie_clicker.cast_spell(spell_to_cast="resurrect abomination", exhaust_magic=False)

    if not prompt_for_save:
        cookie_clicker.click_cookie()

        # Buy upgrades and products
        cookie_clicker.buy_products()
        cookie_clicker.buy_upgrades()

        # Click fortune
        cookie_clicker.click_fortune()

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

    counter += 1

cookie_clicker.save_game(path=PROGRESS_FILE)
cookie_clicker.quit_game()
