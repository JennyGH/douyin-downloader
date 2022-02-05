# coding:utf-8
import os
import json
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

host = ('', 8080)

headers = {
    'user-agent':
    r'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1 Edg/97.0.4692.99'
}


def log_debug(content):
    print(f'[DEBUG] {content}')


def log_error(content):
    print(f'[ERROR] {content}')


def _make_result(status, content):
    return json.dumps({'status': status, 'content': content})


def _make_success_result(urls):
    return _make_result(0, urls)


def _make_fail_result(errmsg):
    return _make_result(-1, errmsg)


def _get_douyin_video_url(share_url):
    # https://v.douyin.com/LYDLoga/
    response = requests.get(url=share_url, headers=headers)
    item_ids = os.path.basename(os.path.dirname(response.url))
    log_debug(f'item_ids: {item_ids}')
    api_url = f'https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={item_ids}'
    log_debug(f'api_url: {api_url}')
    response = requests.get(url=api_url, headers=headers)
    text = response.content.decode('utf-8')
    log_debug(f'response: {text}')
    response = json.loads(text)
    if 'item_list' not in response:
        log_error('No `item_list` in response')
        return _make_fail_result('Bad response.')
    item_list = response['item_list']
    if len(item_list) == 0:
        log_error('No element in response.item_list')
        return _make_fail_result('Bad response.')
    urls = []
    for item in item_list:
        if 'video' not in item:
            log_error(f'No `video` in {json.dumps(item)}')
            continue

        video = item['video']
        if 'download_addr' in video:
            addr = video['download_addr']
        elif 'play_addr' in video:
            addr = video['play_addr']
        else:
            log_error(
                f'No `download_addr` or `play_addr` in {json.dumps(video)}')
            continue
        if 'url_list' not in addr:
            log_error(f'No `url_list` in {json.dumps(addr)}')
            continue

        url_list = addr['url_list']
        for url in url_list:
            urls.append(url)

    return _make_success_result(urls)


def _parse_query(query_string):
    query = {}
    pairs = query_string.split('&')
    for pair in pairs:
        key_value = pair.split('=')
        key = key_value[0]
        value = key_value[1]
        query[key] = value
    return query


class Resquest(BaseHTTPRequestHandler):
    def do_GET(self):
        log_debug('==========================================================')

        splited = self.path.split('?')
        if len(splited) < 2:
            query = {}
        else:
            query = _parse_query(splited[1])

        http_status = 200
        response = ""
        if 'url' not in query:
            http_status = 400
            response = _make_fail_result(f"Bad uri: {self.path}")
        else:
            try:
                response = _get_douyin_video_url(query['url'])
            except Exception as ex:
                http_status = 500
                response = _make_fail_result(
                    f'Unable to get the download url of douyin video, because: {ex}'
                )
        log_debug(f'response: {response}')

        self.send_response(http_status)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(bytes(response, encoding="utf-8"))

        log_debug('==========================================================')


if __name__ == "__main__":
    server = HTTPServer(host, Resquest)
    log_debug("Starting server, listen at: %s:%s" % host)
    server.serve_forever()
