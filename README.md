Android Web Scraper for CarLocate Auctions

This project uses Python + Appium + real Android Chrome to scrape auction data from:

https://carlocate.com/auctions

![Demo](demo.gif)

The script:
  * reads city list from cities.txt
  * opens Chrome on a connected Android phone
  * selects each city and parses all pages
  * saves data to auctions_data.json
  * writes new VINs into a Google Sheet

1. Project Structure

Minimal files needed in the repo:
  * parser_city.py – main scraper script
  * cities.txt – list of city names, one per line
  * requirements.txt – Python dependencies
  * config.py – your local config (Google Sheets settings)
  * <your-google-service-account>.json – Google API credentials (not committed to git)
  * .gitignore – excludes secrets and local files

Output files (created at runtime):
  * auctions_data.json – all parsed records
  * logs / temp files if you add them

2. Installation
2.1. Python dependencies
```
pip install -r requirements.txt
```
requirements.txt should include at least:
```
selenium
appium-python-client
gspread
oauth2client
```
(and anything else you used).

2.2. Appium & drivers

Install Appium globally:
```
npm install -g appium
```
Install Android driver:
```
appium driver install uiautomator2
```
(Chromedriver will be downloaded automatically by Appium.)

2.3. Android SDK / adb

Install Android SDK platform-tools and make sure adb is available in PATH, e.g.:
```
adb devices
```
You should see your device in the list.

3. Google Sheets Setup

Create a service account in Google Cloud Console.

Download the JSON key file (e.g. my-service-account.json) and put it in the project folder.

Create or open a Google Spreadsheet for the VINs.

Share the sheet with the service account email (from the JSON) with Editor rights.

3.1. Create config.py

Create config.py in the project root with the following content:
```
# Path to your service account JSON file (relative to project root)
GOOGLE_JSON_PATH = "my-service-account.json"

# Spreadsheet ID (the long string from the sheet URL)
# Example URL: https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit#gid=0
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE"

# Name of the worksheet tab to write VINs into
WORKSHEET_NAME = "CarLocate.com VINs"
```
Important:
  * Do not commit config.py or the JSON file to GitHub.
  * Keep them only on your local machine (see .gitignore below).

parser_city.py imports these values like this:
```
from config import GOOGLE_JSON_PATH, SPREADSHEET_ID, WORKSHEET_NAME
```

4. Android Device Preparation

On your Android phone:
  * Enable Developer options.
  * Enable USB debugging.
  * Install and update Google Chrome.

Connect the phone via USB and verify:
```
adb devices
```
You should see something like:
```
25241JEGR03491    device
```
5. Start Appium Server

In a separate terminal window, start Appium with chromedriver auto-download enabled:
```
appium --allow-insecure="uiautomator2:chromedriver_autodownload"
```
Leave this window running while the scraper works.

6. Running the Scraper

   1) Make sure:
       * config.py is filled in,
       * service account JSON is in the project folder,
       * cities.txt contains the city names you want to parse,
       * Appium server is running,
       * phone is connected and visible via adb devices.


   2) From the project directory:
```
python parser_city.py
```
The script will:
  * connect to the Android device via Appium
  * open Chrome at https://carlocate.com/auctions
  * for each city from cities.txt:
       * select the city in the dropdown
       * click Submit
       * walk through all result pages
       * collect VIN, company, phone, city
  * append new VINs to your Google Sheet (skipping existing ones)
  * save all collected records into auctions_data.json


