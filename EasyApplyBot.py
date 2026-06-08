import json
import os
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

DEFAULT_TIMEOUT = int(os.getenv("LINKEDIN_TIMEOUT", "15"))


def truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def json_env(name: str) -> dict[str, str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"{name} must be a JSON object.")
    return {str(key).lower(): str(value) for key, value in data.items()}


@dataclass(frozen=True)
class BotConfig:
    email: str = ""
    password: str = ""
    phone: str = ""
    search_terms: list[str] = field(default_factory=lambda: ["analyst", "manager", "intern"])
    location: str = "Fort Lauderdale, Florida"
    max_applications: int = 25
    pages_per_search: int = 2
    days_back_start: int = 2
    days_back_max: int = 30
    dry_run: bool = True
    headless: bool = False
    cookie_file: Path = Path("linkedin_cookies.json")
    seen_jobs_file: Path = Path("seen_jobs.json")
    application_log: Path = Path("applications_log.jsonl")
    default_answer: str | None = "1"
    custom_answers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "BotConfig":
        terms = [term.strip() for term in os.getenv("LINKEDIN_SEARCH_TERMS", "analyst,manager,intern").split(",") if term.strip()]
        return cls(
            email=os.getenv("LINKEDIN_EMAIL", ""),
            password=os.getenv("LINKEDIN_PASSWORD", ""),
            phone=os.getenv("LINKEDIN_PHONE", ""),
            search_terms=terms,
            location=os.getenv("LINKEDIN_LOCATION", "Fort Lauderdale, Florida"),
            max_applications=int(os.getenv("LINKEDIN_MAX_APPLICATIONS", "25")),
            pages_per_search=int(os.getenv("LINKEDIN_PAGES_PER_SEARCH", "2")),
            days_back_start=int(os.getenv("LINKEDIN_DAYS_BACK_START", "2")),
            days_back_max=int(os.getenv("LINKEDIN_DAYS_BACK_MAX", "30")),
            dry_run=truthy(os.getenv("LINKEDIN_DRY_RUN"), default=True),
            headless=truthy(os.getenv("LINKEDIN_HEADLESS"), default=False),
            cookie_file=Path(os.getenv("LINKEDIN_COOKIE_FILE", "linkedin_cookies.json")),
            seen_jobs_file=Path(os.getenv("LINKEDIN_SEEN_JOBS_FILE", "seen_jobs.json")),
            application_log=Path(os.getenv("LINKEDIN_APPLICATION_LOG", "applications_log.jsonl")),
            default_answer=os.getenv("LINKEDIN_DEFAULT_ANSWER", "1") or None,
            custom_answers=json_env("LINKEDIN_CUSTOM_ANSWERS"),
        )

    def validate(self) -> None:
        if not self.search_terms:
            raise RuntimeError("Set at least one search term.")
        if self.max_applications < 1:
            raise RuntimeError("LINKEDIN_MAX_APPLICATIONS must be at least 1.")
        if self.pages_per_search < 1:
            raise RuntimeError("LINKEDIN_PAGES_PER_SEARCH must be at least 1.")
        if self.days_back_start < 1 or self.days_back_max < self.days_back_start:
            raise RuntimeError("The days-back range is invalid.")
        if not self.dry_run and (not self.email or not self.password):
            raise RuntimeError("Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD before live mode.")


