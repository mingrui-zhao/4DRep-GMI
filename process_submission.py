#!/usr/bin/env python3
"""
Process GitHub issue submissions and convert them to JSON format for the 4D Survey database.
"""

import os
import json
import re
import sys
from datetime import datetime

def extract_issue_data(issue_body):
    """Extract data from GitHub issue body using regex patterns."""
    data = {}
    
    # Define patterns for each field
    patterns = {
        'paper-title': r'### Paper Title\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'authors': r'### Authors\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'year': r'### Publication Year\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'venue': r'### Venue\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'paper-url': r'### Paper URL\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'project-page': r'### Project Page\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'code-url': r'### Code Repository\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'representation': r'### Representation Type\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'task': r'### Task Type\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'category': r'### Category\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'motion': r'### Motion Type\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'interaction': r'### Interaction/Control Method\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'code-availability': r'### Code Availability\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'special-flags': r'### Special Flags\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'bibtex': r'### BibTeX Citation\s*\n\n```bibtex\n(.*?)\n```',
        'teaser-image': r'### Teaser Image\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)',
        'additional-notes': r'### Additional Notes\s*\n\n(.*?)(?=\n\n###|\n\n---|\Z)'
    }
    
    for field, pattern in patterns.items():
        match = re.search(pattern, issue_body, re.DOTALL)
        if match:
            data[field] = match.group(1).strip()
        else:
            data[field] = ""
    
    return data

def parse_multiple_selection(text):
    """Parse multiple selection fields (checkboxes) from GitHub issue format."""
    if not text:
        return []
    
    # Split by newlines and extract selected items
    items = []
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('- [x]') or line.startswith('* [x]'):
            # Extract the item name after the checkbox
            item = line.split(']', 1)[1].strip()
            items.append(item)
    
    return items

def create_paper_filename(title):
    """Create a filename from paper title."""
    # Remove special characters and convert to lowercase
    filename = re.sub(r'[^\w\s-]', '', title.lower())
    filename = re.sub(r'[-\s]+', '-', filename)
    # Limit length
    filename = filename[:50]
    return filename

def convert_to_json_format(issue_data, issue_title, issue_number):
    """Convert issue data to the JSON format used by the database."""
    
    # Extract title from issue title (remove [SUBMISSION] prefix)
    title = issue_title.replace('[SUBMISSION]', '').strip()
    
    # Parse authors
    authors = []
    if issue_data.get('authors'):
        authors = [author.strip() for author in issue_data['authors'].split(',')]
    
    # Parse representation type
    representation = parse_multiple_selection(issue_data.get('representation', ''))
    if not representation:
        representation = issue_data.get('representation', '')
    
    # Parse task type
    task = parse_multiple_selection(issue_data.get('task', ''))
    if not task:
        task = issue_data.get('task', '')
    
    # Parse category
    category = parse_multiple_selection(issue_data.get('category', ''))
    if not category:
        category = issue_data.get('category', '')
    
    # Parse motion type
    motion = parse_multiple_selection(issue_data.get('motion', ''))
    if not motion:
        motion = issue_data.get('motion', '')
    
    # Parse special flags
    special_flags = parse_multiple_selection(issue_data.get('special-flags', ''))
    has_dataset = 'This paper has dataset contribution' in special_flags
    is_survey = 'This is a survey/review paper' in special_flags
    
    # Create JSON structure
    paper_data = {
        "title": title,
        "authors": authors,
        "year": issue_data.get('year', ''),
        "venue": issue_data.get('venue', ''),
        "paperUrl": issue_data.get('paper-url', ''),
        "projectPage": issue_data.get('project-page', ''),
        "codeUrl": issue_data.get('code-url', ''),
        "representation": representation,
        "task": task,
        "category": category,
        "motion": motion,
        "interaction": issue_data.get('interaction', ''),
        "codeAvailability": issue_data.get('code-availability', 'No') == 'Yes',
        "bibtex": issue_data.get('bibtex', ''),
        "dataset": has_dataset,
        "survey": is_survey,
        "tags": [],
        "doi": "",
        "filename": create_paper_filename(title)
    }
    
    return paper_data

def update_paper_list(filename):
    """Update the paper-list.json file to include the new paper."""
    paper_list_path = 'data/paper-list.json'
    
    if os.path.exists(paper_list_path):
        with open(paper_list_path, 'r') as f:
            paper_list = json.load(f)
    else:
        paper_list = {
            "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "totalPapers": 0,
            "files": []
        }
    
    # Add new file to the list
    if filename not in paper_list['files']:
        paper_list['files'].append(filename)
        paper_list['totalPapers'] = len(paper_list['files'])
        paper_list['lastUpdated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Save updated paper list
        with open(paper_list_path, 'w') as f:
            json.dump(paper_list, f, indent=2)

def main():
    """Main processing function."""
    # Get environment variables
    issue_number = os.getenv('ISSUE_NUMBER')
    issue_title = os.getenv('ISSUE_TITLE', '')
    issue_body = os.getenv('ISSUE_BODY', '')
    
    if not issue_number:
        print("Error: ISSUE_NUMBER environment variable not set")
        sys.exit(1)
    
    print(f"Processing issue #{issue_number}: {issue_title}")
    
    # Extract data from issue body
    issue_data = extract_issue_data(issue_body)
    
    # Convert to JSON format
    paper_data = convert_to_json_format(issue_data, issue_title, issue_number)
    
    # Create filename
    filename = create_paper_filename(paper_data['title'])
    json_filename = f"{filename}.json"
    
    # Save paper data
    os.makedirs('data', exist_ok=True)
    with open(f'data/{json_filename}', 'w') as f:
        json.dump(paper_data, f, indent=2)
    
    # Update paper list
    update_paper_list(json_filename)
    
    print(f"Successfully processed submission: {json_filename}")
    print(f"Paper: {paper_data['title']}")
    print(f"Authors: {', '.join(paper_data['authors'])}")
    print(f"Year: {paper_data['year']}")
    print(f"Venue: {paper_data['venue']}")

if __name__ == "__main__":
    main()
