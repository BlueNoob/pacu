#!/usr/bin/env python3
import argparse
from botocore.exceptions import ClientError

MASTER_FIELDS = [
    'active-names',
    'blueprints',
    'bundles',
    'instances',
    'key-pairs',
    'operations',
    'static-ips',
    'disks',
    'disk-snapshots',
    'load-balancers'
]

module_info = {
    'name': 'enum_lightsail',
    'author': 'Alexander Morgenstern alexander.morgenstern@rhinosecuritylabs.com',
    'category': 'recon_enum_with_keys',
    'one_liner': 'Captures common data associated with Lightsail',
    'description': """
        This module examines Lightsail data fields and automatically enumerates
        them for all available regions. Available fields can be passed upon execution
        to only look at certain types of data. By default, all Lightsail fields will
        captured.
        """,
    'services': ['Lightsail'],
    'external_dependencies': [],
    'arguments_to_autocomplete': ['--' + field for field in MASTER_FIELDS],
}


def add_field(name):
    parser.add_argument(
        '--' + name,
        required=False,
        default=False,
        action='store_true',
        help='Enumerate Lightsail ' + name.replace('-', ' ')
    )


parser = argparse.ArgumentParser(add_help=False, description=module_info['description'])
for field in MASTER_FIELDS:
    add_field(field)


def setup_storage(fields):
    out = {}
    for field in fields:
        out[field] = []
    return out


# Converts snake_case to camelcase.
def camelCase(name):
    splitted = name.split('_')
    out = splitted[0]
    for word in splitted[1:]:
        out += word[0].upper() + word[1:]
    return out


def fetch_lightsail_data(client, func):
    # Adding 'get_' portion to each field to build command.
    caller = getattr(client, 'get_' + func)
    print('  Attempting to enumerate {}'.format(func))
    try:
        response = caller()
        data = response[camelCase(func)]
        while 'nextPageToken' in response:
            response = caller(pageToken=response['nextPageToken'])
            data.extend(response[camelCase(func)])
        print('    Found {} {}'.format(len(data), func))
        print('  Finished enumerating for {}'.format(func))
        return data
    except ClientError as error:
        if error.response['Error']['Code'] == 'AccessDeniedException':
            print('AccessDenied for: {}'.format(func))
        else:
            print('Unknown Error:\n{}'.format(error))
    return []


def main(args, pacu_main):
    session = pacu_main.get_active_session()
    args = parser.parse_args(args)
    print = pacu_main.print
    get_regions = pacu_main.get_regions

    fields = [arg for arg in vars(args) if getattr(args, arg)]
    if not fields:
        # Converts kebab-case to snake_case to match expected Boto3 function names.
        fields = [field.replace('-', '_') for field in MASTER_FIELDS]

    lightsail_data = {}
    regions = get_regions('lightsail')

    for region in regions:
        lightsail_data[region] = setup_storage(fields)
        print('Starting region {}...'.format(region))
        client = pacu_main.get_boto3_client('lightsail', region)
        for field in fields:
            lightsail_data[region][field] = fetch_lightsail_data(client, field)

    summary_data = {}
    for field in fields:
        summary_data[field] = 0
        for region in lightsail_data:
            summary_data[field] += len(lightsail_data[region][field])

    session.update(pacu_main.database, Lightsail=lightsail_data)
    print('{} completed.\n'.format(module_info['name']))
    return summary_data


def summary(data, pacu_main):
    out = ''
    for field in data:
        out += '  {} {} enumerated\n'.format(data[field], field[:-1] + '(s)')
    return out
