#!/usr/bin/python3

import os
import json
import asyncio
import schedule
import pyfiglet
import argparse
import datetime
import listparser
import feedparser
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from openpyxl import Workbook

from bot import *
from utils import *

import requests
requests.packages.urllib3.disable_warnings()

today = datetime.datetime.now().strftime("%Y-%m-%d")

def update_today(data: list=[]):
    """更新today"""
    root_path = Path(__file__).absolute().parent
    data_path = root_path.joinpath('temp_data.json')
    today_path = root_path.joinpath('today.md')

    if not data and data_path.exists():
        with open(data_path, 'r') as f1:
            data = json.load(f1)

    with open(today_path, 'a') as f1:
        content = ''
        for item in data:
            (feed, value), = item.items()
            content += f'- {feed}\n'
            for title, url in value.items():
                content += f'  - [{title}]({url})\n'
        f1.write(content)

def update_today_exl(data: list=[]):
    """更新today，保存到Excel文件"""
    root_path = Path(__file__).absolute().parent
    excel_path = root_path.joinpath('today.xlsx')

    # 创建一个新的Excel工作簿
    wb = Workbook()
    ws = wb.active
    ws.append(['id', 'title', 'link', 'summary', 'image_url', 'likes', 'author', 'created_at', 'comments'])

    for item in data:
        for feed, articles in item.items():
            for article in articles:
                ws.append([
                    article['uuid'],
                    article['title'],
                    article['link'],
                    article['summary'],
                    article.get('cover', ''),
                    0,  # likes
                    article['author'],  # author
                    today,  # created_at
                    0,  # comments
                ])

    # 保存Excel文件
    wb.save(excel_path)

def update_rss(rss: dict, proxy_url=''):
    """更新订阅源文件"""
    proxy = {'http': proxy_url, 'https': proxy_url} if proxy_url else {'http': None, 'https': None}

    (key, value), = rss.items()
    rss_path = root_path.joinpath(f'rss/{value["filename"]}')

    result = None
    if url := value.get('url'):
        r = requests.get(value['url'], proxies=proxy)
        if r.status_code == 200:
            with open(rss_path, 'w+') as f:
                f.write(r.text)
            print(f'[+] 更新完成：{key}')
            result = {key: rss_path}
        elif rss_path.exists():
            print(f'[-] 更新失败，使用旧文件：{key}')
            result = {key: rss_path}
        else:
            print(f'[-] 更新失败，跳过：{key}')
    else:
        print(f'[+] 本地文件：{key}')

    return result


def parseThread(conf: dict, url: str, proxy_url=''):
    """获取文章线程"""

    def filter(title: str, summary: str):
        if url.startswith('https://pyrsshub.vercel.app'):
            return True
        """过滤文章"""
        # 读取today.md文件
        today_md_path = root_path.joinpath('today.md')
        if today_md_path.exists():
            with open(today_md_path, 'r') as f:
                today_md_content = f.read()
        else:
            today_md_content = ""

        # 检查标题是否在today.md文件中
        if title in today_md_content:
            return False  # 如果标题已存在，过滤掉

        # 原有的过滤逻辑
        for i in conf['include']:
            if i in title or i in summary:
                return True
        return False

    proxy = {'http': proxy_url, 'https': proxy_url} if proxy_url else {'http': None, 'https': None}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

    title = ''
    result = []
    try:
        if url.startswith("https://svc-drcn.developer.huawei.com"):
            # 请求的参数
            payload = {
                "pageSize": 24,
                "pageIndex": 1,
                "type": 2
            }
            title = '鸿蒙官网'
            # 发送POST请求
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                # 打印返回的JSON数据item["blogId"]
                for entry in response.json()["resultList"]:
                    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d%H%M%S")
                    if (entry['publishTime'] >= yesterday) and filter(entry['title'] + "鸿蒙", entry['previewContent']):
                        current_time_uuid = str(uuid.uuid1())
                        upload_info_list = entry.get('uploadInfoList', [])
                        cover = upload_info_list[0]['filePath'] if upload_info_list else ''
                        item = {
                            'uuid': current_time_uuid,
                            'title': entry['title'],
                            'link': f"https://developer.huawei.com/consumer/cn/blog/topic/{entry['blogId']}",
                            'summary': entry['previewContent'],
                            'cover': cover,
                            'author':  title,
                        }

                        print(item)
                        result.append(item)
            else:
                print(f"请求失败，状态码：{response.status_code}")

        else:
            r = requests.get(url, timeout=60, headers=headers, verify=False, proxies=proxy)
            r = feedparser.parse(r.content)
            title = r.feed.title
            if '掘金 Android' in title:
                title = '掘金社区'
            if '应用开发-鸿蒙开发者社区-51CTO.COM' in title:
                title = '51CTO'
            if 'OSCHINA 社区最新新闻' in title:
                title = '开源中国'
            if 'harmony · GitHub Topics · GitHub' in title:
                title = 'GitHub'
            if '博客园_首页' in title:
                title = '博客园'
            if '鸿蒙之家' in title:
                title = '鸿蒙IT之家'
            if '鸿蒙新闻中心' in title:
                title = '鸿蒙新闻中心'
            if 'Gitee Recommened Projects' in title:
                title = '鸿蒙开源工程更新'
            for entry in r.entries:
                if url.startswith('https://pyrsshub.vercel.app'):
                    dstr = entry.get('published') or entry.get('updated')
                    if dstr:
                        if dstr:
                            dstr = datetime.datetime.fromtimestamp(int(dstr)).date()
                    pubday = datetime.date(dstr.year, dstr.month, dstr.day)
                else:
                    dstr = entry.get('published_parsed') or entry.get('updated_parsed')
                    pubday = datetime.date(dstr[0], dstr[1], dstr[2])


                yesterday = datetime.date.today() + datetime.timedelta(-1)
                if (pubday >= yesterday) and filter(entry.title, entry.summary):
                    item = {
                        'uuid': str(uuid.uuid1()),
                        'title': entry.title,
                        'link': entry.link,
                        'summary':  entry.summary,
                        'author':  title,
                    }
                    print(item)
                    result.append(item)
    except Exception as e:
        console.print(f'[-] failed: {url}', style='bold red')
        print(e)
    return title, result


