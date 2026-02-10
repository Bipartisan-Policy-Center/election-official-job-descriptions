"""
Specialized extractor for governmentjobs.com using Playwright for clean text extraction.
"""

import logging
from bs4 import BeautifulSoup
import json


def extract_with_playwright(page):
    """
    Extract job details from governmentjobs.com using Playwright for clean text.

    Args:
        page: Playwright page object with governmentjobs.com job posting loaded

    Returns:
        str: Formatted job details and description
    """
    try:
        metadata_parts = []
        metadata_parts.append("=== JOB DETAILS ===\n")

        # Track added fields to avoid duplicates
        added_fields = set()

        # Extract structured data from JSON-LD
        try:
            json_ld = page.locator('script[type="application/ld+json"]').first.inner_text()
            job_data = json.loads(json_ld)

            if job_data.get('@type') == 'JobPosting':
                if job_data.get('title'):
                    metadata_parts.append(f"Title: {job_data['title']}")
                    added_fields.add('title')

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
                                added_fields.add('salary')

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
                                added_fields.add('location')

                if job_data.get('hiringOrganization'):
                    org = job_data['hiringOrganization']
                    if isinstance(org, dict) and org.get('name'):
                        metadata_parts.append(f"Employer: {org['name']}")
                        added_fields.add('employer')

                if job_data.get('employmentType'):
                    emp_type = job_data['employmentType']
                    if isinstance(emp_type, list):
                        metadata_parts.append(f"Employment Type: {', '.join(emp_type)}")
                    else:
                        metadata_parts.append(f"Employment Type: {emp_type}")
                    added_fields.add('employment type')

                if job_data.get('datePosted'):
                    metadata_parts.append(f"Date Posted: {job_data['datePosted']}")
                    added_fields.add('date posted')
        except:
            pass

        # Extract additional metadata from term-blocks using clean text
        term_blocks = page.locator('div.term-block').all()
        for block in term_blocks:
            try:
                term_name = block.locator('div.term-description').first.inner_text().strip()
                value_text = block.locator('div.span8').first.inner_text().strip()

                # Skip certain fields
                skip_terms = ['Summary', 'Job Duties', 'Experience, Qualifications',
                              'Supplemental Information', 'Employer', 'Address', 'Phone', 'Website']

                # Skip duplicates (case-insensitive check)
                if term_name.lower() in added_fields:
                    continue

                if term_name and value_text and term_name not in skip_terms:
                    if len(value_text) > 200:
                        value_text = value_text[:200] + '...'
                    metadata_parts.append(f"{term_name}: {value_text}")
                    added_fields.add(term_name.lower())
            except:
                continue

        # Extract benefits using clean text
        try:
            dds = page.locator('dd').all()
            for dd in dds:
                # Check if this dd contains a benefits list
                uls = dd.locator('ul').all()
                if uls:
                    ul = uls[0]
                    ul_text = ul.inner_text().lower()

                    # Check for benefits keywords
                    benefits_keywords = ['medical', 'dental', 'vision', 'retirement', 'healthcare']
                    matches = sum(1 for kw in benefits_keywords if kw in ul_text)

                    if matches >= 2:
                        # Extract all li items with clean text
                        lis = ul.locator('li').all()
                        if lis:
                            metadata_parts.append("\nBENEFITS:")
                            for li in lis:
                                item_text = li.inner_text().strip()
                                if item_text:
                                    metadata_parts.append(f"  • {item_text}")

                            # Extract text that comes after the UL using DOM traversal
                            # This gets clean text from elements following the UL, not string slicing
                            after_ul_text = dd.evaluate("""
                                (element) => {
                                    const ul = element.querySelector('ul');
                                    if (!ul) return '';

                                    let result = [];
                                    let node = ul.nextSibling;

                                    while (node) {
                                        if (node.nodeType === Node.TEXT_NODE) {
                                            const text = node.textContent.trim();
                                            if (text) result.push(text);
                                        } else if (node.nodeType === Node.ELEMENT_NODE) {
                                            const text = node.innerText.trim();
                                            if (text) result.push(text);
                                        }
                                        node = node.nextSibling;
                                    }

                                    return result.join('\\n');
                                }
                            """)

                            if after_ul_text and len(after_ul_text) > 20:
                                # Add as separate lines with paragraph breaks preserved
                                metadata_parts.append(f"\n{after_ul_text}")

                            break
        except:
            pass

        # Extract job description with clean text - may span multiple DD elements
        description_parts = []
        try:
            dds = page.locator('dd').all()

            for dd in dds:
                text = dd.inner_text()

                # Check if this is the benefits DD (skip it, already extracted separately)
                if len(text) > 500:
                    ul = dd.locator('ul').first
                    if ul.count() > 0:
                        ul_text = ul.inner_text().lower()
                        if 'medical' in ul_text and 'dental' in ul_text:
                            # Found benefits section - stop collecting description parts
                            break

                # Collect substantial DDs that are part of job description
                if len(text) > 100:
                    # Skip DDs that look like metadata/contact info
                    if any(pattern in text.lower() for pattern in ['king street center', 'http://', 'which of the following']):
                        continue

                    description_parts.append(text)

            description_text = '\n\n'.join(description_parts) if description_parts else None
        except:
            pass

        # Combine metadata and description
        result_parts = []

        if metadata_parts and len(metadata_parts) > 1:
            result_parts.append('\n'.join(metadata_parts))
            result_parts.append('\n=== JOB DESCRIPTION ===\n')

        if description_text:
            result_parts.append(description_text)

        return '\n'.join(result_parts) if result_parts else None

    except Exception as e:
        logging.error(f"Error extracting with Playwright: {e}")
        return None
