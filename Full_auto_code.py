import os
import time
import pandas as pd
import pyautogui
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


EXCEL_PATH = "patients_names.xlsx"
SHEET_NAME = 0

GROUP = os.getenv("APP_GROUP")
USERNAME = os.getenv("APP_USERNAME")
PASSWORD = os.getenv("APP_PASSWORD")

if not GROUP or not USERNAME or not PASSWORD:
    raise RuntimeError("Missing credentials.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_PDF_DIR = os.path.join(BASE_DIR, "patients_name")
os.makedirs(ROOT_PDF_DIR, exist_ok=True)

failed_patients = []



def wait_for_overlay_to_disappear(driver, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "gwt-PopupPanelGlass"))
        )
    except:
        pass


def close_ros_popup_if_present(driver):
    try:
        popup = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Close']"))
        )
        popup.click()
        time.sleep(0.5)
    except:
        pass


df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)

names = (
    df["Patient"]
    .dropna()
    .astype(str)
    .str.strip()
    .loc[lambda s: s.str.lower() != "patient"]
    .tolist()
)


options = Options()
options.add_argument("--start-maximized")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

wait = WebDriverWait(driver, 40)


driver.get("https://ehr.doctorsoft.com/EyeExamEMR.html")

wait.until(EC.element_to_be_clickable((By.ID, "LOGIN_practiceId"))).send_keys(GROUP)
driver.find_element(By.ID, "LOGIN_username").send_keys(USERNAME)
driver.find_element(By.ID, "LOGIN_password").send_keys(PASSWORD)
driver.find_element(By.ID, "LOGIN_loginButton").click()

wait.until(EC.presence_of_element_located((By.ID, "contentBlock")))


for idx, full_name in enumerate(names, start=1):

    print(f"\n[{idx}] Processing: {full_name}")

    try:
        if "," not in full_name:
            failed_patients.append(f"{idx} - {full_name} | Invalid name format")
            continue

        last, rest = full_name.split(",", 1)
        last = last.strip().upper()

        parts = rest.strip().split()
        first = parts[0].upper()
        middle = parts[1].upper() if len(parts) > 1 else ""

        wait_for_overlay_to_disappear(driver)

        wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//*[@id="
            "'contentBlock']/div[1]/table/tbody/tr/td[4]")
        )).click()

        search_box = wait.until(EC.element_to_be_clickable((By.ID, "NAME_SEARCH")))
        search_box.clear()
        search_box.send_keys(last)

        time.sleep(1)

        suggestions = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".gwt-SuggestBoxPopup table tr")
            )
        )

        matched = False
        for row in suggestions:
            txt = row.text.upper()
            if last in txt and first in txt:
                if middle and f"{first} {middle}" not in txt:
                    continue
                row.click()
                matched = True
                break

        if not matched:
            failed_patients.append(f"{idx} - {full_name} | No match")
            continue

        patient_folder = os.path.join(ROOT_PDF_DIR, str(idx))
        os.makedirs(patient_folder, exist_ok=True)

        pdf_path = os.path.join(patient_folder, f"{idx}.pdf")

        if os.path.exists(pdf_path):
            print(f"⏭️ {idx}.pdf already exists, skipping")
            continue

        time.sleep(1.5)
        wait_for_overlay_to_disappear(driver)

        main_exam_buttons = driver.find_elements(
            By.XPATH, "//button[normalize-space()='Main Exam' and not(@disabled)]"
        )

        if not main_exam_buttons:
            failed_patients.append(f"{idx} - {full_name} | No Main Exam")
            continue

        driver.execute_script("arguments[0].click();", main_exam_buttons[0])
        close_ros_popup_if_present(driver)

        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//canvas | //img | //div[contains(@class,'exam')]")
            )
        )

        time.sleep(2)

        print("🖨️ Opening print preview...")

        print_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="contentBlock"]/div[2]/table[2]/tbody/tr/td[9]/button')
            )
        )

        driver.execute_script("arguments[0].click();", print_btn)

        time.sleep(5)

        pyautogui.press("enter")
        time.sleep(3)

        full_path = os.path.abspath(pdf_path)

        time.sleep(1)

        pyautogui.hotkey("ctrl", "a")

        pyautogui.press("backspace")

        time.sleep(0.5)

        pyautogui.write(full_path)

        time.sleep(1)

        pyautogui.press("enter")

        time.sleep(2)
        pyautogui.press("enter")

        print(f"Saved: {pdf_path}")

        if idx % 50 == 0:
            print(f"\n Processed {idx} patients. Taking 60 seconds break...\n")
            time.sleep(60)

    except Exception as e:
        failed_patients.append(f"{idx} - {full_name} | {type(e).__name__}")
        print(f"ERROR: {e}")


driver.quit()

print("\nFAILED PATIENT REPORT")
print("-" * 50)

if failed_patients:
    for f in failed_patients:
        print(f)
else:
    print("All PDFs downloaded successfully!")
