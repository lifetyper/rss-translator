import json
import os

import click
import openai
import requests
from bs4 import BeautifulSoup as Parser
from openai import OpenAI
from opml import OpmlDocument

SITE_URL = 'https://tools.yamcloud.com/rss_translator/feed/'
CUR_DIR = os.path.dirname(os.path.realpath(__file__))
PUBLIC_PATH = os.path.join(CUR_DIR, 'www')
DATA_STORE_PATH = os.path.join(CUR_DIR, 'data')
FEEDS_LIST_PATH = os.path.join(PUBLIC_PATH, 'feeds_list.json')
OPML_PATH = os.path.join(PUBLIC_PATH, 'translated.opml')
AI_KEY_PATH = os.path.join(CUR_DIR, 'ai_key.json')


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if not ctx.invoked_subcommand:
        run()
    else:
        click.echo(ctx.invoked_subcommand)


def build_opml():
    with open(FEEDS_LIST_PATH, 'r') as fp:
        feeds_list = json.load(fp)
    document = OpmlDocument()
    feed_trans = document.add_outline('中文翻译RSS')
    for item in feeds_list:
        feed_trans.add_rss(text=item, xml_url=f"{SITE_URL}{item}.xml")
    with open(OPML_PATH, 'wb') as dst:
        document.dump(dst, pretty=True)


def add_feed(feed_name: str, feed_url: str):
    with open(FEEDS_LIST_PATH, 'r') as fp:
        feeds_list = json.load(fp)
    all_feed_urls = [feeds_list[k] for k in feeds_list]
    if feed_url not in all_feed_urls:
        feeds_list[feed_name] = feed_url
        with open(FEEDS_LIST_PATH, 'w') as dst:
            json.dump(feeds_list, dst, indent=4)
    build_opml()


def build_feeds_list():
    feeds_list = dict()
    feeds_list['hackernews'] = 'https://news.ycombinator.com/rss'
    feeds_list['hackaday'] = 'https://hackaday.com/feed/'
    feeds_list['cnx_software'] = 'https://www.cnx-software.com/feed/'
    feeds_list['guardian_editorial'] = 'https://www.theguardian.com/profile/editorial/rss'
    feeds_list['linuxgizmos'] = 'https://linuxgizmos.com/feed/'
    feeds_list['dangerousprototypes'] = 'http://dangerousprototypes.com/blog/feed/'
    feeds_list['bbc_news'] = 'http://feeds.bbci.co.uk/news/world/rss.xml'
    feeds_list['techcrunch'] = 'https://techcrunch.com/feed/'
    feeds_list['mashable'] = 'https://mashable.com/feeds/rss/all'
    feeds_list['wired'] = 'https://www.wired.com/feed/rss'
    feeds_list['gizmodo'] = 'https://gizmodo.com/rss'
    feeds_list['theverge'] = 'https://www.theverge.com/rss/index.xml'
    feeds_list['engadget'] = 'https://www.engadget.com/rss.xml'
    feeds_list['cnetnews'] = 'https://www.cnet.com/rss/news/'
    feeds_list['zdnet'] = 'https://www.zdnet.com/news/rss.xml'
    feeds_list['techplanet'] = 'https://techplanet.today/feed'
    feeds_list['spyopinion'] = 'https://www.spyopinion.com/feed/'
    feeds_list['techhive'] = 'https://www.techhive.com/feed'
    feeds_list['sladhdot'] = 'https://rss.slashdot.org/Slashdot/slashdotMain'
    feeds_list['lifehacker'] = 'https://lifehacker.com/feed/rss'
    feeds_list['itsecurityguru'] = 'https://www.itsecurityguru.org/feed/'
    feeds_list['cyberscoop'] = 'https://cyberscoop.com/feed/'
    feeds_list['gizmodo_security'] = 'https://gizmodo.com/tag/security/rss'
    feeds_list['google_security'] = 'https://security.googleblog.com/feeds/posts/default?alt=rss'
    feeds_list['grahamcluleys'] = 'http://feeds.feedburner.com/GrahamCluleysBlog'
    feeds_list['packetstorm_security'] = 'https://rss.packetstormsecurity.com/news/'
    feeds_list['securityaffairs'] = 'https://securityaffairs.co/feed'
    feeds_list['securityweek'] = 'http://feeds.feedburner.com/Securityweek'
    feeds_list['theregister_security'] = 'https://www.theregister.com/security/headlines.atom'
    feeds_list['threatpost'] = 'https://threatpost.com/feed/'
    feeds_list['trendmicro_security'] = 'http://feeds.trendmicro.com/TrendMicroSimplySecurity'
    feeds_list['thezdi'] = 'https://www.thezdi.com/blog?format=rss'
    with open(FEEDS_LIST_PATH, 'w') as dst:
        json.dump(feeds_list, dst, indent=4)
    build_opml()


