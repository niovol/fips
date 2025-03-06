import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class WebDriverManager:
    """Manages WebDriver setup and basic operations."""

    def __init__(self, wait_timeout: int = 20):
        self.driver = self._setup_driver()
        self.wait = WebDriverWait(self.driver, wait_timeout)

    @staticmethod
    def _setup_driver() -> webdriver.Chrome:
        """Configure and create Chrome WebDriver."""
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        return webdriver.Chrome(options=options)

    def wait_for_element(self, selector: str, by: By = By.ID) -> WebElement:
        """Wait for element to be present and return it."""
        return self.wait.until(EC.presence_of_element_located((by, selector)))

    def click_element(self, selector: str, by: By = By.ID) -> None:
        """Click element using JavaScript."""
        element = self.wait_for_element(selector, by)
        self.driver.execute_script("arguments[0].click();", element)
        time.sleep(0.5)  # Small delay after click

    def wait_for_page_load(self) -> None:
        """Wait for page to complete loading."""
        self.wait.until(
            lambda driver: driver.execute_script("return document.readyState")
            == "complete"
        )

    def find_element_by_text(self, text: str, element_type: str = "*") -> WebElement:
        """Find element by its text content.

        Args:
            text: Text to search for
            element_type: HTML tag to search in (default: any tag)

        Returns:
            WebElement if found
        """
        xpath = f"//{element_type}[contains(text(), '{text}')]"
        return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

    def find_element_by_partial_id(self, id_part: str) -> WebElement:
        """Find element by partial ID match.

        Args:
            id_part: Part of the ID to search for

        Returns:
            WebElement if found
        """
        xpath = f"//*[contains(@id, '{id_part}')]"
        return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

    def find_checkbox_by_label(self, label_text: str) -> WebElement:
        """Find checkbox by its label text.

        Args:
            label_text: Text of the label associated with checkbox

        Returns:
            WebElement (checkbox) if found
        """
        xpath = (
            f"//label[contains(text(), '{label_text}')]"
            f"/preceding-sibling::input[@type='checkbox'][1]"
        )
        return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

    def find_button_by_value(self, value: str) -> WebElement:
        """Find button by its value attribute.

        Args:
            value: Value attribute of the button

        Returns:
            WebElement if found
        """
        xpath = f"//input[@type='submit' and contains(@value, '{value}')]"
        return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
