import logging

# ANSI цвета
LOG_COLORS = {
    'DEBUG': '\033[94m',     # Синий
    'INFO': '\033[92m',      # Зеленый
    'WARNING': '\033[93m',   # Желтый
    'ERROR': '\033[91m',     # Красный
    'CRITICAL': '\033[95m',  # Пурпурный
}

RESET = '\033[0m'

class ColorFormatter(logging.Formatter):
    def format(self, record):
        log_color = LOG_COLORS.get(record.levelname, '')
        message = super().format(record)
        return f"{log_color}{message}{RESET}"

def setup_logger(name: str = "mylogger") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:  # Чтобы не добавляло дубли
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColorFormatter("[%(asctime)s] [%(levelname)s] %(message)s"))
        logger.addHandler(console_handler)

    return logger