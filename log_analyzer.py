#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
from collections import namedtuple
import gzip
from pathlib import Path
import logging
import json
import re
import os

# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log"
}

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config_path', help='config path', default='default')

    return parser.parse_args()

#ToDo научиться обрбатываться None в config.log_name
def create_logger(logger_name, config, logging_level=logging.INFO):

    formatter = logging.Formatter('[%(asctime)s] %(levelname).1s  '
                                  '%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger(logger_name)
    if len(logger.handlers) > 0:
        return logger
    consoleHandler = logging.FileHandler(config.log_dir + '/log.txt')
    consoleHandler.setFormatter(formatter)
    logger.addHandler(consoleHandler)
    logger.setLevel(logging_level)

    return logger


def check_exists_config(config_path):
    pass

def check_parse_config(config_path):
    pass

def merge_config(default_config, file_config, Config):
    result = {}
    for k, v in default_config.items():
        if k in file_config:
            result[k] = file_config[k]
        else:
            result[k] = default_config[k]

    return Config(report_size=result['REPORT_SIZE'],
           report_dir=result['REPORT_DIR'],
           log_dir=result['LOG_DIR'])


def parse_log_name(name):
    pass


def find_last_log(config, LogMeta):
    re_file_name = re.compile(r'(^nginx-access-ui\.log-([0-9]+)?(\.gz)?)?$')
    file_array_it = (re_file_name.match(file).group(1) for file in os.listdir(config.log_dir) if re_file_name.match(file))
    reDate = re.compile((r'([0-9]+)'))
    last_file = sorted([x for x in file_array_it], key=lambda x: reDate.match(x.split('-')[-1]).group(1), reverse=True)[0]

    if re_file_name.match(last_file).group(3) == '.gz':
        expansion = '.gz'
    else:
        expansion = ''
    return LogMeta(path=config.log_dir + '/' + last_file, date=reDate.match(last_file.split('-')[-1]).group(1),
                                            expansion=expansion)

def get_date(file_name):
    return ''.join(file_name.split('-')[1].split('.')[:-1])


def find_last_report_date(config):
    last_report_date = ''
    try:
        dir_content = os.listdir(config.report_dir)
    except FileNotFoundError as e:
        # logging
        print(e)
        pass
    else:
        file_array_it = (get_date(file) for file in dir_content)
        last_report_date = sorted([file_date for file_date in file_array_it], reverse=True)[0]

    print('last_report_date: {}'.format(last_report_date))

    return last_report_date

def check_already_done(log_meta, config):
    last_report_date = find_last_report_date(config)
    if last_report_date == log_meta.date:
        print('report True')
        return True
    return False

def parserline(line):
    result = line
    return result

def xreadlines(log_meta, parser=parserline):
    total_lines = 0
    processed = 0
    opener = gzip.open(log_meta.path, 'rb') \
                    if log_meta.expansion == '.gz' \
                    else open(log_meta.path)
    with opener as log:
        for line in log:
            total_lines += 1
            parsed_line = parser(line)
            if parsed_line:
                processed += 1
                yield parsed_line



def cals_statistic(parser, config_meta):
    pass


def generate_report(statistic, config_meta):
    pass


def main(args, default_config):
    # проверяем конфиг, если передали в --config, то передаем его в основную процедуру, иначе используем\
    # глобальный
    Config = namedtuple('Config', ['report_size', 'report_dir', 'log_dir'])
    LogMeta = namedtuple('LogMeta', ['path', 'date', 'expansion'])

    if args.config_path != 'default':
        # проверяем, что конфиг корректный.
        # Он существует, он парсится.
        # Парсится - в нем есть нужные поля.
        # Взможно
        try:
            with open(args.config_path, 'r') as conf:
                try:
                    ext_config = json.loads(conf.read())
                    # создаем namedtuple для хранения параметрам конфига
                except json.decoder.JSONDecodeError:
                    print('Config file {} not parse'.format(args.config_path))
        except FileNotFoundError:
            print('Config file {} not found'.format(args.config_path))
    else:
        # создаем namedtuple для хранения параметров конфига.
        ext_config = {}
    config = merge_config(default_config, ext_config, Config)
    print(config)

    logger_info = create_logger('info_logger', config, logging_level=logging.INFO)
    logger_debug = create_logger('debug_logger', config, logging_level=logging.DEBUG)
    logger_error = create_logger('error_logger', config, logging_level=logging.ERROR)


    # возвращается namedtuple с параметрами (path, date time.date, раширение)
    log_meta = find_last_log(config, LogMeta)
    logger_info.info('Find last log file')
    print(log_meta)



    # # если работа уже сделана, нужно как-то скипать работу и логировать.
    if check_already_done(log_meta, config):
        logger_info.info('Report already created')
        return


    # # возможно нужны еще какие-то расширения.
    logger_info.info('Start reading log')
    logfiles = xreadlines(log_meta, parser=parserline)

    stop = 0
    for i in logfiles:
        if stop == 100:
            return
        stop +=1
        print(i)
    # if log_meta.expansion == 'gz':
    #     with gzip.open(log_meta.path, 'rb') as f_in:
    #         parser = log_parser(f_in, log_meta)
    # else:
    #     with open(log_meta.path, 'rb') as f_in:
    #         pass
    #
    # staticticIT = cals_statistic(logfiles, config, log_meta)
    #
    # generate_report(staticticIT, config, log_meta)


if __name__ == "__main__":
    main(parse_args(), default_config=config)
