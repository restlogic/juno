#!/usr/bin/env python3

import json
import sys

import yaml

def json2yaml(json_str):
    return yaml.dump(json.loads(json_str))

if __name__ == '__main__':
    print(json2yaml('\n'.join(sys.stdin)))