async def init_bot(conf: dict, proxy_url=''):
    """初始化机器人"""
    bots = []
    for name, v in conf.items():
        if v['enabled']:
            key = os.getenv(v['secrets']) or v['key']

            if name == 'mail':
                receiver = os.getenv(v['secrets_receiver']) or v['receiver']
                bot = globals()[f'{name}Bot'](v['address'], key, receiver, v['from'], v['server'])
                bots.append(bot)
            elif name == 'qq':
                bot = globals()[f'{name}Bot'](v['group_id'])
                if await bot.start_server(v['qq_id'], key):
                    bots.append(bot)
            elif name == 'telegram':
                bot = globals()[f'{name}Bot'](key, v['chat_id'], proxy_url)
                if await bot.test_connect():
                    bots.append(bot)
            else:
                bot = globals()[f'{name}Bot'](key, proxy_url)
                bots.append(bot)
    return bots


def init_rss(conf: dict, update: bool=False, proxy_url=''):
    """初始化订阅源"""
    rss_list = []
    enabled = [{k: v} for k, v in conf.items() if v['enabled']]
    for rss in enabled:
        if update:
            if rss := update_rss(rss, proxy_url):
                rss_list.append(rss)
        else:
            (key, value), = rss.items()
            rss_list.append({key: root_path.joinpath(f'rss/{value["filename"]}')})

    # 合并相同链接
    feeds = []
    for rss in rss_list:
        (_, value), = rss.items()
        try:
            rss = listparser.parse(open(value).read())
            for feed in rss.feeds:
                url = feed.url.strip().rstrip('/')
                short_url = url.split('://')[-1].split('www.')[-1]
                check = [feed for feed in feeds if short_url in feed]
                if not check:
                    feeds.append(url)
        except Exception as e:
            console.print(f'[-] 解析失败：{value}', style='bold red')
            print(e)

    console.print(f'[+] {len(feeds)} feeds', style='bold yellow')
    return feeds


def cleanup():
    """结束清理"""
    qqBot.kill_server()

async def job(args):
    """定时任务"""
    print(f'{pyfiglet.figlet_format("yarb")}\n{today}')

    global root_path
    root_path = Path(__file__).absolute().parent
    if args.config:
        config_path = Path(args.config).expanduser().absolute()
    else:
        config_path = root_path.joinpath('config.json')
    with open(config_path) as f:
        conf = json.load(f)

    proxy_rss = conf['proxy']['url'] if conf['proxy']['rss'] else ''
    feeds = init_rss(conf['rss'], args.update, proxy_rss)

    results = []
    results_dict = {}

    if args.test:
        # 测试数据
        results.extend({f'test{i}': {Pattern.create(i*500): 'test'}} for i in range(1, 20))
    else:
        # 获取文章
        numb = 0
        tasks = []
        with ThreadPoolExecutor(100) as executor:
            tasks.extend(executor.submit(parseThread, conf['keywords'], url, proxy_rss) for url in feeds)
            for task in as_completed(tasks):
                title, result = task.result()
                if result:
                    numb += len(result)
                    # 检查标题是否已经存在于results_dict中
                    if title in results_dict:
                        # 如果存在，合并结果
                        results_dict[title].extend(result)
                    else:
                        # 如果不存在，添加新的键值对
                        results_dict[title] = result

        # 将results_dict转换为列表形式，以符合之前的代码逻辑
        results = [{title: result} for title, result in results_dict.items()]

        console.print(f'[+] {len(results)} feeds, {numb} articles', style='bold yellow')

        # temp_path = root_path.joinpath('temp_data.json')
        # with open(temp_path, 'w+') as f:
        #     f.write(json.dumps(results, indent=4, ensure_ascii=False))
        #     console.print(f'[+] temp data: {temp_path}', style='bold yellow')

        # 更新today
        results2 = []
        for title, articles in results_dict.items():
            item = {article['title']: article['link'] for article in articles}
            feed_dict = {title: item}
            results2.append(feed_dict)

        # 更新today
        update_today(results2)

        update_today_exl(results)

    # 推送文章
    proxy_bot = conf['proxy']['url'] if conf['proxy']['bot'] else ''
    bots = await init_bot(conf['bot'], proxy_bot)
    for bot in bots:
        await bot.send(bot.parse_results(results2))

    cleanup()

def argument():
    parser = argparse.ArgumentParser()
    parser.add_argument('--update', help='Update RSS config file', action='store_true', required=False)
    parser.add_argument('--cron', help='Execute scheduled tasks every day (eg:"11:00")', type=str, required=False)
    parser.add_argument('--config', help='Use specified config file', type=str, required=False)
    parser.add_argument('--test', help='Test bot', action='store_true', required=False)
    return parser.parse_args()

async def main():
    args = argument()
    if args.cron:
        schedule.every().day.at(args.cron).do(job, args)
        while True:
            schedule.run_pending()
            await asyncio.sleep(1)
    else:
        await job(args)

if __name__ == '__main__':
    asyncio.run(main())