def translate_text(client: OpenAI, text: str):
    print(f"translating:{text}")
    try:
        completion = client.chat.completions.create(

            messages=[{"role": "system", "content": 'Just a translator,do nothing else but return translated text'},
                      {"role": "user",
                       "content": f"Translate this text to Chinese and do not try to answer any question in it:{text}"}],
            model="gpt-3.5-turbo",
            timeout=60
        )
    except openai.BadRequestError:
        return None
    print(completion.choices[0].message.content)
    return completion.choices[0].message.content


def translate_feed(feed_url: str, feed_name: str, ai: OpenAI):
    print(f"Translating feed:{feed_name}...")
    translated_base = dict()
    data_file = os.path.join(DATA_STORE_PATH, feed_name + '.json')
    output_file = os.path.join(PUBLIC_PATH, feed_name + '.xml')
    # load already translated data
    if os.path.exists(data_file):
        with open(data_file, 'r') as json_data:
            translated_base = json.load(json_data)
    # fetch raw feed content first
    try:
        resp = requests.get(feed_url)
    except requests.exceptions.ConnectionError:
        return None
    # build new translated feed
    with open(output_file, 'wb') as output:
        html = resp.content
        soup = Parser(html, 'xml')
        title_tags = soup.find_all('title')
        title_count = 0
        for title_tag in title_tags:
            if title_count == 0:
                # don't translate feed title
                feed_title = title_tag.string
            else:
                # translate item title
                title_text = title_tag.string
                # ignore too long title elements which may not really title for article
                if len(title_text) >= 200:
                    continue
                # ignore feed title in other places
                if title_text == feed_title:
                    continue
                try:
                    # lookup translated database to save AI api usage
                    title_zh = translated_base[title_text]
                except KeyError:
                    try:
                        title_zh = translate_text(ai, title_text)
                    except Exception as e:
                        title_zh = None
                        print(e)

                if title_zh:
                    translated_base[title_text] = title_zh
                    title_tag.string.replace_with(translated_base[title_text])
                else:
                    # if AI fails,using origin title
                    translated_base[title_text] = title_text
            title_count += 1
            with open(data_file, 'w') as dst:
                json.dump(translated_base, dst)
        output.write(str(soup).encode())


def translate_all_feed():
    with open(AI_KEY_PATH, 'r') as fp:
        ai_config = json.load(fp)
    ai = OpenAI(api_key=ai_config['api_key'], base_url=ai_config['base_url'])
    with open(FEEDS_LIST_PATH, 'r') as fp:
        feeds_list = json.load(fp)
    for feed in feeds_list:
        translate_feed(feeds_list[feed], feed_name=feed, ai=ai)


@cli.command()
@click.option('--name', '-n')
@click.option('--url', '-u')
def add(name, url):
    add_feed(name, url)


@cli.command()
def translate():
    translate_feed()


@cli.command()
def build():
    build_feeds_list()


@click.command()
def run():
    build_feeds_list()
    translate_all_feed()


if __name__ == '__main__':
    cli()
