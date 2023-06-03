# coding:utf-8
import base64
import os
import sys
import json
import ffmpy3
import ffmpeg
import requests
from urllib.parse import parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler

headers = {
    'user-agent':
    r'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1 Edg/97.0.4692.99'
}

units = ['B', 'KB', 'MB', 'GB']

share_url_to_video_id_map = {}
video_id_to_share_url_map = {}


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
    if (share_url not in share_url_to_video_id_map) or (
            not share_url_to_video_id_map[share_url]):
        response = requests.get(url=share_url, headers=headers)
        video_id = os.path.basename(os.path.dirname(response.url))
        share_url_to_video_id_map[share_url] = video_id
        video_id_to_share_url_map[video_id] = share_url
    return share_url_to_video_id_map[share_url]


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
        raise Exception('Bad response.')
    item_list = response['item_list']
    if len(item_list) == 0:
        log_error('No element in response.item_list')
        raise Exception('Bad response.')
    for item in item_list:
        if 'video' not in item:
            log_error(f'No `video` in {json.dumps(item)}')
            continue

        video = item['video']

        cover_url = ''
        if 'origin_cover' in video:
            cover = video['origin_cover']
            if 'url_list' in cover:
                url_list = cover['url_list']
                if None != url_list and len(url_list) > 0:
                    cover_url = url_list[0]

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
        return [cover_url, url_list]
    return ['', []]


def _get_video_real_urls_by_id_v2(video_id):
    log_debug(f'video_id: {video_id}')
    api_url = f'https://www.iesdouyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}&aid=1128&version_name=23.5.0&device_platform=android&os_version=2333'
    log_debug(f'api_url: {api_url}')
    response = requests.get(url=api_url, headers=headers)
    text = response.content.decode('utf-8')
    log_debug(f'response: {text}')
    response = json.loads(text)
    if 'aweme_detail' not in response:
        log_error('No `aweme_detail` in response')
        raise Exception('Bad response.')
    aweme_detail = response['aweme_detail']
    if None == aweme_detail or len(aweme_detail) == 0:
        log_error('No element in response.aweme_detail')
        raise Exception('Bad response.')

    if 'video' not in aweme_detail:
        log_error(f'No `video` in {json.dumps(aweme_detail)}')
        return None
    video = aweme_detail['video']

    cover_url = ''
    if 'origin_cover' in video:
        cover = video['origin_cover']
        if 'url_list' in cover:
            url_list = cover['url_list']
            if None != url_list and len(url_list) > 0:
                cover_url = url_list[0]

    if 'download_addr' in video:
        addr = video['download_addr']
    elif 'play_addr' in video:
        addr = video['play_addr']
    else:
        log_error(f'No `download_addr` or `play_addr` in {json.dumps(video)}')
        return None

    if 'url_list' not in addr:
        log_error(f'No `url_list` in {json.dumps(addr)}')
        return None

    url_list = addr['url_list']

    return [cover_url, url_list]


def _get_video_real_urls_by_id_v3(video_id):
    # https://api.cooluc.com/?url=https://v.douyin.com/U8Q2CEN/
    share_url = video_id_to_share_url_map[video_id]
    api_url = f'https://api.cooluc.com/?url={share_url}'
    response = requests.get(url=api_url, headers=headers)
    text = response.content.decode('utf-8')
    log_debug(f'response: {text}')
    response = json.loads(text)
    cover_url = ''
    media_url = ''
    if 'cover' in response:
        cover_url = response['cover']
    if 'video' in response:
        media_url = response['video']
    elif 'audio' in response:
        media_url = response['audio']
    return [cover_url, [media_url]]


def _fix_base64_encode_padding(data):
    missing_padding = 4 - len(data) % 4
    if missing_padding:
        data += b'=' * missing_padding
    return data


def _is_audio(url):
    return url.endswith('.mp3') or '.mp3' in url


def _suffix_from_content_type(type):
    splited = type.split('/')
    return splited[0] if len(splited) < 2 else splited[1]


def _bytes_from_file(path):
    try:
        with open(path, 'rb') as file:
            return file.read()
    except:
        return b''


def _base64_encode_file(path):
    try:
        return str(base64.b64encode(_bytes_from_file(path)), 'utf-8')
    except:
        return ''
    return ''


def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def _ensure_cache_dir(root):
    cache_path = os.path.join(root, 'cache')
    _ensure_dir(cache_path)
    return cache_path


def _default_config():
    return {
        'output_params':
        '-preset ultrafast -tune zerolatency -c:v libx264 -pix_fmt yuv420p -c:a copy'
    }


