import random
import logging
import requests
import re
import time
import selenium
import json

from tqdm import tqdm
from fake_useragent import UserAgent as ua
from selenium.webdriver.remote.webdriver import WebDriver as wd
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait as wdw
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup as BS

fmt = '%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s'
datefmt = '%Y-%m-%d %H:%M:%S'
level = logging.INFO

formatter = logging.Formatter(fmt, datefmt)
logger = logging.getLogger()
logger.setLevel(level)

file = logging.FileHandler('youtube/youtube.log', encoding='utf-8')
file.setLevel(level)
file.setFormatter(formatter)
logger.addHandler(file)

console = logging.StreamHandler()
console.setLevel(level)
console.setFormatter(formatter)
logger.addHandler(console)


def get_video_url_from_youtube(keyword):
    """
    根据输入的关键词在 youtube 中搜索相应的结果，在 youtube/url.txt 下写入目标视频的URL
    注意，youtube 站内搜索结果非常有限，需要通过谷歌搜索才能获取大量内容
    :param keyword: 搜索关键词
    :return:
    """

    # 获取目标网页的源代码
    headers = {'user-agent': ua(use_cache_server=False).random}
    query_url="https://m.youtube.com/results?search_query="+keyword
    resp = requests.get(query_url, headers=headers)

    # 获取包含每个视频信息的 list
    result_str = re.findall(r'ytInitialData = (.*);</script>', resp.text)[0]
    result_dict = json.loads(result_str)
    content_list = result_dict['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']

    # 提取每个视频的 url
    for content in content_list:

        # 不是所有视频都有 videoRenderer tag
        try:
            video_url = "https://www.youtube.com/watch?v="+content['videoRenderer']['videoId']
            with open(f"youtube/url.txt", "a+") as f:
                f.write(video_url + '\n')
        except:
            pass


def get_video_url_from_google(keyword, page):
    """
    根据输入的关键词在 youtube 中搜索相应的结果，在 youtube/url.txt 下写入目标视频的 URL
    注意，如果搜索次数太多请求会返回 429 ，可以多次运行该函数
    :param page: 上次停留的页面值
    :param keyword: 搜索关键词
    :return: page: 停止时的页面
    """

    with open("youtube/settings.json", "r", encoding='utf-8') as f:
        settings = json.load(f)

    headers = {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)Chrome/103.0.0.0 Safari/537.36",
        "cookie": settings['cookie']
    }

    while True:
        resp = requests.get(f"https://www.google.com.hk/search?q=site:youtube.com+{keyword}&newwindow=1&ei=\
        lbDeYqXBBJzQkPIPz7SngAU&start={page}0&sa=N&ved=2ahUKEwjl37rPp5T5AhUcKEQIHU_aCVAQ8tMDegQIARA8&biw=1323&bih=762&dpr=2",
                            headers=headers)

        # 爬多了就会 429，也可以直接把程序停下来多等一会
        if resp.status_code != 200:
            logger.info(f"Response: {resp.status_code}")
            time.sleep(random.uniform(60, 120))
            continue

        # 200 则开始解析！
        soup = BS(resp.text, 'lxml')
        href_list = set(map(lambda x: x['href'],
                            filter(lambda x: 'class' not in x.attrs,
                                   soup.find_all("a", target="_blank")
                                   )
                            )
                        )

        if href_list:
            with open(f"youtube/url.txt", "a+") as f:
                f.write("\n".join(href_list) + '\n')
            logger.info(f"page{page} finished: \n" + '\n'.join(href_list))
            page += 1
            time.sleep(10)

        else:
            # 不确定是错误还是结束了所以输出 text ，并返回 page ，结束程序
            logger.info(f"{resp.text}")
            return page


def get_page():
    """
    根据 youtube/url.txt 下的 URL，依次访问每一个网页，并且获取网页的源代码，写入 ./youtube 文件夹下
    已访问的视频 id 会写入 youtube/written.txt，所以可以随时停下该函数，不用担心 redundant visit
    :return:
    """

    driver = selenium.webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
    time.sleep(5)
    with open("youtube/url.txt", "r") as f:
        url_list = f.read().split()

    # 遍历所有 url
    for url in tqdm(url_list, total=len(url_list)):

        # 过滤访问过的网页
        vid = re.findall("watch\?v=([\w-]+)", url)[0]
        with open("youtube/written.txt", "r") as f:
            written = f.read().split()
        if vid in written:
            continue

        try:
            # 访问网页
            driver.get(url)
            wdw(driver, 20).until(EC.visibility_of_element_located((By.XPATH,
                "//yt-formatted-string[@class='style-scope ytd-button-renderer style-destructive size-default']")))
            logger.info(f"visiting {url}")
            time.sleep(1)

            # 点击 'more' button，但不是每一个网页都有 more
            try:
                btn = driver.find_element(By.XPATH, "//tp-yt-paper-button[@id='expand']")
                time.sleep(5)
                btn.click()
            except Exception as e:
                logger.exception(e)

            # 写入
            with open(f"youtube/{vid}.html", "w") as f:
                f.write(driver.page_source)
            with open("youtube/written.txt", "a+") as f:
                f.write(vid + '\n')
            logger.info(f'{url} written')
            time.sleep(5)

        except Exception as e:
            logger.exception(e)
            time.sleep(random.uniform(10, 40))


def left_num():
    """
    获取剩余的任务数
    :return: 剩余的任务数
    """
    with open("youtube/url.txt", "r") as f:
        url_list = f.read().split()

    left = 0
    for url in url_list:
        vid = re.findall("watch\?v=([\w-]+)", url)[0]
        with open("written.txt", "r") as f:
            written = f.read().split()
        if vid not in written:
            left += 1

    return left
