import os
import time
import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import trafilatura
import requests
from tqdm import tqdm

TQDM_WIDTH = 140

# Configure logging
logging.basicConfig(
    filename='scraping_errors.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Cache for robots.txt parsers by domain
robots_cache = {}

# Configuration
RATE_LIMIT_DELAY = 1.0  # seconds between requests
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
USER_AGENT = 'ElectionJobResearchBot/1.0'


def can_fetch(url):
    """
    Check if we're allowed to scrape this URL according to robots.txt.
    Uses caching to avoid repeated robots.txt fetches for the same domain.
    """
    try:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        # Check cache first
        if domain not in robots_cache:
            # For now, skip robots.txt checking to avoid hangs
            # In production, consider using requests with timeout instead
            logging.info(f"Skipping robots.txt check for {domain} (not implemented with timeout)")
            robots_cache[domain] = None

        rp = robots_cache[domain]
        if rp is None:
            return True

        return rp.can_fetch(USER_AGENT, url)
    except Exception as e:
        logging.error(f"Error checking robots.txt for {url}: {e}")
        # If there's an error, err on the side of caution and allow
        return True


def scrape_full_description(url):
    """
    Scrape the full text content from a URL using trafilatura.

    Returns:
        str: The extracted text content, or None if extraction failed
    """
    try:
        # Check robots.txt
        if not can_fetch(url):
            logging.info(f"Robots.txt blocks scraping: {url}")
            return None

        # Download the page with requests (which has better timeout control)
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        downloaded = response.text

        if downloaded is None:
            logging.warning(f"Failed to download: {url}")
            return None

        # Extract the text content
        text = trafilatura.extract(downloaded, include_comments=False)

        if text is None:
            logging.warning(f"Failed to extract text from: {url}")
            return None

        return text

    except requests.Timeout:
        logging.warning(f"Timeout downloading: {url}")
        return None
    except requests.RequestException as e:
        logging.warning(f"Request error for {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error scraping {url}: {e}")
        return None


def scrape_with_retry(url, max_retries=MAX_RETRIES):
    """
    Attempt to scrape a URL with exponential backoff retry logic.

    Args:
        url: The URL to scrape
        max_retries: Maximum number of retry attempts

    Returns:
        tuple: (text_content, error_message)
    """
    for attempt in range(max_retries):
        try:
            text = scrape_full_description(url)

            if text is not None:
                return text, None

            # If we got None but no exception, it might be a temporary issue
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * RATE_LIMIT_DELAY
                time.sleep(wait_time)

        except requests.exceptions.Timeout:
            logging.warning(f"Timeout on attempt {attempt + 1} for {url}")
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) * RATE_LIMIT_DELAY)
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error on attempt {attempt + 1} for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) * RATE_LIMIT_DELAY)
        except Exception as e:
            logging.error(f"Unexpected error scraping {url}: {e}")
            return None, str(e)

    return None, "Max retries exceeded"


def save_full_description(text, year, date, row_index):
    """
    Save full description text to filesystem.

    Args:
        text: The full text content
        year: Year (e.g., "2024")
        date: Date in MM-DD format (e.g., "01-05")
        row_index: The row index in the CSV (0-based)

    Returns:
        str: Path to the saved file
    """
    # Create directory structure: job-descriptions/YYYY/MM-DD/
    dir_path = os.path.join('job-descriptions', str(year), date)
    os.makedirs(dir_path, exist_ok=True)

    # Create filename: row-XXXX.txt
    filename = f"row-{row_index:04d}.txt"
    file_path = os.path.join(dir_path, filename)

    # Save the text
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return file_path


def scrape_new_jobs(df):
    """
    Scrape full descriptions for new jobs in a dataframe.

    Args:
        df: pandas DataFrame with 'link', 'year', 'date' columns

    Returns:
        DataFrame with additional columns:
            - full_text_preview: First 500 chars
            - full_text_length: Character count
            - full_text_scraped_date: Timestamp
            - full_text_file: Path to saved file
    """
    import pandas as pd
    from datetime import datetime

    # Initialize new columns
    df['full_text_preview'] = None
    df['full_text_length'] = None
    df['full_text_scraped_date'] = None
    df['full_text_file'] = None

    if len(df) == 0:
        return df

    for idx in tqdm(df.index, ncols=TQDM_WIDTH, desc='scraping full job descriptions'):
        row = df.loc[idx]
        url = row['link']

        # Skip empty or invalid URLs
        if pd.isna(url) or url == '' or not url.startswith('http'):
            continue

        # Scrape with retry logic
        text, error = scrape_with_retry(url)

        if text is not None and len(text) > 0:
            # Save to file
            file_path = save_full_description(text, row['year'], row['date'], idx)

            # Update dataframe
            df.at[idx, 'full_text_preview'] = text[:500]
            df.at[idx, 'full_text_length'] = len(text)
            df.at[idx, 'full_text_scraped_date'] = datetime.now().isoformat()
            df.at[idx, 'full_text_file'] = file_path

            logging.info(f"Successfully scraped {url} ({len(text)} chars)")
        else:
            error_msg = error if error else "Unknown error"
            logging.error(f"Failed to scrape {url}: {error_msg}")

        # Rate limiting: wait between requests
        time.sleep(RATE_LIMIT_DELAY)

    return df
