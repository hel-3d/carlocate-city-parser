import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
import os
import sys
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from appium import webdriver as appium_webdriver
import random
from appium.options.android import UiAutomator2Options
from config import GOOGLE_JSON, SPREADSHEET_ID, WORKSHEET_NAME





URL = "https://carlocate.com/auctions"
OUTPUT_FILE = "auctions_data.json"
BUTTON_WAIT = 90


def get_worksheet():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_JSON, scope)
    client = gspread.authorize(creds)

    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(WORKSHEET_NAME)
    return ws



def get_mobile_driver():
    # capabilities для Android + Chrome
    desired_caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "deviceName": "AndroidDevice",     
        "browserName": "Chrome",
        "newCommandTimeout": 100,

        "chromedriver_autodownload": True,
    }

    options = UiAutomator2Options()
    options.load_capabilities(desired_caps)

    driver = appium_webdriver.Remote(
        "http://127.0.0.1:4723",
        options=options
    )
    return driver




def main():
    # --- load city list from local file ---
    with open("cities.txt", "r", encoding="utf-8") as f:
        cities = [line.strip() for line in f if line.strip()]

    total_cities = len(cities)
    print(f"Loaded {total_cities} cities from file.")

    # --- load existing results if JSON file exists ---
    existing_results = []
    processed_cities = set()

    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing_results = json.load(f)
            processed_cities = {item.get("city") for item in existing_results if item.get("city")}
            print(f"Found {OUTPUT_FILE}. Cities already processed: {len(processed_cities)}")
        except Exception as e:
            print(f"Failed to read {OUTPUT_FILE}, starting from scratch. Error: {e}")
            existing_results = []
            processed_cities = set()
    else:
        print(f"File {OUTPUT_FILE} not found, starting from scratch.")

    worksheet = get_worksheet()
    print("Connected to Google Sheets.")

    # --- load existing VINs from Google Sheets ---
    existing_vins_sheet = set()
    try:
        vin_col = worksheet.col_values(1)  # column A

        # assume first row is header, skip it
        for v in vin_col[1:]:
            v = v.strip()
            if v:
                existing_vins_sheet.add(v)
        print(f"VINs already present in sheet: {len(existing_vins_sheet)}")
    except Exception as e:
        print(f"Failed to read column A from Google Sheets: {e}")
        existing_vins_sheet = set()

    proxy_index = 0  # not used now, but kept in case proxies are added later

    # --- main loop over all cities ---
    for city_index, city_name in enumerate(cities, start=1):

        # skip city if it's already present in JSON
        if city_name in processed_cities:
            print(f"City {city_index}/{total_cities}: {city_name} is already in {OUTPUT_FILE}, skipping")
            continue

        # create a new driver for the phone
        driver = get_mobile_driver()
        print(f"\n=== City {city_index}/{total_cities}: {city_name} (mobile Chrome) ===")

        # give the phone some time to "settle"
        time.sleep(random.uniform(2.0, 4.0))

        # open the site
        driver.get(URL)

        # wait for select and its options (captcha often appears here)
        try:
            #  <select name="city">
            select_element = WebDriverWait(driver, BUTTON_WAIT).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'select[name="city"]')
                )
            )
            
            WebDriverWait(driver, BUTTON_WAIT).until(
                lambda d: len(
                    d.find_elements(By.CSS_SELECTOR, 'select[name="city"] option')
                ) > 1
            )
        except TimeoutException:
            print(f"[{city_name}] Could not load city list (possible captcha). Waiting another 60 seconds...")
            try:
                select_element = WebDriverWait(driver, BUTTON_WAIT).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'select[name="city"]')
                    )
                )
                WebDriverWait(driver, BUTTON_WAIT).until(
                    lambda d: len(
                        d.find_elements(By.CSS_SELECTOR, 'select[name="city"] option')
                    ) > 1
                )
            except TimeoutException:
                print(f"[{city_name}] Still couldn't load the city list, skipping this city.")
                driver.quit()
                continue


        dropdown = Select(select_element)

        # --- IMPORTANT: choose city by NAME, not index ---
        found_option = False
        for opt in dropdown.options:
            if opt.text.strip().lower() == city_name.strip().lower():
                opt.click()
                found_option = True
                break

        if not found_option:
            print(f"Could not find city '{city_name}' in dropdown, skipping.")
            driver.quit()
            continue

        selected_city = dropdown.first_selected_option.text.strip()

        print(f"Processing city: {selected_city}")

        # click Submit (force-click via JS, same idea as Matthew's version)
        try:
            submit_button = WebDriverWait(driver, BUTTON_WAIT).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//button[@type='button' and contains(text(),'Submit')]")
                )
            )

            # let the page "settle"
            time.sleep(random.uniform(1.0, 3.0))

            # force click via JavaScript
            driver.execute_script("arguments[0].click();", submit_button)

        except TimeoutException:
            print(f"[{selected_city}] Could not find Submit button (possibly captcha). Waiting 15 seconds and skipping city.")
            time.sleep(15)
            driver.quit()
            continue

        # --- page loop for the selected city ---
        page_num = 1
        city_results = []  # results only for this city

        while True:
            # try to find table rows
            try:
                rows = WebDriverWait(driver, BUTTON_WAIT).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr.auction-row"))
                )
            except TimeoutException:
                print(f"[{selected_city}] Table did not load (possibly captcha). Waiting 15 seconds and trying again...")
                time.sleep(15)
                try:
                    rows = WebDriverWait(driver, BUTTON_WAIT).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr.auction-row"))
                    )
                except TimeoutException:
                    print(f"[{selected_city}] Still no table, skipping this city without saving.")
                    city_results = []  # just in case
                    break

            print(f"[{selected_city}] Page {page_num}: found {len(rows)} rows")

            for row in rows:
                try:
                    vin = row.find_element(By.CSS_SELECTOR, "td.vin button").text.strip()
                except Exception:
                    vin = ""

                try:
                    company = row.find_element(By.CSS_SELECTOR, "td.company").text.strip()
                except Exception:
                    company = ""

                try:
                    phone = row.find_element(By.CSS_SELECTOR, "td.phone").text.strip()
                except Exception:
                    phone = ""

                item = {
                    "vin": vin,
                    "company": company,
                    "phone": phone,
                    "city": selected_city,
                }
                city_results.append(item)

            # try to click "next page" (>) button
            try:
                # 1. find the button (presence is enough)
                next_button = WebDriverWait(driver, BUTTON_WAIT).until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        "//button[@type='button' and contains(@class,'page-link') and normalize-space(text())='>']"
                    ))
                )

                # 2. scroll to the button so nothing covers it
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(1)

                # 3. force click via JavaScript
                driver.execute_script("arguments[0].click();", next_button)

                page_num += 1

                # 4. wait for table to actually refresh
                time.sleep(3)

            except (TimeoutException, ElementClickInterceptedException):
                print(f"[{selected_city}] No more pages or Next button unavailable, exiting pagination.")
                break

        # --- save results for this city ---
        if city_results:
            # 1) update local JSON
            existing_results.extend(city_results)
            processed_cities.add(selected_city)
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(existing_results, f, ensure_ascii=False, indent=2)

            # 2) prepare rows for Google Sheets ONLY for new VINs
            rows_to_append = []
            for item in city_results:
                vin = (item.get("vin") or "").strip()
                phone = item.get("phone", "")
                city_val = item.get("city", "")
                company = item.get("company", "")

                # skip if VIN is empty or already in sheet
                if not vin or vin in existing_vins_sheet:
                    continue

                # prepare row with 24 columns:
                # A (1) -> index 0
                # F (6) -> index 5
                # V (22) -> index 21
                # X (24) -> index 23
                row = [""] * 24
                row[0] = vin          # A
                row[5] = phone        # F
                row[21] = city_val    # V
                row[23] = company     # X

                rows_to_append.append(row)
                existing_vins_sheet.add(vin)

            if rows_to_append:
                try:
                    worksheet.append_rows(rows_to_append, value_input_option="RAW")
                    print(f"[{selected_city}] Added {len(rows_to_append)} new VINs to Google Sheets.")
                except AttributeError:
                    for r in rows_to_append:
                        worksheet.append_row(r, value_input_option="RAW")
                    print(f"[{selected_city}] Added {len(rows_to_append)} new VINs to Google Sheets (row by row).")
            else:
                print(f"[{selected_city}] All VINs for this city are already in the sheet, nothing to add.")

            driver.quit()
            print(f"[{selected_city}] Saved {len(city_results)} records to JSON. Total in JSON: {len(existing_results)}")
        else:
            print(f"[{selected_city}] No data collected (most likely captcha or empty), city is NOT marked as processed.")
            driver.quit()

    print(f"\nDone. Total records in {OUTPUT_FILE}: {len(existing_results)}")


if __name__ == "__main__":
    main()