def _ensure_config(root):
    cache_dir = _ensure_cache_dir(root)
    config_dir = os.path.join(cache_dir, 'config.json')
    if not os.path.exists(config_dir):
        with open(config_dir, mode='w', encoding='utf-8') as file:
            file.write(json.dumps(_default_config()))
    return config_dir


def _config_from(path):
    try:
        with open(path, mode='r', encoding='utf-8') as file:
            return json.loads(file.read())
    except:
        return _default_config()


def _ffmpeg_output_params_from(config):
    if None == config:
        config = _default_config()
    return config['output_params']


def _try_remove_file(path):
    try:
        os.remove(path)
        return True
    except:
        return False


def _make_video(video_id, cover_url, audio_url):
    cover_response = requests.get(url=cover_url, headers=headers)
    audio_response = requests.get(url=audio_url, headers=headers)
    cover_bytes = cover_response.content
    audio_bytes = audio_response.content
    is_valid_cover = None != cover_bytes and len(cover_bytes) > 0
    is_valid_audio = None != audio_bytes and len(audio_bytes) > 0
    if not is_valid_cover:
        raise Exception('Bad cover.')
    if not is_valid_audio:
        raise Exception('Bad audio.')
    tmp_root_path = _ensure_cache_dir('.')
    cover_content_type = cover_response.headers['content-type']
    cover_suffix = _suffix_from_content_type(cover_content_type)
    cover_save_path = os.path.join(tmp_root_path, f'{video_id}.{cover_suffix}')
    audio_save_path = os.path.join(tmp_root_path, f'{video_id}.mp3')
    video_save_path = os.path.join(tmp_root_path, f'{video_id}.mp4')
    config_path = _ensure_config('.')
    config = _config_from(config_path)
    ffmpeg_output_params = _ffmpeg_output_params_from(config)
    if not os.path.exists(cover_save_path):
        with open(cover_save_path, 'wb') as file:
            output_size = file.write(cover_bytes)
            log_debug(
                f'Saved cover to `{cover_save_path}`, size: {_to_friendly_size_string(output_size)}'
            )
    if not os.path.exists(audio_save_path):
        with open(audio_save_path, 'wb') as file:
            output_size = file.write(audio_bytes)
            log_debug(
                f'Saved audio to `{audio_save_path}`, size: {_to_friendly_size_string(output_size)}'
            )
    # ffmpeg -y -loop 1 -i cover.webp -i 7171008521526610719.mp3 -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac video.mp4
    ff = ffmpy3.FFmpeg(global_options=["-y"],
                       inputs={
                           cover_save_path: f"-loop 1 ",
                           audio_save_path: None
                       },
                       outputs={video_save_path: ffmpeg_output_params})
    log_debug(f'FFMPEG command: {ff.cmd}')
    try:
        ff.run()
        return _bytes_from_file(video_save_path)
    except Exception as ex:
        _try_remove_file(cover_save_path)
        _try_remove_file(audio_save_path)
        _try_remove_file(video_save_path)
        raise ex


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
        share_url_base64 = _fix_base64_encode_padding(
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
        cover_url = ''
        urls = []
        downloaders = [
            _get_video_real_urls_by_id_v1, _get_video_real_urls_by_id_v2,
            _get_video_real_urls_by_id_v3
        ]
        last_exception = None
        video_base64 = ''
        for downloader in downloaders:
            try:
                [cover_url, urls] = downloader(video_id)
                if download_video_directly:
                    video_base64 = self.try_download(video_id, cover_url, urls)
                    if not video_base64:
                        continue
                    else:
                        self.send_success_response(video_base64)
                        break
                else:
                    self.send_success_response(urls)
                    break
            except Exception as ex:
                last_exception = ex
                continue

        # There is no valid downloader.
        if download_video_directly and not video_base64:
            self.send_server_fail_response(
                f'Unable to get the download url of douyin video, because: {last_exception}'
            )
            return

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

    def try_download(self, video_id, cover_url, media_urls):
        if not video_id or not cover_url or len(media_urls) <= 0:
            return ''
        video_size = 0
        video_bytes = b''
        for url in media_urls:
            try:
                if _is_audio(url) and cover_url != '':
                    video_bytes = _make_video(video_id, cover_url, url)
                else:
                    video_bytes = _download_video_from(url)
            except:
                continue
            if not video_bytes:
                continue
            video_size = len(video_bytes)
            if video_size > 0:
                break
        if video_size <= 0:
            return ''
        # Base encode video bytes.
        return str(base64.b64encode(video_bytes), 'utf-8')


if __name__ == "__main__":
    port = 8080
    argv = sys.argv
    if len(argv) > 1:
        port = int(argv[1])
    host = ('0.0.0.0', port)
    server = HTTPServer(host, Resquest)
    log_debug("Server started, listen at: %s:%s" % host)
    server.serve_forever()