class LinkedInEasyApplyBot:
    def __init__(self, config: BotConfig) -> None:
        config.validate()
        self.config = config
        self.driver = self.build_driver()
        self.wait = WebDriverWait(self.driver, DEFAULT_TIMEOUT)
        self.applications_sent = 0
        self.jobs_seen = self.load_seen_jobs()

    def build_driver(self):
        options = ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if self.config.headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1440,1000")
        return webdriver.Chrome(options=options)

    def run(self) -> None:
        try:
            self.login()
            while self.applications_sent < self.config.max_applications:
                made_progress = self.apply_recent_then_older_jobs()
                if not made_progress:
                    print("No new jobs found in this cycle. Waiting before checking most recent jobs again.")
                    time.sleep(random.uniform(60, 120))
        finally:
            self.save_seen_jobs()
            self.driver.quit()

    def login(self) -> None:
        self.driver.get("https://www.linkedin.com/")
        if self.load_cookies():
            self.driver.get("https://www.linkedin.com/feed/")
            if self.is_logged_in():
                print("Logged in with saved cookies.")
                return
        if not self.config.email or not self.config.password:
            raise RuntimeError("Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD, or provide a valid cookie file.")
        self.driver.get("https://www.linkedin.com/login")
        self.type(By.ID, "username", self.config.email)
        self.type(By.ID, "password", self.config.password)
        self.click(By.CSS_SELECTOR, "button[type='submit']")
        try:
            self.wait.until(lambda _: self.is_logged_in())
        except TimeoutException as exc:
            raise RuntimeError("Login did not finish. Check for MFA, captcha, or incorrect credentials.") from exc
        self.save_cookies()
        print("Logged in and saved cookies.")

    def apply_recent_then_older_jobs(self) -> bool:
        made_progress = False
        days_options = [self.config.days_back_start] + list(range(self.config.days_back_start + 1, self.config.days_back_max + 1))
        for days_back in days_options:
            for term in self.config.search_terms:
                if self.applications_sent >= self.config.max_applications:
                    return made_progress
                print(f"Searching '{term}' from the last {days_back} day(s), most recent first.")
                if self.apply_for_search(term, days_back):
                    made_progress = True
            if made_progress:
                return True
        return made_progress

    def apply_for_search(self, search_term: str, days_back: int) -> bool:
        made_progress = False
        for page in range(self.config.pages_per_search):
            if self.applications_sent >= self.config.max_applications:
                return made_progress
            self.driver.get(self.jobs_url(search_term, days_back, page))
            self.pause(2.0, 4.0)
            self.dismiss_overlays()
            cards = self.job_cards()
            print(f"Page {page + 1}: found {len(cards)} visible jobs.")
            for index in range(len(cards)):
                if self.try_apply_to_card(index):
                    made_progress = True
                if self.applications_sent >= self.config.max_applications:
                    return made_progress
        return made_progress

    def jobs_url(self, search_term: str, days_back: int, page: int) -> str:
        seconds = days_back * 86400
        return (
            "https://www.linkedin.com/jobs/search/"
            f"?keywords={quote_plus(search_term)}"
            f"&location={quote_plus(self.config.location)}"
            f"&f_TPR=r{seconds}"
            "&f_AL=true&sortBy=DD&f_EA=true&distance=50&f_WT=1,2,3"
            f"&start={page * 25}"
        )

    def try_apply_to_card(self, index: int) -> bool:
        try:
            cards = self.job_cards()
            if index >= len(cards):
                return False
            card = cards[index]
            key = self.job_key(card)
            if not key or key in self.jobs_seen:
                return False
            self.jobs_seen.add(key)
            self.scroll_into_view(card)
            card.click()
            self.pause()
            self.dismiss_overlays()
            easy_apply = self.button_by_text(("Easy Apply",))
            if not easy_apply:
                return False
            title = self.safe_text(By.CSS_SELECTOR, "h1") or key
            print(f"Opening Easy Apply: {title}")
            self.safe_click(easy_apply)
            self.pause()
            return self.complete_application_flow(title, key)
        except (ElementClickInterceptedException, NoSuchElementException, StaleElementReferenceException, TimeoutException) as exc:
            print(f"Skipped job because the page changed or blocked an action: {exc}")
            self.close_application_modal()
            return False

    def complete_application_flow(self, title: str, key: str) -> bool:
        for _ in range(12):
            self.dismiss_overlays()
            self.fill_current_form()
            submit = self.button_by_text(("Submit application", "Submit"))
            if submit:
                if self.config.dry_run:
                    print("Dry run: reached final submit, closing application.")
                    self.write_application_log(title, key, "dry-run-ready")
                    self.close_application_modal()
                    return True
                self.safe_click(submit)
                self.applications_sent += 1
                self.write_application_log(title, key, "submitted")
                print(f"Submitted application #{self.applications_sent}.")
                self.pause(1.5, 3.0)
                return True
            next_button = self.button_by_text(("Next", "Review", "Continue"))
            if next_button:
                self.safe_click(next_button)
                self.pause(1.0, 2.0)
                continue
            print("Could not confidently complete this form; discarding it.")
            self.write_application_log(title, key, "skipped-incomplete-form")
            self.close_application_modal()
            return False
        print("Application flow had too many steps; discarding it.")
        self.write_application_log(title, key, "skipped-too-many-steps")
        self.close_application_modal()
        return False

    def fill_current_form(self) -> None:
        self.fill_text_inputs()
        self.fill_selects()
        self.fill_radios()
        self.fill_checkboxes()

    def fill_text_inputs(self) -> None:
        selector = "input:not([type='hidden']):not([type='file']):not([type='checkbox']):not([type='radio']), textarea"
        for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
            if not self.is_interactable(element) or element.get_attribute("value"):
                continue
            answer = self.answer_for_label(self.field_label(element).lower())
            if answer is None:
                continue
            self.scroll_into_view(element)
            element.clear()
            element.send_keys(answer)

    def fill_selects(self) -> None:
        for element in self.driver.find_elements(By.TAG_NAME, "select"):
            if not self.is_interactable(element):
                continue
            select = Select(element)
            selected = select.first_selected_option.text.strip()
            if selected and not re.search(r"select|choose", selected, re.I):
                continue
            label = self.field_label(element).lower()
            preferred = self.answer_for_label(label)
            options = [option for option in select.options if option.get_attribute("value") and option.text.strip()]
            if not options:
                continue
            match = None
            if preferred:
                match = next((option for option in options if preferred.lower() in option.text.lower()), None)
            select.select_by_visible_text((match or options[0]).text)

    def fill_radios(self) -> None:
        groups: dict[str, list] = {}
        for radio in self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
            if self.is_interactable(radio) and not radio.is_selected():
                groups.setdefault(radio.get_attribute("name") or radio.id, []).append(radio)
        for radios in groups.values():
            label = " ".join(self.field_label(radio).lower() for radio in radios)
            preferred = self.answer_for_label(label)
            target = self.radio_by_text(radios, preferred) or self.radio_by_text(radios, "yes")
            if target:
                self.safe_click(target)

    def fill_checkboxes(self) -> None:
        for checkbox in self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
            if self.is_interactable(checkbox) and not checkbox.is_selected():
                label = self.field_label(checkbox).lower()
                if any(word in label for word in ("agree", "confirm", "certify", "terms", "acknowledge")):
                    self.safe_click(checkbox)

    def answer_for_label(self, label: str) -> str | None:
        label = " ".join(label.split()).lower()
        for key, value in self.config.custom_answers.items():
            if key in label and value:
                return value
        answers = {
            "phone": self.config.phone,
            "mobile": self.config.phone,
            "email": self.config.email,
            "salary": os.getenv("LINKEDIN_DESIRED_SALARY", ""),
            "notice": os.getenv("LINKEDIN_NOTICE_PERIOD", "2 weeks"),
            "sponsorship": os.getenv("LINKEDIN_SPONSORSHIP", "No"),
            "authorized": os.getenv("LINKEDIN_WORK_AUTHORIZED", "Yes"),
            "work authorization": os.getenv("LINKEDIN_WORK_AUTHORIZED", "Yes"),
            "years": os.getenv("LINKEDIN_DEFAULT_YEARS", "1"),
            "experience": os.getenv("LINKEDIN_DEFAULT_YEARS", "1"),
            "commute": os.getenv("LINKEDIN_COMMUTE", "Yes"),
            "relocate": os.getenv("LINKEDIN_RELOCATE", "Yes"),
        }
        for key, value in answers.items():
            if key in label and value:
                return value
        return self.config.default_answer

    def field_label(self, element) -> str:
        aria = element.get_attribute("aria-label")
        if aria:
            return aria
        element_id = element.get_attribute("id")
        if element_id:
            labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{element_id}']")
            if labels:
                return labels[0].text
        try:
            parent = element.find_element(By.XPATH, "./ancestor::*[self::label or self::fieldset or contains(@class, 'jobs-easy-apply-form-section')][1]")
            return parent.text
        except NoSuchElementException:
            return element.text or element.get_attribute("placeholder") or ""

    def radio_by_text(self, radios, answer: str | None):
        if not answer:
            return None
        answer = answer.lower()
        for radio in radios:
            label = self.field_label(radio).lower()
            value = (radio.get_attribute("value") or "").lower()
            if answer in label or answer == value:
                return radio
        return None

    def job_cards(self) -> list:
        selectors = ("li[data-occludable-job-id]", "li.jobs-search-results__list-item", ".job-card-container", "[data-job-id]")
        for selector in selectors:
            cards = [card for card in self.driver.find_elements(By.CSS_SELECTOR, selector) if card.is_displayed()]
            if cards:
                return cards
        return []

    def job_key(self, card) -> str:
        for attr in ("data-occludable-job-id", "data-job-id"):
            value = card.get_attribute(attr)
            if value:
                return value
        try:
            return card.find_element(By.CSS_SELECTOR, "a[href*='/jobs/view/']").get_attribute("href")
        except NoSuchElementException:
            return card.text[:200]

    def button_by_text(self, labels: tuple[str, ...]):
        for selector in ("button", "[role='button']"):
            for button in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if not self.is_interactable(button):
                    continue
                text = " ".join(button.text.split())
                aria = button.get_attribute("aria-label") or ""
                if any(label.lower() in text.lower() or label.lower() in aria.lower() for label in labels):
                    return button
        return None

    def dismiss_overlays(self) -> None:
        for label in ("Dismiss", "Close", "Not now", "No thanks"):
            button = self.button_by_text((label,))
            if button:
                try:
                    self.safe_click(button)
                    self.pause(0.3, 0.8)
                except Exception:
                    pass

    def close_application_modal(self) -> None:
        close = self.button_by_text(("Dismiss", "Close"))
        if close:
            self.safe_click(close)
            self.pause()
        discard = self.button_by_text(("Discard", "Discard application"))
        if discard:
            self.safe_click(discard)
            self.pause()

    def is_logged_in(self) -> bool:
        selector = "a[href*='/feed/'], a[href*='/mynetwork/'], input[placeholder*='Search']"
        return bool(self.driver.find_elements(By.CSS_SELECTOR, selector))

    def load_cookies(self) -> bool:
        if not self.config.cookie_file.exists():
            return False
        with self.config.cookie_file.open("r", encoding="utf-8") as file:
            cookies = json.load(file)
        for cookie in cookies:
            cookie.pop("sameSite", None)
            try:
                self.driver.add_cookie(cookie)
            except Exception:
                pass
        return True

    def save_cookies(self) -> None:
        with self.config.cookie_file.open("w", encoding="utf-8") as file:
            json.dump(self.driver.get_cookies(), file, indent=2)

    def load_seen_jobs(self) -> set[str]:
        if not self.config.seen_jobs_file.exists():
            return set()
        try:
            with self.config.seen_jobs_file.open("r", encoding="utf-8") as file:
                return {str(item) for item in json.load(file) if item}
        except Exception:
            return set()

    def save_seen_jobs(self) -> None:
        with self.config.seen_jobs_file.open("w", encoding="utf-8") as file:
            json.dump(sorted(self.jobs_seen), file, indent=2)

    def write_application_log(self, title: str, key: str, status: str) -> None:
        entry = {"time": datetime.now(timezone.utc).isoformat(), "title": title, "job_key": key, "status": status, "dry_run": self.config.dry_run}
        with self.config.application_log.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry) + "\n")

    def click(self, by, value: str) -> None:
        self.safe_click(self.wait.until(EC.element_to_be_clickable((by, value))))

    def type(self, by, value: str, text: str) -> None:
        element = self.wait.until(EC.visibility_of_element_located((by, value)))
        element.clear()
        element.send_keys(text)

    def safe_click(self, element) -> None:
        self.scroll_into_view(element)
        try:
            element.click()
        except ElementClickInterceptedException:
            self.driver.execute_script("arguments[0].click();", element)

    def scroll_into_view(self, element) -> None:
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)

    def safe_text(self, by, value: str) -> str:
        try:
            return self.driver.find_element(by, value).text.strip()
        except NoSuchElementException:
            return ""

    def is_interactable(self, element) -> bool:
        try:
            return element.is_displayed() and element.is_enabled()
        except Exception:
            return False

    def pause(self, low: float = 0.8, high: float = 1.8) -> None:
        time.sleep(random.uniform(low, high))


if __name__ == "__main__":
    mode = "DRY RUN" if truthy(os.getenv("LINKEDIN_DRY_RUN"), default=True) else "LIVE SUBMIT"
    print(f"Starting EasyApplyBot in {mode} mode.")
    LinkedInEasyApplyBot(BotConfig.from_env()).run()
