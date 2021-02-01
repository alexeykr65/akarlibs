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

