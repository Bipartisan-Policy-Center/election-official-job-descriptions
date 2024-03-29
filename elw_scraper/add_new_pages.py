import os, requests, datetime, sys
from bs4 import BeautifulSoup
import pandas as pd

sys.path.append('elw_scraper')
import process_listings

## Part 1: Download new pages

cur_year = datetime.date.today().year
YEARS = range(2011, cur_year+1)

# Define user-agent to simulate a web browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

base_url = 'https://electionline.org'

downloaded_files = []

# look for any electionline weeks that are not associated with a local HTML file
for year in YEARS:
    elw = 'electionline-weekly'

    # make folder if it doesn't exist
    dir_path = f"{elw}/{year}"
    os.makedirs(dir_path, exist_ok=True)
    
    # get the URL for the year
    year_url = f"{base_url}/{elw}/{year}"
    
    # Send an HTTP GET request with headers
    response = requests.get(year_url, headers=headers)

    # parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # get all the weeks in the year
    weeks = soup.find('ul', class_='weeks').find_all('li')
    week_urls = {}
    for week in weeks:
        url = f"{base_url}{week.find('a')['href']}"
        local_path = f"{url.split('electionline.org/')[-1]}.html"

        # add url and local path to dictionary if local file doesn't exist
        if not os.path.exists(local_path):
            week_urls[url] = local_path

    # download weekly files
    for url in week_urls:
        print(f"Downloading {week_url[url]}")
        response = requests.get(url, headers=headers)
        with open(week_urls[url], 'w') as f:
            f.write(response.text)

        downloaded_files.append(week_urls[url])


## Part 2: Determine which jobs are new

old_df = pd.read_csv('dataset.csv')

new_df = pd.DataFrame()

for file in downloaded_files:
    # get the year and week from the file path
    year = file.split('/')[1]
    date = file.split('/')[2].split('.')[0]
    week_jobs = process_listings.job_descriptions(file, date, year)
    new_df = pd.concat([new_df, week_jobs], ignore_index=True)


def letters_only(x):
    # reduce string to just lower-case letters, for matching purposes
    return ''.join(filter(str.isalpha, x)).lower()


# most recent year and week in the current version of the dataset
# most_recent_year = old_df['year'].max()
# most_recent_week = old_df[old_df['year']==most_recent_year]['week'].max()

# most_recent_year = 2023
# most_recent_week = '02-08'

# newer_rows = x[(x['year'] > most_recent_year) | ((x['year'] == most_recent_year) & (x['date'] > most_recent_week))]


# Apply the letters_only() function to fingerprint the 'description' column in both DataFrames
old_fingerprint = old_df['description'].apply(letters_only)
new_fingerprint = new_df['description'].apply(letters_only)

# Find rows in new_df where the fingerprinted description is not present in old_df
new_df = new_df[~new_fingerprint.isin(old_fingerprint)]

## Part 3: Process new jobs, add to dataset

new_df = process_listings.postprocess(new_df)
new_df = process_listings.add_gpt_fields(new_df)
new_df = process_listings.handle_pay_basis(new_df)
new_df = process_listings.classify_job(new_df)

job_df = pd.concat([old_df, new_df], ignore_index=True)

job_df = job_df.sort_values(['year', 'date', 'description'],
                             ascending=[False, False, True])
job_df = job_df[process_listings.COL_ORDER]
job_df.to_csv('dataset.csv', index=False)
process_listings.clean_and_upload(job_df)
