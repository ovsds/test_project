import json
import logging
from datetime import datetime, timedelta

from tornado import httputil
from tornado.httpclient import AsyncHTTPClient


class Config:
    url = 'https://test.ru'
    api = '12345'


class Ziteboard:
    def __init__(self, url, key, db_lessons=None, default_lesson_id=None):
        self.url = url
        self.key = key
        self.db_lessons = db_lessons
        self.client = AsyncHTTPClient()
        self.token_expiry_in_seconds = 3600 * 24 * 365
        self.default_lesson_id = default_lesson_id

    async def req(self, method, path, params):
        url = '{}{}'.format(self.url, path)
        data = httputil.urlencode(params)
        try:
            response = await self.client.fetch(
                url,
                method=method,
                body=data,
                connect_timeout=3,
                request_timeout=10
            )
            result = json.loads(response.body)
            if result['success'] != True:
                logging.error(f'ziteboard error: {result}')
                raise Exception('ziteboard unsuccess')
        except Exception as e:
            logging.error(f'ziteboard error: {e}', exc_info=True)
            raise
        return result

    async def create_board(self):
        data = {
            'api_key': self.key,
            'token_expiry_in_seconds': self.token_expiry_in_seconds
        }
        board = (await self.req('POST', '/api/createboard', data))['board']
        return board['bid'], board['token']

    async def update_token(self, board_id):
        data = {
            'api_key': self.key,
            'token_expiry_in_seconds': self.token_expiry_in_seconds,
            'bid': board_id
        }
        board = (await self.req('POST', '/api/updateboard', data))['board']
        return board['token']

    async def view_only(self, board_id):
        data = {
            'api_key': self.key,
            'bid': board_id,
            'viewonly': 'true'
        }
        await self.req('POST', '/api/updateboard', data)

    async def get_board(self, lesson_id, create_new=True):
        try:
            lesson = await self.db_lessons.get_lesson_board_data(lesson_id)
        except self.db_lessons.NotExists:
            logging.warning('ziteboard.get_board() error: lesson %s was not found. Return default board', lesson_id)
            lesson_id = self.default_lesson_id
            lesson = await self.db_lessons.get_lesson_board_data(lesson_id)

        if not lesson['ziteboard_id'] and not create_new:
            return None, None, None
        if not lesson['ziteboard_id']:
            expires = datetime.now() + timedelta(seconds=self.token_expiry_in_seconds)
            board_id, token = await self.create_board()
            board_id, token, expires = await self.db_lessons.set_or_get_lesson_ziteboard(lesson_id, board_id, token, expires)
        elif lesson['ziteboard_id'] and lesson['ziteboard_token_expires_at'] <= datetime.now():
            board_id = lesson['ziteboard_id']
            expires = datetime.now() + timedelta(seconds=self.token_expiry_in_seconds)
            token = await self.update_token(board_id)
            old_token = lesson['ziteboard_token']
            token, expires = await self.db_lessons.set_or_get_ziteboard_token(board_id, token, expires, old_token)
        elif lesson['ziteboard_id']:
            board_id = lesson['ziteboard_id']
            token = lesson['ziteboard_token']
            expires = lesson['ziteboard_token_expires_at']
        return board_id, token, expires


async def test():
    ziteboard = Ziteboard(Config.url, Config.api)
    board = await ziteboard.create_board()
    logging.error(board)


if __name__ == '__main__':
    import asyncio
    asyncio.get_event_loop().run_until_complete(test())
