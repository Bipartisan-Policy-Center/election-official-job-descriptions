import os
import time
import logging
import re
import json
import html
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import trafilatura
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup

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

# Domains that require JavaScript rendering (SPAs)
JS_REQUIRED_DOMAINS = [
    'governmentjobs.com',
    'neogov.com',
    'paycomonline.net',
    'applicantpro.com',
]

# Playwright browser instance (initialized lazily)
_browser = None
_playwright = None


def get_browser():
    """
    Get or initialize the Playwright browser instance.
    Uses lazy initialization and keeps browser alive for performance.
    """
    global _browser, _playwright

    if _browser is None:
        try:
            from playwright.sync_api import sync_playwright
            _playwright = sync_playwright().start()
            _browser = _playwright.chromium.launch(headless=True)
            logging.info("Playwright browser initialized")
        except Exception as e:
            logging.error(f"Failed to initialize Playwright: {e}")
            return None

    return _browser


def close_browser():
    """Close the Playwright browser if it's open."""
    global _browser, _playwright

    if _browser:
        try:
            _browser.close()
            _browser = None
        except:
            pass

    if _playwright:
        try:
            _playwright.stop()
            _playwright = None
        except:
            pass


def needs_javascript(url):
    """Check if a URL requires JavaScript rendering."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')

    return any(js_domain in domain for js_domain in JS_REQUIRED_DOMAINS)


def scrape_with_browser(url):
    """
    Scrape content using Playwright for JavaScript-rendered pages.

    Args:
        url: The URL to scrape

    Returns:
        str: The page HTML content, or None if failed
    """
    browser = get_browser()
    if not browser:
        logging.error("Browser not available for JavaScript rendering")
        return None

    page = None
    try:
        page = browser.new_page(user_agent=USER_AGENT)
        page.set_default_timeout(REQUEST_TIMEOUT * 1000)  # Convert to milliseconds

        # Navigate to the page
        page.goto(url, wait_until='domcontentloaded')

        # Try to close cookie/privacy banners (common on governmentjobs.com)
        try:
            # Wait a moment for banner to appear
            page.wait_for_timeout(1000)

            # Common selectors for cookie/privacy accept buttons
            accept_selectors = [
                'button:has-text("Accept")',
                'button:has-text("I Accept")',
                'button:has-text("OK")',
                'button:has-text("Got it")',
                '.cookie-accept',
                '#cookie-accept',
            ]

            for selector in accept_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.locator(selector).first.click(timeout=2000)
                        logging.info(f"Clicked accept button: {selector}")
                        break
                except:
                    pass
        except:
            pass

        # Wait for page to be fully loaded
        page.wait_for_load_state('networkidle', timeout=10000)

        # Extra wait for dynamic content
        page.wait_for_timeout(2000)

        # Get the rendered HTML
        content = page.content()

        if page:
            page.close()

        return content

    except Exception as e:
        logging.error(f"Browser scraping failed for {url}: {e}")
        if page:
            try:
                page.close()
            except:
                pass
        return None


def is_generic_content(text):
    """
    Detect if the extracted text is generic/useless (like privacy policy).

    Args:
        text: The extracted text

    Returns:
        bool: True if content appears to be generic/useless
    """
    if not text or len(text) < 100:
        return True

    text_lower = text.lower()

    # Check the first 1000 chars for generic indicators
    # (Job descriptions should mention job-related terms early)
    preview = text_lower[:1000]

    # Strong indicators of generic content
    strong_generic_phrases = [
        'privacy policy',
        'cookie policy',
        'terms of service',
        'terms and conditions',
        'data protection',
        'gdpr',
        'page not found',
        '404 error',
    ]

    # Count how many generic phrases appear
    generic_count = sum(1 for phrase in strong_generic_phrases if phrase in preview)

    # If multiple generic phrases in the beginning, it's probably generic
    if generic_count >= 2:
        return True

    # If text is very short, check more carefully
    if len(text) < 500:
        if generic_count >= 1:
            return True

    # Check for job-related keywords that indicate it's a real job posting
    job_keywords = [
        'responsibilities',
        'qualifications',
        'salary',
        'position',
        'required',
        'experience',
        'education',
        'duties',
        'benefits',
        'apply',
        'application',
    ]

    # If we find job keywords, it's probably valid
    job_keyword_count = sum(1 for keyword in job_keywords if keyword in text_lower)
    if job_keyword_count >= 3:
        return False

    # Default: if it's short and has any generic phrase, reject it
    if len(text) < 1000 and generic_count > 0:
        return True

    return False


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


def extract_governmentjobs_content(page_html):
    """
    Extract job description from governmentjobs.com JSON structure.
    Also extracts metadata from JSON-LD structured data.

    Args:
        page_html: The HTML content of the page

    Returns:
        str: Extracted job description text with metadata, or None if not found
    """
    try:
        description_text = None

        # Extract main job description from JSON
        match = re.search(r'"description"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', page_html)

        if match:
            # Get the JSON-escaped string
            description_json = match.group(1)

            # Decode JSON escaping
            description_json = description_json.replace('\\"', '"')
            description_json = description_json.replace('\\n', '\n')

            # Decode HTML entities (like &lt; &gt; &amp;)
            description_html = html.unescape(description_json)

            # Parse HTML and extract text with better formatting
            soup = BeautifulSoup(description_html, 'html.parser')

            # Remove inline formatting tags that shouldn't cause line breaks
            inline_tags = ['strong', 'b', 'em', 'i', 'u', 'span', 'a']
            for tag in inline_tags:
                for element in soup.find_all(tag):
                    element.unwrap()  # Replace tag with its contents

            # Now extract text (block elements will create line breaks)
            description_text = soup.get_text(separator='\n', strip=True)

            # Clean up excessive whitespace
            lines = [line.strip() for line in description_text.split('\n') if line.strip()]
            description_text = '\n'.join(lines)

        # Extract metadata from JSON-LD structured data
        soup = BeautifulSoup(page_html, 'html.parser')
        metadata_parts = []

        # Find JSON-LD script tag
        json_ld_script = soup.find('script', type='application/ld+json')

        if json_ld_script:
            try:
                job_data = json.loads(json_ld_script.string)

                if job_data.get('@type') == 'JobPosting':
                    metadata_parts.append("=== JOB DETAILS ===\n")

                    # Extract structured fields
                    if job_data.get('title'):
                        metadata_parts.append(f"Title: {job_data['title']}")

                    if job_data.get('baseSalary'):
                        salary = job_data['baseSalary']
                        if isinstance(salary, dict):
                            value = salary.get('value', {})
                            if isinstance(value, dict):
                                min_val = value.get('minValue')
                                max_val = value.get('maxValue')
                                unit = salary.get('value', {}).get('unitText', 'Annually')
                                if min_val and max_val:
                                    metadata_parts.append(f"Salary: ${min_val:,.2f} - ${max_val:,.2f} {unit}")
                            elif isinstance(value, (int, float)):
                                metadata_parts.append(f"Salary: ${value:,.2f}")

                    if job_data.get('jobLocation'):
                        location = job_data['jobLocation']
                        if isinstance(location, dict):
                            address = location.get('address', {})
                            if isinstance(address, dict):
                                city = address.get('addressLocality', '')
                                state = address.get('addressRegion', '')
                                postal = address.get('postalCode', '')
                                loc_parts = [p for p in [city, state, postal] if p]
                                if loc_parts:
                                    metadata_parts.append(f"Location: {', '.join(loc_parts)}")

                    if job_data.get('hiringOrganization'):
                        org = job_data['hiringOrganization']
                        if isinstance(org, dict) and org.get('name'):
                            metadata_parts.append(f"Employer: {org['name']}")

                    if job_data.get('employmentType'):
                        emp_type = job_data['employmentType']
                        if isinstance(emp_type, list):
                            metadata_parts.append(f"Employment Type: {', '.join(emp_type)}")
                        else:
                            metadata_parts.append(f"Employment Type: {emp_type}")

                    if job_data.get('datePosted'):
                        metadata_parts.append(f"Date Posted: {job_data['datePosted']}")

                    if job_data.get('validThrough'):
                        metadata_parts.append(f"Valid Through: {job_data['validThrough']}")

            except json.JSONDecodeError:
                logging.warning("Failed to parse JSON-LD data")

        # Extract additional details from term-block structure
        term_blocks = soup.find_all('div', class_='term-block')
        for block in term_blocks:
            # Find the term name in span4 > term-description
            term_div = block.find('div', class_='term-description')
            if term_div:
                term_name = term_div.get_text(strip=True)

                # Find the value in span8
                span8 = block.find('div', class_='span8')
                if span8:
                    term_value = span8.get_text(separator=' ', strip=True)

                    # Skip certain fields we don't want or already have
                    skip_terms = ['Summary', 'Job Duties', 'Experience, Qualifications',
                                  'Supplemental Information', 'Employer', 'Address', 'Phone', 'Website']

                    if term_name and term_value and term_name not in skip_terms:
                        # Avoid duplicates
                        if not any(term_name in part for part in metadata_parts):
                            # Truncate very long values
                            if len(term_value) > 200:
                                term_value = term_value[:200] + '...'
                            metadata_parts.append(f"{term_name}: {term_value}")

        # Look for benefits information in dd elements
        # Look specifically for a UL with multiple benefits-related items
        dds = soup.find_all('dd')
        for dd in dds:
            ul = dd.find('ul')
            if ul:
                # Check if the UL items contain benefits keywords
                ul_text = ul.get_text(separator=' ', strip=True).lower()
                # Must have at least 2 of these strong benefits indicators
                strong_benefits_keywords = ['medical', 'dental', 'vision', 'retirement', '401k', 'pension', 'healthcare']
                matches = sum(1 for kw in strong_benefits_keywords if kw in ul_text)

                if matches >= 2:  # At least 2 benefits keywords in the list
                    # Check if we haven't already added this
                    if 'BENEFITS' not in '\n'.join(metadata_parts):
                        benefits_items = []
                        for li in ul.find_all('li'):
                            item_text = li.get_text(separator=' ', strip=True)
                            if item_text:
                                benefits_items.append(f"  • {item_text}")

                        if benefits_items:
                            metadata_parts.append("\nBENEFITS:")
                            metadata_parts.extend(benefits_items)  # Include all items

                            # Also capture any text after the UL (like notes about eligibility)
                            # Get all content after the UL but within the same DD
                            collected_text = []
                            for sibling in ul.find_next_siblings():
                                sibling_text = sibling.get_text(separator=' ', strip=True)
                                if sibling_text and len(sibling_text) > 20:  # Skip empty/short elements
                                    collected_text.append(sibling_text)

                            # Also get direct text nodes in the DD (not in child elements)
                            for content in dd.contents:
                                # Check if it's a text node (NavigableString) after the UL
                                if isinstance(content, str):
                                    text = content.strip()
                                    if text and len(text) > 20:
                                        # Check if this text isn't already in the UL or collected text
                                        if text not in ul_text and not any(text in ct for ct in collected_text):
                                            collected_text.append(text)

                            # Add all collected text
                            if collected_text:
                                metadata_parts.append("")  # Empty line for spacing
                                for text in collected_text:
                                    metadata_parts.append(text)

                            break  # Found benefits, stop searching

        # Combine description and metadata
        result_parts = []

        if metadata_parts and len(metadata_parts) > 1:  # More than just header
            result_parts.append('\n'.join(metadata_parts))
            result_parts.append('\n=== JOB DESCRIPTION ===\n')

        if description_text:
            result_parts.append(description_text)

        final_text = '\n'.join(result_parts)

        if final_text and len(final_text) > 200:
            return final_text

        return None
    except Exception as e:
        logging.error(f"Error extracting governmentjobs content: {e}")
        return None


def scrape_full_description(url):
    """
    Scrape the full text content from a URL using trafilatura.
    Uses Playwright for JavaScript-heavy sites, simple requests for static sites.

    Returns:
        str: The extracted text content, or None if extraction failed
    """
    try:
        # Check robots.txt
        if not can_fetch(url):
            logging.info(f"Robots.txt blocks scraping: {url}")
            return None

        # For governmentjobs.com, use Playwright with specialized extraction
        if 'governmentjobs.com' in url:
            logging.info(f"Using Playwright for governmentjobs.com: {url}")
            browser = get_browser()
            if browser:
                try:
                    page = browser.new_page(user_agent=USER_AGENT)
                    page.set_default_timeout(REQUEST_TIMEOUT * 1000)
                    page.goto(url, wait_until='networkidle', timeout=15000)
                    page.wait_for_timeout(2000)

                    # Use specialized extractor
                    import scrape_governmentjobs
                    text = scrape_governmentjobs.extract_with_playwright(page)
                    page.close()

                    if text:
                        logging.info(f"Extracted governmentjobs.com content: {len(text)} chars")
                        return text
                except Exception as e:
                    logging.error(f"Playwright extraction failed for {url}: {e}")
                    try:
                        page.close()
                    except:
                        pass

        # For other sites, use standard approach
        downloaded = None
        used_browser = False

        # Check if this domain requires JavaScript
        if needs_javascript(url):
            logging.info(f"Using browser for JavaScript site: {url}")
            downloaded = scrape_with_browser(url)
            used_browser = True
        else:
            # Try simple fetch first (faster for static sites)
            try:
                headers = {'User-Agent': USER_AGENT}
                response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                downloaded = response.text
            except Exception as e:
                logging.warning(f"Simple fetch failed for {url}, trying browser: {e}")
                downloaded = scrape_with_browser(url)
                used_browser = True

        if downloaded is None:
            logging.warning(f"Failed to download: {url}")
            return None

        # Use trafilatura for extraction
        text = trafilatura.extract(downloaded, include_comments=False)

        if text is None:
            logging.warning(f"Failed to extract text from: {url}")
            return None

        # Check if we got generic/useless content
        if is_generic_content(text):
            if not used_browser:
                # Retry with browser for JavaScript rendering
                logging.info(f"Generic content detected, retrying with browser: {url}")
                downloaded = scrape_with_browser(url)
                if downloaded:
                    text = trafilatura.extract(downloaded, include_comments=False)

                    if text and not is_generic_content(text):
                        return text

            logging.warning(f"Only generic content found for: {url}")
            return None

        return text

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


def create_slug(text, max_length=50):
    """
    Create a URL-friendly slug from text.

    Args:
        text: The text to slugify
        max_length: Maximum length of the slug

    Returns:
        str: A slugified version of the text
    """
    if not text or text == '' or str(text).lower() == 'nan':
        return 'untitled'

    # Convert to lowercase and string
    slug = str(text).lower()

    # Replace spaces and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)

    # Remove any character that isn't alphanumeric or hyphen
    slug = re.sub(r'[^a-z0-9-]', '', slug)

    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)

    # Trim hyphens from start and end
    slug = slug.strip('-')

    # Truncate to max length
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('-')

    # Return 'untitled' if slug is empty
    return slug if slug else 'untitled'


def save_full_description(text, year, date, job_number, job_title=''):
    """
    Save full description text to filesystem.

    Args:
        text: The full text content
        year: Year (e.g., "2024")
        date: Date in MM-DD format (e.g., "01-05")
        job_number: The job number (1-based, 01-99)
        job_title: The job title for the slug

    Returns:
        str: Path to the saved file
    """
    # Create directory structure: job-descriptions/YYYY/MM-DD/
    dir_path = os.path.join('job-descriptions', str(year), date)
    os.makedirs(dir_path, exist_ok=True)

    # Create filename: NN-job-title-slug.txt
    title_slug = create_slug(job_title)
    filename = f"{job_number:02d}-{title_slug}.txt"
    file_path = os.path.join(dir_path, filename)

    # Save the text
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return file_path


def scrape_new_jobs(df):
    """
    Scrape full descriptions for new jobs in a dataframe.

    Args:
        df: pandas DataFrame with 'link', 'year', 'date', 'job_title' columns

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

    # Track job numbers per date (reset counter for each date)
    date_counters = {}

    for idx in tqdm(df.index, ncols=TQDM_WIDTH, desc='scraping full job descriptions'):
        row = df.loc[idx]
        url = row['link']

        # Skip empty or invalid URLs
        if pd.isna(url) or url == '' or not url.startswith('http'):
            continue

        # Get job number for this date (1-based)
        date_key = f"{row['year']}-{row['date']}"
        if date_key not in date_counters:
            date_counters[date_key] = 1
        else:
            date_counters[date_key] += 1
        job_number = date_counters[date_key]

        # Scrape with retry logic
        text, error = scrape_with_retry(url)

        if text is not None and len(text) > 0:
            # Get job title for slug
            job_title = row.get('job_title', '')
            if pd.isna(job_title):
                job_title = ''

            # Save to file
            file_path = save_full_description(text, row['year'], row['date'],
                                             job_number, job_title)

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

    # Clean up browser if it was used
    close_browser()

    return df
