import os
import re
import time
import base64
import traceback
from datetime import datetime
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
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
    # Set correct path for chromedriver
    chrome_driver_path = os.path.join(os.getcwd(), "chromedriver")

    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    service = Service(executable_path=chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# Configuration
DOWNLOAD_DIR = r"C:\Users\AmanFarkade\OneDrive - Pepper India Resolution Private Limited\SeleniumProj\UK_AUTO\pdf_dwn"
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

def sanitize_filename(text):
    return re.sub(r'[\\/*?:"<>|]', "_", text)

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

# def extract_pdf_info(pdf_text):
#     normalized_pdf = ' '.join(pdf_text.replace('\n', ' ').split()).upper()
#     print("#####--->>>",normalized_pdf)
#     company_match = re.search(r'COMPANY NAME:\s*(.*?)\s*COMPANY NUMBER:', normalized_pdf)
#     company_name = company_match.group(1).strip() if company_match else None

#     desc_match = re.search(r'BRIEF DESCRIPTION:\s*(.*?)(?=(CONTAINS|AUTHENTICATION OF FORM|CERTIFIED BY:|CERTIFICATION STATEMENT:))', normalized_pdf)
#     brief_description = desc_match.group(1).strip() if desc_match else None

#     if brief_description:
#         stop_phrases = ['CONTAINS FIXED CHARGE', 'CONTAINS NEGATIVE PLEDGE', 'CONTAINS FLOATING CHARGE', 'CONTAINS']
#         for phrase in stop_phrases:
#             if phrase in brief_description:
#                 brief_description = brief_description.split(phrase)[0].strip()

#     date_match = re.search(r'DATE OF CREATION:\s*(\d{2}/\d{2}/\d{4})', normalized_pdf)
#     month_in_num = date_match.group(1) if date_match else None

#     return {
#         'company_name': company_name,
#         'brief_description': brief_description,
#         'month_in_num': month_in_num
#     }

def extract_pdf_info(pdf_text):
    normalized_pdf = ' '.join(pdf_text.replace('\n', ' ').split()).upper()
    print("#####--->>>", normalized_pdf)

    # Extract company name
    company_match = re.search(r'COMPANY NAME:\s*(.*?)\s*COMPANY NUMBER:', normalized_pdf)
    company_name = company_match.group(1).strip() if company_match else None

    # Extract brief description
    desc_match = re.search(r'BRIEF DESCRIPTION:\s*(.*?)(?=(CONTAINS|AUTHENTICATION OF FORM|CERTIFIED BY:|CERTIFICATION STATEMENT:))', normalized_pdf)
    brief_description = desc_match.group(1).strip() if desc_match else None

    if brief_description:
        stop_phrases = ['CONTAINS FIXED CHARGE', 'CONTAINS NEGATIVE PLEDGE', 'CONTAINS FLOATING CHARGE', 'CONTAINS']
        for phrase in stop_phrases:
            if phrase in brief_description:
                brief_description = brief_description.split(phrase)[0].strip()

    # Extract date
    date_match = re.search(r'DATE OF CREATION:\s*(\d{2}/\d{2}/\d{4})', normalized_pdf)
    month_in_num = date_match.group(1) if date_match else None

    # Extract persons entitled
    entitled_match = re.search(r'PERSONS ENTITLED:\s*(.*?)(?=(CHARGE|DATE OF CREATION|BRIEF DESCRIPTION|AUTHENTICATION|CERTIFIED BY:|CERTIFICATION STATEMENT:))', normalized_pdf)
    persons_entitled = entitled_match.group(1).strip() if entitled_match else None

    return {
        'company_name': company_name,
        'brief_description': brief_description,
        'month_in_num': month_in_num,
        'persons_entitled': persons_entitled
    }

def check_pdf_conditions(pdf_text, date_info, company_name,persons_entitled, brief_description):
    pdf_text = pdf_text
    date_info =date_info
    company_name =company_name
    persons_entitled =persons_entitled
    brief_description =brief_description

    normalized_pdf = ' '.join(pdf_text.replace('\n', ' ').split())
    normalized_description_brief_description = ' '.join(brief_description.split()).upper()
    normalized_description_persons_entitled = ' '.join(persons_entitled.split()).upper()
    result = extract_pdf_info(normalized_pdf)

    print(f"Company Name: {result['company_name']}")
    print(f"Brief Description: {result['brief_description']} ### {normalized_description_brief_description}")
    print(f"Month in Numeric: {result['month_in_num']}")
    print(f"------persons_entitled: {result['persons_entitled']}")

    brief_description_score = int(similarity_ratio(result['brief_description'], normalized_description_brief_description) * 100)
    print("📊 Brief description similarity score:", brief_description_score)
    persons_entitled_score = int(similarity_ratio(result['persons_entitled'], normalized_description_persons_entitled) * 100)
    print("persons_entitled_score:",persons_entitled_score)

    conditions_met = True
    if company_name != result['company_name']:
        print_timed("❌ Company name mismatch")
        conditions_met = False
    
    if persons_entitled_score < 95:
        print_timed("❌ persons_entitled_score mismatch")
        conditions_met = False

    if brief_description_score < 95:
        print_timed("❌ Brief description mismatch")
        conditions_met = False

    if date_info["month_in_num"] != result['month_in_num']:
        print_timed("❌ Date mismatch")
        conditions_met = False

    return conditions_met

def save_pdf_file(pdf_content, charge_code, date_info):
    base_name = f"{company_name.replace(' ', '_')}_{charge_code or 'UNKNOWN'}_{date_info.get('filename_date', 'UNKNOWN_DATE')}"
    safe_filename = sanitize_filename(base_name) + ".pdf"
    full_path = os.path.join(DOWNLOAD_DIR, safe_filename)

    # Save the PDF content to the file
    with open(full_path, "wb") as f:
        f.write(pdf_content.getvalue())

    # print_timed(f"💾 Saved PDF: {safe_filename}")
    print(f"💾 Saved PDF: {safe_filename}")
    st.success("✅ PDF downloaded successfully!")  # Streamlit UI message
    time.sleep(1)
    show_pdf_in_streamlit(full_path)
    return full_path

def show_pdf_in_streamlit(file_path):
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode("utf-8")

    pdf_display = f"""
    <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700px" type="application/pdf"></iframe>
    """
    st.markdown(pdf_display, unsafe_allow_html=True)

def get_company_info(company_name, persons_entitled, brief_description, input_date):
    company_name = company_name
    persons_entitled = persons_entitled
    brief_description = brief_description
    input_date =input_date
    start_time = time.time()
    date_info = parse_date(input_date)
    print_timed(f"📅 Parsed date info: {date_info}")
    
    driver = scrape_title()

    try:
        driver.get("https://find-and-update.company-information.service.gov.uk/")
        wait = WebDriverWait(driver, 20)

        search_box = wait.until(EC.presence_of_element_located((By.ID, "site-search-text")))
        search_box.send_keys(company_name + Keys.RETURN)

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.results-list li")))
        company_link = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//a[contains(., '{company_name}') and contains(@href, '/company/')]")))
        company_link.click()

        wait.until(EC.presence_of_element_located((By.ID, "content-container")))
        filing_history_tab = wait.until(EC.element_to_be_clickable((By.ID, "filing-history-tab")))
        filing_history_tab.click()

        # Scroll to and click the Charges filter
        charges_filter_label = wait.until(EC.presence_of_element_located((By.XPATH, "//label[@for='filter-category-mortgage']")))
        driver.execute_script("arguments[0].scrollIntoView(true);", charges_filter_label)
        time.sleep(1)
        try:
            charges_filter_label.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", charges_filter_label)

        # Wait for results or "no filings" message
        try:
            wait.until(EC.presence_of_element_located((By.ID, "fhTable")))
            print_timed("✅ Charges filings loaded")
        except TimeoutException:
            print_timed("❌ No filings found under Charges")
            return

        rows = driver.find_elements(By.CSS_SELECTOR, "#fhTable tbody tr:not(:first-child)")
        print_timed(f"📋 Total filings found: {len(rows)}")

        for idx, row in enumerate(rows, 1):
            try:
                print_timed(f"🔍 Processing filing {idx}...")
                description = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)").text
                if date_info["month_in_word"].split()[1] in description:
                    pdf_link = row.find_element(By.CSS_SELECTOR, "a[href*='/document']")
                    pdf_url = pdf_link.get_attribute("href")
                    pdf_content = get_pdf_content(pdf_url)
                    pdf_text, charge_code = parse_pdf_content(pdf_content)

                    if check_pdf_conditions(pdf_text, date_info, company_name, persons_entitled, brief_description):
                        save_path = save_pdf_file(pdf_content, charge_code, date_info)
                        print_timed(f"✅ Match found and PDF saved: {os.path.basename(save_path)}")
                        return
                    else:
                        print_timed("⏭️ Criteria not met for this filing")

            except Exception as e:
                print_timed(f"⚠️ Error in filing {idx}: {str(e)}")
            time.sleep(0.5)

        print_timed("❌ No valid filings matched all conditions")
        st.success("✅ No valid filings matched all conditions!")
    except Exception as e:
        print_timed(f"🔥 Script Error: {str(e)[:200]}")
        traceback.print_exc()
    finally:
        print_timed(f"🕒 Script completed in {time.time() - start_time:.2f} seconds")
        driver.quit()

# Streamlit UI for user inputs
st.title("Company Information Finder")
company_name = st.text_input("Enter Company Name:")
persons_entitled = st.text_area("Enter Persons entitled:")
brief_description = st.text_area("Enter Brief Description:")
input_date = st.date_input("Enter Date of creation (YYYY MMM DD):")

if st.button("Find Company Info"):
    get_company_info(company_name, persons_entitled, brief_description, input_date.strftime("%d %B %Y"))

