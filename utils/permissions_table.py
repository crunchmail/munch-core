#!/usr/bin/env python3
import yaml
from tabulate import tabulate  # version: 0.7.5
groups = yaml.load(open(
    'munch/apps/users/fixtures/permissions/0001_group_permissions.yaml'))

table = [['Group', 'Object', 'Permission']]
for group in groups:

    table.append([
        group['fields']['name'],
        "{}.{}".format(
            group['fields']['permissions'][0][1],
            group['fields']['permissions'][0][2].title()),
        "*{}*".format(group['fields']['permissions'][0][0])])
    for permission in group['fields']['permissions'][1:]:
        table.append([
            group['fields']['name'],
            "{}.{}".format(permission[1], permission[2].title()),
            "*{}*".format(permission[0])])

print(tabulate(table, tablefmt="rst", headers="firstrow"))
