# coding:utf-8
import base64
import os
import sys
import json
import requests
from urllib.parse import parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler

headers = {
    'user-agent':
    r'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1 Edg/97.0.4692.99'
}

units = ['B', 'KB', 'MB', 'GB']


def log_debug(content):
    print(f'[DEBUG] {content}')


def log_error(content):
    print(f'[ERROR] {content}')


def _make_result(status, content):
    return json.dumps({'status': status, 'content': content})


def _make_success_result(content):
    return _make_result(0, content)


def _make_fail_result(errmsg):
    return _make_result(-1, errmsg)


def _get_video_id(share_url):
    response = requests.get(url=share_url, headers=headers)
    video_id = os.path.basename(os.path.dirname(response.url))
    return video_id


def _to_friendly_size_string(size, unit_index=0):
    if size < 1024:
        return '%.2f' % size + units[unit_index]
    return _to_friendly_size_string(size / 1024, unit_index + 1)


def _download_video_from(url):
    response = requests.get(url=url, headers=headers)
    if None != response.content and len(response.content) > 0:
        log_debug(
            f'Downloaded video from `{url}`, video size: {_to_friendly_size_string(len(response.content))}'
        )
    return response.content


def _get_video_real_urls_by_id_v1(video_id):
    # https://v.douyin.com/LYDLoga/
    log_debug(f'video_id: {video_id}')
    api_url = f'https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}'
    log_debug(f'api_url: {api_url}')
    response = requests.get(url=api_url, headers=headers)
    text = response.content.decode('utf-8')
    if len(text) == 0:
        log_error(f'No response from `{api_url}`')
    else:
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

    return urls


def _get_video_real_urls_by_id_v2(video_id):
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

    return urls


def fix_base64_encode_padding(data):
    missing_padding = 4 - len(data) % 4
    if missing_padding:
        data += b'=' * missing_padding
    return data


class Resquest(BaseHTTPRequestHandler):
    def do_GET(self):
        log_debug('==========================================================')
        log_debug(f'Request path: {self.path}')

        query_string = urlparse(self.path).query
        log_debug(f'Query string: {query_string}')
        if len(query_string) == 0:
            self.send_client_fail_response(f"Bad uri")

        query = parse_qs(query_string)

        download_video_directly = ('download_video_directly' in query) and (
            len(query['download_video_directly']) > 0) and (int(
                query['download_video_directly'][0]) == 1)
        log_debug(f'download_video_directly: {download_video_directly}')

        if ('url' not in query) or len(query['url']) <= 0:
            self.send_client_fail_response(f"Bad query: {self.path}")
            return

        # Decode share url from base64.
        share_url_base64 = fix_base64_encode_padding(
            query['url'][0].encode("utf-8"))
        share_url = str(base64.b64decode(share_url_base64), 'utf-8')
        log_debug(f'share_url: {share_url}')

        # Try to get video id from share url.
        video_id = ''
        try:
            video_id = _get_video_id(share_url)
        except Exception as ex:
            self.send_server_fail_response(
                f'Unable to get video id from share url, because: {ex}')
            return

        # Try to get video download urls from video id.
        urls = []
        try:
            urls = _get_video_real_urls_by_id_v1(video_id)
        except:
            try:
                urls = _get_video_real_urls_by_id_v2(video_id)
            except Exception as ex:
                self.send_server_fail_response(
                    f'Unable to get the download url of douyin video, because: {ex}'
                )
                return

        if download_video_directly:
            video_size = 0
            video_bytes = b''
            if len(urls) > 0:
                for url in urls:
                    video_bytes = _download_video_from(url)
                    if None == video_bytes:
                        continue
                    video_size = len(video_bytes)
                    if video_size > 0:
                        break

            if None != video_bytes and video_size > 0:
                # Base encode video bytes.
                video_base64 = str(base64.b64encode(video_bytes), 'utf-8')
                self.send_success_response(video_base64)
        else:
            self.send_success_response(urls)

    def send_fail_response(self, code, message):
        response = _make_fail_result(message)
        self.send_response(code)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(bytes(response, encoding="utf-8"))
        pass

    def send_success_response(self, message):
        response = _make_success_result(message)
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(bytes(response, encoding="utf-8"))
        pass

    def send_client_fail_response(self, message):
        self.send_fail_response(400, message)
        pass

    def send_server_fail_response(self, message):
        self.send_fail_response(500, message)
        pass


if __name__ == "__main__":
    port = 8080
    argv = sys.argv
    if len(argv) > 1:
        port = int(argv[1])
    host = ('0.0.0.0', port)
    server = HTTPServer(host, Resquest)
    log_debug("Server started, listen at: %s:%s" % host)
    server.serve_forever()
