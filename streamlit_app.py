import os
import re
import time
import base64
import traceback
from datetime import datetime
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from streamlit.components.v1 import html  
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
from difflib import SequenceMatcher
import PyPDF2
from io import BytesIO
import streamlit as st

def scrape_title():
    chrome_driver_path = os.path.join(os.getcwd(), "chromedriver")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service(executable_path=chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

DOWNLOAD_DIR = os.path.join(os.getcwd(), "pdf_dwn")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def print_timed(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def similarity_ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()

def parse_date(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%d %B %Y")
        return {
            "month_in_word": date_obj.strftime("%d %B %Y"),
            "month_in_num": date_obj.strftime("%d/%m/%Y"),
            "filename_date": date_obj.strftime("%Y%m%d")
        }
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}")

def get_pdf_content(url):
    print_timed(f"📥 Downloading PDF from {url}")
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return BytesIO(response.content)

def parse_pdf_content(pdf_content):
    reader = PyPDF2.PdfReader(pdf_content)
    text = ""
    charge_code = ""
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text += page_text + "\n"
        if not charge_code:
            match = re.search(r"Charge code:\s*(\d{3,4}\s*\d{3,4}\s*\d{3,4})", page_text)
            if match:
                charge_code = match.group(1).replace(" ", "")
    return text, charge_code

def extract_pdf_info(pdf_text):
    normalized_pdf = ' '.join(pdf_text.replace('\n', ' ').split()).upper()
    company_match = re.search(r'COMPANY NAME:\s*(.*?)\s*COMPANY NUMBER:', normalized_pdf)
    company_name = company_match.group(1).strip() if company_match else None
    desc_match = re.search(r'BRIEF DESCRIPTION:\s*(.*?)(?=(CONTAINS|AUTHENTICATION OF FORM|CERTIFIED BY:|CERTIFICATION STATEMENT:))', normalized_pdf)
    brief_description = desc_match.group(1).strip() if desc_match else None
    if brief_description:
        stop_phrases = ['CONTAINS FIXED CHARGE', 'CONTAINS NEGATIVE PLEDGE', 'CONTAINS FLOATING CHARGE', 'CONTAINS']
        for phrase in stop_phrases:
            if phrase in brief_description:
                brief_description = brief_description.split(phrase)[0].strip()
    date_match = re.search(r'DATE OF CREATION:\s*(\d{2}/\d{2}/\d{4})', normalized_pdf)
    month_in_num = date_match.group(1) if date_match else None
    entitled_match = re.search(r'PERSONS ENTITLED:\s*(.*?)(?=(CHARGE|DATE OF CREATION|BRIEF DESCRIPTION|AUTHENTICATION|CERTIFIED BY:|CERTIFICATION STATEMENT:))', normalized_pdf)
    persons_entitled = entitled_match.group(1).strip() if entitled_match else None
    return {
        'company_name': company_name,
        'brief_description': brief_description,
        'month_in_num': month_in_num,
        'persons_entitled': persons_entitled
    }

def check_pdf_conditions(pdf_text, date_info, company_name, persons_entitled, brief_description):
    result = extract_pdf_info(pdf_text)
    brief_description_score = int(similarity_ratio(result['brief_description'], brief_description.upper())) * 100
    persons_entitled_score = int(similarity_ratio(result['persons_entitled'], persons_entitled.upper())) * 100
    conditions_met = True
    if company_name.upper() != result['company_name']:
        conditions_met = False
    if persons_entitled_score < 95:
        conditions_met = False
    if brief_description_score < 95:
        conditions_met = False
    if date_info["month_in_num"] != result['month_in_num']:
        conditions_met = False
    return conditions_met

# def show_pdf_in_streamlit(pdf_content_io):
#     pdf_content_io.seek(0)
#     base64_pdf = base64.b64encode(pdf_content_io.read()).decode("utf-8")
#     pdf_display = f"""
#     <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700px" type="application/pdf"></iframe>
#     """
#     st.markdown(pdf_display, unsafe_allow_html=True)

def show_companies_house_pdf(url):
    """Safe PDF display for UK Companies House documents"""
    try:
        # Download PDF content
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Verify content type
        if 'application/pdf' not in response.headers.get('Content-Type', ''):
            st.error("Not a valid PDF document")
            return

        # Create in-memory buffer
        pdf_buffer = BytesIO(response.content)
        
        # Method 1: PDF.js Viewer (hosted version)
        base64_pdf = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
        viewer_html = f"""
        <div style="height: 700px;">
            <iframe 
                src="https://mozilla.github.io/pdf.js/web/viewer.html?file=data:application/pdf;base64,{base64_pdf}"
                width="100%"
                height="700px"
                style="border: none;">
            </iframe>
        </div>
        """
        html(viewer_html, height=700)

        # Method 2: Direct download
        st.markdown("---")
        st.download_button(
            label="⬇️ Download Original PDF",
            data=pdf_buffer.getvalue(),
            file_name="companies_house_document.pdf",
            mime="application/pdf"
        )

        # Method 3: External link
        st.markdown("---")
        st.markdown(f"🔗 [Open in Companies House Website]({url})")

    except requests.exceptions.RequestException as e:
        st.error(f"Failed to retrieve document: {str(e)}")
    except Exception as e:
        st.error(f"Error displaying PDF: {str(e)}")
    
def get_company_info(company_name, persons_entitled, brief_description, input_date):
    date_info = parse_date(input_date)
    driver = scrape_title()
    try:
        driver.get("https://find-and-update.company-information.service.gov.uk/")
        wait = WebDriverWait(driver, 20)
        search_box = wait.until(EC.presence_of_element_located((By.ID, "site-search-text")))
        search_box.send_keys(company_name + Keys.RETURN)
        company_link = wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[contains(., '{company_name}') and contains(@href, '/company/')]")))
        company_link.click()
        filing_history_tab = wait.until(EC.element_to_be_clickable((By.ID, "filing-history-tab")))
        filing_history_tab.click()
        charges_filter_label = wait.until(EC.presence_of_element_located((By.XPATH, "//label[@for='filter-category-mortgage']")))
        driver.execute_script("arguments[0].scrollIntoView(true);", charges_filter_label)
        time.sleep(1)
        try:
            charges_filter_label.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", charges_filter_label)
        try:
            wait.until(EC.presence_of_element_located((By.ID, "fhTable")))
        except TimeoutException:
            return
        rows = driver.find_elements(By.CSS_SELECTOR, "#fhTable tbody tr:not(:first-child)")
        for idx, row in enumerate(rows, 1):
            try:
                description = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)").text
                if date_info["month_in_word"].split()[1] in description:
                    pdf_link = row.find_element(By.CSS_SELECTOR, "a[href*='/document']")
                    pdf_url = pdf_link.get_attribute("href")
                    pdf_content = get_pdf_content(pdf_url)
                    pdf_text, charge_code = parse_pdf_content(pdf_content)
                    if check_pdf_conditions(pdf_text, date_info, company_name, persons_entitled, brief_description):
                        st.success("✅ PDF Matched All Requirements!")
                        # Get PDF content
                        # pdf_content = get_pdf_content(pdf_url)  # Your existing function
                        
                        # Verify PDF validity
                        try:
                            PyPDF2.PdfReader(pdf_content)
                            show_companies_house_pdf(pdf_url)
                        except PyPDF2.errors.PdfReadError:
                            st.error("⚠️ Invalid PDF File - Content cannot be displayed")
                            st.download_button(
                                label="⚠️ Download Raw File",
                                data=pdf_content.getvalue(),
                                file_name="document.pdf",
                                mime="application/pdf"
                            )
            except Exception as e:
                print_timed(f"⚠️ Error in filing {idx}: {str(e)}")
        st.success("❌ No valid filings matched all conditions!")
    except Exception as e:
        st.error(f"Script Error: {str(e)[:200]}")
    finally:
        driver.quit()

# Streamlit UI
st.title("Company Information Finder")
company_name = st.text_input("Company Name:")
persons_entitled = st.text_area("Persons Entitled:")
brief_description = st.text_area("Brief Description:")
input_date = st.date_input("Date of Creation (YYYY-MM-DD):")

if st.button("Find"):
    get_company_info(
        company_name,
        persons_entitled,
        brief_description,
        input_date.strftime("%d %B %Y")
    )