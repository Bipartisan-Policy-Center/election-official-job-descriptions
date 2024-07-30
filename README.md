# Election Official Historical Job Posting Dataset
**The code in this repository runs every week, updating a record of all election official job descriptions posted to [electionline Weekly](https://electionline.org/electionline-weekly/) since 2011. You can access the dataset directly via this [Google Sheet](https://docs.google.com/spreadsheets/d/1t-oMIQVFW1uPRjjQ0Ffnf7w65C-uF1HKFQNp0hFgyzg/edit?usp=sharing) or download it as a [CSV file](dataset.csv).**

This repository contains the dataset (and associated code) described in the May 2024 Bipartisan Policy Center blog post, "[Understanding the Election Official Job Market.](https://bipartisanpolicy.org/blog/understanding-the-election-administrator-job-market/)"

Much about the landscape of the elections workforce, especially roles beyond chief election officials, is poorly understood. There exist some surveys of [chief election officials](https://evic.reed.edu/leo-survey-summary/), but there are few comprehensive data sources about other election workers. However, job postings for non-chief officials have been posted on the [electionline Weekly](https://electionline.org/electionline-weekly/) site weekly since 2011, providing some information about positions, responsibilities, and compensation.

The code in this dataset aggregates the job postings on electionline Weekly into a dataset usable by researchers seeking to better understand characteristics of the election workforce.



# Methods
The code used to create this dataset includes both traditional web scraping techniques and modern AI-powered tools. The following steps are executed automatically each Friday, the day after an edition of electionline Weekly is typically issued:

- **Data acquisition:** Maintain a mirror of electionline Weekly postings in the [electionline-weekly](electionline-weekly) folder.
- **Job posting extraction:** Use the [Beautiful Soup](https://beautiful-soup-4.readthedocs.io/en/latest/) web scraping package to extract job descriptions, organizing them into a [pandas](https://pandas.pydata.org/docs/index.html) DataFrame.
- **Filtering:** Exclude job descriptions posted in previous weeks. Exclude job postings from the most popular private employers, to maintain focus on public sector election roles.
- **Feature extraction:** Use the [scrapeghost](https://jamesturk.github.io/scrapeghost/) package (which in turn uses GPT-3.5) to extract features from the job descriptions, including *job title*, *employing office*, *state name*, *salary range*, and *pay basis* (e.g., yearly, monthly, hourly). (This appears to work much more reliably than regular expressions, due to inconsistencies in the job description formatting.)
- **Salary normalization:** Use pay basis information to adjust pay fields for comparison to a standard yearly salary (e.g., by multiplying monthly salaries by 12).
- **Job classification (experimental):** Use GPT-3.5 via the [OpenAI Python API](https://github.com/openai/openai-python) to determine whether a job description is for a position as a chief election official, a non-chief election official, or for a non-election-official position. This classification appears to be only moderately accurate, so should be considered experimental.
- **Append new jobs to the previous version of the dataset.**
- **Upload dataset to GitHub and Google Sheets.**
