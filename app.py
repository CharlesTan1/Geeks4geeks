# ===================== IMPORTS SECTION =====================
# Import libraries for file operations, text processing, and web scraping
import os  # For checking if files exist and deleting old cache
import re  # For regular expressions (cleaning titles, removing extra text)
import json  # For saving scraped data to JSON file
from urllib.parse import urljoin  # For converting relative URLs to full URLs
from datetime import datetime  # For adding timestamp to PDF header
from bs4 import BeautifulSoup  # For parsing HTML and extracting data
# Flask imports for creating web server and handling routes
from flask import Flask, render_template, jsonify, send_file
# ReportLab imports for PDF generation (styling, pages, paragraphs)
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

# ===================== CONFIGURATION =====================
# These constants control file names and URLs
BASE_URL = "https://www.geeksforgeeks.org"  # Base website URL
SEARCH_PAGE_FILE = "search_page.html"  # Your downloaded HTML file
DATA_FILE = 'scraped_data.json'  # Where scraped data is saved
PDF_FILE = 'Ruby_Learning_Module.pdf'  # Name of generated PDF

# ===================== UTILITY FUNCTIONS =====================

def read_soup_from_file(filepath):
    """Read HTML file and return BeautifulSoup object for parsing."""
    try:
        # Open the HTML file with UTF-8 encoding
        with open(filepath, 'r', encoding='utf-8') as f:
            # Parse HTML and return BeautifulSoup object
            return BeautifulSoup(f.read(), 'html.parser')
    except Exception as e:
        # Print error if file can't be read
        print(f"Error reading {filepath}: {e}")
        return None

def clean_title(raw_title):
    """Clean article titles by removing ' - GeeksforGeeks' suffix and extra spaces."""
    # Remove " - GeeksforGeeks" from the end of title
    cleaned = re.sub(r'\s*-\s*GeeksforGeeks$', '', raw_title, flags=re.IGNORECASE)
    # Replace multiple spaces with single space and trim
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else raw_title

def normalize_spacing(text):
    """Replace multiple whitespace characters with a single space."""
    return re.sub(r'\s+', ' ', text).strip()

# ===================== SEARCH PAGE PARSING =====================

