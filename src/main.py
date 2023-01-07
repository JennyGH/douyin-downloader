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


def _get_video_id(share_url):
    response = requests.get(url=share_url, headers=headers)
    video_id = os.path.basename(os.path.dirname(response.url))
    return video_id


def _get_video_real_url_by_id_v1(video_id):
    # https://v.douyin.com/LYDLoga/
    log_debug(f'video_id: {video_id}')
    api_url = f'https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}'
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


def _get_video_real_url_by_id_v2(video_id):
    log_debug(f'video_id: {video_id}')
    api_url = f'https://www.iesdouyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}'
    log_debug(f'api_url: {api_url}')
    response = requests.get(url=api_url, headers=headers)
    text = response.content.decode('utf-8')
    log_debug(f'response: {text}')
    response = json.loads(text)
    if 'aweme_detail' not in response:
        log_error('No `aweme_detail` in response')
        return _make_fail_result('Bad response.')
    aweme_detail = response['aweme_detail']
    if len(aweme_detail) == 0:
        log_error('No element in response.aweme_detail')
        return _make_fail_result('Bad response.')

    urls = []

    if 'video' not in aweme_detail:
        log_error(f'No `video` in {json.dumps(aweme_detail)}')
        return _make_success_result(urls)
    video = aweme_detail['video']

    if 'download_addr' in video:
        addr = video['download_addr']
    elif 'play_addr' in video:
        addr = video['play_addr']
    else:
        log_error(f'No `download_addr` or `play_addr` in {json.dumps(video)}')
        return _make_success_result(urls)

    if 'url_list' not in addr:
        log_error(f'No `url_list` in {json.dumps(addr)}')
        return _make_success_result(urls)

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
            share_url = query['url']
            video_id = ''
            try:
                video_id = _get_video_id(share_url)
            except Exception as ex:
                http_status = 500
                response = _make_fail_result(
                    f'Unable to get video id from share url, because: {ex}')

            try:
                response = _get_video_real_url_by_id_v1(video_id)
            except:
                try:
                    response = _get_video_real_url_by_id_v2(video_id)
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
