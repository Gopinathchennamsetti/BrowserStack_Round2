from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from translate import Translator
import requests
import os
from datetime import datetime, timedelta
import logging
import time
from urllib.parse import urljoin
import hashlib
from collections import Counter
import re

class ElPaisArticleAnalyzer:
    def __init__(self, base_url="https://elpais.com"):
        """Initialize the analyzer with WebDriver and Translator"""
        self.base_url = base_url
        self.translator = Translator(to_lang="en", from_lang="es")
        self.setup_logging()
        self.setup_driver()
        self.setup_directories()

    def setup_logging(self):
        """Set up logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('elpais_scraper.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_driver(self):
        """Configure and initialize Chrome WebDriver"""
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--lang=es')
        options.add_argument('--accept-lang=es')
        options.add_experimental_option('prefs', {'intl.accept_languages': 'es,es_ES'})
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)

    def setup_directories(self):
        """Create directory for storing downloaded images"""
        self.image_dir = "article_images"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.image_dir = f"{self.image_dir}_{timestamp}"
        
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)
            self.logger.info(f"Created image directory: {self.image_dir}")

    def navigate_to_opinion_section(self):
        """Navigate to the Opinion section of El País"""
        try:
            self.driver.get(self.base_url)
            time.sleep(2)

            try:
                cookie_button = self.wait.until(
                    EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button"))
                )
                cookie_button.click()
                self.logger.info("Accepted cookies")
                time.sleep(1)
            except TimeoutException:
                self.logger.info("No cookie consent needed")

            opinion_url = urljoin(self.base_url, "/opinion")
            self.driver.get(opinion_url)
            time.sleep(2)
            self.logger.info("Navigated to Opinion section")

        except Exception as e:
            self.logger.error(f"Navigation error: {str(e)}")
            raise

    def get_article_links(self, max_links=10):
        """Get links to opinion articles for today or yesterday."""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            allowed_dates = [f"/opinion/{today}/", f"/opinion/{yesterday}/"]

            articles = self.wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "article a[href*='/opinion/']")
                )
            )
            
            article_links = []
            seen_links = set()
            
            for article in articles:
                href = article.get_attribute('href')
                if href and href not in seen_links and any(date in href for date in allowed_dates):
                    seen_links.add(href)
                    article_links.append(href)
                    if len(article_links) >= max_links:
                        break

            self.logger.info(f"Found {len(article_links)} article links matching dates: {allowed_dates}")
            return article_links

        except Exception as e:
            self.logger.error(f"Error getting article links: {str(e)}")
            return []

    def translate_title(self, title):
        """Translate article title to English"""
        try:
            translated_title = self.translator.translate(title)
            return translated_title
        except Exception as e:
            self.logger.error(f"Translation error: {str(e)}")
            return title

    def scrape_article(self, url, article_number):
        """Scrape content from a single article"""
        try:
            print(f"Scraping article {article_number}: {url}")
            self.driver.get(url)
            time.sleep(2)

            if "/opinion/editoriales/" in url or "/opinion/tribunas/" in url:
                self.logger.warning(f"Skipping folder-like article URL: {url}")
                return None

            try:
                title_element = self.wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "article h1")
                    )
                )
                title = title_element.text.strip()
                if not title:
                    self.logger.warning("Article has no valid title. Skipping.")
                    return None

                self.logger.info(f"Found title: {title}")
            except TimeoutException:
                self.logger.error("Could not find article title")
                return None

            try:
                paragraphs = self.wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "article p")
                    )
                )
                content = [p.text for p in paragraphs]
            except TimeoutException:
                self.logger.error("Could not find article content")
                return None

            try:
                image_element = self.wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "article img")
                    )
                )
                image_url = image_element.get_attribute('src')
                self.logger.info(f"Found image URL: {image_url}")

                # Download and save the image
                if image_url:
                    image_response = requests.get(image_url, stream=True)
                    if image_response.status_code == 200:
                        image_name = hashlib.md5(image_url.encode('utf-8')).hexdigest() + ".jpg"
                        image_path = os.path.join(self.image_dir, image_name)
                        with open(image_path, 'wb') as image_file:
                            for chunk in image_response.iter_content(1024):
                                image_file.write(chunk)
                        self.logger.info(f"Image saved: {image_path}")
                    else:
                        self.logger.error(f"Failed to download image: {image_url}")
                else:
                    self.logger.warning("No image URL found")
            except TimeoutException:
                image_url = None
                self.logger.warning("No image found")

            return {
                'title': title,
                'content': "\n".join(content),
                'url': url
            }

        except Exception as e:
            self.logger.error(f"Error scraping article {url}: {str(e)}")
            return None

    def process_articles(self, num_articles=5):
        """Main method to process articles"""
        try:
            self.navigate_to_opinion_section()
            article_links = self.get_article_links(max_links=10)
            
            articles = []
            for i, url in enumerate(article_links, 1):
                self.logger.info(f"Processing article {i} of {len(article_links)}")
                article = self.scrape_article(url, i)
                if article:
                    articles.append(article)
                if len(articles) >= num_articles:
                    break

            return articles

        finally:
            self.driver.quit()

    def analyze_translated_headers(self, articles):
        """Translate and analyze article headers"""
        translated_titles = []
        for article in articles:
            translated_title = self.translate_title(article['title'])
            translated_titles.append(translated_title)
            print(f"Original Title: {article['title']}\nTranslated Title: {translated_title}\n")

        all_words = []
        for title in translated_titles:
            words = re.findall(r'\b\w+\b', title.lower())
            all_words.extend(words)

        word_counts = Counter(all_words)
        repeated_words = {word: count for word, count in word_counts.items() if count > 2}

        print("\nRepeated Words Analysis:")
        for word, count in repeated_words.items():
            print(f"{word}: {count}")

def main():
    try:
        analyzer = ElPaisArticleAnalyzer()
        articles = analyzer.process_articles()
        if articles:
            analyzer.analyze_translated_headers(articles)
        else:
            print("No articles to analyze.")
    except Exception as e:
        print(f"Error in main execution: {str(e)}")

if __name__ == "__main__":
    main()
