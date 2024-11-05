# EasyApplyBot
AI Agent for Linkedin easy apply jobs, customizable

# EasyApplyBot

This Python script automates the process of applying for jobs on LinkedIn using Selenium. It allows users to configure job titles they want to apply for and automates the entire application process for easy apply jobs.

## Features

- **Automated Login**: Logs into LinkedIn with the provided credentials and saves cookies for subsequent logins.
- **Job Search**: Searches for jobs based on user-defined keywords (e.g., "analyst", "manager", etc.). It cycles through different job titles to apply evenly and iterates through multiple pages of search results.
- **Automated Job Application**: Automatically applies to jobs using LinkedIn's easy apply feature. The bot can fill out common fields such as experience and contact details.
- **Timeout Management**: Moves on to other job listings or job titles if it takes too long (over 2 minutes) to apply for a particular job.
- **Error Handling and Retries**: Handles various errors during login and job application, with retries to increase the success rate.
- **Supports Multiple Job Titles**: Switches between different job titles at an even pace to cover more opportunities.
- **Field Autofill**: Attempts to fill in common input fields, dropdowns, checkboxes, and radio buttons in application forms.

## Setup

1. **Dependencies**: Ensure you have Selenium installed and that you have the correct version of ChromeDriver that matches your installed Chrome browser.
   ```sh
   pip install selenium
   ```

2. **Chromedriver Path**: Update `CHROMEDRIVER_PATH` with the correct path where your ChromeDriver executable is located.

3. **Credentials**: Update the `LINKEDIN_USERNAME` and `LINKEDIN_PASSWORD` variables with your LinkedIn credentials.

4. **Job Titles**: Modify the `JOB_TITLES` list to include the job titles you are interested in.

5. **Optional Configuration**:
   - To run Chrome in headless mode (without opening a browser window), uncomment the `chrome_options.add_argument("--headless")` line.
   - Update `PHONE_NUMBER`, `LANGUAGE_PROFICIENCIES`, and `EXPERIENCE_LEVEL` with your personal details.

## How It Works

- **Login**: The bot first attempts to load saved cookies for faster login. If no cookies are found, it logs in manually using the credentials provided.
- **Job Search and Application**: The bot searches for jobs based on the titles in the `JOB_TITLES` list. It iterates through job postings, filling out forms where required and submitting applications.
- **Continuous Application**: The script is designed to keep applying to jobs, switching between job titles and never stagnating. If a job application takes too long (over 2 minutes), the bot will move on to the next available job.

## Important Notes

- **Use Caution with Your Credentials**: The script requires your LinkedIn credentials in plain text, which can be a security risk. Use this script with caution and never share your credentials publicly.
- **Legal Disclaimer**: Automating actions on LinkedIn may violate LinkedIn's terms of service. Use this script responsibly and at your own risk.
- **Debugging**: If something goes wrong, the script prints error messages to the console, which can help identify the problem.

## Usage

1. Run the script in a Python environment.
   ```sh
   python EasyApplyBot.py
   ```
2. The bot will keep searching and applying for jobs until you manually close the browser or stop the script.

## Future Improvements

- **More Robust Form Handling**: Add more sophisticated logic to handle custom questions in application forms.
- **Captcha Handling**: Implement a solution to detect and handle captchas.
- **Enhanced Logging**: Improve logging to track which jobs have been successfully applied to, and which have failed.

