# Copyright 2018-2019 Rumma & Ko Ltd
# License: BSD (see file COPYING for details)
"""
Read the Belgian eID card from reader and display the data to
stdout or post it to a web server.

Details see http://eidreader.lino-framework.org/usage.html
"""

import logging

import os
from os.path import expanduser, join, dirname
import sys
import argparse
import base64
import platform
import json
import configparser
import requests
from urllib.request import getproxies
from requests.exceptions import ConnectionError
# from eidreader import eid2dict
from eidreader.setup_info import SETUP_INFO
from PyKCS11 import PyKCS11, CKA_CLASS, CKO_DATA, CKA_LABEL, CKA_VALUE, CKO_CERTIFICATE, PyKCS11Error

SCHEMESEP = '://'

#
# Categorize all fields to be decoded respectively to their charset
# More information: https://github.com/Fedict/eid-mw/blob/master/doc/sdk/documentation/Applet%201.8%20eID%20Cards/ID_ADRESSE_File_applet1_8_v4.pdf
#

_utf8 = set("""
carddata_os_number
carddata_os_version
carddata_soft_mask_number
carddata_soft_mask_version
carddata_appl_version
carddata_glob_os_version
carddata_appl_int_version
carddata_pkcs1_support
carddata_key_exchange_version
carddata_appl_lifecycle
issuing_municipality
surname
firstnames
first_letter_of_third_given_name
nationality
location_of_birth
date_of_birth
nobility
address_street_and_number
address_zip
address_municipality
member_of_family
""".split())

_ascii = set("""
card_number
validity_begin_date
validity_end_date
national_number
gender
document_type
special_status
duplicata
special_organization
date_and_country_of_protection
""".split())

_binary = set("""
chip_number
photo_hash
basic_key_hash
carddata_appl_version
""".split())

_blob = set("""
DATA_FILE
ADDRESS_FILE
PHOTO_FILE
CERT_RN_FILE
SIGN_DATA_FILE
SIGN_ADDRESS_FILE
BASIC_KEY_FILE
Authentication
Signature
CA
Root
""".split())

# the following fields caused encoding problems, so we ignore them for
# now:
# carddata_serialnumber
# carddata_comp_code


def eid2dict():
    if 'PYKCS11LIB' not in os.environ:
        if platform.system().lower() == 'linux':
            os.environ['PYKCS11LIB'] = 'libbeidpkcs11.so.0'
        elif platform.system().lower() == 'darwin':
            os.environ['PYKCS11LIB'] = 'libbeidpkcs11.dylib'
        else:
            os.environ['PYKCS11LIB'] = 'beidpkcs11.dll'

    pkcs11 = PyKCS11.PyKCS11Lib()
    pkcs11.load()

    slots = pkcs11.getSlotList()

    data = dict(
        eidreader_version=SETUP_INFO['version'], success=False,
        message="Could not find any reader with a card inserted")

    # if len(slots) == 0:
    #     quit("No slot available")

    for slot in slots:
        try:
            sess = pkcs11.openSession(slot)
        except PyKCS11Error:
            continue
            # data.update(error=str(e))
            # quit("Error: {}".format(e))

        # print(dir(sess))
        try:
            # Get all data and certificate objects from Eid card
            dataobjs = sess.findObjects([(CKA_CLASS, CKO_DATA)])
            certobjs = sess.findObjects([(CKA_CLASS, CKO_CERTIFICATE)])
            objs = dataobjs + certobjs
        except PyKCS11Error as e:
            data.update(message=str(e))
            break
            # print(len(objs))
        # print(type(objs[0]), dir( objs[0]), objs[0].to_dict())
        for o in objs:
            label = sess.getAttributeValue(o, [CKA_LABEL])[0]
            value = sess.getAttributeValue(o, [CKA_VALUE])
            if len(value) == 1:
                # value = ''.join(chr(i) for i in value[0])
                value = bytes(value[0])
                try:
                    if label in _utf8:
                        value = value.decode('utf-8')
                    elif label in _ascii:
                        value = value.decode('ascii')
                    elif label in _binary:
                        value = value.hex()
                    elif label in _blob:
                        value = base64.b64encode(value)
                        value = value.decode('ascii')
                    data[label] = value
                except UnicodeDecodeError:
                    print("20180414 {} : {!r}".format(label, value))

            # print("{}: {}".format(label, value))
            # d = o.to_dict()
            # print(o['CKA_LABEL'])
        #     d['TLV'] = ''.join(chr(i) for i in d['CKA_VALUE']) if 'CKA_VALUE' in d else ''
        #     print("%(CKA_CLASS)s %(CKA_LABEL)s %(TLV)r" % d )
        # for o in objs:
        #     print(o, dir( o ))
        # data.update(card_data=card_data)
        data.update(success=True)
        data.update(message="OK")
        data.update(eidreader_country="BE")
        # del data['error']

    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", default=None, nargs='?')
    parser.add_argument("-l", "--logfile", default=None)
    parser.add_argument("-c", "--cfgfile", default=None)
    args = parser.parse_args()
    url = args.url

    cfg_files = ["eidreader.ini", expanduser("~/eidreader.ini"),
                 join(dirname(__file__), "eidreader.ini")]
    if args.cfgfile:
        cfg_files = [args.cfgfile]
    if args.logfile:
        logging.basicConfig(filename=args.logfile, level=logging.INFO,
                            format='[%(asctime)s] %(levelname)s %(message)s')
        # stderrLogger = logging.StreamHandler()
        # stderrLogger.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
        # logging.getLogger().addHandler(stderrLogger)

        # file_handler = logging.FileHandler(filename=args.logfile)
        # stdout_handler = logging.StreamHandler(sys.stderr)
        # handlers = [file_handler, stdout_handler]

        # logging.basicConfig(
        #     level=logging.INFO,
        #     format='[%(asctime)s] %(levelname)s - %(message)s',
        #     handlers=handlers
        # )

    logger = logging.getLogger('eidreader')
    logger.info("Invoked as %s", ' '.join(sys.argv))

    if url:
        proxies = getproxies()
        logger.info("getproxies() returned %s", proxies)
        cp = configparser.ConfigParser()
        logger.info("Load config from %s", cfg_files)
        cp.read(cfg_files)
        if cp.has_option('eidreader', 'http_proxy'):
            proxies['http'] = cp.get('eidreader', 'http_proxy')
        if cp.has_option('eidreader', 'https_proxy'):
            proxies['https'] = cp.get('eidreader', 'https_proxy')
        logger.info("Using proxies: %s", proxies)

        lst = url.split(SCHEMESEP, 2)
        if len(lst) == 3:
            url = lst[1] + SCHEMESEP + lst[2]
        elif len(lst) == 2:
            pass
            # url = lst[1]
        else:
            quit("Invalid URL {}".format(url))

        logger.info("Reading data...")
        # data = eid2dict()  20180521 fix 2393
        data = dict(card_data=json.dumps(eid2dict()))
        logger.info("Got data %s", data)
        logger.info("POST data to %s", url)
        try:
            r = requests.post(url, data=data, proxies=proxies)
            logger.info("POST returned {}".format(r))
        except ConnectionError as e:
            logger.info("ConnectionError %s", e)
    else:
        print(json.dumps(eid2dict()))


if __name__ == '__main__':
    main()
