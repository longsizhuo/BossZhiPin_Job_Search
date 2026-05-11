import os
import time

# 让 Selenium 连接 ChromeDriver 时绕过系统代理
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

from selenium import webdriver
from selenium.common import NoSuchElementException, NoSuchWindowException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 持久化 Chrome profile：第一次手动扫码后，cookie 会留在这里，
# 后续运行就不需要再登。可用环境变量 BOSS_CHROME_PROFILE 覆盖。
CHROME_PROFILE_DIR = os.path.abspath(
    os.environ.get("BOSS_CHROME_PROFILE", "./chrome_profile")
)

LOGGED_IN_SELECTOR = '.user-nav, .nav-userinfo, [ka="header-username"]'

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
        try:
            cur = driver.current_url
        except NoSuchWindowException:
            return last_url
        if cur != last_url:
            last_url = cur
            last_change = time.time()
        elif time.time() - last_change >= stable_for:
            return cur
        time.sleep(0.2)
    return last_url


def _is_logged_in() -> bool:
    """头部出现用户区元素则视为已登录。"""
    try:
        return bool(driver.find_elements(By.CSS_SELECTOR, LOGGED_IN_SELECTOR))
    except NoSuchWindowException:
        return False


def _on_login_page(current_url: str) -> bool:
    return any(s in current_url for s in ("/web/user/", "passport-zp", "/login"))


def open_browser_with_options(url, browser):
    global driver

    if browser == "chrome":
        os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
        options = Options()
        options.add_experimental_option("detach", True)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
    elif browser == "edge":
        edge_options = webdriver.EdgeOptions()
        edge_options.add_experimental_option("detach", True)
        driver = webdriver.Edge(options=edge_options)
        driver.maximize_window()
    elif browser == "safari":
        driver = webdriver.Safari()
        driver.maximize_window()
    else:
        raise ValueError("Browser type not supported")

    driver.get(url)
    print(f"页面加载中... 当前URL: {driver.current_url}")
    stable_url = _wait_url_stable(driver, stable_for=2.0, timeout=30)
    print(f"页面已稳定，当前URL: {stable_url}")


def log_in():
    """处理三种入口状态：已登录 / 在首页带 header 登录入口 / 已被踢到独立登录页。"""
    global driver

    if _is_logged_in():
        print(f"检测到已登录（profile: {CHROME_PROFILE_DIR}），跳过扫码")
        return

    try:
        cur_url = driver.current_url
    except NoSuchWindowException:
        print("浏览器窗口已被关闭，可能被反爬拦截。建议先手动开一次 Chrome 用这个 profile 完成登录")
        return
    print(f"log_in 入口 URL: {cur_url}")

    # 不在登录页 → 先点 header 的"登录/注册"打开登录页
    if not _on_login_page(cur_url):
        try:
            login_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "登录"))
            )
            login_button.click()
            print("已点击 header 登录入口，等待登录页加载...")
            _wait_url_stable(driver, stable_for=2.0, timeout=15)
        except NoSuchWindowException:
            print("点击 header 登录入口时窗口已关闭，疑似反爬触发")
            return
        except Exception:
            try:
                print(f"未找到 header 登录入口，当前URL: {driver.current_url}")
            except NoSuchWindowException:
                print("未找到 header 登录入口，窗口已关闭")
                return

    # 在登录页：找微信 tab。这个入口在 BOSS 上可能是 <a> / <div> / <span>，
    # 所以按多个选择器依次试，不再硬卡 PARTIAL_LINK_TEXT。
    wechat_selectors = [
        (By.PARTIAL_LINK_TEXT, "微信"),
        (By.XPATH, "//*[contains(@class,'wechat') or contains(@class,'wx-')]"),
        (By.XPATH, "//*[(self::a or self::button or self::div or self::li or self::span)"
                   " and contains(normalize-space(text()),'微信')]"),
    ]
    clicked_wechat = False
    for by, sel in wechat_selectors:
        try:
            btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, sel)))
            btn.click()
            print(f"已点击微信登录入口（{by}={sel}），请扫码...")
            clicked_wechat = True
            break
        except NoSuchWindowException:
            print("查找微信入口时窗口已关闭，疑似反爬触发")
            return
        except Exception:
            continue
    if not clicked_wechat:
        print("没自动点上微信入口，请在浏览器里手动选择登录方式（脚本会继续等扫码完成）")

    # 等待扫码完成（5 分钟，留足第一次手动登录的时间）
    print("等待扫码登录... (最多等待 300 秒)")
    try:
        WebDriverWait(driver, 300).until(lambda d: _is_logged_in())
        print("登录成功！cookie 已写入 profile，下次跑应该不用再扫")
    except NoSuchWindowException:
        print("等待登录期间窗口已关闭，疑似反爬触发")
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
