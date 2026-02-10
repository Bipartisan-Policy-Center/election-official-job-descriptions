#!/usr/bin/env python3
"""
Debug script to test Claude API response
"""

import os
import json
import anthropic

if 'ANTHROPIC_API_KEY' not in os.environ:
    print("ERROR: ANTHROPIC_API_KEY not set")
    exit(1)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

test_description = """County Elections Office seeks experienced Election Director for San Francisco County. Salary $120,000-$150,000/year. Must have 5+ years experience in election administration."""

print("Sending request to Claude...")
print(f"Description: {test_description}\n")

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
{test_description}"""
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

print("Response received!")
print(f"Response type: {type(response.content[0])}")
print(f"Response text type: {type(response.content[0].text)}")
print(f"Response text: {response.content[0].text}\n")

data = json.loads(response.content[0].text)
print(f"Parsed data type: {type(data)}")
print(f"Parsed data: {data}\n")

print("Fields extracted:")
for key, value in data.items():
    print(f"  {key}: {value} (type: {type(value).__name__})")
