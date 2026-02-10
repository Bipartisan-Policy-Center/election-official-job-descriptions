import os, sys, re, datetime, gspread, json
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urlparse
from tqdm import tqdm
import anthropic

TQDM_WIDTH = 140


# this line is not necessary, but for the code to run you will need
# to set the ANTHROPIC_API_KEY environment variable to your Anthropic API key
# os.environ["ANTHROPIC_API_KEY"]

def disable_console_printing():
    sys.stdout = open(os.devnull, 'w')

def reenable_console_printing():
    sys.stdout = sys.__stdout__

def job_descriptions(html_file, date, year):
    # return df of jobs from an electionline weekly html file

    df = pd.DataFrame()

    with open(html_file) as f:
        text = f.read()
    soup = BeautifulSoup(text, 'html.parser')

    # Find all divs with the class 'article-wrapper'
    divs_with_class = soup.find_all('div', class_='article-wrapper')

    # iterate over article-wrapper divs until finding one with h2 tag containing 'job'
    for div in divs_with_class:
        
        h2_tag = div.find_all('h2', string=re.compile(r'^job', re.I))
        
        if h2_tag:
            # Find all p elements within the div containing the matched h2 tag
            # Skip the first paragraph
            job_paragraphs = div.find_all('p')[1:]  

            # Skip intro and empty paragraphs
            job_paragraphs = [para for para in job_paragraphs if (not para.text.startswith('electionlineWeekly')) and (len(para.text)>10)]    
            
            for paragraph in job_paragraphs:
                # Extract job information from the paragraph
                link = paragraph.find('a')
                job_link = link['href'] if link is not None else ""
                                        
                description = paragraph.get_text()

                # Append job information to the list as a dictionary
                new_row = pd.DataFrame({'link': job_link,
                                        'description': description}, index=[0])
                df = pd.concat([df, new_row], ignore_index=True)
    
    df['date'] = date
    df['year'] = year

    return df

def build_from_html():
    cur_year = datetime.date.today().year
    YEARS = list(reversed(range(2011, cur_year+1)))

    job_df = pd.DataFrame()

    for year in tqdm(YEARS, ncols=TQDM_WIDTH, desc='building from html'):
        dir = f"electionline-weekly/{year}"
        dates = reversed(os.listdir(dir))

        for date in dates:
            file_location = os.path.join(dir, date)
            week_jobs = job_descriptions(file_location, date[:5], year)

            job_df = pd.concat([job_df, week_jobs], ignore_index=True)

    return job_df

# to save work, exclude listings from some of the top URLs for
# non-public employers, which we are not interested in
EXCLUDED_DOMAINS = ['dominionvoting.com',
                    'clearballot.com',
                    'electioninnovation.org',
                    'runbeck.net',
                    'rockthevote.com',
                    'hartintercivic.com',
                    'fordfoundation.org',
                    'techandciviclife.org',
                    'bipartisanpolicy.org',
                    'cdt.org',
                    'ericstates.org',
                    'centerfortechandciviclife.recruitee.com',
                    'democracy.works',
                    'electionreformers.org',
                    'verifiedvoting.org']

def is_not_excluded_domain(url):
    netloc = urlparse(url).netloc.replace('www.', '')
    return netloc not in EXCLUDED_DOMAINS

def postprocess(job_df):
    job_df = job_df.drop_duplicates(subset=['description', 'link'], keep='last') 
    job_df = job_df[job_df['link'].apply(is_not_excluded_domain)]

    return job_df


def parse_and_classify_with_claude(job_df, starting_row=0):
    """Extract structured data and classify jobs in single Claude API call."""
    disable_console_printing()

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Initialize columns that will be added
    new_columns = ['job_title', 'employer', 'state', 'salary_low_end',
                   'salary_high_end', 'pay_basis', 'classification_experimental']
    for col in new_columns:
        if col not in job_df.columns:
            job_df[col] = None

    extra_rows = []
    for row in tqdm(job_df.loc[starting_row:].index, ncols=TQDM_WIDTH, desc='parsing and classifying with Claude Haiku 4.5'):
        description = job_df.loc[row]['description']

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": f"""Extract structured data from this job posting.

Classification guidelines:
- election_official: Works in a public elections office
- top_election_official: Directs entire elections office, typically salary >$100k, reports to board/secretary of state
- not_election_official: Non-profit or private company

