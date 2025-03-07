import time
from pathlib import Path
from typing import Dict, List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from fips.logger import logger
from fips.models import PatentHeader, PatentResult, StatusOptions
from fips.storage import PatentStorage
from fips.web import WebDriverManager


class FIPSParser:
    """Parser for FIPS patent database."""

    BASE_URL = "https://new.fips.ru/iiss/"

    # Text constants for finding elements
    TEXT_LABELS = {
        "section_header": "Патентные документы РФ (рус.)",
        "search_button_value": "перейти к поиску",
        "status_active": "Действует",
        "status_may_terminate": "Может прекратить свое действие",
        "status_terminated_recoverable": (
            "Прекратил действие, но может быть восстановлен"
        ),
        "status_terminated": "Прекратил действие",
        "patent_owner_label": "Патентообладатель",
        "status_label": "Статус документа",
    }

    # CSS classes for finding elements
    CSS_CLASSES = {
        "checkbox_container": "oneline",
        "button_container": "button-set",
        "search_form": "fields",
        "status_container": "oneblock",
    }

    def __init__(
        self,
        base_dir: Path,
        status_options: Optional[StatusOptions] = None,
        test_mode: bool = False,
    ):
        self.driver_manager = WebDriverManager()
        self.storage = PatentStorage(base_dir / "output")
        self.status_options = status_options or StatusOptions()
        self.test_mode = test_mode

    def _select_search_options(self) -> None:
        """Select required search options."""
        try:
            # Try to find section header by text
            section_header = self.driver_manager.find_element_by_text(
                self.TEXT_LABELS["section_header"], "div"
            )
            self.driver_manager.driver.execute_script(
                "arguments[0].click();", section_header
            )
        except Exception as e:
            logger.warning(f"Failed to find section header by text: {e}")
            # Try to find by class as fallback
            self.driver_manager.find_element_by_class_and_text(
                "name", self.TEXT_LABELS["section_header"]
            ).click()

        time.sleep(1)  # Wait for animation

        # Find checkboxes by their position in the container
        try:
            # First checkbox (Рефераты российских изобретений)
            checkbox1 = self.driver_manager.find_checkbox_by_position(
                self.CSS_CLASSES["checkbox_container"], 0
            )
            # Fourth checkbox (Формулы российских полезных моделей)
            checkbox4 = self.driver_manager.find_checkbox_by_position(
                self.CSS_CLASSES["checkbox_container"], 3
            )

            self.driver_manager.driver.execute_script(
                "arguments[0].click();", checkbox1
            )
            self.driver_manager.driver.execute_script(
                "arguments[0].click();", checkbox4
            )
        except Exception as e:
            logger.error(f"Failed to find checkboxes: {e}")

        # Find search button by value
        try:
            search_button = self.driver_manager.find_button_by_value(
                self.TEXT_LABELS["search_button_value"]
            )
            self.driver_manager.driver.execute_script(
                "arguments[0].click();", search_button
            )
        except Exception as e:
            logger.warning(f"Failed to find search button by value: {e}")
            # Try to find button in container
            self.driver_manager.find_button_in_container(
                self.CSS_CLASSES["button_container"]
            ).click()

    def _set_status_filters(self) -> None:
        """Set status filter checkboxes according to options."""
        status_mapping = {
            "status_active": self.status_options.active,
            "status_may_terminate": self.status_options.may_terminate,
            "status_terminated_recoverable": self.status_options.terminated_recoverable,
            "status_terminated": self.status_options.terminated,
        }

        for status_key, should_be_checked in status_mapping.items():
            try:
                # Try to find checkbox by label text
                element = self.driver_manager.find_checkbox_by_label(
                    self.TEXT_LABELS[status_key]
                )
                is_checked = element.is_selected()

                # Click only if current state doesn't match desired state
                if is_checked != should_be_checked:
                    self.driver_manager.driver.execute_script(
                        "arguments[0].click();", element
                    )
                    time.sleep(0.5)

            except Exception as e:
                logger.error(f"Failed to set status checkbox: {e}")

    def _fill_search_form(self, query: str) -> None:
        """Fill and submit search form."""
        try:
            # Find patent owner input field by label text
            search_input = self.driver_manager.find_input_by_parent_text(
                self.TEXT_LABELS["patent_owner_label"]
            )
            logger.info("Found patent owner input field by label text")

        except Exception as e:
            logger.error(f"Failed to find patent owner: {e}")
            raise

        # Clear the field and enter the query
        search_input.clear()
        search_input.send_keys(query)
        logger.info(f"Entered query into patent owner field: {query}")
        time.sleep(0.5)

        self._set_status_filters()

        try:
            # Try to find search form submit button
            search_form_button = self.driver_manager.driver.find_element(
                By.CSS_SELECTOR, "input[type='submit'][value='Поиск']"
            )
            self.driver_manager.driver.execute_script(
                "arguments[0].click();", search_form_button
            )
        except Exception as e:
            logger.error(f"Failed to find search form button: {e}")
            raise

        logger.info("Search form submitted")

    def _get_patent_details(self, patent_id: str) -> Dict:
        """Get detailed information about a patent."""
        try:
            # Open patent details in new tab
            patent_url = f"{self.BASE_URL}document.xhtml?id={patent_id}"
            self.driver_manager.driver.execute_script(
                f'window.open("{patent_url}","_blank");'
            )
            self.driver_manager.driver.switch_to.window(
                self.driver_manager.driver.window_handles[-1]
            )

            self.driver_manager.wait_for_element("StatusR")
            self.driver_manager.wait_for_element("bib")

            # Extract information
            details = self._extract_patent_details()

            # Close tab and return to main window
            self.driver_manager.driver.close()
            self.driver_manager.driver.switch_to.window(
                self.driver_manager.driver.window_handles[0]
            )

            return details

        except Exception as e:
            logger.error(f"Error getting patent details for {patent_id}: {e}")
            self._handle_failed_detail_extraction()
            return {}

    def _extract_patent_header(self) -> PatentHeader:
        """Extract patent header information from top right corner."""
        try:
            # Extract country code (RU)
            country_code = self.driver_manager.driver.find_element(
                By.ID, "top2"
            ).text.strip()

            # Extract patent number (2 820 873)
            number_element = self.driver_manager.driver.find_element(
                By.ID, "top4"
            ).find_element(By.TAG_NAME, "a")
            number = number_element.text.strip()
            doc_url = number_element.get_attribute("href")

            # Extract kind code (C1)
            kind_code = self.driver_manager.driver.find_element(
                By.ID, "top6"
            ).text.strip()

            # Extract IPC codes
            ipc_codes = []
            ipc_elements = self.driver_manager.driver.find_elements(
                By.CSS_SELECTOR, "ul.ipc li a"
            )

            for element in ipc_elements:
                # Extract both the IPC code and its date
                ipc_text = element.find_element(By.CLASS_NAME, "i").text.strip()
                date_text = element.text.split("(")[-1].strip(")")
                ipc_codes.append(f"{ipc_text.strip()} ({date_text})")

            return PatentHeader(
                doc_url=doc_url,
                country_code=country_code,
                number=number,
                kind_code=kind_code,
                ipc_codes=ipc_codes,
            )
        except Exception as e:
            logger.error(f"Error extracting patent header: {e}")
            return PatentHeader("", "", "", [])

    def _extract_patent_details(self) -> Dict:
        """Extract all available patent details from the current page."""

        # Get document name from NameDoc element
        try:
            name_doc_element = self.driver_manager.driver.find_element(By.ID, "NameDoc")
            doc_name = name_doc_element.find_element(By.TAG_NAME, "b").text.strip()
        except Exception as e:
            logger.warning(f"Error extracting document name: {e}")
            doc_name = "ОПИСАНИЕ ???"  # fallback value

        details = {
            doc_name: "",
            "Статус": self._get_status_text(),
            "Пошлина": self._get_fee_text(),
        }

        # Extract header information
        header = self._extract_patent_header()
        details["Ссылка"] = header.doc_url
        details["Документ"] = (
            f"{header.country_code} (11) {header.number} (13) {header.kind_code}"
        )
        if header.ipc_codes:
            details["МПК"] = "\n".join(header.ipc_codes)
        try:
            spk_div = self.driver_manager.driver.find_element(By.CLASS_NAME, "spk")
            details["СПК"] = spk_div.text.strip()
        except Exception as e:
            logger.debug(f"Failed to find SPK element: {e}")
            pass

        # Process all paragraphs
        bib_table = self.driver_manager.driver.find_element(By.ID, "bib")
        for paragraph in bib_table.find_elements(By.TAG_NAME, "p"):
            self._process_paragraph(paragraph, details)

        # Extract invention title from B542
        try:
            b542_element = self.driver_manager.driver.find_element(By.ID, "B542")
            title_text = b542_element.text.strip()
            # Extract text between (54) and the actual title
            if "(54)" in title_text:
                details["(54) Название"] = title_text.split("(54)")[1].strip()
        except Exception as e:
            logger.warning(f"Error extracting B542 title: {e}")

        return details

    def _get_status_text(self) -> str:
        """Get patent status text."""
        elements = self.driver_manager.driver.find_elements(By.ID, "StatusR")
        return elements[0].text if elements else ""

    def _get_fee_text(self) -> str:
        """Get patent fee text."""
        elements = self.driver_manager.driver.find_elements(By.ID, "StatusR")
        return elements[1].text if len(elements) > 1 else ""

    def _process_paragraph(self, paragraph: WebElement, details: Dict) -> None:
        """Process a single paragraph and add its content to details."""
        try:
            text = paragraph.get_attribute("textContent").strip()
            if text:
                parts = text.split(":", 1)
                if len(parts) > 1:
                    details[parts[0].strip()] = parts[1].strip()
                else:
                    details[text] = ""
        except Exception as e:
            logger.warning(f"Error processing paragraph: {e}")

    def _handle_failed_detail_extraction(self) -> None:
        """Handle cleanup after failed detail extraction."""
        try:
            self.driver_manager.driver.close()
            self.driver_manager.driver.switch_to.window(
                self.driver_manager.driver.window_handles[0]
            )
        except Exception as e:
            logger.debug(f"Failed to close window or switch to main window: {e}")
            pass

    def _parse_search_results(self, page_number: int) -> List[PatentResult]:
        """Parse patents from current search results page."""
        results = []

        # Use explicit wait instead of sleep
        try:
            # Wait for search results to appear with explicit timeout
            WebDriverWait(self.driver_manager.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.tr"))
            )
        except Exception as e:
            logger.warning(f"Timeout waiting for search results: {e}")
            return results

        # Find all patent elements
        elements = self.driver_manager.driver.find_elements(By.CSS_SELECTOR, "a.tr")
        if not elements:
            logger.warning("No patent elements found on page")
            return results

        if self.test_mode:
            elements = elements[:5]
            logger.info(f"Test mode: limiting to {len(elements)} patents")

        # Process each patent element
        for element in elements:
            try:
                patent = self._parse_patent_element(element)
                if patent:
                    results.append(patent)

                    # Get and save patent details
                    details = self._get_patent_details(patent.link_id)
                    if details:
                        self.storage.save_patent_details(patent.number, details)
                        self.storage.save_patent_to_csv(patent)
                        logger.info(f"Processed patent {patent.number}")
                    else:
                        logger.warning(
                            f"Failed to get details for patent {patent.number}"
                        )
            except Exception as e:
                logger.warning(f"Error parsing patent element: {e}")
                continue

        return results

    def _parse_patent_element(self, element: WebElement) -> Optional[PatentResult]:
        """Parse single patent element from search results."""
        try:
            link_id = element.get_attribute("id")
            columns = element.find_elements(By.CSS_SELECTOR, "div.td")

            img_element = element.find_elements(By.TAG_NAME, "img")
            img_url = img_element[0].get_attribute("src") if img_element else None

            return PatentResult(
                number=columns[1].text.strip(),
                publication_date=columns[2].text.strip("()"),
                title=columns[4].text.strip(),
                document_type=columns[5].text.strip(),
                link_id=link_id,
                image_url=img_url,
            )
        except Exception as e:
            logger.warning(f"Error creating PatentResult: {e}")
            return None

    def _has_next_page(self) -> bool:
        """Check if there is a next page of results."""
        try:
            # Try to find next page button
            next_button = self.driver_manager.driver.find_element(
                By.CSS_SELECTOR, "a.ui-commandlink.ui-widget.modern-page-next"
            )

            # Check if button is disabled
            disabled = "ui-state-disabled" in next_button.get_attribute(
                "class"
            ) or "disabled" in next_button.get_attribute("class")

            # Also check if onclick attribute is empty or None
            onclick = next_button.get_attribute("onclick")
            if not onclick or onclick == "return false;":
                return False

            return not disabled

        except Exception as e:
            logger.debug(f"Failed to check for next page: {e}")
            return False

    def collect_all_results(self) -> List[PatentResult]:
        """Collect all patent results across pages."""
        page = 1
        all_results = []
        max_retries = 3

        while True:
            logger.info(f"Processing page {page}")

            # Try to parse results with retries
            retry_count = 0
            results = []

            while retry_count < max_retries and not results:
                try:
                    results = self._parse_search_results(page)
                    if not results and retry_count < max_retries - 1:
                        logger.warning(f"No results found on page {page}, retrying...")
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"Error parsing page {page}: {e}")
                    if retry_count < max_retries - 1:
                        logger.info(f"Retrying page {page}...")
                        time.sleep(1)

                retry_count += 1

            # Add results to collection
            if results:
                all_results.extend(results)
                logger.info(f"Found {len(results)} results on page {page}")
            else:
                logger.warning(
                    f"No results found on page {page} after {max_retries} attempts"
                )

            # Exit conditions
            if self.test_mode and page >= 3:
                logger.info("Test mode: stopping after 3 pages")
                break

            # Try to go to next page
            if not self._go_to_next_page():
                logger.info("No more pages available")
                break

            page += 1

        logger.info(f"Total results collected: {len(all_results)}")
        return all_results

    def _go_to_next_page(self) -> bool:
        """Navigate to next page if available."""
        if not self._has_next_page():
            return False

        try:
            try:
                next_button = self.driver_manager.driver.find_element(
                    By.CSS_SELECTOR, "a.ui-commandlink.ui-widget.modern-page-next"
                )

                # Check if button is disabled
                disabled = "ui-state-disabled" in next_button.get_attribute(
                    "class"
                ) or "disabled" in next_button.get_attribute("class")

                # Also check if onclick attribute is empty or None
                onclick = next_button.get_attribute("onclick")
                if disabled or not onclick or onclick == "return false;":
                    return False
            except Exception:
                logger.error("Failed to find next page button")

            # Use JavaScript click which is more reliable
            self.driver_manager.driver.execute_script(
                "arguments[0].click();", next_button
            )

            # Wait for specific elements to indicate page has loaded
            try:
                # Wait for results to load (more specific than generic page load)
                WebDriverWait(self.driver_manager.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".search-result-item")
                    )
                )
            except Exception:
                # Fallback to generic page load wait
                logger.warning(
                    "Failed to wait for results to load, falling back to page load"
                )
                self.driver_manager.wait_for_page_load()

            # Short pause to ensure page is fully interactive
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to next page: {e}")
            return False

    def start_search(
        self,
        query: str = (
            "аэрогидродинамический or (аэрогидродинамический институт) "
            "or (цаги not научно)"
        ),
    ) -> List[PatentResult]:
        """Start patent search process."""
        try:
            logger.info("Opening FIPS page")
            self.driver_manager.driver.get(self.BASE_URL)
            self.driver_manager.wait_for_page_load()

            self._select_search_options()
            self._fill_search_form(query)
            self.driver_manager.wait_for_page_load()

            results = self.collect_all_results()

            logger.info("Search completed successfully")
            logger.info(f"Detailed information saved to: {self.storage.patents_dir}")

            return results

        except Exception as e:
            logger.error(f"Error during search: {e}")
            raise

    def close(self) -> None:
        """Clean up resources."""
        if self.driver_manager.driver:
            self.driver_manager.driver.quit()
            logger.info("Browser closed")