def scrape_search_page():
    """Main function that extracts article information from the search page."""
    # Read and parse the HTML file
    soup = read_soup_from_file(SEARCH_PAGE_FILE)
    if not soup:
        return []  # Return empty list if file couldn't be read

    # Find all article containers using their CSS class pattern
    # The class name changes but contains "ResultArticle_articleContainer"
    articles = soup.find_all('article', class_=re.compile(r'ResultArticle_articleContainer__\w+'))
    
    # If no articles found with specific class, try alternative selectors
    if not articles:
        print("No article containers found with the expected class. Trying alternative selectors...")
        # Look for any div with class containing "article", "result", or "search"
        articles = soup.find_all('div', class_=re.compile(r'article|result|search', re.I))
    
    scraped_data = []  # List to store all article data
    
    # Loop through articles, but limit to 15 to ensure we get 10 good ones
    for article in articles[:15]:
        # Find the link tag that contains the URL
        link_tag = article.find('a', href=True)
        if not link_tag:
            continue  # Skip if no link found
            
        # Convert relative URL to full URL
        url = urljoin(BASE_URL, link_tag['href'])
        
        # Try to find title in h2 with headerLink class first
        title_tag = article.find('h2', class_=re.compile(r'headerLink', re.I))
        if not title_tag:
            # If not found, try any heading tag
            title_tag = article.find(['h2', 'h3', 'h4'])
        if not title_tag:
            # Last resort: use the link text as title
            title_tag = link_tag
            
        # Get and clean the title
        raw_title = title_tag.get_text(strip=True)
        title = clean_title(raw_title)
        
        # Skip if title is too short or doesn't contain "Ruby"
        if len(title) < 5 or not re.search(r'ruby|Ruby', title, re.I):
            continue
            
        # Find description paragraph
        desc_tag = article.find('p', class_=re.compile(r'excerpt|description|content', re.I))
        if not desc_tag:
            # If no paragraph with specific class, take any paragraph
            desc_tag = article.find('p')
            
        description = "Not Available"  # Default value
        if desc_tag:
            # Get text without stripping to preserve spaces
            raw_desc = desc_tag.get_text(strip=False)
            # Remove "...Read More" from the end
            description = re.sub(r'\.\.\.\.\.\.Read More$', '', raw_desc, flags=re.IGNORECASE)
            description = re.sub(r'Read More$', '', description, flags=re.IGNORECASE)
            # Normalize spacing
            description = normalize_spacing(description)
            if len(description) < 20:  # If too short, mark as not available
                description = "Not Available"
        
        # Create data dictionary with all 6 required fields
        data = {
            'url': url,  # Article URL
            'topic_title': title,  # Cleaned title
            'difficulty': 'Not Available',  # Not on search page
            'key_concepts': description,  # Use description as key concepts
            'code_snippets': [],  # Not on search page
            'complexity': 'Not Available',  # Not on search page
            'references': [url]  # Put URL in references
        }
        
        scraped_data.append(data)
        print(f"Found: {title}")
        
        # Stop once we have 10 articles
        if len(scraped_data) >= 10:
            break
    
    # If we didn't get 10 articles, try a more general approach
    if len(scraped_data) < 10:
        print(f"Only found {len(scraped_data)} articles with specific selectors. Trying general link search...")
        
        # Find all links on the page
        all_links = soup.find_all('a', href=True)
        seen_urls = {item['url'] for item in scraped_data}  # Track URLs we already have
        
        for link in all_links:
            href = link['href']
            if not href.startswith(('http', '/')):
                continue
                
            url = urljoin(BASE_URL, href)
            if url in seen_urls:
                continue
                
            # Check if it's a Ruby article link
            if '/ruby/' in url or '/ruby' in href:
                title = link.get_text(strip=True)
                if len(title) > 10 and not any(item['url'] == url for item in scraped_data):
                    # Create minimal data for this article
                    data = {
                        'url': url,
                        'topic_title': clean_title(title),
                        'difficulty': 'Not Available',
                        'key_concepts': 'Not Available',
                        'code_snippets': [],
                        'complexity': 'Not Available',
                        'references': [url]
                    }
                    scraped_data.append(data)
                    print(f"Found (general): {title}")
                    if len(scraped_data) >= 10:
                        break
    
    # Save all scraped data to JSON file
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(scraped_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nSuccessfully extracted {len(scraped_data)} articles from search page.")
    return scraped_data

# ===================== PDF GENERATOR =====================

def generate_pdf(data=None, filename=PDF_FILE):
    """Generate a professionally formatted PDF from scraped data."""
    # If no data provided, try to load from cache file
    if data is None:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []

    # Create PDF document with letter size
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()  # Get default styles
    story = []  # List to hold PDF elements

    # Define custom style for article titles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.darkblue,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    # Define custom style for section headings
    heading2_style = ParagraphStyle(
        'Heading2',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.darkgreen,
        spaceAfter=12,
        spaceBefore=12
    )

    # Create header with generation info
    header_text = f"""
    <para align=center>
    <b>Ruby Programming Language - Learning Module</b><br/>
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>
    Subject: Computer Science / Programming<br/>
    <i>Based on search results page. Detailed fields are not available.</i>
    </para>
    """
    story.append(Paragraph(header_text, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))  # Add space after header

    if not data:
        story.append(Paragraph("No data available. Please run scraper first.", styles['Normal']))
    else:
        # Loop through each article and add to PDF
        for article in data:
            # Add article title
            story.append(Paragraph(article['topic_title'], title_style))
            story.append(Spacer(1, 0.1*inch))

            # Add URL section
            story.append(Paragraph("URL", heading2_style))
            story.append(Paragraph(article['url'], styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

            # Add Difficulty section
            story.append(Paragraph("Difficulty", heading2_style))
            story.append(Paragraph(article['difficulty'], styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

            # Add Key Concepts section
            story.append(Paragraph("Key Concepts", heading2_style))
            story.append(Paragraph(article['key_concepts'], styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

            # Add Code Examples section
            story.append(Paragraph("Code Examples", heading2_style))
            if article['code_snippets']:
                # Use Preformatted to preserve code formatting
                for code in article['code_snippets']:
                    story.append(Preformatted(code, styles['Code'], maxLineLength=80))
                    story.append(Spacer(1, 0.1*inch))
            else:
                story.append(Paragraph("Not Available on search page", styles['Italic']))

            # Add Complexity Analysis section
            story.append(Paragraph("Complexity Analysis", heading2_style))
            story.append(Paragraph(article['complexity'], styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

            # Add References section
            story.append(Paragraph("References", heading2_style))
            if article['references']:
                for ref in article['references']:
                    story.append(Paragraph(ref, styles['Normal']))
            else:
                story.append(Paragraph("Not Available", styles['Italic']))

            # Add separator and page break
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph(f"--- End of {article['topic_title']} ---", styles['Italic']))
            story.append(PageBreak())  # Start next article on new page

    # Build and save the PDF
    doc.build(story)
    return filename

# ===================== FLASK WEB INTERFACE =====================

# Create Flask application
app = Flask(__name__)

@app.route('/')
def index():
    """Home page route - renders the dashboard HTML."""
    return render_template('dashboard.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    """Scraping endpoint - triggered by button click."""
    # Delete old cache to ensure fresh scrape
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
        print("Old scraped_data.json deleted.")
    # Run the scraper and get data
    data = scrape_search_page()
    # Return JSON response with status and count
    return jsonify({'status': 'success', 'count': len(data)})

@app.route('/data')
def get_data():
    """Data endpoint - returns scraped data as JSON for preview."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify([])  # Return empty list if no data

@app.route('/download')
def download_pdf():
    """Download endpoint - generates and sends PDF file."""
    # Load data from cache or use empty list
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = []
    # Generate PDF and send as downloadable file
    pdf_file = generate_pdf(data)
    return send_file(pdf_file, as_attachment=True, download_name='Ruby_Learning_Module.pdf')

# Run the Flask app if this file is executed directly
if __name__ == '__main__':
    app.run(debug=True)
