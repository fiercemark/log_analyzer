#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
from collections import namedtuple, defaultdict
import gzip
from pathlib import Path
import logging
import json
import os
import re
import sys


# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log"
}

html_template = """
<!doctype html>

<html lang="en">
<head>
  <meta charset="utf-8">
  <title>rbui log analysis report</title>
  <meta name="description" content="rbui log analysis report">
  <style type="text/css">
    html, body {
      background-color: black;
    }
    th {
      text-align: center;
      color: silver;
      font-style: bold;
      padding: 5px;
      cursor: pointer;
    }
    table {
      width: auto;
      border-collapse: collapse;
      margin: 1%;
      color: silver;
    }
    td {
      text-align: right;
      font-size: 1.1em;
      padding: 5px;
    }
    .report-table-body-cell-url {
      text-align: left;
      width: 20%;
    }
    .clipped {
      white-space: nowrap;
      text-overflow: ellipsis;
      overflow:hidden !important;
      max-width: 700px;
      word-wrap: break-word;
      display:inline-block;
    }
    .url {
      cursor: pointer;
      color: #729FCF;
    }
    .alert {
      color: red;
    }
  </style>
</head>

<body>
  <table border="1" class="report-table">
  <thead>
    <tr class="report-table-header-row">
    </tr>
  </thead>
  <tbody class="report-table-body">
  </tbody>

  <script type="text/javascript" src="https://ajax.googleapis.com/ajax/libs/jquery/3.2.1/jquery.min.js"></script>
  <script type="text/javascript" src="/Users/s.stupnikov/Dev/hive7/home/s.stupnikov/custom/analyzer/jquery.tablesorter.min.js"></script> 
  <script type="text/javascript">
  !function($) {
    var table = {table_json}
        var reportDates;
    var columns = new Array();
    var lastRow = 150;
    var $table = $(".report-table-body");
    var $header = $(".report-table-header-row");
    var $selector = $(".report-date-selector");

    $(document).ready(function() {
      $(window).bind("scroll", bindScroll);
        var row = table[0];
        for (k in row) {
          columns.push(k);
        }
        columns = columns.sort();
        columns = columns.slice(columns.length -1, columns.length).concat(columns.slice(0, columns.length -1));
        drawColumns();
        drawRows(table.slice(0, lastRow));
        $(".report-table").tablesorter(); 
    });

    function drawColumns() {
      for (var i = 0; i < columns.length; i++) {
        var $th = $("<th></th>").text(columns[i])
                                .addClass("report-table-header-cell")
        $header.append($th);
      }
    }

    function drawRows(rows) {
      for (var i = 0; i < rows.length; i++) {
        var row = rows[i];
        var $row = $("<tr></tr>").addClass("report-table-body-row");
        for (var j = 0; j < columns.length; j++) {
          var columnName = columns[j];
          var $cell = $("<td></td>").addClass("report-table-body-cell");
          if (columnName == "url") {
            var url = "https://rb.mail.ru" + row[columnName];
            var $link = $("<a></a>").attr("href", url)
                                    .attr("title", url)
                                    .attr("target", "_blank")
                                    .addClass("clipped")
                                    .addClass("url")
                                    .text(row[columnName]);
            $cell.addClass("report-table-body-cell-url");
            $cell.append($link);
          }
          else {
            $cell.text(row[columnName]);
            if (columnName == "time_avg" && row[columnName] > 0.9) {
              $cell.addClass("alert");
            }
          }
          $row.append($cell);
        }
        $table.append($row);
      }
      $(".report-table").trigger("update"); 
    }

    function bindScroll() {
      if($(window).scrollTop() == $(document).height() - $(window).height()) {
        if (lastRow < 1000) {
          drawRows(table.slice(lastRow, lastRow + 50));
          lastRow += 50;
        }
      }
    }

  }(window.jQuery)
  </script>
</body>
</html>
"""

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config_path', help='config path', default='/usr/local/etc/config.json')

    return parser.parse_args()

