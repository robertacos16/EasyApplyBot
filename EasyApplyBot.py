from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import random
import pickle
import os

# Configuration Section
LINKEDIN_USERNAME = ""  # <-- Replace with your LinkedIn email
LINKEDIN_PASSWORD = ""  # <-- Replace with your LinkedIn password
PHONE_NUMBER = ""  # <-- Replace with your actual phone number
LANGUAGE_PROFICIENCIES = {
    "english": "native or bilingual",
    "spanish": "native or bilingual",
    "portuguese": "native or bilingual"
}
EXPERIENCE_LEVEL = "1 year"  # Default experience level for fields that ask about experience
DEFAULT_EXPERIENCE_ANSWER = "1"  # Default answer for experience-related questions

# Define the job titles you want to search for
JOB_TITLES = [
    "analyst",
    "manager",
    "intern"
]  # <-- Add any additional keywords as needed

# Chromedriver Setup - Ensure chromedriver is installed and in PATH
CHROMEDRIVER_PATH = r"C:"  # <-- Modify to the correct path of your Chromedriver
chrome_options = Options()
# chrome_options.add_argument("--headless")  # Uncomment this line to run Chrome in headless mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

COOKIE_FILE = "linkedin_cookies.pkl"

# LinkedIn Login Function
def linkedin_login(username, password):
    driver.get("https://www.linkedin.com/login")
    try:
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        password_field = driver.find_element(By.ID, "password")
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")

        username_field.send_keys(username)
        password_field.send_keys(password)
        login_button.click()

        # Save cookies after successful login
        time.sleep(5)  # Wait for login to complete
        with open(COOKIE_FILE, "wb") as file:
            pickle.dump(driver.get_cookies(), file)
    except Exception as e:
        print(f"Error during login: {e}")

# Load Cookies Function
def load_cookies():
    if os.path.exists(COOKIE_FILE):
        driver.get("https://www.linkedin.com")
        with open(COOKIE_FILE, "rb") as file:
            cookies = pickle.load(file)
            for cookie in cookies:
                driver.add_cookie(cookie)
        driver.get("https://www.linkedin.com/feed/")

# Job Application Function - Example of Automation
def apply_to_jobs():
    days_ago = 2  # Start with jobs posted in the last 2 days
    job_title_index = 0  # Start with the first job title
    while True:
        job_title = JOB_TITLES[job_title_index]
        search_keyword = job_title.replace(' ', '%20')  # URL-encode the job title
        for page in range(1, 4):  # Iterate through the first three pages
            driver.get(f"https://www.linkedin.com/jobs/search/?keywords={search_keyword}&location=Fort%20Lauderdale%2C%20Florida&f_TPR=r{days_ago * 86400}&f_AL=true&sortBy=DD&f_EA=true&distance=50&f_WT=1,2,3&start={25 * (page - 1)}&sortBy=DD")  # Job search URL with pagination, sorted by most recent, including onsite, hybrid, and remote jobs

            try:
                jobs = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "job-card-container"))
                )
                if not jobs:
                    continue
                for job in jobs:
                    start_time = time.time()
                    try:
                        retry_count = 3
                        while retry_count > 0:
                            try:
                                job.click()
                                # Handle job search safety reminder
                                try:
                                    continue_button = WebDriverWait(driver, 5).until(
                                        EC.element_to_be_clickable((By.XPATH, "//button[text()='Continue applying']"))
                                    )
                                    continue_button.click()
                                except:
                                    pass

                                # Increase waiting time for the easy apply button
                                easy_apply_button = WebDriverWait(driver, 15).until(
                                    EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'jobs-apply-button')]"))
                                )
                                easy_apply_button.click()

                                # Wait for application form to load
                                time.sleep(2)
                                fill_out_application_form()

                                # Click buttons until application submission is complete
                                while True:
                                    if time.time() - start_time > 120:
                                        print("Timeout reached, moving to the next job title or search criteria.")
                                        break
                                    try:
                                        button = WebDriverWait(driver, 15).until(
                                            EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Continue') or contains(@aria-label, 'Next') or contains(@aria-label, 'Review') or contains(@aria-label, 'Submit application')]"))
                                        )
                                        button.click()
                                        time.sleep(2)
                                        fill_out_application_form()  # Fill out fields on each page if any
                                        if "Submit application" in button.get_attribute("aria-label"):
                                            print(f"Applied to job containing keyword '{job_title}' successfully!")
                                            time.sleep(random.uniform(2, 5))  # Random delay to avoid detection
                                            break
                                    except Exception as e:
                                        print(f"Error during button click: {e}")
                                        break
                                break
                            except Exception as e:
                                retry_count -= 1
                                if retry_count == 0:
                                    raise e
                                else:
                                    print(f"Retrying due to exception: {e}")
                                    time.sleep(2)
                    except Exception as e:
                        print(f"Could not apply to job containing keyword '{job_title}': {e}")
                        continue
            except Exception as e:
                print(f"Error during job search for '{job_title}' on page {page} with {days_ago} days filter: {e}")
        job_title_index = (job_title_index + 1) % len(JOB_TITLES)  # Switch to the next job title
        days_ago += 1  # Expand the search if fewer jobs are available
        if days_ago > 30:
            days_ago = 2  # Reset to 2 days and move to the next job title

