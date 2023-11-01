from flask import Flask, render_template, request, redirect, url_for, send_file
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import os
import concurrent.futures

app = Flask(__name__)

# Configuration options
CHROME_OPTIONS = ["--headless", "--log-level=3"]
WAIT_TIMEOUT = 5
MAX_THREADS = 5  # Adjust the number of parallel threads

def scrape_company_data(company_url):
    options = webdriver.ChromeOptions()
    for opt in CHROME_OPTIONS:
        options.add_argument(opt)

    with webdriver.Chrome(options=options) as driver:
        driver.get(company_url)
        WebDriverWait(driver, WAIT_TIMEOUT).until(EC.presence_of_element_located((By.CLASS_NAME, "details")))
        company_data = driver.page_source

    company_soup = BeautifulSoup(company_data, 'html.parser')
    company_details = company_soup.find('div', class_='details')

    company_name = company_details.find('h6').get_text()
    company_address, contact_number, company_email = "", "", ""
    p_element = company_details.find('p').get_text().strip()
    company_address = p_element.split('\n')[0]
    contact_number = company_details.find('p').find_all('br')[-1].next_sibling.strip()
    if len(company_details.find('p').find_all('br')) >= 2:
        company_email = company_details.find('p').find('a').get_text()

    return {
        "Company Name": company_name,
        "Company Address": company_address,
        "Contact Number": contact_number,
        "Company Email": company_email,
        "Company Url": company_url
    }

def scrape_website(query):
    url = f"https://www.propertymark.co.uk/find-an-expert.html?q={query}&property_badge="
    options = webdriver.ChromeOptions()
    for opt in CHROME_OPTIONS:
        options.add_argument(opt)

    with webdriver.Chrome(options=options) as driver:
        driver.get(url)
        wait = WebDriverWait(driver, WAIT_TIMEOUT)

        while True:
            try:
                load_more = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "load-more-link")))
                driver.execute_script("arguments[0].scrollIntoView(true);", load_more)
                driver.execute_script("arguments[0].click();", load_more)
            except Exception as _:
                break

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        result_container = soup.find('div', class_="member-list")
        member_items = result_container.find_all('div', class_="member-item")

        data = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = []
            for member_item in member_items:
                member_item_details = member_item.find('div', class_="member-item-detail")
                company_acc_url = member_item_details.find('h6', class_='member-name').find('a').get('href')
                futures.append(executor.submit(scrape_company_data, company_acc_url))

            for future in concurrent.futures.as_completed(futures):
                data.append(future.result())

        return data

@app.route("/", methods=["GET", "POST"])
def index():
    scraped_data = None
    download_filename = None
    
    if request.method == "POST":
        query = request.form.get("query")

        if query:
            scraped_data = scrape_website(query)
            download_filename = f"{query}.xlsx"
            df = pd.DataFrame(scraped_data)
            df.to_excel(download_filename, index=False)

    return render_template("index.html", scraped_data=scraped_data, download_filename=download_filename)

@app.route("/download_excel/<filename>")
def download(filename):
    if not filename.endswith(".xlsx"):
        filename += ".xlsx"

    if os.path.exists(filename):
        return send_file(filename, as_attachment=True)
    else:
        return render_template("error.html", message="File not found")

if __name__ == "__main__":
    app.run()
