import logging
import time
import os


class Logger(object):
    def __init__(self, root_dir, topic, level=logging.INFO, when='D',
                 fmt='%(asctime)s - %(levelname)s: %(message)s'):
        self.logger = logging.getLogger(topic)
        format_str = logging.Formatter(fmt)
        self.logger.setLevel(level)
        sh = logging.StreamHandler()
        sh.setFormatter(format_str)
        fh = logging.FileHandler(filename=os.path.join(root_dir, 'logs', f'{topic}.log'))
        fh.setFormatter(format_str)
        self.logger.addHandler(sh)
        self.logger.addHandler(fh)

    def debug(self, *args, **kwargs):
        self.logger.debug(*args, **kwargs)

    def info(self, *args, **kwargs):
        self.logger.info(*args, **kwargs)

    def warning(self, *args, **kwargs):
        self.logger.warning(*args, **kwargs)

    def error(self, *args, **kwargs):
        self.logger.error(*args, **kwargs)

    def critical(self, *args, **kwargs):
        self.logger.critical(*args, **kwargs)
