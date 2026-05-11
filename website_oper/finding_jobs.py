import os
import time

# 让 Selenium 连接 ChromeDriver 时绕过系统代理
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 全局 WebDriver 实例
driver = None


def get_driver():
    global driver
    return driver


def _wait_url_stable(driver, stable_for=2.0, timeout=30):
    """等到 URL 连续 stable_for 秒未变化再返回，避开 BOSS 登录页的重定向抖动。"""
    end = time.time() + timeout
    last_url = driver.current_url
    last_change = time.time()
    while time.time() < end:
        cur = driver.current_url
        if cur != last_url:
            last_url = cur
            last_change = time.time()
        elif time.time() - last_change >= stable_for:
            return cur
        time.sleep(0.2)
    return last_url


def open_browser_with_options(url, browser):
    global driver
    options = Options()
    options.add_experimental_option("detach", True)
    # 反自动化检测
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    if browser == "chrome":
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        # 隐藏 webdriver 标志
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
    elif browser == "edge":
        driver = webdriver.Edge()
        driver.maximize_window()
    elif browser == "safari":
        driver = webdriver.Safari()
        driver.maximize_window()
    else:
        raise ValueError("Browser type not supported")

    driver.get(url)
    print(f"页面加载中... 当前URL: {driver.current_url}")

    # 先让 URL 在重定向中稳下来，再等登录按钮可点击；只等 title 不够，
    # bounce 中间页也有 title，容易在抖动中途 find_element 扑空。
    stable_url = _wait_url_stable(driver, stable_for=2.0, timeout=30)
    print(f"页面已稳定，当前URL: {stable_url}")
    try:
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "登录"))
        )
    except Exception:
        print(f"未在稳定后的页面上找到登录入口，当前URL: {driver.current_url}")
        raise


def log_in():
    global driver

    # 用文字内容找到"登录/注册"按钮
    try:
        login_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "登录/注册"))
        )
    except Exception:
        # 备选：部分匹配
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "登录"))
        )
    login_button.click()
    print("已点击登录按钮，等待登录方式选择...")
    time.sleep(2)

    # 找到微信登录按钮（用文字匹配）
    try:
        wechat_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "微信"))
        )
        wechat_button.click()
        print("已选择微信登录，请扫码...")
    except Exception:
        print("未找到微信登录按钮，请手动选择登录方式...")

    # 等待用户扫码登录成功（最多等 120 秒）
    print("等待扫码登录... (最多等待120秒)")
    try:
        WebDriverWait(driver, 120).until(
            lambda d: "登录" not in d.page_source[:5000] or
                      d.find_elements(By.CSS_SELECTOR, '.user-nav, .nav-userinfo, [ka="header-username"]')
        )
        print("登录成功！")
    except Exception:
        print("登录超时，请确认是否已扫码登录")


def get_job_description():
    global driver

    # 使用给定的 XPath 定位职位描述元素
    xpath_locator_job_description = "//*[@id='wrap']/div[2]/div[2]/div/div/div[2]/div/div[2]/p"

    # 确保元素已加载并且可以获取文本
    job_description_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, xpath_locator_job_description))
    )

    # 获取职位描述文本
    job_description = job_description_element.text
    print(job_description)  # 打印出职位描述，或者你可以在这里做其他处理

    # 返回职位描述文本，如果函数需要
    return job_description


def select_dropdown_option(driver, label):
    # 尝试在具有特定类的元素中找到文本
    trigger_elements = driver.find_elements(By.XPATH, "//*[@class='recommend-job-btn has-tooltip']")

    # 标记是否找到元素
    found = False

    for element in trigger_elements:
        if label in element.text:
            # 确保元素可见并且可点击
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(element))
            element.click()  # 点击找到的元素
            found = True
            break

    # 如果在按钮中找到了文本，就不再继续下面的操作
    if found:
        # 取消注释，提供选择更多tag的时间
        # time.sleep(20)
        return

    # 如果在按钮中没有找到文本，执行原来的下拉列表操作
    trigger_selector = "//*[@id='wrap']/div[2]/div[1]/div/div[1]/div"
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, trigger_selector))
    ).click()  # 打开下拉菜单

    dropdown_selector = "ul.dropdown-expect-list"
    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, dropdown_selector))
    )

    option_selector = f"//li[contains(text(), '{label}')]"
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, option_selector))
    ).click()  # 选择下拉菜单中的选项


def get_job_description_by_index(index):
    try:
        job_selector = f"//*[@id='wrap']/div[2]/div[2]/div/div/div[1]/ul/li[{index}]"
        job_element = driver.find_element(By.XPATH, job_selector)
        job_element.click()

        description_selector = "//*[@id='wrap']/div[2]/div[2]/div/div/div[2]/div/div[2]/p"
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, description_selector))
        )
        job_description_element = driver.find_element(By.XPATH, description_selector)
        return job_description_element.text

    except NoSuchElementException:
        print(f"No job found at index {index}.")
        return None


# Variables
url = "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend"
browser_type = "chrome"
