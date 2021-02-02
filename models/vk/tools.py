""" Use Python 3.7 """

import requests

from time import sleep
from random import uniform
from python_rucaptcha import ImageCaptcha


def _anticaptcha(captcha_img, rucaptcha_key):
    """
    Функция для работы с API рукапчи

    :param captcha_img:         str, ссылка на изображение капчи
    :param rucaptcha_key:       str, ключ от аккаунта на рукапче
    :return:                    str, разгаданная капча
    """
    user_answer = ImageCaptcha.ImageCaptcha(rucaptcha_key=rucaptcha_key).captcha_handler(
        captcha_link=captcha_img)
    captcha_key = user_answer['captchaSolve']

    return captcha_key


def get_api_response(url, data, rucaptcha_key, proxy=None, captcha_sid=None, captcha_key=None):
    """
    Возвращает ответ апи ВК, отбиваясь от капчи и ту мэни реквестс пер секонд

    :param url:             str, урл запроса к апи с названием метода (без параметров!!!)
    :param data:            dict, дикт с параметрами метода
    :param rucaptcha_key:   str, ключ от аккаунта на рукапче
    :param proxy:           str, прокси в виде login:pass&ip:port
    :param captcha_sid:     str, сид капчи
    :param captcha_key:     str, разгаданная капча
    :return:                dict, разобранный из JSON ответ апи ВК (None - если ошибка в ответе)
    """
    sleep(uniform(0.4, 0.6))

    if proxy:
        proxy_dict = {'https': f'https://{proxy}'}
    else:
        proxy_dict = None

    if captcha_sid and captcha_key:
        if data:
            data.update({'captcha_sid': captcha_sid, 'captcha_key': captcha_key})
        else:
            data = {'captcha_sid': captcha_sid, 'captcha_key': captcha_key}

    resp = requests.post(url, data, proxies=proxy_dict).json()

    if 'error' in resp.keys():
        if resp['error']['error_msg'] == 'Captcha needed':
            captcha_sid = resp['error']['captcha_sid']
            captcha_img = resp['error']['captcha_img']
            captcha_key = _anticaptcha(captcha_img, rucaptcha_key)
            return get_api_response(url, data, rucaptcha_key, proxy, captcha_sid, captcha_key)
        elif resp['error']['error_msg'] == 'Too many requests per second':
            sleep(uniform(0.4, 0.6))
            return get_api_response(url, data, rucaptcha_key)
        else:
            print(resp)
            return None
    else:
        return resp['response']


def pars_playlist_url(playlist_url):
    """
    Возвращает дикст с параметрами плейлиста, распарсенными из ссылки на плейлист

    :param playlist_url:    str, полная ссылка на плейлист в ВК (из "поделиться" -> "экспортировать")
    :return:                dict, {'owner_id': str, 'playlist_id': str, 'access_key': str}
    """
    owner_id, playlist_id, access_key = None, None, None
    if isinstance(playlist_url, str):
        if 'playlist' in playlist_url:
            owner_id, playlist_id, access_key = playlist_url.replace('https://vk.com/music/playlist/', '').split('_')
        elif 'album' in playlist_url:
            owner_id, playlist_id, access_key = playlist_url.replace('https://vk.com/music/album/', '').split('_')
    if owner_id:
        return {'owner_id': owner_id, 'playlist_id': playlist_id, 'access_key': access_key}


def match_search_results(search_results, track_name):
    """
    Возвращает лист объектов аудиозаписей, полученных из поиска, которые сходятся с поисковым запросом

    :param search_results:      list, лист объектов аудиозаписей ВК
    :param track_name:          str, поисковый запрос в формате "artist - title"
    :return:                    list, лист объектов аудиозаписей ВК
    """
    artist, title = track_name.split(' - ')
    matched_audios = []
    for audio in search_results:
        full_audio_title = f"{audio['title']} ({audio['subtitle']})" if 'subtitle' in audio.keys() else audio['title']
        match_check_list = [artist.lower() in audio['artist'].lower(), title.lower() in full_audio_title.lower()]
        if all(match_check_list):
            matched_audios.append(audio)
    return matched_audios


