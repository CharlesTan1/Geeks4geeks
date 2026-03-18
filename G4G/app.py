import os 
import re  
import json  
from urllib.parse import urljoin  
from datetime import datetime  
from bs4 import BeautifulSoup  
from flask import Flask, render_template, jsonify, send_file
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

BASE_URL = "https://www.geeksforgeeks.org"  
SEARCH_PAGE_FILE = "search_page.html"  
DATA_FILE = 'scraped_data.json' 
PDF_FILE = 'Ruby_Learning_Module.pdf'  

def read_soup_from_file(filepath):
    """Read HTML file and return BeautifulSoup object for parsing."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return BeautifulSoup(f.read(), 'html.parser')
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def clean_title(raw_title):
    """Clean article titles by removing ' - GeeksforGeeks' suffix and extra spaces."""
    cleaned = re.sub(r'\s*-\s*GeeksforGeeks$', '', raw_title, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else raw_title

def normalize_spacing(text):
    """Replace multiple whitespace characters with a single space."""
    return re.sub(r'\s+', ' ', text).strip()

def scrape_search_page():
    """Main function that extracts article information from the search page."""
    soup = read_soup_from_file(SEARCH_PAGE_FILE)
    if not soup:
        return []  

    articles = soup.find_all('article', class_=re.compile(r'ResultArticle_articleContainer__\w+'))
    if not articles:
        print("No article containers found with the expected class. Trying alternative selectors...")
        articles = soup.find_all('div', class_=re.compile(r'article|result|search', re.I))
    
    scraped_data = []  
    
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
            if len(description) < 20: 
                description = "Not Available"
        
        data = {
            'url': url,  
            'topic_title': title,  
            'difficulty': 'Not Available', 
            'key_concepts': description,  
            'code_snippets': [],  
            'complexity': 'Not Available',  
            'references': [url]  
        }
        
        scraped_data.append(data)
        print(f"Found: {title}")
        
        if len(scraped_data) >= 10:
            break
    
    if len(scraped_data) < 10:
        print(f"Only found {len(scraped_data)} articles with specific selectors. Trying general link search...")
        
        all_links = soup.find_all('a', href=True)
        seen_urls = {item['url'] for item in scraped_data}
        
        for link in all_links:
            href = link['href']
            if not href.startswith(('http', '/')):
                continue
                
            url = urljoin(BASE_URL, href)
            if url in seen_urls:
                continue
                
            if '/ruby/' in url or '/ruby' in href:
                title = link.get_text(strip=True)
                if len(title) > 10 and not any(item['url'] == url for item in scraped_data):
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
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(scraped_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nSuccessfully extracted {len(scraped_data)} articles from search page.")
    return scraped_data



def generate_pdf(data=None, filename=PDF_FILE):
    """Generate a professionally formatted PDF from scraped data."""
    if data is None:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []

    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()  
    story = []  

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.darkblue,
        spaceAfter=30,
        alignment=1  
    )
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
    story.append(Spacer(1, 0.3*inch)) 

    if not data:
        story.append(Paragraph("No data available. Please run scraper first.", styles['Normal']))
    else:
        for article in data:
            story.append(Paragraph(article['topic_title'], title_style))
            story.append(Spacer(1, 0.1*inch))

            story.append(Paragraph("URL", heading2_style))
            story.append(Paragraph(article['url'], styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

            story.append(Paragraph("Difficulty", heading2_style))
            story.append(Paragraph(article['difficulty'], styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

            story.append(Paragraph("Key Concepts", heading2_style))
            story.append(Paragraph(article['key_concepts'], styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

            story.append(Paragraph("Code Examples", heading2_style))
            if article['code_snippets']:

                for code in article['code_snippets']:
                    story.append(Preformatted(code, styles['Code'], maxLineLength=80))
                    story.append(Spacer(1, 0.1*inch))
            else:
                story.append(Paragraph("Not Available on search page", styles['Italic']))

            story.append(Paragraph("Complexity Analysis", heading2_style))
            story.append(Paragraph(article['complexity'], styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

            story.append(Paragraph("References", heading2_style))
            if article['references']:
                for ref in article['references']:
                    story.append(Paragraph(ref, styles['Normal']))
            else:
                story.append(Paragraph("Not Available", styles['Italic']))


            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph(f"--- End of {article['topic_title']} ---", styles['Italic']))
            story.append(PageBreak())  # Start next article on new page


    doc.build(story)
    return filename


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