# Fill Out Application Form Function
def fill_out_application_form():
    try:
        # Example logic to fill out form fields automatically
        form_fields = driver.find_elements(By.XPATH, "//input[not(@type='hidden') and (@type='text' or @type='tel' or @type='email')]")
        for field in form_fields:
            if field.get_attribute("value").strip() == "":  # Only fill empty fields
                field_name = field.get_attribute("name").lower()
                if "experience" in field_name or "tools" in field_name:
                    field.send_keys(DEFAULT_EXPERIENCE_ANSWER)
                elif "phone" in field_name:
                    field.send_keys(PHONE_NUMBER)  # Use the provided phone number
                elif "connectwise" in field_name:
                    field.send_keys("1 year")  # Provide a default value for ConnectWise experience
                else:
                    field.send_keys(DEFAULT_EXPERIENCE_ANSWER)

        # Handle numerical experience questions
        numerical_fields = driver.find_elements(By.XPATH, "//input[@type='text' and (contains(@aria-label, 'experience') or contains(@aria-label, 'years'))]")
        for field in numerical_fields:
            if field.get_attribute("value").strip() == "":  # Only fill empty fields
                field.send_keys(DEFAULT_EXPERIENCE_ANSWER)

        dropdowns = driver.find_elements(By.XPATH, "//select")
        for dropdown in dropdowns:
            if dropdown.get_attribute("value").strip() == "":  # Only fill empty fields
                options = dropdown.find_elements(By.TAG_NAME, "option")
                if options:
                    # Always try to select "Yes" if available, otherwise select the first option that is not "Select"
                    for option in options:
                        if "yes" in option.text.lower() and "need a visa" not in dropdown.get_attribute("name").lower():
                            option.click()
                            break
                    else:
                        # Select the first available option that is not "Select"
                        for option in options:
                            if "select" not in option.text.lower():
                                option.click()
                                break

        # Handle checkboxes and radio buttons
        checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox']")
        for checkbox in checkboxes:
            if not checkbox.is_selected():
                checkbox.click()

        # Corrected XPath expression for radio buttons
        radio_buttons = driver.find_elements(By.XPATH, "//input[@type='radio']")
        for radio in radio_buttons:
            radio_name = radio.get_attribute("name").lower()
            if not radio.is_selected():
                if "need a visa" in radio_name and "no" in radio.get_attribute("value").lower():
                    radio.click()
                elif "yes" in radio.get_attribute("value").lower() and "need a visa" not in radio_name:
                    radio.click()
                elif "no" in radio.get_attribute("value").lower() and ("disability" in radio_name or "veteran" in radio_name):
                    radio.click()
                elif "yes" in radio.get_attribute("value").lower() and "commuting" in radio_name:
                    radio.click()
                elif "male" in radio.get_attribute("value").lower() and "gender" in radio_name:
                    radio.click()
                elif "white" in radio.get_attribute("value").lower() and "race" in radio_name:
                    radio.click()
    except Exception as e:
        print(f"Error while filling out the application form: {e}")

# Main Execution
try:
    load_cookies()
    time.sleep(5)  # Wait for cookies to load
    if "feed" not in driver.current_url:
        linkedin_login(LINKEDIN_USERNAME, LINKEDIN_PASSWORD)
    apply_to_jobs()
finally:
    driver.quit()  # Close the browser

# Notes:
# 1. Replace LINKEDIN_USERNAME and LINKEDIN_PASSWORD with your actual LinkedIn login details.
# 2. Ensure that the chromedriver version matches your installed Chrome version.
# 3. Add more detailed form-filling logic as needed for specific job postings. Please make sure it keeps applying to jobs for the last month and also keeps looking for the most recent jobs, like a sorting type of thing, like all of the jobs from the most recent job tabs then next then another job title and it goes from job title to job title until their first 2 tabs are all applied for then we keep applying to all most recent jobs since jobs just keep getting posted, if for any reason no new jobs were getting posted just apply to job categories up to a month old.
