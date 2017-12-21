def _decode(message):
    message.replace(chr(31), '|').replace(chr(30), '+')
    if not isinstance(message, unicode) and isinstance(message, str):
        message = message.decode('utf-8')
    message = message.replace(chr(31), '|').replace(chr(30), '+')
    return message


def _encode(message):
    if isinstance(message, unicode):
        message = message.encode('utf-8')
    return message.replace('|', chr(31)).replace('+', chr(30))

def msg(message):
    return _encode(message)