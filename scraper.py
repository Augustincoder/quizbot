"""
Web scraper for extracting exam questions from the source website.
Parses question text, options, and correct answers from HTML.
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import Optional
import logging

from config import BASE_URL, SCRAPE_PARAMS, REQUEST_TIMEOUT, REQUEST_DELAY, MAX_RETRIES

logger = logging.getLogger(__name__)


class QuestionScraper:
    """Asynchronous scraper for exam questions."""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Initialize HTTP session."""
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
    
    def _build_url(self, question_number: int) -> str:
        """Construct URL for a specific question number."""
        params = "&".join(f"{k}={v}" for k, v in SCRAPE_PARAMS.items())
        return f"{BASE_URL}?{params}&q={question_number}"
    
    async def _fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from URL with retry logic.
        Returns None if page doesn't exist or request fails.
        """
        for attempt in range(MAX_RETRIES):
            try:
                async with self.session.get(url) as response:
                    if response.status == 404:
                        return None
                    if response.status != 200:
                        logger.warning(f"HTTP {response.status} for {url}")
                        continue
                    return await response.text()
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on attempt {attempt + 1} for {url}")
            except aiohttp.ClientError as e:
                logger.warning(f"Request error on attempt {attempt + 1}: {e}")
            
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(REQUEST_DELAY * (attempt + 1))
        
        return None
    
    def _parse_question(self, html: str, question_number: int) -> Optional[dict]:
        """
        Parse question data from HTML content.
        
        Extracts:
        - Question text
        - Answer options (maintaining original order)
        - Correct answer index (from data-correct="1" attribute)
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find question text - try multiple selectors
        question_elem = (
            soup.select_one('.question-text') or
            soup.select_one('.question') or
            soup.select_one('h2') or
            soup.select_one('h3')
        )
        
        if not question_elem:
            logger.warning(f"No question text found for q={question_number}")
            return None
        
        question_text = question_elem.get_text(strip=True)
        
        # Find all option labels with data-correct attribute
        option_labels = soup.select('label.option-item[data-correct]')
        
        if not option_labels:
            # Fallback: try finding options by other selectors
            option_labels = soup.select('.option-item[data-correct]')
        
        if not option_labels:
            logger.warning(f"No options found for q={question_number}")
            return None
        
        options = []
        correct_index = None
        
        for idx, label in enumerate(option_labels):
            # Extract option text
            option_text_elem = label.select_one('.option-text')
            if option_text_elem:
                option_text = option_text_elem.get_text(strip=True)
            else:
                # Fallback: get all text from label
                option_text = label.get_text(strip=True)
            
            options.append(option_text)
            
            # Check if this is the correct answer
            data_correct = label.get('data-correct', '0')
            if data_correct == '1':
                correct_index = idx
        
        if correct_index is None:
            logger.warning(f"No correct answer marked for q={question_number}")
            return None
        
        if len(options) < 2:
            logger.warning(f"Too few options ({len(options)}) for q={question_number}")
            return None
        
        return {
            "question": question_text,
            "options": options,
            "correct_index": correct_index
        }
    
    async def scrape_question(self, question_number: int) -> Optional[dict]:
        """Scrape a single question by number."""
        url = self._build_url(question_number)
        html = await self._fetch_page(url)
        
        if html is None:
            return None
        
        return self._parse_question(html, question_number)
    
    async def scrape_all_questions(self, progress_callback=None) -> list[dict]:
        """
        Scrape all available questions sequentially.
        Stops when a question returns None (end of questions).
        
        Args:
            progress_callback: Optional async function called with (current, total_estimate)
        
        Returns:
            List of question dictionaries
        """
        questions = []
        question_number = 1
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        logger.info("Starting to scrape all questions...")
        
        while True:
            question_data = await self.scrape_question(question_number)
            
            if question_data is None:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.info(f"Reached end of questions at q={question_number}")
                    break
                question_number += 1
                continue
            
            consecutive_failures = 0
            questions.append(question_data)
            
            if progress_callback:
                await progress_callback(question_number, question_number + 50)
            
            logger.debug(f"Scraped question {question_number}: {question_data['question'][:50]}...")
            
            question_number += 1
            await asyncio.sleep(REQUEST_DELAY)
        
        logger.info(f"Scraping complete. Total questions: {len(questions)}")
        return questions


async def run_scraper(progress_callback=None) -> list[dict]:
    """
    Main scraper entry point.
    Returns list of all scraped questions.
    """
    async with QuestionScraper() as scraper:
        return await scraper.scrape_all_questions(progress_callback)


# For standalone testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        questions = await run_scraper()
        print(f"Scraped {len(questions)} questions")
        if questions:
            print(f"First question: {questions[0]}")
    
    asyncio.run(main())
