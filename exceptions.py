class SendMessageFailure(Exception):
    """Ошибка отправки сообщения."""

    pass


class APIResponseStatusCodeException(Exception):
    """Неверный код ответа API."""

    pass


class UnknownStatusException(Exception):
    """Неизвестный статус."""

    pass
