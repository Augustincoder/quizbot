"""
Data storage module for managing test questions.
Handles JSON file persistence and in-memory caching.
"""
import json
import asyncio
from pathlib import Path
from typing import Optional
import logging

from config import DATA_DIR, QUESTIONS_PER_TEST
from scraper import run_scraper

logger = logging.getLogger(__name__)


class TestStorage:
    """
    Manages test data storage and retrieval.
    
    On first run: scrapes questions and saves to JSON files.
    On subsequent runs: loads from JSON files (no scraping).
    """
    
    def __init__(self):
        # In-memory cache: test_id -> list of questions
        self._tests: dict[int, list[dict]] = {}
        self._loaded = False
        self._total_questions = 0
    
    def _get_test_file(self, test_id: int) -> Path:
        """Get path to JSON file for a test."""
        return DATA_DIR / f"test_{test_id}.json"
    
    def _get_existing_test_files(self) -> list[Path]:
        """Find all existing test JSON files."""
        return sorted(DATA_DIR.glob("test_*.json"))
    
    def _split_into_tests(self, questions: list[dict]) -> dict[int, dict]:
        """
        Split questions into test blocks of QUESTIONS_PER_TEST.
        
        Returns dict of test_id -> test_data
        """
        tests = {}
        
        for i in range(0, len(questions), QUESTIONS_PER_TEST):
            test_id = (i // QUESTIONS_PER_TEST) + 1
            test_questions = questions[i:i + QUESTIONS_PER_TEST]
            
            start = i + 1
            end = i + len(test_questions)
            
            tests[test_id] = {
                "test_id": test_id,
                "range": f"{start}-{end}",
                "questions": test_questions
            }
        
        return tests
    
    async def _scrape_and_save(self, progress_callback=None) -> None:
        """Scrape all questions and save to JSON files."""
        logger.info("No existing data found. Starting scraping...")
        
        questions = await run_scraper(progress_callback)
        
        if not questions:
            raise RuntimeError("No questions scraped. Check the source URL and network.")
        
        tests = self._split_into_tests(questions)
        
        # Save each test to JSON
        for test_id, test_data in tests.items():
            file_path = self._get_test_file(test_id)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(test_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {file_path.name} with {len(test_data['questions'])} questions")
        
        # Load into memory
        self._tests = {tid: data["questions"] for tid, data in tests.items()}
        self._total_questions = len(questions)
        logger.info(f"Created {len(tests)} tests from {len(questions)} questions")
    
    def _load_from_files(self) -> None:
        """Load all test data from JSON files into memory."""
        test_files = self._get_existing_test_files()
        
        for file_path in test_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                test_id = data["test_id"]
                self._tests[test_id] = data["questions"]
                self._total_questions += len(data["questions"])
                logger.debug(f"Loaded {file_path.name}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error loading {file_path}: {e}")
        
        logger.info(f"Loaded {len(self._tests)} tests with {self._total_questions} total questions")
    
    async def initialize(self, force_scrape: bool = False, progress_callback=None) -> None:
        """
        Initialize storage - load existing data or scrape if needed.
        
        Args:
            force_scrape: If True, re-scrape even if data exists
            progress_callback: Optional callback for scraping progress
        """
        if self._loaded and not force_scrape:
            return
        
        self._tests.clear()
        self._total_questions = 0
        
        existing_files = self._get_existing_test_files()
        
        if existing_files and not force_scrape:
            logger.info(f"Found {len(existing_files)} existing test files. Loading...")
            self._load_from_files()
        else:
            await self._scrape_and_save(progress_callback)
        
        self._loaded = True
    
    def get_test_count(self) -> int:
        """Get number of available tests."""
        return len(self._tests)
    
    def get_total_questions(self) -> int:
        """Get total number of questions across all tests."""
        return self._total_questions
    
    def get_test_ids(self) -> list[int]:
        """Get list of available test IDs in order."""
        return sorted(self._tests.keys())
    
    def get_test(self, test_id: int) -> Optional[list[dict]]:
        """
        Get questions for a specific test.
        
        Returns None if test doesn't exist.
        """
        return self._tests.get(test_id)
    
    def get_test_info(self, test_id: int) -> Optional[dict]:
        """Get test metadata (id, range, question count)."""
        questions = self._tests.get(test_id)
        if questions is None:
            return None
        
        # Calculate range
        start = (test_id - 1) * QUESTIONS_PER_TEST + 1
        end = start + len(questions) - 1
        
        return {
            "test_id": test_id,
            "range": f"{start}-{end}",
            "question_count": len(questions)
        }
    
    def get_question(self, test_id: int, question_index: int) -> Optional[dict]:
        """
        Get a specific question from a test.
        
        Args:
            test_id: Test number (1-based)
            question_index: Question index within test (0-based)
        
        Returns:
            Question dict or None if not found
        """
        test = self._tests.get(test_id)
        if test is None:
            return None
        
        if 0 <= question_index < len(test):
            return test[question_index]
        
        return None


# Global storage instance
storage = TestStorage()


async def initialize_storage(force_scrape: bool = False, progress_callback=None) -> None:
    """Initialize the global storage instance."""
    await storage.initialize(force_scrape, progress_callback)


def get_storage() -> TestStorage:
    """Get the global storage instance."""
    return storage


# Example JSON structure (for reference)
EXAMPLE_JSON = """
{
  "test_id": 1,
  "range": "1-25",
  "questions": [
    {
      "question": "Korporativ boshqaruv nima?",
      "options": [
        "Kompaniya faoliyatini tartibga solish tizimi",
        "Moliyaviy hisobot tizimi",
        "Xodimlarni boshqarish usuli",
        "Marketing strategiyasi"
      ],
      "correct_index": 0
    },
    {
      "question": "Korporativ boshqaruvning asosiy maqsadi nima?",
      "options": [
        "Foyda olish",
        "Xodimlar sonini oshirish",
        "Aktsiyadorlar manfaatlarini himoya qilish",
        "Reklama faoliyatini kengaytirish"
      ],
      "correct_index": 2
    }
  ]
}
"""


if __name__ == "__main__":
    # Print example JSON structure
    print("Example JSON format:")
    print(EXAMPLE_JSON)
