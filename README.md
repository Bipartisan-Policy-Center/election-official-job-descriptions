# Election Official Historical Job Posting Dataset
This repository contains the dataset (and associated code) released in the upcoming Bipartisan Policy Center blog post, "Understanding the Election Official Job Market."

Much about the landscape of the elections workforce, especially roles beyond chief election officials, is poorly understood. There exist some surveys of [chief election officials](https://evic.reed.edu/leo-survey-summary/), but there are few comprehensive data sources about other election workers. However, job postings for non-chief officials have been posted on the [Electionline Weekly](https://electionline.org/electionline-weekly/) site weekly since 2011, providing some information about positions, responsibilities, and compensation.

The code in this dataset aggregates the job postings on Electionline Weekly into a dataset usable by researchers seeking to better understand characteristics of the election workforce.

**You can access the dataset directly via this [Google Sheet](https://docs.google.com/spreadsheets/d/1t-oMIQVFW1uPRjjQ0Ffnf7w65C-uF1HKFQNp0hFgyzg/edit?usp=sharing) or download it directly as a [CSV file](dataset.csv).**

# Methods
This dataset is built with both traditional web scraping techniques and modern AI-powered tools via the following steps:
- **Data acquisition:** Maintain a mirror of electionline-weekly postings in the [electionline-weekly](electionline-weekly) folder.
- **Job posting extraction:** Use the [Beautiful Soup](https://beautiful-soup-4.readthedocs.io/en/latest/) web scraping package to extract job descriptions, organizing them into a [pandas](https://pandas.pydata.org/docs/index.html) DataFrame.
- **De-duplication:** Remove repetitive job descriptions.
- **Filtering:** Exclude job postings from the most popular private employers, to maintain focus on public sector election roles.
- **Feature extraction:** Use GPT-3.5 via [scrapeghost](https://jamesturk.github.io/scrapeghost/) to extract features from the job descriptions, including *job title*, *employing office*, *state name*, *salary range*, and *pay basis* (e.g., yearly, monthly, hourly). (This appears to work much more reliably than regular expressions, due to inconsistencies in the job description formatting.)
- **Salary normalization:** Use pay basis information to adjust pay fields to a standard yearly salary.
- **Job classification (experimental):** Use GPT-3.5 via the [OpenAI Python API](https://github.com/openai/openai-python) to determine whether a job description is for a position as an election official, as a chief election official, or for a non-election-official position. This classification appears to be only moderately accurate, so should be considered experimental.
- **Upload dataset to GitHub and Google Sheets.**
The above process runs automatically each Friday, the day after Electionline Weekly is typically published.