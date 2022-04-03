#!/usr/local/bin/python3
#
# sonar-tools
# Copyright (C) 2019-2022 Olivier Korach
# mailto:olivier.korach AT gmail DOT com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
'''
    Exports some measures of all projects
    - Either all measures (-m _all)
    - Or the main measures (-m _main)
    - Or a custom selection of measures (-m <measure1,measure2,measure3...>)
'''
import sys
from sonarqube import measures, metrics, projects, env, version, options
import sonarqube.utilities as util

RATINGS = 'letters'
PERCENTS = 'float'
DATEFMT = 'datetime'
CONVERT_OPTIONS = {'ratings': 'letters', 'percents': 'float', 'dates': 'datetime'}

def __diff(first, second):
    second = set(second)
    return [item for item in first if item not in second]


def __last_analysis(project_or_branch):
    last_analysis = project_or_branch.last_analysis_date()
    with_time = True
    if CONVERT_OPTIONS['dates'] == 'dateonly':
        with_time = False
    if last_analysis is None:
        last_analysis = "Never"
    else:
        last_analysis = util.date_to_string(last_analysis, with_time)
    return last_analysis


def __open_output(file):
    if file is None:
        fd = sys.stdout
        util.logger.info("Dumping report to stdout")
    else:
        fd = open(file, "w", encoding='utf-8')
        util.logger.info("Dumping report to file '%s'", file)
    return fd


def __close_output(file, fd):
    if file is not None:
        fd.close()
        util.logger.info("File '%s' generated", file)


def __get_csv_header(wanted_metrics, edition, **kwargs):
    sep = kwargs['csvSeparator']
    if edition == 'community' or not kwargs[options.WITH_BRANCHES]:
        header = f"# Project Key{sep}Project Name{sep}Last Analysis"
    else:
        header = f"# Project Key{sep}Project Name{sep}Branch{sep}Last Analysis"
    for m in util.csv_to_list(wanted_metrics):
        header += f"{sep}{m}"
    if kwargs[options.WITH_URL]:
        header += f"{sep}URL"
    return header


def __get_object_measures(obj, wanted_metrics):
    util.logger.info("Getting measures for %s", str(obj))
    measures_d = obj.get_measures(wanted_metrics)
    measures_d['lastAnalysis'] = __last_analysis(obj)
    measures_d['url'] = obj.url()
    proj = obj
    if not isinstance(obj, projects.Project):
        proj = obj.project
        measures_d['branch'] = obj.name
    measures_d['projectKey'] = proj.key
    measures_d['projectName'] = proj.name
    return measures_d

def __get_json_measures(obj, wanted_metrics, **kwargs):
    d = __get_object_measures(obj, wanted_metrics)
    if not kwargs[options.WITH_URL]:
        d.pop('url', None)
    if not kwargs[options.WITH_BRANCHES]:
        d.pop('branch', None)
    return d

def __get_csv_measures(obj, wanted_metrics, **kwargs):
    measures_d = __get_object_measures(obj, wanted_metrics)
    sep = kwargs[options.CSV_SEPARATOR]
    overall_metrics = 'projectKey' + sep + 'projectName'
    if kwargs[options.WITH_BRANCHES]:
        overall_metrics += sep + 'branch'
    overall_metrics += sep + 'lastAnalysis' + sep + wanted_metrics
    if kwargs[options.WITH_BRANCHES]:
        overall_metrics += sep + 'url'
    line = ''
    for metric in util.csv_to_list(overall_metrics):
        val = ''
        if metric in measures_d:
            if measures_d[metric] is None:
                val = ''
            elif sep in measures_d[metric]:
                val = util.quote(measures_d[metric], sep)
            else:
                val = str(measures.convert(metric, measures_d[metric], **CONVERT_OPTIONS))
        line += val + sep
    return line[:-len(sep)]


def __get_wanted_metrics(args, endpoint):
    main_metrics = util.list_to_csv(metrics.Metric.MAIN_METRICS)
    wanted_metrics = args.metricKeys
    if wanted_metrics == '_all':
        all_metrics = util.csv_to_list(metrics.as_csv(metrics.search(endpoint=endpoint).values()))
        wanted_metrics = main_metrics + ',' + util.list_to_csv(__diff(all_metrics, metrics.Metric.MAIN_METRICS))
    elif wanted_metrics == '_main' or wanted_metrics is None:
        wanted_metrics = main_metrics
    return wanted_metrics


