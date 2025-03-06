import time
from pathlib import Path
from typing import Dict, List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

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
    }

    # Fallback selectors if text-based search fails
    FALLBACK_SELECTORS = {
        "checkbox1": "db-selection-form:dbsGrid1:0:dbsGrid1checkbox",
        "checkbox4": "db-selection-form:dbsGrid1:3:dbsGrid1checkbox",
        "patent_owner_input": "fields:6:j_idt109",
        "search_form_button": "j_idt128",
        "next_page_button": "j_idt98:j_idt109",
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
            # Try to find by partial ID as fallback
            self.driver_manager.find_element_by_partial_id("db-selection-form").click()

        time.sleep(1)  # Wait for animation

        # Find checkboxes by partial ID
        try:
            checkbox1 = self.driver_manager.find_element_by_partial_id(
                "dbsGrid1:0:dbsGrid1checkbox"
            )
            checkbox4 = self.driver_manager.find_element_by_partial_id(
                "dbsGrid1:3:dbsGrid1checkbox"
            )

            self.driver_manager.driver.execute_script(
                "arguments[0].click();", checkbox1
            )
            self.driver_manager.driver.execute_script(
                "arguments[0].click();", checkbox4
            )
        except Exception as e:
            logger.warning(f"Failed to find checkboxes by partial ID: {e}")
            # Fallback to original selectors
            self.driver_manager.click_element(
                self.FALLBACK_SELECTORS["checkbox1"], By.NAME
            )
            self.driver_manager.click_element(
                self.FALLBACK_SELECTORS["checkbox4"], By.NAME
            )

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
            # Try to find by partial ID as fallback
            self.driver_manager.click_element(
                self.FALLBACK_SELECTORS["search_button"], By.NAME
            )

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
                logger.warning(f"Error setting status checkbox {status_key}: {e}")
                # No fallback for status checkboxes as they're critical

    def _fill_search_form(self, query: str) -> None:
        """Fill and submit search form."""
        try:
            # Try to find patent owner input by partial ID
            search_input = self.driver_manager.find_element_by_partial_id(
                "fields:6:j_idt"
            )
        except Exception as e:
            logger.debug(f"Failed to find patent owner input by partial ID: {e}")
            # Fallback to original selector
            search_input = self.driver_manager.wait_for_element(
                self.FALLBACK_SELECTORS["patent_owner_input"]
            )

        search_input.clear()
        search_input.send_keys(query)
        time.sleep(0.5)

        self._set_status_filters()

        try:
            # Try to find search form button by partial ID
            search_form_button = self.driver_manager.find_element_by_partial_id(
                "j_idt128"
            )
            self.driver_manager.driver.execute_script(
                "arguments[0].click();", search_form_button
            )
        except Exception as e:
            logger.debug(f"Failed to find search form button by partial ID: {e}")
            # Fallback to original selector
            self.driver_manager.click_element(
                self.FALLBACK_SELECTORS["search_form_button"], By.NAME
            )

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
        time.sleep(2)  # Wait for content to load

        elements = self.driver_manager.driver.find_elements(By.CSS_SELECTOR, "a.tr")
        if self.test_mode:
            elements = elements[:5]

        for element in elements:
            try:
                patent = self._parse_patent_element(element)
                if patent:
                    results.append(patent)
                    details = self._get_patent_details(patent.link_id)
                    self.storage.save_patent_details(patent.number, details)
                    self.storage.save_patent_to_csv(patent)
                    logger.info(f"Processed patent {patent.number}")
            except Exception as e:
                logger.warning(f"Error parsing patent element: {e}")
                continue

        logger.info(f"Found {len(results)} results on page {page_number}")
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
            # Try to find next page button by partial ID
            next_button = self.driver_manager.find_element_by_partial_id(
                "j_idt98:j_idt109"
            )
            return "ui-state-disabled" not in next_button.get_attribute("class")
        except Exception as e:
            try:
                # Fallback to original selector
                next_button = self.driver_manager.wait_for_element(
                    self.FALLBACK_SELECTORS["next_page_button"]
                )
                return "ui-state-disabled" not in next_button.get_attribute("class")
            except Exception as e2:
                logger.debug(f"Failed to check for next page: {e2} (after {e})")
                return False

    def collect_all_results(self) -> List[PatentResult]:
        """Collect all patent results across pages."""
        page = 1
        all_results = []

        while True:
            logger.info(f"Processing page {page}")
            results = self._parse_search_results(page)
            all_results.extend(results)

            if self.test_mode and page >= 3:
                break

            if not self._go_to_next_page():
                break

            page += 1
            time.sleep(2)

        logger.info(f"Total results collected: {len(all_results)}")
        return all_results

    def _go_to_next_page(self) -> bool:
        """Navigate to next page if available."""
        if self._has_next_page():
            try:
                # Try to find next page button by partial ID
                next_button = self.driver_manager.find_element_by_partial_id(
                    "j_idt98:j_idt109"
                )
                self.driver_manager.driver.execute_script(
                    "arguments[0].click();", next_button
                )
            except Exception as e:
                logger.debug(f"Failed to find next page button by partial ID: {e}")
                # Fallback to original selector
                self.driver_manager.click_element(
                    self.FALLBACK_SELECTORS["next_page_button"]
                )

            self.driver_manager.wait_for_page_load()
            return True
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