Job posting:
{description}"""
                }],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "job_title": {"type": "string"},
                                "employer": {"type": "string"},
                                "state": {"type": "string"},
                                "salary_low_end": {"type": ["number", "null"]},
                                "salary_high_end": {"type": ["number", "null"]},
                                "pay_basis": {
                                    "type": "string",
                                    "enum": ["yearly", "monthly", "hourly", "biweekly", "semi-monthly", "unknown"]
                                },
                                "classification": {
                                    "type": "string",
                                    "enum": ["election_official", "top_election_official", "not_election_official"]
                                }
                            },
                            "required": ["job_title", "employer", "state", "classification", "pay_basis"],
                            "additionalProperties": False
                        }
                    }
                }
            )

            data = json.loads(response.content[0].text)

            if isinstance(data, list):  # Multiple jobs in one paragraph
                extra_rows += data
            else:  # Normal case
                # Map classification to expected column name
                data['classification_experimental'] = data.pop('classification')
                # Assign each field individually
                for key, value in data.items():
                    job_df.at[row, key] = value

        except Exception as e:
            print(f"Failed to parse row {row}: {e}")
            continue

    if len(extra_rows) > 0:
        extra_df = pd.DataFrame(extra_rows)
        # Rename classification column for extra rows too
        extra_df = extra_df.rename(columns={'classification': 'classification_experimental'})
        job_df = pd.concat([job_df, extra_df])

    reenable_console_printing()
    return job_df

def handle_pay_basis(job_df):
    job_df['pay_basis'] = job_df['pay_basis'].str.lower()

    yearly_synonyms = ['salary', 'annually']
    for syn in yearly_synonyms:
        job_df['pay_basis'] = job_df['pay_basis'].str.replace(syn, 'yearly')

    # get mean salary
    job_df['salary_mean'] = job_df[['salary_low_end', 'salary_high_end']].mean(axis=1)

    low_no_high = (job_df['salary_low_end'] > 0) & (job_df['salary_high_end'] == 0)
    job_df.loc[low_no_high, ['salary_high_end', 'salary_mean']] = job_df.loc[low_no_high, 'salary_low_end']

    high_no_low = (job_df['salary_high_end'] > 0) & (job_df['salary_low_end'] == 0)
    job_df.loc[high_no_low, ['salary_low_end', 'salary_mean']] = job_df.loc[high_no_low, 'salary_high_end']

    lowpay = (job_df['pay_basis']=='yearly') & (job_df['salary_mean'] < 10000) & (job_df['salary_mean'] > 2000)
    job_df.loc[lowpay, 'pay_basis'] = 'monthly'

    salary_multipliers = {'monthly': 12,
                          'biweekly': 26,
                          'semi-monthly': 24,
                          'hourly': 2080}

    for basis, multiplier in salary_multipliers.items():
        for col in ['salary_mean', 'salary_low_end', 'salary_high_end']:
            jobs = job_df['pay_basis']==basis
            job_df.loc[jobs, col] = job_df.loc[jobs, col]*multiplier

    return job_df


def letters_only(x):
    """Reduce string to just lower-case letters."""
    return ''.join(filter(str.isalpha, str(x))).lower()

def create_job_fingerprint(row):
    """Create composite fingerprint from multiple fields."""
    title = letters_only(row.get('job_title', ''))
    employer = letters_only(row.get('employer', ''))
    state = letters_only(row.get('state', ''))
    desc_preview = letters_only(row.get('description', ''))[:500]
    return f"{title}|{employer}|{state}|{desc_preview}"

def mark_duplicates(df):
    """Mark duplicate jobs based on improved fingerprinting."""
    # Generate fingerprints for all rows
    fingerprints = df.apply(create_job_fingerprint, axis=1)

    # Mark duplicates (keeps first occurrence as False, marks subsequent as True)
    df['is_duplicate_job'] = fingerprints.duplicated()

    return df


def process_columns(job_df):
    job_df = job_df.sort_values(['year', 'date', 'description'],
                                ascending=[False, False, True])
    col_order = ['year',
                'date',
                'description',
                'link',
                'job_title',
                'employer',
                'state',
                'salary_low_end',
                'salary_high_end',
                'salary_mean',
                'pay_basis',
                'classification_experimental',
                'full_text_preview',
                'full_text_length',
                'full_text_scraped_date',
                'is_duplicate_job']
    
    job_df = job_df[col_order]
    job_df = job_df.astype({'year': 'int', 'salary_low_end': 'float', 'salary_high_end': 'float', 'salary_mean': 'float'})
    job_df = job_df.reset_index(drop=True)

    return job_df

def upload(df):
    # upload to google sheets
    gc = gspread.service_account(filename='gspread_credentials.json')
    sht1 = gc.open_by_key('1t-oMIQVFW1uPRjjQ0Ffnf7w65C-uF1HKFQNp0hFgyzg')
    worksheet = sht1.get_worksheet(0)

    n_rows = len(worksheet.get_all_values()) - 1

    if len(df) > n_rows: # check to make sure the new data is longer than the old data
        print(f"old data: {n_rows} rows\nnew data: {len(df)} rows\nupdating google sheet...")
        # clear old data
        worksheet.clear()

        # upload new data
        worksheet.update([df.fillna("").columns.values.tolist()] + df.fillna("").values.tolist())

        # set column widths
        widths = [50,   # year
                50,   # date
                150,  # description
                50,   # link
                150,  # job_title
                150,  # employer
                150,  # state
                120,  # salary_low_end
                120,  # salary_high_end
                120,  # salary_mean
                100,  # pay_basis
                200,  # classification
                300,  # full_text_preview
                80,   # full_text_length
                100,  # full_text_scraped_date
                80]   # is_duplicate_job

        width_requests = [{
                        "updateDimensionProperties": {
                            "range": {
                                "sheetId": 0,
                                "dimension": "COLUMNS",
                                "startIndex": i,
                                "endIndex": i+1
                            },
                            "properties": {
                                "pixelSize": width
                            },
                            "fields": "pixelSize"
                        }
                    } for i, width in enumerate(widths)]

        body = {
            "requests": width_requests
        }

        sht1.batch_update(body)

        # format the sheet
        worksheet.format('1:1', {'textFormat': {'bold': True}}) # bold header row
        worksheet.format('H:J', {'numberFormat': {'type': "NUMBER", 'pattern': "$#,##0.00"}}) # format salary columns as currency
    else:
        print("new data is not longer than old data, not updating google sheet")


def main():
    # to rebuild the entire database
    job_df = build_from_html()
    job_df = postprocess(job_df)
    job_df = parse_and_classify_with_claude(job_df)
    job_df = handle_pay_basis(job_df)
    job_df = mark_duplicates(job_df)
    job_df = process_columns(job_df)

    job_df.to_csv('dataset.csv', index=False)

    upload(job_df)

if __name__ == "__main__":
    main()