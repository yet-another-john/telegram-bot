import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
    except Exception as error:
        logger.error(f'Сообщение не удалось отправить: {error}')
    else:
        logger.debug(f'Отправлено сообщение: {message}')


def get_api_answer(timestamp):
    """Запрос к API сервиса."""
    params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    try:
        response = requests.get(**params)
        if response.status_code != HTTPStatus.OK:
            raise exceptions.APIResponseStatusCodeException(
                f'Ошибка. Код ответа (API): {response.status_code}'
            )
    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе к API: {error}')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not response:
        message = "В ответе пришел пустой словарь."
        logging.error(message)
        raise KeyError(message)
    if not isinstance(response, dict):
        message = 'Тип ответа не соответствует "dict".'
        logging.error(message)
        raise TypeError(message)
    if "homeworks" not in response:
        message = 'В ответе отсутствует ключ "homeworks".'
        logging.error(message)
        raise KeyError(message)
    if not isinstance(response.get("homeworks"), list):
        message = "Формат ответа не соответствует списку."
        logging.error(message)
        raise TypeError(message)
    return response.get("homeworks")


def parse_status(homework):
    """Проверка статуса домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        message = f'Неизвестный статус работы: {homework_status}'
        logger.error(message)
        raise exceptions.UnknownStatusException(message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}": {verdict}'


def main():
    """Основная логика работы."""
    if not check_tokens():
        logger.critical("Отсутствуют токены. Программа остановлена")
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    error = ''
    homework = {}
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0:
                current_homework = homeworks[0]
                if homework != current_homework:
                    current_homework_status = parse_status(current_homework)
                    homework = current_homework
                    send_message(bot, current_homework_status)
                else:
                    logger.debug(
                        "Отсутствуют изменения статуса последней работы"
                    )
        except Exception as current_error:
            message = f'Сбой в работе программы: {current_error}'
            if str(current_error) != str(error):
                send_message(bot, message)
                error = current_error
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s [in %(pathname)s:%(lineno)d]'
    )
    rotationHandler = RotatingFileHandler(
        'log.txt',
        maxBytes=50000000,
        backupCount=5,
        encoding='UTF-8',
    )
    streamHandler = logging.StreamHandler(sys.stdout)
    rotationHandler.setFormatter(formatter)
    streamHandler.setFormatter(formatter)
    logger.addHandler(rotationHandler)
    logger.addHandler(streamHandler)
    main()
