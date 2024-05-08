import os, sys, re, openai, timeout_decorator, datetime, gspread
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urlparse
from tqdm import tqdm
from scrapeghost import SchemaScraper

TQDM_WIDTH = 140


# this line is not necessary, but for the code to run you will need
# to set the OPENAI_API_KEY environment variable to your OpenAI API key
# openai.api_key = os.environ["OPENAI_API_KEY"]

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


def add_gpt_fields(job_df, starting_row=0): 
    # starting row is bc sometimes it gets stuck and you need to start from whatever row you left off
    disable_console_printing()
    schema = {
            "job_title": "string",
            "employer": "string",
            "state_full_name": "string",
            "salary_low_end": "float",
            "salary_high_end": "float",
            "pay_basis": "yearly, monthly, hourly, etc.",
                    }

    scrape_job_description = SchemaScraper(schema=schema, max_cost=2)

    # add new columns from schema
    # job_df[list(schema.keys())] = None

    extra_rows = []
    for row in tqdm(job_df.loc[starting_row:].index, ncols=TQDM_WIDTH, desc='parsing job descriptions with GPT-3.5 and scrapeghost'):
        description = job_df.loc[row]['description']
        response = scrape_job_description(description)
        
        if isinstance(response.data, list): # sometimes (rarely), it will be a list because multiple jobs are in one paragraph
            extra_rows += response.data
        else: # vast majority of rows
            # data = {f'{key}{suffix}': value for key, value in response.data.items()}
            job_df.loc[row, response.data.keys()] = response.data.values()

    if len(extra_rows) > 0:
        extra_df = pd.DataFrame(extra_rows)
        extra_df.columns = list(schema.keys())
        job_df = pd.concat([job_df, extra_df])

    job_df = job_df.rename(columns={'state_full_name': 'state'})

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

def get_next_message(messages):
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        seed=1,
        temperature=0)
    return response.choices[0].message.content

@timeout_decorator.timeout(5)
def job_description_analysis(system_prompt, job_description):
    messages = [{
        "role": "system",
        "content": system_prompt
    }, {
        "role": "user",
        "content": job_description
    }]

    return get_next_message(messages)


def classify_job(job_df, starting_row=0):
    # Use GPT-3.5 to determine whether a job description appears to be for
    # an election official, a top election official, or other


    system_prompt = """
    You are to be given a job description.
    - If the job appears to be in an office responsible for public elections, you shall say "election_official".
    - If the job appears to be for the top official in an office responsible for public elections, you shall say "top_election_official". A description for the top elections official typically indicates that they direct the operations for the entire elections office, not just one piece of it. They often report to a board, or to the secretary of state, or to a county director. They typically have a salary above 100,000.
    - If the job appears to be for an office or company with no election-related duties, such as a non-profit or for-profit organization, you shall say "not_election_official".

    You are to return NO OTHER ANSWER BESIDES `election_official`, `top_election_official` or `not_election_official`.
    """

    # for i, row in tqdm(job_df.loc[starting_row:].iterrows(), total=job_df.loc[starting_row:].shape[0]):
    for row in tqdm(job_df.loc[starting_row:].index, ncols=TQDM_WIDTH, desc='classifying job descriptions with GPT-3.5'):
        attempts = 0
        while attempts < 100:
            try:
                is_top = job_description_analysis(system_prompt, job_df.loc[row]['description'])
                job_df.loc[row, 'classification_experimental'] = is_top
                break

            except timeout_decorator.TimeoutError:
                # Handle the timeout (API call took more than 5 seconds) here
                attempts += 1

    return job_df

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
                'classification_experimental']
    
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
                200]  # classification

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
    job_df = add_gpt_fields(job_df)
    job_df = handle_pay_basis(job_df)
    job_df = classify_job(job_df)
    job_df = process_columns(job_df)

    job_df.to_csv('dataset.csv', index=False)
    
    upload(job_df)

if __name__ == "__main__":
    main()