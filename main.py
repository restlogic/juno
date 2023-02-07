from functools import reduce
import os
import json
import pickle
import logging

import yaml
from yaml import Loader

SWAGGER_SPEC_PATH = 'swagger-spec/'
PREFIX_AGG_PATH = 'prefix-agg/'

JSON_DUMP_INDENT = 4

class PrefixAggregationUnit:
    # TODO: Add docstring
    '''
    
    '''
    api_unit = None
    sub_components = {}
    token = ''
    token_is_parameter = False

    def __init__(self, token):
        self.token = token
        self.api_unit = None

        self.token_is_parameter = len(self.token) > 1 and self.token[0] == '{'

        self.sub_components = {}

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return repr(self.__dict__)

    def toJSON(self, **kwargs):
        return json.dumps(self.__dict__, default=lambda o: o.__dict__, **kwargs)

def mkdir_if_not_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)

def count_methods(all_paths):
    r = {}
    for i in all_paths:
        for j in all_paths[i]:
            if j not in r:
                r[j] = []
            r[j] += [i]
    return r

def count_method_combination(all_paths):
    r = {}
    for i in all_paths:
        k = str(set(all_paths[i].keys()))
        if k not in r:
            r[k] = []
        r[k] += [i]
    return r

def methods_from_api_unit(api_unit):
    return [str(i) for i in api_unit.keys()]

def p_agg_recur(node, store, path_inherit='', detail=False):
    logging.debug('p_agg_recur({}, {}, {})'.format(node, store, path_inherit))
    path_inherit = path_inherit + '/' + node.token
    if node.api_unit != None:
        store[path_inherit] = {
            '#': {
                'methods': methods_from_api_unit(node.api_unit),
                'detail': node.api_unit if detail else None
            } 
        }
        if detail:
            store[path_inherit]['#']['detail'] = node.api_unit
    if len(node.sub_components):
        if not path_inherit in store:
            store[path_inherit] = {}
        store = store[path_inherit]
        path_inherit = '' 
        for i in node.sub_components:
            p_agg_recur(node.sub_components[i], store, path_inherit, detail=detail)

def p_agg(node, store, detail=True):
    logging.debug('p_agg({}, {})'.format(node, store))
    for i in node.sub_components:
        p_agg_recur(node.sub_components[i], store, '', detail)

def parse_swagger_spec():
    all_paths = {}

    # Load all docs into variable
    # https://docs.python.org/3/library/os.html
    for root, dirs, files in os.walk(SWAGGER_SPEC_PATH, topdown=False):
        for name in files:
            with open(SWAGGER_SPEC_PATH + name) as f:
                data = yaml.load(f, Loader=Loader)
                all_paths[name] = data['paths']
    
    # iterate through files
    prefix_agg_all = {}
    for i in all_paths:
        single_file = all_paths[i]

        prefix_agg = PrefixAggregationUnit('')

        for j in single_file.keys():
            key_split_by_token = j.split('/')
            if len(key_split_by_token) > 1:
                key_split_by_token = key_split_by_token[1:] # strip '[1]/[2]' [1]

            logging.debug('key_split_by_token = ' + str(key_split_by_token))
            if key_split_by_token[0] not in prefix_agg.sub_components:
                prefix_agg_unit = PrefixAggregationUnit(key_split_by_token[0])
                prefix_agg.sub_components[key_split_by_token[0]] = prefix_agg_unit
            else:
                prefix_agg_unit = prefix_agg.sub_components[key_split_by_token[0]]
            
            c = prefix_agg_unit
            
            for k in key_split_by_token[1:]:
                pau = PrefixAggregationUnit(k)
                if not k in c.sub_components:
                    c.sub_components[k] = pau
                c = c.sub_components[k]
            
            c.api_unit = single_file[j]
        
        prefix_agg_all[i] = prefix_agg
        logging.debug(i)
        logging.debug(single_file.keys())
        logging.debug(prefix_agg.toJSON(indent=2))
    
    return prefix_agg_all