def iter_zip_audio_obj_and_savers(audios, execute_response):
    """
    Возвращает лист упрощенных объектов аудиозаписей с количеством их добавлений и,
    если переданы айди людей, которые добавили аудио, с листом айди добавивших людей

    :param audios:              list, лист объектов аудиозаписей ВК
    :param execute_response:    dict, ответ метода execute АПИ ВК
    :return:                    list, лист упрощенных и обновленных объектов аудиозаписей ВК
    """
    audios_with_savers_count = []
    for n, audio in enumerate(audios):
        savers_count = None
        if execute_response[n]:
            savers_count = execute_response[n]['count']
        zipped = zip_audio_obj_and_savers(audio, savers_count)
        audios_with_savers_count.append(zipped)
    return audios_with_savers_count


def zip_audio_obj_and_savers(audio, savers):
    """
    Вовзращает упрощенный объект аудиозаписи ВК с количеством ее добавлений и,
    если переданы айди людей, которые добавили аудио, с листом айди добавивших людей

    :param audio:       dict, объект аудиозаписи ВК
    :param savers:      list - айди добавивших аудиозапсь людей или int - их количество
    :return:            dict, упрощенный объект аудиозаписи ВК с инфой о ее добавлениях
    """
    audio_obj = {
        'owner_id': audio['owner_id'],
        'audio_id': audio['id'],
        'artist': audio['artist'],
        'title': f"{audio['title']} ({audio['subtitle']})" if 'subtitle' in audio.keys() else audio['title'],
        'date': audio['date'],
    }
    if 'chart_position' in audio.keys():
        audio_obj.update({'chart_position': audio['chart_position']})
    if isinstance(savers, list):
        audio_obj.update({'savers': savers, 'savers_count': len(savers)})
    elif isinstance(savers, int):
        audio_obj.update({'savers_count': savers})

    return audio_obj


def clean_audio_repeats(audios):
    """
    Возвращает лист объектов аудиозаписей ВК, очищенный от повторений

    :param audios:      list, лист объектов аудиозаписей ВК
    :return:            list, лист объектов аудиозаписей ВК
    """
    audio_str_list = []
    cleaned_audios = []
    for audio in audios:
        audio_str = f'{audio["owner_id"]}_{audio["id"]}'
        if audio_str not in audio_str_list:
            audio_str_list.append(audio_str)
            cleaned_audios.append(audio)
    return cleaned_audios


def code_for_iter_get_audio_savers(owner_id, audio_id, offsets_batch):
    """
    Возвращает параметр code для метода execute АПИ ВК для итерирования по аудиозаписям
    для получения айди людей, эти аудиозаписи добавивших

    :param owner_id:        int, owner_id объекта аудиозаписи ВК
    :param audio_id:        int, audio_id объекта аудиозаписи ВК
    :param offsets_batch:   list, лист с параметрами offset
    :return:                str
    """
    code = 'return ['
    for offset in offsets_batch:
        tmp = 'API.likes.getList({type: "audio", count: 1000, ' \
                                 'owner_id: ' + str(owner_id) + ', ' \
                                 'item_id: ' + str(audio_id) + ', ' \
                                 'offset: ' + str(offset) + '}), '
        code += tmp
    code = code[:-2]
    code += '];'
    return code


def code_for_get_savers_count(audios_batch):
    """
    Возвращает параметр code для метода execute АПИ ВК для итерирования по аудиозаписям
    для получения количества людей, эти аудиозаписи добавивших

    :param audios_batch:    list, лист с объектами аудиозаписей
    :return:                str
    """
    code = 'return ['
    for audio in audios_batch:
        tmp = 'API.likes.getList({type: "audio", count: 1000, ' \
                                 'owner_id: ' + str(audio["owner_id"]) + ', ' \
                                 'item_id: ' + str(audio["id"]) + ', count: 1}), '
        code += tmp
    code = code[:-2]
    code += '];'
    return code


def unpack_execute_response_with_audio_savers(execute_response):
    """
    Возвращает распакованный ответ метода execute АПИ ВК с айди людей

    :param execute_response:    list, ответ метода execute АПИ ВК
    :return:                    list, лист с айди людей
    """
    savers = []
    for x in execute_response:
        savers.extend(x['items'])
    return savers