#ToDo научиться обрбатываться None в config.log_name
def create_logger(name):
    formatter = logging.Formatter('[%(asctime)s] %(levelname).1s  %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger(name)
    if len(logger.handlers) > 0:
        return logger

    consoleHandler = logging.FileHandler('log.txt')
    consoleHandler.setFormatter(formatter)
    logger.addHandler(consoleHandler)

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


def parse_config(config):
    try:
        rs = config['REPORT_SIZE']
        rd = config['REPORT_DIR']
        ld = config['LOG_DIR']
    except KeyError as e:
        raise ValueError('Config parsing error') from e
    return True


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

#ToDo обрабатывать и логировать нормально ситуацию отсутствия report


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
    line = line.decode('utf-8').split()
    url_path = line[6]
    request_time = line[-1]
    result = (url_path, request_time)
    return result

def xreadlines(log_meta, logger, parser=parserline):
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


def cals_statistic(loglines, config_meta, log_meta, logger):
    url_count = 0
    total_req_time = 0.0
    agreggatebyurl = defaultdict(lambda : defaultdict(float))
    for line in loglines:
        url_count += 1
        url_path = line[0]
        time_request = float(line[1])
        total_req_time += time_request
        agreggatebyurl[url_path]['count'] += 1
        agreggatebyurl[url_path]['request_time'] += time_request
        if agreggatebyurl[url_path]['request_time_max'] < time_request:
            agreggatebyurl[url_path]['request_time_max'] = time_request

    print(url_count)
    print(total_req_time)
    agreggatebyurl = sorted(agreggatebyurl.items(), key=lambda item : item[1]['time_request'], reverse=True)
    agreggatebyurl = agreggatebyurl[:config_meta.report_size]

    for url, val in agreggatebyurl:
        try:
            yield  dict(
                        [('url', url),
                         ('count', val['count']),
                         ('count_perc', val['count'] / url_count ),
                         ('time_sum', val['request_time']),
                         ('time_perc', val['request_time'] / total_req_time),
                         ('time_max', val['request_time_max']),
                         ('time_avg', val['request_time'] / val['count'])
                         ])
        except ZeroDivisionError as e:
            # логирование
            print('divizion by zero')
            yield   dict([
                         ('url', url),
                         ('count', val['count']),
                         ('count_perc',  val['count'] / url_count ),
                         ('time_sum', val['request_time']),
                         ('time_perc', 0.0),
                         ('time_max', val['request_time_max']),
                         ('time_avg', val['request_time'] / val['count'])
                         ])

# Как создать новый каталог правильно
# if not os.path.exists(dir_path):
#     os.makedirs(dir_path)


def generate_report(statistic, config, log_meta, template):
    result = []
    print('Start here!!!')
    result = list(statistic)[:10]
    result_file = template.replace("{", "{{").replace("}", "}}").replace("{table_json}", "table_json").format(table_json=result)
    # report-2017.06.30.html
    report_name = 'report-' + '.'.join([log_meta.date[:4], log_meta.date[4:6], log_meta.date[6:]]) + '.html'
    print(report_name)
    print(os.path.join(config.report_dir, report_name))
    with open(os.path.join(config.report_dir, report_name), 'w') as fw:
        fw.write(result_file)


def main(args, default_config, template):
    # проверяем конфиг, если передали в --config, то передаем его в основную процедуру, иначе используем\
    # глобальный
    Config = namedtuple('Config', ['report_size', 'report_dir', 'log_dir'])
    LogMeta = namedtuple('LogMeta', ['path', 'date', 'expansion'])

    # ToDo подумать, нужно ли проверять существование каталогов для конфигов и репортов.

    logger = create_logger('log analyzer')
    config = ''

    try:
        with open(args.config_path, 'r') as conf:
            print('try to open config')
            ext_config = json.loads(conf.read())
            try:
                parse_config(ext_config)
                config = merge_config(default_config, ext_config, Config)
                if not config:
                    raise ValueError('No config')
            except ValueError as e:
                logger.exception('Config file {} not parse. Exception: {}'.format(args.config_path, e), exc_info=True)
    except FileNotFoundError as e:
        logger.exception('Config file {} not found. Exception: {}'.format(args.config_path, e), exc_info=True)



    # возвращается namedtuple с параметрами (path, date time.date, раширение)
    log_meta = find_last_log(config, LogMeta)
    logger.info('Find last log file: {}'.format(log_meta.path))
    print(log_meta)

    # # если работа уже сделана, нужно как-то скипать работу и логировать.
    # ToDo переименовать функцию в check_report_done
    if check_already_done(log_meta, config):
        logger.info('Report already created')
        return

    # возможно нужны еще какие-то расширения.
    logger.info('Start reading log')
    loglinesit = xreadlines(log_meta, logger, parser=parserline)

    # stop = 0
    # for i in logfiles:
    #     if stop == 1000:
    #         return
    #     stop +=1
    #     print(i)
    # if log_meta.expansion == 'gz':
    #     with gzip.open(log_meta.path, 'rb') as f_in:
    #         parser = log_parser(f_in, log_meta)
    # else:
    #     with open(log_meta.path, 'rb') as f_in:
    #         pass
    #
    staticticit = cals_statistic(loglinesit, config, log_meta, logger)
    # for n, i in enumerate(staticticit):
    #     if n >= 10:
    #         return
    #     print(i)
    print(type(staticticit))
    generate_report(staticticit, config, log_meta, template)


if __name__ == "__main__":
    main(parse_args(), default_config=config, template=html_template)
