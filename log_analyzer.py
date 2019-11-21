#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
from collections import namedtuple, defaultdict
from datetime import datetime
import gzip
import json
import logging
from statistics import median
import os
import re
import sys

# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

config = {
    'REPORT_SIZE': 1000,
    'REPORT_DIR': './reports',
    'LOG_DIR': './log'
}


html_template = '''
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
  <script type="text/javascript" 
  src="/Users/s.stupnikov/Dev/hive7/home/s.stupnikov/custom/analyzer/jquery.tablesorter.min.js"></script> 
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
'''


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config_path', help='config path', default='/usr/local/etc/config.json')
    return parser.parse_args()


def create_logger(log_path):
    formatter = logging.Formatter('[%(asctime)s] %(levelname).1s  %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger('log_analyzer')

    if log_path:
        log_dir = os.path.split(log_path)[0]
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    log_hadler = logging.FileHandler(log_path) if log_path else logging.StreamHandler()
    log_hadler.setFormatter(formatter)
    logger.addHandler(log_hadler)
    logger.setLevel(logging.INFO)
    return logger


def merge_config(default_config, file_config):
    result = {}

    default_keys = default_config.keys()
    file_config_keys = file_config.keys()

    for k in set(list(default_keys) + list(file_config_keys)):
        if k in file_config:
            result[k] = file_config[k]
        else:
            result[k] = default_config[k]

    return result


def find_last_log(config, LogMeta):
    last_file = None
    last_file_date = None

    re_file_name = re.compile(r'(^nginx-access-ui\.log-(?P<date>[0-9]+)?(\.gz)?)?$')
    redate = re.compile((r'([0-9]+)'))

    if not os.path.exists(config.LOG_DIR):
        return None
    file_array_it = (re_file_name.match(file).group(1) for file in os.listdir(config.LOG_DIR) if re_file_name.match(file))

    for file in file_array_it:
        date_parse = redate.match(file.split('-')[-1]).group(1)
        try:
            date = datetime.strptime(date_parse, '%Y%m%d')
        except ValueError:
            logging.exception('Wrong date in log file', exc_info=True)
            continue

        if not last_file or date > last_file_date:
            last_file = file
            last_file_date = date

    if not last_file:
        return None

    if re_file_name.match(last_file).group(3) == '.gz':
        expansion = '.gz'
    else:
        expansion = ''

    return LogMeta(path=config.LOG_DIR + '/' + last_file, date=redate.match(last_file.split('-')[-1]).group(1),
                                            expansion=expansion)


def get_date(file_name):
    return ''.join(file_name.split('-')[1].split('.')[:-1])


def check_current_report_done(log_meta, config):
    file_array_it = (get_date(file) for file in os.listdir(config.REPORT_DIR))
    reports = set([report_date for report_date in file_array_it if log_meta.date == report_date])
    if reports:
        return True
    return False


def parserline(line):
    parse_regexp = r'(^\S+ )\S+\s+\S+ (\[\S+ \S+\] )' \
                   r'(\"\S+ (\S+) \S+\") \d+ \d+ \"\S+\" ' \
                   r'\".*\" \"\S+\" \"\S+\" \"\S+\" (\d+\.\d+)'
    regex = re.compile(parse_regexp)
    if not regex.match(line):
        return None
    url_path = regex.match(line).group(4)
    request_time = float(regex.match(line).group(5))
    result = (url_path, request_time)
    return result


def xreadlines(log_meta, logger, parser=parserline, errors_limit=None):
    total_lines = 0
    processed = 0
    error = 0
    opener = gzip.open(log_meta.path, 'rb') \
                    if log_meta.expansion == '.gz' \
                    else open(log_meta.path, 'rb')
    with opener as log:
        for line in log:
            total_lines += 1
            line = line.decode('utf-8')
            parsed_line = parser(line)
            if not parsed_line:
                error += 1
                continue

            processed += 1
            yield parsed_line

    if errors_limit is not None and total_lines > 0 and error / float(total_lines) > errors_limit:
        raise RuntimeError('To much errors in log!')


def update_statistic_store(store, url, response_time):
    rec = store.get(url)
    if not rec:
        rec = {
            'url': url,
            'request_count': 0,
            'response_time_sum': response_time,
            'max_response_time': response_time,
            'avg_responce_time': 0.,
            'all_responce_time': []
        }
        store[url] = rec

    rec['request_count'] += 1
    rec['response_time_sum'] += response_time
    rec['max_response_time'] = max(store[url]['max_response_time'], response_time)
    rec['avg_responce_time'] = rec['response_time_sum'] / rec['request_count']
    rec['all_responce_time'].append(response_time)


def cals_statistic(log_lines, config_meta):
    url_count = 0
    total_req_time = 0.0
    store = {}
    for url, request_time in log_lines:
        url_count += 1
        total_req_time += request_time
        update_statistic_store(store, url, request_time)
    agreggatebyurl = sorted(store.items(), key=lambda item : item[1]['avg_responce_time'], reverse=True)
    if config_meta.REPORT_SIZE > len(agreggatebyurl):
        agreggatebyurl = agreggatebyurl[:config_meta.REPORT_SIZE]

    #
    for url, val in agreggatebyurl:
        yield  {
                'url': url,
                'count': val['request_count'],
                'count_perc': round((val['request_count'] / url_count) * 100.0, 5) ,
                'time_sum': round(val['response_time_sum'], 5),
                'time_med': round(median(val['all_responce_time']), 5),
                'time_perc': round((val['response_time_sum'] / total_req_time) * 100.0, 5),
                'time_max': round(val['max_response_time'], 5),
                'time_avg': round(val['response_time_sum'] / val['request_count'], 5)
        }


def generate_report(statistic, config, log_meta, template):
    result_file = template.replace("{", "{{").replace("}", "}}").replace("{table_json}", "table_json").\
                                                                format(table_json=list(statistic))
    report_name = 'report-' + '.'.join([log_meta.date[:4], log_meta.date[4:6], log_meta.date[6:]]) + '.html'

    if not os.path.exists(config.REPORT_DIR):
        os.makedirs(config.REPORT_DIR)

    with open(os.path.join(config.REPORT_DIR, report_name), 'wb') as fw:
        result_file = result_file.encode('utf-8')
        fw.write(result_file)


def main(config, logger, template):
    LogMeta = namedtuple('LogMeta', ['path', 'date', 'expansion'])
    log_meta = find_last_log(config, LogMeta)
    if not log_meta:
        logger.info('Sorry. No log yet!!!!')
        return
    logger.info('Find last log file: {}'.format(log_meta.path))

    logger.info('Check report')
    if os.path.exists(config.REPORT_DIR) and os.listdir(config.REPORT_DIR):
        exist = check_current_report_done(log_meta, config)
        if exist:
            logger.info('Report already created')
            return

    logger.info('Start reading log')
    try:
        log_lines_it = xreadlines(log_meta, logger, parser=parserline)
        print(list(log_lines_it)[:10])
    except RuntimeError as e:
        logger.exception('msg: {}'.format(e), exc_info=True)

    staticticit = cals_statistic(log_lines_it, config)
    logger.info('Calc Statistic finish')
    print(list(staticticit)[:10])
    generate_report(staticticit, config, log_meta, template)
    logger.info('Generate statistic finish')


if __name__ == "__main__":
    args = parse_args()

    if args.config_path:
        with open(args.config_path, 'rb') as conf:
            ext_config = json.load(conf, encoding='utf-8')

    merged_config = merge_config(config, ext_config)

    logger = create_logger(merged_config.get('SCRIPT_LOG_PATH'))
    logger.info('Analyzer start work')

    Config = namedtuple('Config', sorted(merged_config))
    config = Config(**merged_config)

    try:
        main(config, logger, template=html_template)
    except:
        logger.exception('Something wrong')