def __get_fmt_and_file(args):
    kwargs = vars(args)
    fmt = kwargs['format']
    file = kwargs.get('outputFile', None)
    if file is not None:
        ext = file.split('.')[-1].lower()
        if ext in ('csv', 'json'):
            fmt = ext
    return (fmt, file)


def __parse_cmd_line():
    parser = util.set_common_args('Extract measures of projects')
    parser = util.set_component_args(parser)
    parser.add_argument('-o', '--outputFile', required=False, help='File to generate the report, default is stdout'
                        'Format is automatically deducted from file extension, if extension given')
    parser.add_argument('-f', '--format', required=False, default='csv',
                        help='Format of output (json, csv), default is csv')
    parser.add_argument('-m', '--metricKeys', required=False, help='Comma separated list of metrics or _all or _main')
    parser.add_argument('-b', '--' + options.WITH_BRANCHES, required=False, action='store_true',
                        help='Also extract branches metrics')
    parser.add_argument('--withTags', required=False, action='store_true', help='Also extract project tags')
    parser.set_defaults(withBranches=False, withTags=False)
    parser.add_argument('-r', '--ratingsAsNumbers', action='store_true', default=False, required=False,
                        help='Reports ratings as 12345 numbers instead of ABCDE letters')
    parser.add_argument('-p', '--percentsAsString', action='store_true', default=False, required=False,
                        help='Reports percentages as string xy.z%% instead of float values 0.xyz')
    parser.add_argument('-d', '--datesWithoutTime', action='store_true', default=False, required=False,
                        help='Reports timestamps only with date, not time')
    parser.add_argument('--' + cmd.INCLUDE_URL, action='store_true', default=False, required=False,
                        help='Add projects/branches URLs in report')
    parser.add_argument('--csvSeparator', required=False, default=util.CSV_SEPARATOR,
                        help=f'CSV separator (for CSV output), default {util.CSV_SEPARATOR}')

    args = util.parse_and_check_token(parser)
    util.check_environment(vars(args))
    util.logger.info('sonar-tools version %s', version.PACKAGE_VERSION)
    if args.ratingsAsNumbers:
        CONVERT_OPTIONS['ratings'] = 'numbers'
    if args.percentsAsString:
        CONVERT_OPTIONS['percents'] = 'percents'
    if args.datesWithoutTime:
        CONVERT_OPTIONS['dates'] = 'dateonly'

    return args


def main():
    args = __parse_cmd_line()
    endpoint = env.Environment(some_url=args.url, some_token=args.token)

    with_branches = args.withBranches
    if endpoint.edition() == 'community':
        with_branches = False

    wanted_metrics = __get_wanted_metrics(args, endpoint)
    (fmt, file) = __get_fmt_and_file(args)

    filters = None
    if args.componentKeys is not None:
        filters = {'projects': args.componentKeys.replace(' ', '')}
    util.logger.info("Getting project list")
    project_list = projects.search(endpoint=endpoint, params=filters).values()
    is_first = True
    obj_list = []
    if with_branches:
        for project in project_list:
            obj_list += project.get_branches()
    else:
        obj_list = project_list
    nb_branches = len(obj_list)

    fd = __open_output(file)
    if fmt == 'json':
        print('[', end='', file=fd)
    else:
        print(__get_csv_header(wanted_metrics, endpoint.edition(), **vars(args)), file=fd)

    for obj in obj_list:
        if fmt == 'json':
            if not is_first:
                print(',', end='', file=fd)
            values = __get_json_measures(obj, wanted_metrics, **vars(args))
            json_str = util.json_dump(values)
            print(json_str, file=fd)
            is_first = False
        else:
            print(__get_csv_measures(obj, wanted_metrics, **vars(args)), file=fd)

    if fmt == 'json':
        print("\n]\n", file=fd)
    __close_output(file, fd)

    util.logger.info("Computing LoCs")
    nb_loc = 0
    for project in project_list:
        nb_loc += project.ncloc_with_branches()

    util.logger.info("%d PROJECTS %d branches %d LoCs", len(project_list), nb_branches, nb_loc)
    sys.exit(0)


if __name__ == '__main__':
    main()