def prefix_agg_group_by_intuition(single_file_prefix_agg, prefix=''):
    '''
    when a sub group contains 'POST' or 'PUT' method, count as a group

    from parent, parent count group contains all children
    '''
    if '#' in single_file_prefix_agg:
        contains_put_or_post = reduce(lambda x, y: x or y, 
            map(lambda x: x == 'post' or x == 'put', 
                single_file_prefix_agg['#']['methods']
            )
        ) if len(single_file_prefix_agg['#']['methods']) else False
        # keystone_v2.yaml /v2.0/ec2tokens doesn't have any methods
        if contains_put_or_post:
            yield { prefix: single_file_prefix_agg }
    for i in single_file_prefix_agg.keys():
        if i != '#':
            yield from prefix_agg_group_by_intuition(single_file_prefix_agg[i], prefix=prefix + i)


def pretty_print_prefix_summary(prefix_summary, prefix=''):
    n_prefix = prefix + '| '
    for i in prefix_summary.keys():
        if i != '#':
            if '#' in prefix_summary[i]:
                print(prefix + i + ' # ' + str(prefix_summary[i]['#']['methods']))
            else:
                print(prefix + i)
            pretty_print_prefix_summary(prefix_summary=prefix_summary[i], prefix=n_prefix)

if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG)

    import coloredlogs
    coloredlogs.install(level='DEBUG')

    prefix_agg_group_unit_detail = True

    prefix_agg_all = parse_swagger_spec()

    with open('prefix-agg-all.pkl', 'wb') as f:
        pickle.dump(prefix_agg_all, f)
        logging.info('saved prefix-agg-all.pkl')
    with open('prefix-agg-all.pkl', 'rb') as f:
        prefix_agg_all = pickle.load(f)
    

    # save to PREFIX_AGG_PATH 
    mkdir_if_not_exists(PREFIX_AGG_PATH)
    for i in prefix_agg_all:
        with open(PREFIX_AGG_PATH + i + '-prefix-agg.json', 'w') as f:
            f.write(prefix_agg_all[i].toJSON(indent=JSON_DUMP_INDENT))

    prefix_summary_agg_all = {}
    for i in prefix_agg_all:
        apis = prefix_agg_all[i]
        # print('== ' + i + ' ==')
        store = {}
        p_agg(apis, store, prefix_agg_group_unit_detail)
        prefix_summary_agg_all[i] = store
        # print(json.dumps(store, indent=2))
        # print('')

    with open('prefix-summary-agg-all.pkl', 'wb') as f:
        pickle.dump(prefix_summary_agg_all, f)
        logging.info('saved prefix-summary-agg-all.pkl')

    with open('prefix-summary-agg-all.pkl', 'rb') as f:
        prefix_summary_agg_all = pickle.load(f)
    
    prefix_summary_agg_group = {}
    for i in prefix_summary_agg_all:
        j = prefix_summary_agg_all[i]
        print('== ' + i + ' ==')
        pretty_print_prefix_summary(j)
        c = list(prefix_agg_group_by_intuition(j))
        # for idx, k in enumerate(c):
        #     print(idx, k)
        prefix_summary_agg_group[i] = c
    
    with open('prefix-summary-agg-group.pkl', 'wb') as f:
        pickle.dump(prefix_summary_agg_group, f)
        logging.info('saved prefix-summary-agg-group.pkl')

    with open('prefix-summary-agg-group.pkl', 'rb') as f:
        prefix_summary_agg_group = pickle.load(f)
    
    mkdir_if_not_exists('prefix-summary-agg-group')
    for i in prefix_summary_agg_group:
        mkdir_if_not_exists('prefix-summary-agg-group/' + i)
        for idx, j in enumerate(prefix_summary_agg_group[i]):
            fn = 'prefix-summary-agg-group/' + i + '/' + str(idx) + '.json'
            with open(fn, 'w') as f:
                f.write(json.dumps(j, indent=JSON_DUMP_INDENT))
                logging.info('saved ' + fn)