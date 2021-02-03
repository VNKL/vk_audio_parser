""" Use Python 3.7 """

import models.vk.utils as utils


VK_API_VERSION = 5.96
NEW_RELEASES_BLOCK_ID = 'PUlYRhcOWlJqSVhBFw5JBScfCBpaU0kb'
CHART_BLOCK_ID = 'PUlYRhcOWFVqSVhBFw5JBScfCBpaU0kb'


class AudioSaversParser:

    def __init__(self, token, rucaptcha_key, proxy=None):
        self.token = token
        self.rucaptcha_key = rucaptcha_key
        self.proxy = proxy

    def _api_response(self, method, params=None):
        """
        Возвращает ответ от API ВК (None - если ошибка)

        :param method:  str, название метода API ВК
        :param params:  dict, параметры метода
        :return:        dict, разобранный из JSON ответ апи ВК (None - если ошибка)
        """
        url = f'https://api.vk.com/method/{method}'
        if params:
            params.update({'access_token': self.token, 'v': VK_API_VERSION})
        else:
            params = {'access_token': self.token, 'v': VK_API_VERSION}
        return utils.get_api_response(url=url, data=params, rucaptcha_key=self.rucaptcha_key, proxy=self.proxy)

    def get_by_artist_url(self, artist_card_url: str, count_only: bool):
        audios = []
        artist_id = artist_card_url.replace('https://vk.com/artist/', '')

        resp = self._api_response('catalog.getAudioArtist', {'artist_id': artist_id, 'need_blocks': 1})
        if resp:
            artist_name = resp['artists'][0]['name']
            audios.extend(resp['audios'])
            audios.extend(self._search_audios(artist_name, performer_only=1))

        if audios:
            audios = utils.clean_audio_repeats(audios)
            return self._iter_get_audios_savers(audios, count_only)

    def get_by_track_name(self, track_name: str, count_only: bool):
        search_results = self._search_audios(track_name, performer_only=0)
        audios = utils.match_search_results(search_results, track_name)
        if audios:
            return self._iter_get_audios_savers(audios, count_only)

    def get_by_group(self, group, count_only):
        audios = []

        group_id = self._get_group_id(group)
        if group_id:
            group_params = {'owner_id': f'-{group_id}'}
            audios.extend(self._offsets_get_audios_from_list(group_params))

        if audios:
            return self._iter_get_audios_savers(audios, count_only)

    def get_by_playlist(self, playlist_url, count_only):
        audios = []

        playlist_params = utils.pars_playlist_url(playlist_url)
        if playlist_params:
            audios.extend(self._offsets_get_audios_from_list(playlist_params))

        if audios:
            return self._iter_get_audios_savers(audios, count_only)

    def get_by_chart(self, count_only):
        audios = self._get_block_audios(CHART_BLOCK_ID)
        if audios:
            return self._iter_get_audios_savers(audios, count_only)

    def get_by_new_releases(self, count_only):
        audios = self._get_block_audios(NEW_RELEASES_BLOCK_ID)
        if audios:
            return self._iter_get_audios_savers(audios, count_only)

    def get_by_newsfeed(self, q, count_only):
        posts = self._get_newsfeed_posts(q)
        audios = utils.iter_get_audios_from_posts(posts)
        audios = utils.match_search_results(audios, q)
        if audios:
            return self._iter_get_audios_savers(audios, count_only)

    def get_by_post(self, post_url, count_only):
        post_id = utils.pars_post_id_from_post_url(post_url)
        if post_id:
            post = self._get_post(post_id)
            audios = utils.get_audios_from_post(post)
            if audios:
                return self._iter_get_audios_savers(audios, count_only)

    def _get_block_audios(self, block_id):
        audios = []
        next_from = None
        i = 0
        while True:
            resp = self._get_block_response(block_id, next_from)
            if resp:
                for n, audio in enumerate(resp['block']['audios']):
                    if block_id == CHART_BLOCK_ID:
                        chart_position = n + i * 20 + 1
                        audio['chart_position'] = chart_position
                    audios.append(audio)
                if 'next_from' in resp['block']:
                    next_from = resp['block']['next_from']
                    i += 1
                else:
                    break
        return audios

    def _get_block_response(self, block_id, next_from=None):
        api_method_params = {'block_id': block_id, 'start_from': next_from, 'extended': 1}
        return self._api_response('audio.getCatalogBlockById', api_method_params)

    def _offsets_get_audios_from_list(self, method_params_dict):
        count = 0
        audios = []
        resp = self._api_response('audio.get', method_params_dict)
        if resp and 'items' in resp.keys() and 'count' in resp.keys():
            audios.extend(resp['items'])
            count = resp['count']

        if count > 200:
            for offset in range(200, count, 200):
                params = method_params_dict.copy()
                params['offset'] = offset
                offset_resp = self._api_response('audio.get', params)
                if offset_resp:
                    audios.extend(offset_resp['items'])

        return audios

    def _iter_get_audios_savers(self, audios, count_only):
        if count_only:
            return self._get_savers_count(audios)

        audios_with_savers = []
        for n, audio in enumerate(audios):
            audio_savers = self._get_audio_savers(audio['owner_id'], audio['id'])
            if isinstance(audio_savers, list):
                audios_with_savers.append(utils.zip_audio_obj_and_savers(audio, audio_savers))
            print(f'{n+1} / {len(audios)}')
        return audios_with_savers

    def _get_savers_count(self, audios):
        audio_batches = []
        for x in range(0, len(audios), 25):
            y = x + 25 if x + 25 <= len(audios) else None
            audio_batches.append(audios[x:y])

        audios_with_savers_count = []
        for batch in audio_batches:
            code = utils.code_for_get_savers_count(batch)
            execute_resp = self._api_response('execute', {'code': code})
            if execute_resp:
                audios_with_savers_count.extend(utils.iter_zip_audio_obj_and_savers(batch, execute_resp))

        return audios_with_savers_count

    def _get_audio_savers(self, owner_id, audio_id):
        params = {'type': 'audio', 'owner_id': owner_id, 'item_id': audio_id, 'count': 1}
        resp = self._api_response('likes.getList', params)
        if resp and 'count' in resp.keys():
            return self._offsets_get_audio_savers(owner_id, audio_id, resp['count'])

    def _offsets_get_audio_savers(self, owner_id, audio_id, count):
        offsets_list = list(range(0, count, 1000))
        offsets_batches = []
        for x in range(0, len(offsets_list), 25):
            y = x + 25 if x + 25 <= len(offsets_list) else None
            offsets_batches.append(offsets_list[x:y])

        savers = []
        for offsets_batch in offsets_batches:
            code = utils.code_for_iter_get_audio_savers(owner_id, audio_id, offsets_batch)
            execute_resp = self._api_response('execute', {'code': code})
            if execute_resp:
                savers.extend(utils.unpack_execute_response_with_audio_savers(execute_resp))

        return savers

    def _search_audios(self, q, performer_only: int):
        responses = []
        for sort in [0, 2]:
            params = {'q': q, 'performer_only': performer_only, 'count': 300, 'sort': sort}
            responses.append(self._api_response('audio.search', params))

        audios = []
        for resp in responses:
            if resp and 'items' in resp.keys():
                audios.extend(resp['items'])

        return audios

    def _get_group_id(self, group):
        group_id = None

        if isinstance(group, int):
            group_id = group

        elif isinstance(group, str):
            if 'https://vk.com/public' in group:
                group_id = group.replace('https://vk.com/public', '')
            elif 'https://vk.com/' in group:
                group_id = group.replace('https://vk.com/', '')

        if group_id:
            resp = self._api_response('groups.getById', {'group_id': group_id, 'fields': 'counters'})
            if resp and resp[0]['counters']['audios']:
                return resp[0]['id']

    def _get_newsfeed_posts(self, q):
        posts = []
        next_from = None
        for _ in range(4):
            resp = self._api_response('newsfeed.search', {'q': q, 'attach': 3, 'count': 200, 'start_from': next_from})
            if resp and 'items' in resp.keys():
                posts.extend(resp['items'])
            if resp and 'next_from' in resp.keys():
                next_from = resp['next_from']
        return posts

    def _get_post(self, post_id):
        resp = self._api_response('wall.getById', {'posts': post_id})
        if resp:
            return resp[0]
