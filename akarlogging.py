#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# My lib for logging
#
# alexeykr@gmail.com
# coding=utf-8
# import codecs
"""
Classes for logging
version: 1.0
@author: alexeykr@gmail.com
"""

import coloredlogs
import warnings
import logging
from rich.logging import RichHandler


class AkarLoggingRich:
    """
    For logging configuration
    """

    def __init__(self, log_name, level=logging.WARNING):
        self.__logging_level = level
        self.__logging_name = log_name
        # FORMAT = '%(name)-20s: %(funcName)-30s - %(levelname)-6s - %(message)s'
        FORMAT = "%(funcName)-20s - %(message)s"
        # FORMAT = "%(message)s"
        logging.basicConfig(level=level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler(markup=True)])
        self.__logger = logging.getLogger(self.__logging_name)

        # self.__logger.propagate = False

    def get_logger(self):
        return self.__logger

    # def info(self, msg):
    #     self.__logger.info(f'[magenta]{msg}')

    # def warn(self, msg):
    #     self.__logger.warning(f'[yellow]{msg}')

    # def error(self, msg):
    #     self.__logger.error(f'[green]{msg}')

    # def debug(self, msg):
    #     self.__logger.debug(f'[blue]{msg}')


class AkarLogging:
    """
    For logging configuration
    """

    def __init__(self, level, log_name):
        self.__logging_level = level
        self.__logging_name = log_name

    def get_color_logger(self):
        logger = logging.getLogger(self.__logging_name)
        logger.setLevel(self.__logging_level)
        coloredlogs.install(level=self.__logging_level, logger=logger, fmt='%(name)-20s: %(funcName)-30s - %(levelname)-6s - %(message)s')

        logger.propagate = False

        return logger
