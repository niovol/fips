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

    def click_element(self, element: WebElement) -> None:
        """Click element using JavaScript for better reliability.

        Args:
            element: WebElement to click
        """
        self.driver.execute_script("arguments[0].click();", element)
        time.sleep(0.5)  # Small delay after click

    def wait_for_page_load(self, timeout: int = 20) -> None:
        """Wait for page to complete loading with improved reliability.

        Args:
            timeout: Maximum time to wait in seconds
        """
        # Wait for document ready state
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState")
                == "complete"
            )

            # Also wait for jQuery to complete (if present)
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.execute_script(
                        "return typeof jQuery !== 'undefined' && jQuery.active === 0"
                    )
                )
            except Exception:
                # jQuery may not be present, which is fine
                pass

            # Wait a short time for any animations to complete
            time.sleep(0.3)
        except Exception as e:
            # Log but continue if timeout occurs
            print(f"Warning: Page load wait timed out: {e}")

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

    def find_element_by_class_and_text(self, class_name: str, text: str) -> WebElement:
        """Find element by its class and text content.

        Args:
            class_name: CSS class name
            text: Text to search for

        Returns:
            WebElement if found
        """
        xpath = f"//*[contains(@class, '{class_name}') and contains(text(), '{text}')]"
        return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

    def find_input_by_parent_text(self, parent_text: str) -> WebElement:
        """Find input element by text in its parent element.

        Args:
            parent_text: Text in parent element

        Returns:
            WebElement (input) if found
        """
        xpath = (
            f"//div[contains(@class, 'oneblock')]"
            f"//div[contains(@class, 'name')][contains(., '{parent_text}')]"
            f"/following-sibling::div[contains(@class, 'input')]//input"
        )
        return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

    def find_checkbox_by_position(
        self, container_class: str, position: int
    ) -> WebElement:
        """Find checkbox by its position in a container.

        Args:
            container_class: Class of the container
            position: Position of the checkbox (0-based)

        Returns:
            WebElement (checkbox) if found
        """
        xpath = (
            f"(//*[contains(@class, '{container_class}')]//input[@type='checkbox'])"
            f"[{position + 1}]"
        )
        return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

    def find_button_in_container(
        self, container_class: str, button_type: str = "submit"
    ) -> WebElement:
        """Find button in a container.

        Args:
            container_class: Class of the container
            button_type: Type of the button (default: submit)

        Returns:
            WebElement (button) if found
        """
        xpath = (
            f"//*[contains(@class, '{container_class}')]//input[@type='{button_type}']"
        )
        return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

    def open_url_in_new_tab(self, url: str) -> None:
        """Open URL in a new tab and switch to it.

        Args:
            url: URL to open
        """
        self.driver.execute_script(f'window.open("{url}","_blank");')
        self.driver.switch_to.window(self.driver.window_handles[-1])
