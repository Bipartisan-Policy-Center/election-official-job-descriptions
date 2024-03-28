from bs4 import BeautifulSoup
import os, requests
import datetime


cur_year = datetime.date.today().year
YEARS = range(2011, cur_year+1)

# Define user-agent to simulate a web browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

base_url = 'https://electionline.org'


for year in YEARS:
    elw = 'electionline-weekly'
    # make folder if it doesn't exist
    dir_path = f"{elw}/{year}"
    os.makedirs(dir_path, exist_ok=True)
    
    # get the URL for the year
    year_url = f"{base_url}/{elw}/{year}"
    
    # Send an HTTP GET request with headers
    response = requests.get(year_url, headers=headers)

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
        response = requests.get(url, headers=headers)
        with open(week_urls[url], 'w') as f:
            f.write(response.text)