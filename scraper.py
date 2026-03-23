import requests
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://6799ad7a0ea7b.xvest4.ru/ReadyForExam/ReadyForExam/index.php?page=fulltest&slug=korporativ-boshqaruv-1&session=4D92718D&q="

def fetch_all_questions() -> list:
    """Scrapes questions from the URL sequentially."""
    logger.info("Starting web scraper...")
    questions = []
    q_num = 1
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    while True:
        url = f"{BASE_URL}{q_num}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find options first to verify this page has a valid question
            option_elements = soup.select('[data-correct]')
            if not option_elements:
                break # No options found, assuming end of test

            # Attempt to find question text (Fallback to a generic approach if specific class varies)
            question_el = soup.select_one('.question-text')
            if question_el:
                question_text = question_el.get_text(strip=True)
            else:
                # Fallback: grab the first prominent paragraph or heading
                fallback_el = soup.select_one('h3, .text-question, p.lead')
                question_text = fallback_el.get_text(strip=True) if fallback_el else f"Question {q_num}"

            options = []
            correct_index = 0
            
            for idx, opt in enumerate(option_elements):
                # Extract text from .option-text if it exists, else from the container
                text_el = opt.select_one('.option-text')
                opt_text = text_el.get_text(strip=True) if text_el else opt.get_text(strip=True)
                options.append(opt_text)
                
                # Check data-correct rule
                if opt.get('data-correct') == "1":
                    correct_index = idx

            questions.append({
                "question": question_text,
                "options": options,
                "correct_index": correct_index
            })
            
            logger.info(f"Scraped Question {q_num}")
            q_num += 1
            
        except Exception as e:
            logger.error(f"Error scraping question {q_num}: {e}")
            break

    logger.info(f"Scraping complete. Total questions scraped: {len(questions)}")
    return questions
